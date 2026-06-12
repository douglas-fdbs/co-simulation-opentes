import mosaik
import sys
import pprint
import pandas as pd
from pathlib import Path

# ==============================================================================
# 1. CAMINHOS NO HOST (Windows)
# ==============================================================================
CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR_HOST = PROJECT_ROOT / "data" / "123Bus"
CIRCUITO_DSS_HOST = DATA_DIR_HOST / "run_ieee123_cosim_pv_5min.dss"
OUTPUT_DIR_HOST = PROJECT_ROOT / "output"
OUTPUT_DIR_HOST.mkdir(parents=True, exist_ok=True)
ARQUIVO_RESULTADOS_CSV_HOST = OUTPUT_DIR_HOST / 'result_run_ieee123_cosim_pv_5min.csv'

# ==============================================================================
# 2. CAMINHOS NO CONTAINER (Linux/Docker)
# ==============================================================================
CONTAINER_DATA = "/app/src/data/123Bus"
CIRCUITO_DSS_CONT = f"{CONTAINER_DATA}/run_ieee123_cosim_pv_5min.dss"
IRRADIANCE_CONT = f"{CONTAINER_DATA}/ieee123_shape_pv_5min.csv"
TEMPERATURE_CONT = f"{CONTAINER_DATA}/ieee123_temperature_5min.csv"
ARQUIVO_RESULTADOS_CSV_CONT = "/app/output/result_run_ieee123_cosim_pv_5min.csv"

START_DATE = "2026-01-01 00:00:00"
STEP_SIZE = 60 * 5
N_PASSOS = 288
END_TIME = N_PASSOS * STEP_SIZE

# ==============================================================================
# 3. CONFIGURAÇÃO DE CONEXÃO (DOCKER)
# ==============================================================================
SIM_CONFIG = {
    'DSS': {
        'connect': 'localhost:5671',
    },
    'PVSimulator': {
        'connect': 'localhost:5678'
    },
    'InverterSim': {
        'connect': 'localhost:5677' # Porta 5677 = inverter-std
    },
    'CSV_Irr': {
        'connect': 'localhost:5675' # Porta 5675 = csv-data-1
    },
    'CSV_Temp': {
        'connect': 'localhost:5676' # Porta 5676 = csv-data-2
    },
    'Collector': {
        'connect': 'localhost:5673',
    },
}

def run_scenario():
    if not CIRCUITO_DSS_HOST.exists():
        print(f"[ERRO]: Arquivo DSS não encontrado no Windows em:\n{CIRCUITO_DSS_HOST}")
        return

    with mosaik.World(SIM_CONFIG) as world:
        print("--- Conectando aos Simuladores no Docker ---")

        # 1. Iniciando Simuladores via Rede
        dss_sim = world.start(
            'DSS', 
            topofile=CIRCUITO_DSS_CONT, 
            step_size=STEP_SIZE)
        
        pv_sim = world.start(
            'PVSimulator',
            step_size=STEP_SIZE)
        
        inv_sim = world.start(
            'InverterSim',
            step_size=STEP_SIZE)
        
        csv_sim_irr = world.start(
            'CSV_Irr',
            sim_start=START_DATE,
            datafile=IRRADIANCE_CONT)
        
        csv_sim_temp = world.start(
            'CSV_Temp',
            sim_start=START_DATE,
            datafile=TEMPERATURE_CONT)

        collector = world.start(
            'Collector',
            start_date=START_DATE,
            output_file=ARQUIVO_RESULTADOS_CSV_CONT,
            print_results=False
        )

        print("Instanciando a Grid do OpenDSS...")
        grid = dss_sim.Grid()
        csv_data_irr = csv_sim_irr.Data.create(1)
        csv_data_temp = csv_sim_temp.Data.create(1)
        monitor = collector.Monitor()

        pv_info = dss_sim.get_detected_pvsystems()
        pvs_dss_map = {e.eid: e for e in grid.children if e.type == 'PVSystem'}

        for info in pv_info:
            pv_name = info['name']
            eid_dss = info['eid_dss']

            if eid_dss in pvs_dss_map:
                pv_dss_obj = pvs_dss_map[eid_dss]

                pv_panel_obj = pv_sim.PVPanel.create(
                    1,
                    P_mpp=info['pmpp'],
                    irradiance_base=0.8,
                    pt_curve_x=info['pt_curve_x'],
                    pt_curve_y=info['pt_curve_y'],
                )[0]

                inv_obj = inv_sim.Inverter.create(
                    1,
                    kVA=info['kva'],
                    priority='Active',
                    eff_curve_x=info['eff_curve_x'],
                    eff_curve_y=info['eff_curve_y'],
                    pct_cutin=info['pct_cutin'],
                    pct_cutout=info['pct_cutout']
                )[0]

                world.connect(csv_data_irr[0], pv_panel_obj, ('my_shape2_pv', 'irradiance'))
                world.connect(csv_data_temp[0], pv_panel_obj, ('temperature', 'temperature'))

                world.connect(pv_panel_obj, inv_obj, ('P_dc', 'P_dc'))
                world.connect(inv_obj, pv_dss_obj, ('P_ac', 'P_des'), ('Q_ac', 'Q_des'))

                world.connect(pv_panel_obj, monitor, 'irradiance', 'temperature', 'P_dc')
                world.connect(inv_obj, monitor, 'P_ac', 'Q_ac')
                world.connect(pv_dss_obj, monitor, 'P_meas', 'Q_meas')

                world.connect(pv_dss_obj, monitor, 'P1', 'P2', 'P3', 'Q1', 'Q2', 'Q3')


        # Monitorar Barra 149 e 97
        target_names = ['149', '97']
        for target_name in target_names:
            target_eid = f'Bus-{target_name}'
            bus_entities = [e for e in grid.children if e.eid == target_eid]
            if bus_entities:
                world.connect(bus_entities[0], monitor, 'V1_pu', 'V2_pu', 'V3_pu')
                print(f"Monitorando Barra: {target_eid}")

        # Monitorar Linha L115
        target_name = 'L115'
        target_eid = f'Line-{target_name}'
        line_entities = [e for e in grid.children if e.eid.lower() == target_eid.lower()]
        if line_entities:
            world.connect(line_entities[0], monitor,
                          'I1_A', 'I1_ang', 'I2_A', 'I2_ang', 'I3_A', 'I3_ang',
                          'P1_w', 'Q1_var', 'P2_w', 'Q2_var', 'P3_w', 'Q3_var')
            print(f"Monitorando Linha: {target_eid}")

        print(f"\nInicializando simulação de {N_PASSOS} para (Step={STEP_SIZE}...)")

        world.run(until=END_TIME, print_progress=False)
        print("Simulação concluída.")

        # --- Check Rápido ---
        if ARQUIVO_RESULTADOS_CSV_HOST.exists():
            print(f"\nResultados salvos em: {ARQUIVO_RESULTADOS_CSV_HOST}")
            
if __name__ == '__main__':
    run_scenario()