import mosaik
from pathlib import Path

# --- CONFIGURAÇÃO DE CAMINHOS ---
CURRENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = CURRENT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "teste-pv"
IRRADIANCE = DATA_DIR / "irradiance.csv"
TEMPERATURE = DATA_DIR / "temperature.csv"
CIRCUITO_DSS = DATA_DIR / "main.dss"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ARQUIVO_RESULTADOS_CSV = OUTPUT_DIR / 'result_opendss_pv.csv'

# --- PARÂMETROS DE TEMPO ---
STEP_SIZE = 60 * 60 # 1 hora em segundos
N_PASSOS = 24
END_TIME = N_PASSOS * STEP_SIZE
START = '2026-01-01 00:00:00'  

SIM_CONFIG = {
    'CSV': {'python': 'simulators.csv_sim_pandas:CSV'},
    'PVSimulator': {'python': 'simulators.pv_panel_simulator:PVPanelSim'},
    'InverterSim': {'python': 'simulators.inverter_simulator:InverterSim'},
    'OpenDSS': {'python': 'simulators.api_opendss:OpenDSSSimulator'},
    'Collector': {'python': 'simulators.collector:Collector'}
}

def main():
    # 1. Inicialização do Mosaik
    world = mosaik.World(SIM_CONFIG)

    dss_sim = world.start('OpenDSS', step_size=STEP_SIZE, topofile=str(CIRCUITO_DSS))
    pv_sim = world.start('PVSimulator', step_size=STEP_SIZE)
    inv_sim = world.start('InverterSim', step_size=STEP_SIZE)
    csv_sim_irr = world.start('CSV', sim_start=START, datafile=str(IRRADIANCE))
    csv_sim_temp = world.start('CSV', sim_start=START, datafile=str(TEMPERATURE))
    
    # Resolvido o problema do salto das datas!
    collector = world.start('Collector', start_date=START, output_file=str(ARQUIVO_RESULTADOS_CSV))

    # 2. Instanciar a Rede do OpenDSS (Isso fará o wrapper descobrir os PVs e lobotomizá-los)
    grid = dss_sim.Grid()
    csv_data_irr = csv_sim_irr.Data.create(1)
    csv_data_temp = csv_sim_temp.Data.create(1)
    monitor = collector.Monitor()

    # 3. Extrair os parâmetros via Mosaik (A Mágica acontece aqui)
    pv_infos = dss_sim.get_detected_pvsystems()
    pvs_dss_map = {e.eid: e for e in grid.children if e.type == 'PVSystem'}

    # 4. Criação Dinâmica dos Simuladores em Python
    for info in pv_infos:
        pv_name = info['name']
        eid_dss = info['eid_dss']
        
        if eid_dss in pvs_dss_map:
            pv_dss_obj = pvs_dss_map[eid_dss]
            
            # Instancia as camadas lendo exatamente as curvas retiradas do arquivo .dss!
            pv_panel_obj = pv_sim.PVPanel.create(1, 
                P_mpp=info['pmpp'], 
                irradiance_base=0.8,
                pt_curve_x=info['pt_curve_x'],
                pt_curve_y=info['pt_curve_y']
            )[0]
            
            inv_obj = inv_sim.Inverter.create(1, 
                kVA=info['kva'], 
                priority='Active',
                eff_curve_x=info['eff_curve_x'],
                eff_curve_y=info['eff_curve_y'],
                pct_cutin=info['pct_cutin'],
                pct_cutout=info['pct_cutout']
            )[0]
            
            # --- Conexões ---
            world.connect(csv_data_irr[0], pv_panel_obj, ('irradiance', 'irradiance'))
            world.connect(csv_data_temp[0], pv_panel_obj, ('temperature', 'temperature'))

            world.connect(pv_panel_obj, inv_obj, ('P_dc', 'P_dc'))
            world.connect(inv_obj, pv_dss_obj, ('P_ac', 'P_des'), ('Q_ac', 'Q_des'))

            # --- Monitoramento ---
            world.connect(pv_panel_obj, monitor, 'irradiance', 'temperature', 'P_dc')
            world.connect(inv_obj, monitor, 'P_ac', 'Q_ac')
            world.connect(pv_dss_obj, monitor, 'P_meas', 'Q_meas')

    # 5. Rodar Simulação
    print(f"\nIniciando Co-simulação Mosaik para PV em {N_PASSOS} passos...")
    world.run(until=END_TIME)
    print(f"Simulação concluída! Resultados salvos em: {ARQUIVO_RESULTADOS_CSV}")

if __name__ == '__main__':
    main()