import mosaik_api_v3
import random

META = {
    "type": "time-based",
    "models": {
        "Random": {
            "public": True,
            "params": [],
            "attrs": ["val"],
        },
    },
}


class RandomSim(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(META)
        self.sid = None
        self.data = {}

    def init(self, sid, time_resolution=1.0):
        self.sid = sid
        return self.meta

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = f"rand_{i}"
            entities.append({"eid": eid, "type": model})
            self.data[eid] = 0  # Valor inicial
        return entities

    def step(self, time, inputs, max_advance):
        # Atualiza o valor de 'val' para cada entidade
        for eid in self.data:
            self.data[eid] = random.randint(0, 100)
        return time + 1

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr == "val":
                    data[eid][attr] = self.data[eid]
        return data


if __name__ == "__main__":
    # Normalmente não executamos isso diretamente aqui,
    # mas via mosaik-api-server no CMD do Docker
    
    mosaik_api_v3.start_simulation(RandomSim())
    # randomsim.run_as_server("0.0.0.0", 5555)
