import mosaik
import sys
import pprint
import pandas as pd
from pathlib import Path

# --- Definição Dinâmica de Caminhos ---
# Pega o diretório onde ESTE script está (src/scenarios)
CURRENT_DIR = Path(__file__).parent.resolve()

# Define a raiz do projeto (src)
PROJECT_ROOT = CURRENT_DIR.parent

# Define onde estão os dados (src/data/13Bus)
DATA_DIR = PROJECT_ROOT / "data" / "13Bus"
CIRCUITO_DSS = DATA_DIR / "IEEE13Nodeckt_w_loadcurve.dss"

# Define onde salvar os resultados (src/output)
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True) # Cria a pasta se não existir
ARQUIVO_RESULTADOS_CSV = OUTPUT_DIR / 'result_opendss.csv'

# Adiciona a raiz ao Python Path para importar os módulos 'simulators'
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Configuração do Cenário ---
STEP_SIZE = 600  
N_PASSOS = 144   
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
    # Verifica se o arquivo DSS existe antes de rodar
    if not CIRCUITO_DSS.exists():
        print(f"ERRO CRÍTICO: Arquivo DSS não encontrado em:\n{CIRCUITO_DSS}")
        print("Verifique se você copiou a pasta '13Bus' para 'src/data/'")
        sys.exit(1)

    try:
        # Importação local para evitar erros circulares e garantir que o path está certo
        from simulators import api_opendss
        from simulators import collector 
    except ImportError as e:
        print(f"Erro de importação: {e}")
        print(f"Verifique se a pasta 'simulators' está em {PROJECT_ROOT}")
        sys.exit(1)

    with mosaik.World(SIM_CONFIG) as world:
        # Note que passamos o caminho como string (str(CIRCUITO_DSS)) para o OpenDSS entender
        dss_sim = world.start('DSS', topofile=str(CIRCUITO_DSS), step_size=STEP_SIZE)
        
        collector = world.start('Collector', 
                                start_date='2025-01-01 00:00:00',
                                output_file=str(ARQUIVO_RESULTADOS_CSV),
                                print_results=False)

        grid = dss_sim.Grid()
        monitor = collector.Monitor()

        # ==========================================================
        # 1. Monitoramento da LINHA "650632"
        # ==========================================================
        nome_alvo = '650632'
        eid_alvo = f'Line-{nome_alvo}'

        # Busca a entidade no grid
        entidades_encontradas = [e for e in grid.children if e.eid.lower() == eid_alvo.lower()]
        
        if not entidades_encontradas:
            print("\n--- ENTIDADES ENCONTRADAS ---")
            pprint.pprint(sorted([child.eid for child in grid.children]))
            raise RuntimeError(f"Não foi possível encontrar '{eid_alvo}'.")
        
        entidade_monitorada = entidades_encontradas[0]
        print(f"Monitorando Linha: '{entidade_monitorada.eid}'")

        # Conectar Correntes (Fases A, B, C e ângulos)
        world.connect(entidade_monitorada, monitor, 'I1_A', 'I1_ang')
        world.connect(entidade_monitorada, monitor, 'I2_A', 'I2_ang')
        world.connect(entidade_monitorada, monitor, 'I3_A', 'I3_ang')

        # ==========================================================
        # 2. Monitoramento da BARRA "rg60"
        # ==========================================================
        target_name = 'rg60'
        target_eid = f'Bus-{target_name}'
        
        # Busca a entidade
        entities = [e for e in grid.children if e.eid == target_eid]
        if not entities:
            print(f"Erro: Barra {target_eid} não encontrada.")
            # Opcional: listar barras se falhar
            # pprint.pprint([e.eid for e in grid.children if 'Bus' in e.eid])
        else:
            bus_entity = entities[0]
            print(f"Monitorando Barra: '{bus_entity.eid}'\n")

            # Conecta tensões (PU e Ângulo)
            world.connect(bus_entity, monitor, 'V1_pu', 'V1_ang', 'V2_pu', 'V2_ang', 'V3_pu', 'V3_ang')

        # --- Execução ---
        print(f"Iniciando simulação de {N_PASSOS} passos (Step={STEP_SIZE}s)...")
        world.run(until=END_TIME)
        print("Simulação concluída.")

        # --- Leitura dos Resultados ---
        print(f"\n--- DADOS COLETADOS ('{ARQUIVO_RESULTADOS_CSV}') ---")
        try:
            results_df = pd.read_csv(ARQUIVO_RESULTADOS_CSV, index_col='date', parse_dates=True)
            print("Primeiras 5 linhas:")
            print(results_df.head(5))
            print("\nÚltimas 5 linhas:")
            print(results_df.tail(5))
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")

if __name__ == '__main__':
    run_scenario()