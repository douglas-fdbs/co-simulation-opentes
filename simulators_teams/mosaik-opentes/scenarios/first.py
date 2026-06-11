"""Cenario integrado OpenTES — evolucao causal do first.py (Volt/Var no inversor).

O first.py original ja unia os 3 simuladores isolados do TSCC:
    PADE (agentes)  <->  OMNeT++ (rede)  <->  Mosaik (orquestrador) + Collector

Aqui ele e ADAPTADO (nao reescrito do zero) para fechar o laco com a rede
eletrica do TSRE (OpenDSS / IEEE 13 Barras). NAO ha bateria: o atuador e o
proprio inversor fotovoltaico, com controle Volt/Var:

  [OpenDSS] --(tensao)--> AgenteA(medidor) --> OMNeT++ --(atraso/perda)-->
  AgenteB(controlador Volt/Var) --(P ativa, Q reativa)--> PVSystem --> [OpenDSS]
                                                                            |
                                                              (proximo passo, loop fecha)

  - P (ativa)   = potencia solar disponivel (cadeia irradiancia -> PV panel)
  - Q (reativa) = funcao da tensao recebida pela rede (regula a tensao)
  - S = sqrt(P^2 + Q^2) <= kVA do inversor

Toda a tensao passa pela camada de comunicacao (OMNeT++); latencia/jitter/perda
sao contabilizados no benchmark. O controle liga/desliga por CONTROL_ENABLED,
permitindo comparar a co-simulacao SEM controle (baseline) e COM controle.

Saidas em /app/output/integrated/ (sufixadas por RESULT_TAG):
  - result_<tag>.csv     : trajetorias eletricas (V, P_ref, Q_ref, P_meas, ...)
  - comm_trace_<tag>.csv : rastro das mensagens via OMNeT++ (telemetria de rede)
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
IRRADIANCE = f"{CONTAINER_DATA}/ieee13_shape_pv_5min.csv"
TEMPERATURE = f"{CONTAINER_DATA}/ieee13_temperature_5min.csv"

OUTPUT_DIR = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output/integrated"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_TAG = os.environ.get("RESULT_TAG", "volt_var")
RESULT_CSV = str(OUTPUT_DIR / f"result_{RESULT_TAG}.csv")
COMM_CSV = str(OUTPUT_DIR / f"comm_trace_{RESULT_TAG}.csv")

START_DATE = os.environ.get("MOSAIK_START_DATE", "2026-01-01 00:00:00")
STEP_SIZE = int(os.environ.get("MOSAIK_STEP_SIZE", "300"))   # 5 min
N_PASSOS = int(os.environ.get("MOSAIK_N_PASSOS", "288"))
END_TIME = N_PASSOS * STEP_SIZE

# 1 = Volt/Var ativo | 0 = baseline (inversor injeta so a solar, Q=0)
CONTROL_ENABLED = os.environ.get("CONTROL_ENABLED", "1")
# Barramento observado / inversor controlado (PV2 fica no Bus 632).
BUS_ALVO = os.environ.get("BUS_ALVO", "632")
PV_ALVO = os.environ.get("PV_ALVO", "pv2")


sim_config = {
    # --- comunicacao (do first.py original) ---
    'OmnetSim':      {'python': 'omnet_wrapper:OmnetAdapter'},
    'ColetorSim':    {'python': 'collectors.comm_collector:Coletor'},
    'PadeSim':       {'connect': f'{PADE_HOST}:{PADE_PORT}'},
    # --- rede eletrica (TSRE) ---
    'DSS':           {'connect': f"{os.environ.get('OPENDSS_HOST', 'opendss')}:5671"},
    'PVSimulator':   {'connect': f"{os.environ.get('PV_HOST', 'pv-panel')}:5678"},
    'CSV_Irr':       {'connect': f"{os.environ.get('CSV_IRR_HOST', 'csv-data-1')}:5675"},
    'CSV_Temp':      {'connect': f"{os.environ.get('CSV_TEMP_HOST', 'csv-data-2')}:5676"},
    'ElecCollector': {'connect': f"{os.environ.get('ELEC_COLLECTOR_HOST', 'elec-collector')}:5673"},
}


def create_scenario(world):
    modo = "COM controle (Volt/Var)" if CONTROL_ENABLED == "1" else "SEM controle (baseline)"
    print(f"🌍 Cenario causal {modo}: OpenDSS <-> OMNeT++ <-> PADE...")

    dss_sim = world.start('DSS', topofile=CIRCUITO_DSS, step_size=STEP_SIZE)
    pv_sim = world.start('PVSimulator', step_size=STEP_SIZE)
    csv_irr = world.start('CSV_Irr', sim_start=START_DATE, datafile=IRRADIANCE)
    csv_temp = world.start('CSV_Temp', sim_start=START_DATE, datafile=TEMPERATURE)
    elec_collector = world.start('ElecCollector', start_date=START_DATE,
                                 output_file=RESULT_CSV, print_results=False)
    pade_sim = world.start('PadeSim')
    omnet_sim = world.start('OmnetSim', step_size=STEP_SIZE)
    coletor_sim = world.start('ColetorSim', output_file=COMM_CSV)

    grid = dss_sim.Grid()
    pv_info = dss_sim.get_detected_pvsystems()
    pvs_map = {e.eid: e for e in grid.children if e.type == 'PVSystem'}

    # PV2 (no Bus 632): ponto de medicao e de atuacao
    info = next((i for i in pv_info if PV_ALVO in i['name'].lower()), None)
    if info is None:
        raise RuntimeError(f"PV '{PV_ALVO}' nao detectado. PVs={[i['name'] for i in pv_info]}")
    pv_dss = pvs_map.get(info['eid_dss'])
    bus = next((e for e in grid.children
                if e.type == 'Bus' and e.eid.lower() == f'bus-{BUS_ALVO}'), None)
    if pv_dss is None or bus is None:
        raise RuntimeError(f"Bus-{BUS_ALVO} ou {info['eid_dss']} nao encontrado.")
    print(f"   observacao: {bus.eid}  |  atuacao: {pv_dss.eid}  (kVA={info['kva']})")

    # entidades de comunicacao + agentes
    rede_omnet = omnet_sim.NetworkNode(node_type='NetworkNode')
    comm_monitor = coletor_sim.Monitor()
    elec_monitor = elec_collector.Monitor()
    agente_a = pade_sim.PadeAgent(agent_id='AgenteA')              # medidor
    agente_b = pade_sim.PadeAgent(                                  # controlador Volt/Var
        agent_id='AgenteB',
        control_enabled=CONTROL_ENABLED, kva=info['kva'],
        v_ref=1.0, v_deadband=0.01, v_min=0.95, v_max=1.05, q_max_pct=0.44,
    )

    # painel PV (irradiancia/temperatura -> P_dc disponivel) para o PV2
    pv_number = ''.join(filter(str.isdigit, info['name']))
    pv_panel = pv_sim.PVPanel.create(
        1, P_mpp=info['pmpp'], irradiance_base=0.8,
        pt_curve_x=info['pt_curve_x'], pt_curve_y=info['pt_curve_y'],
    )[0]
    irr = csv_irr.Data.create(1)[0]
    tmp = csv_temp.Data.create(1)[0]
    world.connect(irr, pv_panel, (f'my_shape{pv_number}_irrad', 'irradiance'))
    world.connect(tmp, pv_panel, (f'my_shape{pv_number}_temperature', 'temperature'))

    # ==========================================================
    # PONTE 1 (OBSERVACAO): OpenDSS Bus -> AgenteA (medidor)
    # time_shifted: medidor reporta o ultimo estado resolvido; quebra o ciclo
    # DSS->PADE->PVSystem->DSS para o Mosaik.
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

    # solar disponivel (P) chega localmente ao controlador (entrada DC do inversor)
    world.connect(pv_panel, agente_b, ('P_dc', 'P_avail_in'))

    # ==========================================================
    # PONTE 2 (ATUACAO): AgenteB -> inversor PVSystem -> OpenDSS
    # ==========================================================
    world.connect(agente_b, pv_dss, ('P_ref', 'P_des'), ('Q_ref', 'Q_des'))

    # ==========================================================
    # REGISTRO: telemetria de rede + trajetorias eletricas
    # ==========================================================
    world.connect(rede_omnet, comm_monitor,
                  'status', 'packets_sent', 'packets_received', 'packets_dropped',
                  'packet_sizes_out', 'latencies_out', 'jitters_out', 'val_out')
    world.connect(agente_b, elec_monitor, 'P_ref', 'Q_ref')
    world.connect(pv_panel, elec_monitor, 'P_dc')
    # registro amplo da rede: tensão de TODAS as barras e potência de TODOS os PVs
    # (permite o dashboard com as 13 barras e a geração FV agregada).
    n_bus = n_pv = 0
    for e in grid.children:
        if e.type == 'Bus':
            world.connect(e, elec_monitor, 'V1_pu', 'V2_pu', 'V3_pu')
            n_bus += 1
        elif e.type == 'PVSystem':
            world.connect(e, elec_monitor, 'P_meas', 'Q_meas')
            n_pv += 1
    print(f"   monitorando {n_bus} barras e {n_pv} PVs")


if __name__ == '__main__':
    print("🎬 Iniciando o Orquestrador Mosaik (cenario integrado causal Volt/Var)...")
    with mosaik.World(sim_config) as world:
        create_scenario(world)
        world.run(until=END_TIME, print_progress=False)
    print("✅ Co-simulacao finalizada.")
    print(f"   eletrico:    {RESULT_CSV}")
    print(f"   comunicacao: {COMM_CSV}")
