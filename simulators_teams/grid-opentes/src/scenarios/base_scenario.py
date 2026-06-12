# Importa pacotes necessários
import mosaik
from mosaik.util import connect_many_to_one

from pathlib import Path

current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent

# Configuração dos simuladores utilizados no cenário
# A chave 'Ctrl' define o controlador ativo no cenário:
# - 'controller_des_SEM': sem geração distribuída
# - 'controller_des_NO': com GD adicional, sem controle
# - 'controller_des_VV': com GD adicional, com controle Volt-Var
# - 'controller_des_VW': com GD adicional, com controle Volt-Watt
sim_config = {
    'Grid': {'python': 'mosaik_pandapower.simulator:Pandapower'},
    'CSV': {'python': 'simulators.csv_sim_pandas:CSV'},
    'PV': {'python': 'simulators.pv_simulator:PvAdapter'},
    'Ctrl': {'python': 'simulators.controller_des_SEM:Controller'},
    'Collector': {'python': 'simulators.collector:Collector'},
}# - 'controller_des_VV': com GD adicional, com controle Volt-Var


# Parâmetros da simulação
END =   1*60*60  # duração da simulação 
START = '2016-01-01 11:00:00'  # horário de início da simulação
GRID_FILE = parent_dir / 'data' / 'rede_1-LV-rural2--0-sw.json'  # arquivo da rede elétrica
PV_DATA = parent_dir / 'data' / 'solar_data_Bremen_minutes.csv'  # dados de irradiância solar

def config_cosimul() -> mosaik.World:
    # Cria o "mundo" da simulação com base na configuração dos simuladores
    world = mosaik.World(sim_config)

    # Inicializa os simuladores
    gridsim = world.start('Grid', step_size=60, mode='pf_timeseries')  # simulador da rede elétrica
    DNIdata = world.start('CSV', sim_start=START, datafile=PV_DATA)  # simulador csv
    pvsim = world.start('PV', start_date=START, gen_neg=False)  # simulador da geração fotovoltaica
    ctrlsim = world.start('Ctrl', output_delay=5)  # controlador (substituído conforme o cenário)
    grid = gridsim.Grid(gridfile=GRID_FILE, sim_start=START).children  # elementos da rede elétrica
    solar_data = DNIdata.Data.create(1)  # entidade de dados solares
    pv = pvsim.PV(lat=53.07, area=3e4)  # entidade de geração FV 

    # Criação dos 48 controladores para as unidades geradoras
    controllers = [ctrlsim.Ctrl() for _ in range(48)]

    # Filtragem das entidades da rede para facilitar as conexões
    nodes_gen = [element for element in grid if 'ext_gen' in element.eid]  # geradores externos
    nodes = [e for e in grid if e.type in 'Bus']  # barras da rede
    lines = [e for e in grid if e.type in 'Line']  # linhas da rede
    loads = [e for e in grid if e.type in 'Load']  # cargas

    # Conecta a irradiância solar à geração fotovoltaica
    world.connect(solar_data[0], pv, 'DNI')

    # Índices das barras onde estão alocados os geradores fotovoltaicos
    indices_nodes_gen = [2, 4, 5, 10, 12, 15, 16, 21, 22, 24, 25, 27, 28, 30, 31, 34, 35, 37,
                        32, 40, 44, 45, 46, 43, 49, 51, 52, 53, 56, 57, 59, 63, 65, 66, 68,
                        69, 71, 72, 74, 76, 79, 80, 84, 86, 88, 91, 92, 93]

    # Conexão dos controladores aos nós da rede
    generated_nodes = []
    for i, idx in enumerate(indices_nodes_gen):
        # Entrada dos controladores: potência FV e tensão da barra
        world.connect(pv, controllers[i], ('P_gen', 'p_dc'))
        world.connect(nodes[idx], controllers[i], ('vm_pu', 'val_in'))

        # Saídas dos controladores: potência reativa (q) e ativa (p) para os geradores
        world.connect(controllers[i], nodes_gen[idx], ('mod', 'q_mvar'), ('pot', 'p_mw'), weak=True)

        generated_nodes.append(nodes_gen[idx])

    # Inicializa o coletor de dados
    collector = world.start('Collector', start_date=START, print_results=False)
    monitor = collector.Monitor()

    # Coleta de dados específicos
    world.connect(pv, monitor, 'P_gen')  # geração FV total
    world.connect(nodes_gen[14], monitor, 'q_mvar', 'p_mw')  # potência em um dos geradores
    world.connect(nodes[24], monitor, 'p_mw', 'vm_pu', 'q_mvar')  # potência e tensão em uma barra

    # Coleta de dados em todas as linhas: carregamento percentual
    connect_many_to_one(world, lines, monitor, 'loading_percent')

    # Coleta de tensão e potência em todas as barras
    connect_many_to_one(world, nodes, monitor, 'vm_pu')
    connect_many_to_one(world, nodes, monitor, 'p_mw')

    return world

def run_cosimul() -> None:
    
    world = config_cosimul()
    
    # Executa a simulação
    world.run(until=END, print_progress=True)


if __name__ == "__main__":
    run_cosimul()
