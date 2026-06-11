"""Cenario integrado OpenTES — evolucao causal do first.py.

O first.py original ja unia os 3 simuladores isolados do TSCC:
    PADE (agentes)  <->  OMNeT++ (rede)  <->  Mosaik (orquestrador) + Collector

Aqui ele e ADAPTADO (nao reescrito do zero) para fechar o laco com a rede
eletrica do TSRE (OpenDSS / IEEE 13 Barras), realizando o fluxo causal:

  [OpenDSS] --(tensao)--> AgenteA(medidor) --> OMNeT++ --(atraso/perda)-->
  AgenteB(controlador) --(setpoint P)--> bateria --> PVSystem --> [OpenDSS]
                                                                        |
                                                              (proximo passo, loop fecha)

Toda a informacao da rede eletrica passa pela camada de comunicacao simulada
(OMNeT++), de modo que latencia/jitter/perda sejam contabilizados no benchmark.

A rota de comunicacao (AgenteA -> OMNeT++ -> AgenteB) e a MESMA do first.py
original; o que mudou foi o conteudo (tensao em vez de texto) e as duas pontas
ligadas ao OpenDSS (observacao da tensao e atuacao do setpoint).

Saidas em /app/output/integrated/:
  - result_ieee13_integrated.csv : trajetorias eletricas (V, SoC, P_ref, ...)
  - comm_trace.csv               : rastro das mensagens via OMNeT++ (telemetria)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mosaik


PADE_HOST = os.environ.get('PADE_HOST', 'pade-integrated')
PADE_PORT = os.environ.get('PADE_PORT', '5678')

CONTAINER_DATA = "/app/src/data/13Bus"
CIRCUITO_DSS = f"{CONTAINER_DATA}/run_ieee13_cosim_pv_5min.dss"

OUTPUT_DIR = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output/integrated"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_CSV = str(OUTPUT_DIR / "result_ieee13_integrated.csv")
COMM_CSV = str(OUTPUT_DIR / "comm_trace.csv")

START_DATE = os.environ.get("MOSAIK_START_DATE", "2026-01-01 00:00:00")
STEP_SIZE = int(os.environ.get("MOSAIK_STEP_SIZE", "300"))   # 5 min
N_PASSOS = int(os.environ.get("MOSAIK_N_PASSOS", "288"))
END_TIME = N_PASSOS * STEP_SIZE

# Barramento observado e ponto de atuacao (PV2 fica no Bus 632 -> medir e atuar
# no mesmo ponto eletrico).
BUS_ALVO = os.environ.get("BUS_ALVO", "632")
PV_ALVO = os.environ.get("PV_ALVO", "pv2")


sim_config = {
    # --- comunicacao (do first.py original) ---
    'OmnetSim':      {'python': 'omnet_wrapper:OmnetAdapter'},
    'ColetorSim':    {'python': 'collectors.comm_collector:Coletor'},
    'PadeSim':       {'connect': f'{PADE_HOST}:{PADE_PORT}'},
    # --- rede eletrica (TSRE, adicionada no link) ---
    'DSS':           {'connect': f"{os.environ.get('OPENDSS_HOST', 'opendss')}:5671"},
    'Battery':       {'connect': f"{os.environ.get('BATTERY_HOST', 'battery')}:5672"},
    'ElecCollector': {'connect': f"{os.environ.get('ELEC_COLLECTOR_HOST', 'elec-collector')}:5673"},
}


def create_scenario(world):
    print("🌍 Montando cenario causal: OpenDSS <-> OMNeT++ <-> PADE...")

    # remotos com timeout curto primeiro; OmnetSim (in-process) conecta no comm
    # via ZMQ e pode demorar (compilacao do OMNeT++).
    dss_sim = world.start('DSS', topofile=CIRCUITO_DSS, step_size=STEP_SIZE)
    battery_sim = world.start('Battery', step_size=STEP_SIZE)
    elec_collector = world.start('ElecCollector', start_date=START_DATE,
                                 output_file=RESULT_CSV, print_results=False)
    pade_sim = world.start('PadeSim')
    omnet_sim = world.start('OmnetSim', step_size=STEP_SIZE)
    coletor_sim = world.start('ColetorSim', output_file=COMM_CSV)

    # entidades
    rede_omnet = omnet_sim.NetworkNode(node_type='NetworkNode')
    comm_monitor = coletor_sim.Monitor()
    elec_monitor = elec_collector.Monitor()
    agente_a = pade_sim.PadeAgent(agent_id='AgenteA')   # medidor
    agente_b = pade_sim.PadeAgent(agent_id='AgenteB')   # controlador
    grid = dss_sim.Grid()
    bateria = battery_sim.Battery.create(
        1, kw_rated=50.0, kwh_rated=200.0, kwh_stored=100.0, kva_rated=55.0,
    )[0]

    bus = next((e for e in grid.children
                if e.type == 'Bus' and e.eid.lower() == f'bus-{BUS_ALVO}'), None)
    pv = next((e for e in grid.children
               if e.type == 'PVSystem' and PV_ALVO in e.eid.lower()), None)
    if bus is None or pv is None:
        raise RuntimeError(
            f"Bus-{BUS_ALVO} ou PV '{PV_ALVO}' nao encontrado. "
            f"Buses={[e.eid for e in grid.children if e.type=='Bus'][:6]} "
            f"PVs={[e.eid for e in grid.children if e.type=='PVSystem']}")
    print(f"   observacao: {bus.eid}  |  atuacao: {pv.eid}")

    # ==========================================================
    # PONTE 1 (OBSERVACAO): OpenDSS Bus -> AgenteA (medidor)
    # time_shifted: o medidor reporta o ultimo estado resolvido da rede (passo
    # anterior). Tambem quebra o ciclo DSS->PADE->Bateria->DSS para o Mosaik.
    # ==========================================================
    world.connect(bus, agente_a, ('V1_pu', 'V_in'), ('V2_pu', 'V_in'), ('V3_pu', 'V_in'),
                  time_shifted=True,
                  initial_data={'V1_pu': 1.0, 'V2_pu': 1.0, 'V3_pu': 1.0})

    # ==========================================================
    # COMUNICACAO (do first.py): AgenteA -> OMNeT++ -> AgenteB
    # ==========================================================
    world.connect(agente_a, rede_omnet, ('val_out', 'val_in'))
    world.connect(rede_omnet, agente_b, ('val_out', 'val_in'),
                  time_shifted=True, initial_data={'val_out': ''})

    # ==========================================================
    # PONTE 2 (ATUACAO): AgenteB -> bateria -> PVSystem -> OpenDSS
    # ==========================================================
    world.connect(agente_b, bateria, ('P_ref', 'P_ref'), ('Q_ref', 'Q_ref'))
    world.connect(bateria, agente_b, ('SoC', 'SoC_in'),
                  time_shifted=True, initial_data={'SoC': 50.0})
    world.connect(bateria, pv, ('P_out', 'P_des'), ('Q_out', 'Q_des'))

    # ==========================================================
    # REGISTRO: telemetria de rede + trajetorias eletricas
    # ==========================================================
    world.connect(rede_omnet, comm_monitor,
                  'status', 'packets_sent', 'packets_received', 'packets_dropped',
                  'packet_sizes_out', 'latencies_out', 'jitters_out', 'val_out')
    world.connect(bus, elec_monitor, 'V1_pu', 'V2_pu', 'V3_pu')
    world.connect(agente_b, elec_monitor, 'P_ref', 'Q_ref')
    world.connect(bateria, elec_monitor, 'SoC', 'P_out', 'Q_out')
    world.connect(pv, elec_monitor, 'P_meas', 'Q_meas')


if __name__ == '__main__':
    print("🎬 Iniciando o Orquestrador Mosaik (cenario integrado causal)...")
    with mosaik.World(sim_config) as world:
        create_scenario(world)
        world.run(until=END_TIME, print_progress=False)
    print("✅ Co-simulacao finalizada.")
    print(f"   eletrico:    {RESULT_CSV}")
    print(f"   comunicacao: {COMM_CSV}")
