import mosaik
import sys
import pprint
import pandas as pd
from pathlib import Path

# --- Definição Dinâmica de Caminhos ---
CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "34Bus"
CIRCUITO_DSS = DATA_DIR / "ieee34Mod1_w_loadcurve.dss"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARQUIVO_RESULTADOS_CSV = OUTPUT_DIR / 'result_opendss_34bus_regcontrol.csv'

STEP_SIZE = 60 * 5
N_PASSOS = 288
END_TIME = N_PASSOS * STEP_SIZE 

# --- Configuração dos Simuladores ---
SIM_CONFIG = {
    'DSS': {
        'python': 'simulators.api_opendss:OpenDSSSimulator',
    },
    'RegControl': {
        'python': 'simulators.regulator_control:RegulatorSimulator', # Certifique-se de ter criado este arquivo
    },
    'Collector': {
        'python': 'simulators.collector:Collector',
    },
}

def run_scenario():
    # Validações iniciais
    if not CIRCUITO_DSS.exists():
        print(f"ERRO CRÍTICO: Arquivo DSS não encontrado em:\n{CIRCUITO_DSS}")
        sys.exit(1)

    with mosaik.World(SIM_CONFIG) as world:
        print("--- Inicializando Simuladores ---")
        
        # 1. Iniciar OpenDSS
        dss_sim = world.start('DSS', topofile=str(CIRCUITO_DSS), step_size=STEP_SIZE)
        
        # 2. Iniciar Simulador de Controle
        # Usamos o mesmo step_size para sincronia simples, ou menor se quiser simular sub-intervalos
        reg_sim = world.start('RegControl', step_size=STEP_SIZE)
        
        # 3. Iniciar Coletor
        collector = world.start('Collector', 
                                start_date='2025-01-01 00:00:00',
                                output_file=str(ARQUIVO_RESULTADOS_CSV),
                                print_results=False)

        # 4. Instanciar a Rede
        print("Instanciando a Grid do OpenDSS...")
        grid = dss_sim.Grid()
        monitor = collector.Monitor()
        
        # [IMPORTANTE] Forçar a execução do 'create' no OpenDSS para popular a lista de reguladores
        # Acessar grid.children obriga o Mosaik a processar as entidades
        _ = list(grid.children)
        
        # ==========================================================
        # 5. AUTO-CONFIGURAÇÃO DOS REGULADORES (Plug and Play)
        # ==========================================================
        # Recupera os metadados detectados pelo api_opendss.py
        detected_regs = dss_sim.get_detected_regulators()
        
        if detected_regs:
            print(f"\n[AUTO-SETUP] Configurando {len(detected_regs)} reguladores de tensão detectados:")
            
            for info in detected_regs:
                eid_dss = info['eid_dss'] # Ex: RegControl-Reg1
                name = info['name']
                tap_ini = info.get('tap_ini', 0)

                print(f"  -> Conectando {name} (Vreg={info['vreg']}, Band={info['band']}, PT={info['pt_ratio']})")
                print(f" -> Conectando {name} (Vreg={info['vreg']}, PT={info['pt_ratio']}, LDC_R={info['R']})")
                
                # A. Instanciar o Controlador Python com os parâmetros do DSS
                ctrl_entity = reg_sim.RegController(
                    vreg=info['vreg'],
                    band=info['band'],
                    pt_ratio=info['pt_ratio'],
                    ct_primary=info.get('ct_primary', 0),
                    R=info.get('R', 0),
                    X=info.get('X', 0),
                    delay=info['delay'],
                    tap_delay=info['tap_delay'],
                    tap_ini=0
                )
                
                # B. Encontrar a entidade correspondente no OpenDSS
                # grid.children contém todas as entidades (Load, Line, Bus, RegControl)
                try:
                    dss_entity = next(e for e in grid.children if e.eid == eid_dss)
                    print(dss_entity)
                except StopIteration:
                    print(f"     [ERRO] Entidade {eid_dss} não encontrada no grid.children!")
                    continue

                # C. Realizar as Conexões de Malha Fechada
                
                # Feedback: DSS envia Tensão Medida -> Controlador
                world.connect(dss_entity, ctrl_entity, ('v_meas', 'v_meas'),
                              time_shifted=True,
                              initial_data={'v_meas': info['vreg']})

                world.connect(dss_entity, ctrl_entity, ('i_meas', 'i_meas'),
                              time_shifted=True,
                              initial_data={'i_meas': 0})
                
                # Ação: Controlador envia Novo Tap -> DSS
                world.connect(ctrl_entity, dss_entity, ('tap_cmd', 'tap'))
                
                # (Opcional) Monitorar o Tap no Collector para ver se está mudando
                world.connect(dss_entity, monitor, 'tap')
                
        else:
            print("\n[AVISO] Nenhum regulador de tensão detectado no circuito.")

        # ==========================================================
        # 6. Monitoramento Padrão (Linhas e Barras)
        # ==========================================================
        
        # # Monitorar Linha 650632
        # nome_alvo = 'L1'
        # eid_alvo = f'Line-{nome_alvo}'
        # entidades_encontradas = [e for e in grid.children if e.eid.lower() == eid_alvo.lower()]
        # if entidades_encontradas:
        #     world.connect(entidades_encontradas[0], monitor, 'I1_A', 'I1_ang', 'I2_A', 'I2_ang', 'I3_A', 'I3_ang')
        #     print(f"Monitorando Linha: {eid_alvo}")

        # Monitorar Barra 632 (onde chega a linha acima) para ver tensão
        target_name = '800'
        target_eid = f'Bus-{target_name}'
        bus_entities = [e for e in grid.children if e.eid == target_eid]
        if bus_entities:
            world.connect(bus_entities[0], monitor, 'V1_pu', 'V2_pu', 'V3_pu')
            print(f"Monitorando Barra: {target_eid}")

        # Monitorar Barra 840
        target_name = '840'
        target_eid = f'Bus-{target_name}'
        bus_entities = [e for e in grid.children if e.eid == target_eid]
        if bus_entities:
            world.connect(bus_entities[0], monitor, 'V1_pu', 'V2_pu', 'V3_pu')
            print(f"Monitorando Barra: {target_eid}")

        # --- Execução ---
        print(f"\nIniciando simulação de {N_PASSOS} passos (Step={STEP_SIZE}s)...")
        world.run(until=END_TIME, print_progress=False)
        print("Simulação concluída.")

        # --- Check Rápido ---
        if ARQUIVO_RESULTADOS_CSV.exists():
            print(f"\nResultados salvos em: {ARQUIVO_RESULTADOS_CSV}")
            try:
                df = pd.read_csv(ARQUIVO_RESULTADOS_CSV)
                if not df.empty:
                    cols = [c for c in df.columns if 'tap' in c.lower()]
                    if cols:
                        print("\nResumo da Operação dos Taps:")
                        print(df[cols].describe())
            except:
                pass

if __name__ == '__main__':
    run_scenario()