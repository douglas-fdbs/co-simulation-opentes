import mosaik
import sys
import pprint
import pandas as pd
from pathlib import Path

# --- Definição Dinâmica de Caminhos ---
CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "123Bus"
CIRCUITO_DSS = DATA_DIR / "run_ieee123_cosim_pv_5min.dss"

CIRCUITO_DSS = DATA_DIR / "run_ieee123_cosim_multiple_pv_5min.dss"

IRRADIANCE = DATA_DIR / "ieee123_shape_pv_5min.csv"
TEMPERATURE = DATA_DIR / "ieee123_temperature_5min.csv"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARQUIVO_RESULTADOS_CSV = OUTPUT_DIR / 'result_run_ieee123_cosim_smart_pv_5min.csv'

START_DATE = "2026-01-01 00:00:00"
STEP_SIZE = 60 * 5
N_PASSOS = 288
END_TIME = N_PASSOS * STEP_SIZE

# --- Configuração dos Simuladores ---
SIM_CONFIG = {
    'DSS': {
        'python': 'simulators.api_opendss:OpenDSSSimulator',
    },
    'PVSimulator': {
        'python': 'simulators.pv_panel_simulator:PVPanelSim'
    },
    'InverterSim': {
        'python': 'simulators.smart_inverter_simulator:InverterSim'
    },
    'CSV': {
        'python': 'simulators.csv_sim_pandas:CSV'
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

        # 1. Iniciando Simuladores
        dss_sim = world.start(
            'DSS', 
            topofile=str(CIRCUITO_DSS), 
            step_size=STEP_SIZE)
        
        pv_sim = world.start(
            'PVSimulator',
            step_size=STEP_SIZE)
        
        inv_sim = world.start(
            'InverterSim',
            step_size=STEP_SIZE)
        
        csv_sim_irr = world.start(
            'CSV',
            sim_start=START_DATE,
            datafile=str(IRRADIANCE))
        
        csv_sim_temp = world.start(
            'CSV',
            sim_start=START_DATE,
            datafile=str(TEMPERATURE)
        )

        # 2. Iniciando Coletor
        collector = world.start(
            'Collector',
            start_date=START_DATE,
            output_file=str(ARQUIVO_RESULTADOS_CSV),
            print_results=False
        )

        print("Instanciando a Grid do OpenDSS...")
        grid = dss_sim.Grid()
        csv_data_irr = csv_sim_irr.Data.create(1)
        csv_data_temp = csv_sim_temp.Data.create(1)
        monitor = collector.Monitor()

        # ====================================================================
        # MAPAS DE ENTIDADES DO OPENDSS
        # ====================================================================
        pv_info = dss_sim.get_detected_pvsystems()
        pvs_dss_map = {e.eid: e for e in grid.children if e.type == 'PVSystem'}
        buses_map = {e.eid: e for e in grid.children if e.type == 'Bus'} 

        # ====================================================================
        # ALGORITMO DE AGRUPAMENTO TOPOLÓGICO (Por Barramento)
        # ====================================================================
        inversores_logicos = {}

        for info in pv_info:
            bus_full = info.get('bus', '') 
            bus_base = bus_full.split('.')[0]
            
            if bus_base not in inversores_logicos:
                inversores_logicos[bus_base] = []
            inversores_logicos[bus_base].append(info)

        print(f"\n[OpenTES] Detectados {len(inversores_logicos)} Inversores Lógicos baseados na Topologia:")

        # ====================================================================
        # INSTANCIAÇÃO E CONEXÃO DINÂMICA DO OPEN DER
        # ====================================================================
        for bus_base, lista_pvs in inversores_logicos.items():
            qtd_elementos = len(lista_pvs)
            kva_total = sum([p['kva'] for p in lista_pvs]) 
            pmpp_total = sum([p['pmpp'] for p in lista_pvs])
            
            bus_eid = f"Bus-{bus_base}"
            if bus_eid not in buses_map:
                print(f"[AVISO] Barramento {bus_eid} não encontrado para monitoramento!")
                continue
            bus_obj = buses_map[bus_eid]
            
            print(f" -> Barra {bus_base}: Agrupando {qtd_elementos} PV(s) | Potência: {kva_total} kVA")

            # Instancia o Painel Físico (DC) consolidado
            pv_panel_obj = pv_sim.PVPanel.create(
                1,
                P_mpp=pmpp_total,
                irradiance_base=0.8,  # Corrigido para a base do OpenDSS!
                pt_curve_x=lista_pvs[0]['pt_curve_x'],
                pt_curve_y=lista_pvs[0]['pt_curve_y'],
            )[0]

            # Instancia o Smart Inverter (OpenDER)
            modo_fase = 'INDEP' if qtd_elementos > 1 else 'AVG'
            
            inv_obj = inv_sim.Inverter.create(
                1,
                kVA=kva_total,
                phase_mode=modo_fase,
                eff_curve_x=lista_pvs[0]['eff_curve_x'],
                eff_curve_y=lista_pvs[0]['eff_curve_y'],
                # Habilitamos Volt-Var (QV) como teste inicial!
                ctrl_config={'Volt_Var': True, 'Const_PF': False} 
            )[0]

            # Conexões Climáticas
            world.connect(csv_data_irr[0], pv_panel_obj, ('my_shape2_pv', 'irradiance'))
            world.connect(csv_data_temp[0], pv_panel_obj, ('temperature', 'temperature'))
            world.connect(pv_panel_obj, inv_obj, ('P_dc', 'P_dc'))

            # Monitoramento Base
            world.connect(pv_panel_obj, monitor, 'irradiance', 'temperature', 'P_dc')
            world.connect(inv_obj, monitor, 'P_ac', 'Q_ac')

            # Roteamento AC e Realimentação de Tensão (Fechando a malha)
            if modo_fase == 'INDEP':
                for i, pv_fase_info in enumerate(lista_pvs):
                    eid_dss = pv_fase_info['eid_dss']
                    pv_dss_obj = pvs_dss_map[eid_dss]
                    
                    idx = i + 1 
                    partes_bus = pv_fase_info.get('bus', '').split('.')
                    no_fase = partes_bus[1] if len(partes_bus) > 1 else '1'
                    attr_tensao_mag = f'V{no_fase}_pu'
                    
                    # IDA: Tensão da Barra para a respectiva perna do Inversor
                    world.connect(bus_obj, inv_obj,
                                  (attr_tensao_mag, f'V_meas_{idx}'),
                                  time_shifted=True,
                                  initial_data={attr_tensao_mag: 1.0})
                    
                    # VOLTA: Potência do Inversor para a fatia monofásica do OpenDSS
                    world.connect(inv_obj, pv_dss_obj, (f'P_ac_{idx}', 'P_des'), (f'Q_ac_{idx}', 'Q_des'))
                    
                    # Monitoramento de Injeção
                    world.connect(pv_dss_obj, monitor, 'P_meas', 'Q_meas')
                    world.connect(pv_dss_obj, monitor, 'P1', 'P2', 'P3', 'Q1', 'Q2', 'Q3')
                    
            else:
                pv_dss_obj = pvs_dss_map[lista_pvs[0]['eid_dss']]
                
                # IDA: Envia a tensão trifásica média
                world.connect(bus_obj, inv_obj,
                              ('V1_pu', 'V_meas_1'), ('V2_pu', 'V_meas_2'), ('V3_pu', 'V_meas_3'),
                              time_shifted=True,
                              initial_data={'V1_pu': 1.0, 'V2_pu': 1.0, 'V3_pu': 1.0})
                
                # VOLTA: Injeta a potência global no elemento
                world.connect(inv_obj, pv_dss_obj, ('P_ac', 'P_des'), ('Q_ac', 'Q_des'))
                
                # Monitoramento de Injeção
                world.connect(pv_dss_obj, monitor, 'P_meas', 'Q_meas')
                world.connect(pv_dss_obj, monitor, 'P1', 'P2', 'P3', 'Q1', 'Q2', 'Q3')


        # ====================================================================
        # MONITORES GERAIS DA REDE
        # ====================================================================
        target_names = ['149', '97']
        for target_name in target_names:
            target_eid = f'Bus-{target_name}'
            bus_entities = [e for e in grid.children if e.eid == target_eid]
            if bus_entities:
                world.connect(bus_entities[0], monitor, 'V1_pu', 'V2_pu', 'V3_pu')
                print(f"Monitorando Barra: {target_eid}")

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

        if ARQUIVO_RESULTADOS_CSV.exists():
            print(f"\nResultados salvos em: {ARQUIVO_RESULTADOS_CSV}")
            
if __name__ == '__main__':
    run_scenario()