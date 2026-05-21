import mosaik
import sys
import pprint
import pandas as pd
from pathlib import Path

# --- Definição Dinâmica de Caminhos ---
CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "123Bus"

CIRCUITO_DSS = DATA_DIR / "run_ieee123_cosim_5min.dss"
CIRCUITO_DSS = DATA_DIR / "run_ieee123_cosim_5min_edited.dss"

OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ARQUIVO_RESULTADOS_CSV = OUTPUT_DIR / 'result_run_ieee123_cosim_5min.csv'
ARQUIVO_RESULTADOS_CSV = OUTPUT_DIR / 'result_run_ieee123_cosim_5min_edited.csv'

START_DATE = "2024-01-01 00:00:00"
STEP_SIZE = 60 * 5
N_PASSOS = 288
END_TIME = N_PASSOS * STEP_SIZE

# --- Configuração dos Simuladores ---
SIM_CONFIG = {
    'DSS': {
        'python': 'simulators.api_opendss:OpenDSSSimulator',
    },
    'Collector': {
        'python': 'simulators.collector:Collector',
    },
}

def run_scenario():
    if not CIRCUITO_DSS.exists():
        print(f"[ERRO]: Arquivo DSS não encontrado em:\n{CIRCUITO_DSS}")

    with mosaik.World(SIM_CONFIG) as world:
        print("--- Inicializando Simuladores ---")

        # 1. Iniciando OpenDSS
        dss_sim = world.start(
            'DSS', 
            topofile=str(CIRCUITO_DSS), 
            step_size=STEP_SIZE)

        # 2. Iniciando Coletor
        collector = world.start(
            'Collector',
            start_date=START_DATE,
            output_file=str(ARQUIVO_RESULTADOS_CSV),
            print_results=False
        )

        print("Instanciando a Grid do OpenDSS...")
        grid = dss_sim.Grid()
        monitor = collector.Monitor()

        # Monitorar Barra 149
        target_names = ['149', '97', '450', '114']
        # target_name = '149'
        # target_name = '1'

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
        if ARQUIVO_RESULTADOS_CSV.exists():
            print(f"\nResultados salvos em: {ARQUIVO_RESULTADOS_CSV}")
            
if __name__ == '__main__':
    run_scenario()