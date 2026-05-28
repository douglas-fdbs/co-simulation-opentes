"""Cenario integrado IEEE 13 Bus usando os 4 simulators_teams.

Junta, num unico mundo Mosaik, os dois dominios da co-simulacao OpenTES:

  Comunicacao (containers comm + pade):
    PADE agents  <-> OMNeT++ (rede)  <-> comm_collector (telemetria)
  Rede eletrica (container grid):
    CSV -> PVPanel -> Inverter -> OpenDSS (IEEE13, feedback de tensao)
                                  -> elec_collector (dados eletricos)

Ambos os dominios avancam na mesma escala de tempo (passo de 5 min), de modo
que o relogio do Mosaik sincroniza a troca de mensagens dos agentes com a
evolucao da rede eletrica ao longo do dia.

Os 4 containers participam: comm (OMNeT++), pade (agentes via pade-integrated),
grid (OpenDSS+PV+inversor) e mosaik (este orquestrador + collectors).

Observacao: nesta etapa os dois dominios COEXISTEM no mesmo relogio mas o
acoplamento causal forte (decisao de agente -> despacho na rede) ainda nao e
modelado; e o proximo passo do time TTESO (modelos de mercado/DSO). Aqui
validamos que a co-simulacao multi-dominio roda de ponta a ponta.

Rodar:
    docker compose --profile integrated up --abort-on-container-exit \
      --exit-code-from mosaik-integrated mosaik-integrated
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mosaik


# ------------------------------------------------------------------------------
# Comunicacao
# ------------------------------------------------------------------------------
NUM_PERIFERICOS = int(os.environ.get("NUM_PERIFERICOS", "5"))
PADE_HOST = os.environ.get("PADE_HOST", "pade-integrated")
PADE_PORT = os.environ.get("PADE_PORT", "5678")
OMNET_HOST = os.environ.get("OMNET_HOST", "comm")
OMNET_PORT = int(os.environ.get("OMNET_PORT", "5555"))

# ------------------------------------------------------------------------------
# Rede eletrica
# ------------------------------------------------------------------------------
CONTAINER_DATA = "/app/src/data/13Bus"
CIRCUITO_DSS = f"{CONTAINER_DATA}/run_ieee13_cosim_pv_5min.dss"
IRRADIANCE = f"{CONTAINER_DATA}/ieee13_shape_pv_5min.csv"
TEMPERATURE = f"{CONTAINER_DATA}/ieee13_temperature_5min.csv"
OUTPUT_DIR = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_CSV = str(OUTPUT_DIR / "result_ieee13_integrated.csv")

START_DATE = os.environ.get("MOSAIK_START_DATE", "2026-01-01 00:00:00")
STEP_SIZE = int(os.environ.get("MOSAIK_STEP_SIZE", "300"))  # 5 min
N_PASSOS = int(os.environ.get("MOSAIK_N_PASSOS", "288"))
END_TIME = N_PASSOS * STEP_SIZE


SIM_CONFIG = {
    # --- comunicacao ---
    "OmnetSim": {"python": "omnet_wrapper:OmnetAdapter"},
    "PadeSim": {"connect": f"{PADE_HOST}:{PADE_PORT}"},
    "CommCollector": {"python": "collectors.comm_collector:Coletor"},
    # --- rede eletrica ---
    "DSS": {"connect": f"{os.environ.get('OPENDSS_HOST', 'opendss')}:5671"},
    "PVSimulator": {"connect": f"{os.environ.get('PV_HOST', 'pv-panel')}:5678"},
    "InverterSim": {"connect": f"{os.environ.get('INVERTER_HOST', 'smart-inverter')}:5680"},
    "CSV_Irr": {"connect": f"{os.environ.get('CSV_IRR_HOST', 'csv-data-1')}:5675"},
    "CSV_Temp": {"connect": f"{os.environ.get('CSV_TEMP_HOST', 'csv-data-2')}:5676"},
    "ElecCollector": {"connect": f"{os.environ.get('ELEC_COLLECTOR_HOST', 'elec-collector')}:5673"},
}


def build_comunicacao(world):
    """Camada de comunicacao: PADE agents <-> OMNeT++ <-> comm_collector."""
    omnet_sim = world.start("OmnetSim", step_size=STEP_SIZE)
    pade_sim = world.start("PadeSim")
    comm_collector = world.start("CommCollector")

    rede_omnet = omnet_sim.NetworkNode(node_type="NetworkNode")
    comm_monitor = comm_collector.Monitor()
    agente_central = pade_sim.PadeAgent(agent_id="AgenteCentral")

    world.connect(agente_central, rede_omnet, ("val_out", "val_in"))
    world.connect(rede_omnet, agente_central, ("val_out", "val_in"),
                  time_shifted=True, initial_data={"val_out": ""})

    for i in range(1, NUM_PERIFERICOS + 1):
        agente_p = pade_sim.PadeAgent(agent_id=f"AgenteP_{i}")
        world.connect(agente_p, rede_omnet, ("val_out", "val_in"))
        world.connect(rede_omnet, agente_p, ("val_out", "val_in"),
                      time_shifted=True, initial_data={"val_out": ""})

    world.connect(rede_omnet, comm_monitor,
                  "status", "packets_sent", "packets_received", "packets_dropped",
                  "packet_sizes_out", "latencies_out", "jitters_out", "val_out")
    print(f"[mosaik] comunicacao: 1 central + {NUM_PERIFERICOS} perifericos via OMNeT++")


def build_rede_eletrica(world):
    """Camada eletrica: CSV -> PV -> Inverter -> OpenDSS (IEEE13) -> collector."""
    dss_sim = world.start("DSS", topofile=CIRCUITO_DSS, step_size=STEP_SIZE)
    pv_sim = world.start("PVSimulator", step_size=STEP_SIZE)
    inv_sim = world.start("InverterSim", step_size=STEP_SIZE)
    csv_sim_irr = world.start("CSV_Irr", sim_start=START_DATE, datafile=IRRADIANCE)
    csv_sim_temp = world.start("CSV_Temp", sim_start=START_DATE, datafile=TEMPERATURE)
    elec_collector = world.start("ElecCollector", start_date=START_DATE,
                                 output_file=RESULT_CSV, print_results=False)

    grid = dss_sim.Grid()
    csv_data_irr = csv_sim_irr.Data.create(1)
    csv_data_temp = csv_sim_temp.Data.create(1)
    monitor = elec_collector.Monitor()

    pv_info = dss_sim.get_detected_pvsystems()
    pvs_dss_map = {e.eid: e for e in grid.children if e.type == "PVSystem"}
    buses_map = {e.eid: e for e in grid.children if e.type == "Bus"}

    for info in pv_info:
        if info["eid_dss"] not in pvs_dss_map:
            continue
        pv_dss_obj = pvs_dss_map[info["eid_dss"]]
        bus_base = info.get("bus", "").split(".")[0]
        bus_eid = f"Bus-{bus_base}"
        if bus_eid not in buses_map:
            continue
        bus_obj = buses_map[bus_eid]

        pv_panel_obj = pv_sim.PVPanel.create(
            1, P_mpp=info["pmpp"], irradiance_base=0.8,
            pt_curve_x=info["pt_curve_x"], pt_curve_y=info["pt_curve_y"],
        )[0]
        inv_obj = inv_sim.Inverter.create(
            1, kVA=info["kva"], phase_mode="AVG",
            eff_curve_x=info["eff_curve_x"], eff_curve_y=info["eff_curve_y"],
            ctrl_config={"Volt_Var": False, "Const_PF": False},
        )[0]

        pv_number = "".join(filter(str.isdigit, info["name"]))
        world.connect(csv_data_irr[0], pv_panel_obj, (f"my_shape{pv_number}_irrad", "irradiance"))
        world.connect(csv_data_temp[0], pv_panel_obj, (f"my_shape{pv_number}_temperature", "temperature"))
        world.connect(pv_panel_obj, inv_obj, ("P_dc", "P_dc"))
        world.connect(bus_obj, inv_obj,
                      ("V1_pu", "V_meas_1"), ("V2_pu", "V_meas_2"), ("V3_pu", "V_meas_3"),
                      time_shifted=True, initial_data={"V1_pu": 1.0, "V2_pu": 1.0, "V3_pu": 1.0})
        world.connect(inv_obj, pv_dss_obj, ("P_ac", "P_des"), ("Q_ac", "Q_des"))
        world.connect(pv_panel_obj, monitor, "irradiance", "P_dc")
        world.connect(inv_obj, monitor, "P_ac", "Q_ac")
        world.connect(pv_dss_obj, monitor, "P_meas", "Q_meas")

    print("[mosaik] rede eletrica: IEEE13 com PV + inversores")


def run_scenario():
    with mosaik.World(SIM_CONFIG) as world:
        print("[mosaik] montando cenario integrado (comunicacao + rede eletrica)...")
        build_comunicacao(world)
        build_rede_eletrica(world)
        print(f"[mosaik] iniciando simulacao ({N_PASSOS} passos x {STEP_SIZE}s)")
        world.run(until=END_TIME, print_progress=False)
        print(f"[mosaik] concluido. dados eletricos em {RESULT_CSV}")


if __name__ == "__main__":
    run_scenario()
