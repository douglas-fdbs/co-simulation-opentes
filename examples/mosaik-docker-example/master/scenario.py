import mosaik
import time

# Configuração da Simulação
sim_config = {
    # Conecta via TCP ao container 'mosaik-sim' na porta 5555
    "RandomSim": {
        "connect": "mosaik-sim:5555",
    },
    # Usamos um coletor padrão (pode rodar localmente no master)
    "MonitorSim": {
        "python": "monitor_sim:MonitorSim",
    },
}


def main():
    # Pequeno delay para garantir que o simulador remoto iniciou
    print("Aguardando simulador iniciar...")
    time.sleep(5)

    world = mosaik.World(sim_config)

    # Inicia os simuladores
    # O Mosaik vai tentar conectar no host 'mosaik-sim' porta 5555
    random_sim = world.start("RandomSim")
    monitor_sim = world.start("MonitorSim")

    # Instancia os modelos
    rand_model = random_sim.Random()
    monitor_model = monitor_sim.Monitor()

    world.connect(rand_model, monitor_model, "val")
    
    # Executa a simulação por 10 passos
    print("Iniciando simulação...")
    world.run(until=10)
    print("Simulação finalizada!")


if __name__ == "__main__":
    main()