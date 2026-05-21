# - 'controller_des_NO': com GD adicional, sem controle

import mosaik_api
from opender import DER_PV

META = {
    'type': 'event-based',
    'models': {
        'Ctrl': {
            'public': True,
            'params': [],
            'attrs': ['val_in', 'p_dc', 'mod', 'pot'],
        },
    },
}


class Controller(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(META)
        self.agents = []

    def init(self, sid, time_resolution, output_delay=None):
        self.sid = sid
        self.output_delay = output_delay
        return self.meta

    def create(self, num, model):
        n_agents = len(self.agents)
        entities = []
        for i in range(n_agents, n_agents + num):
            eid = f'Agent_{i}'
            self.agents.append(eid)
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        self.time = time
        cache = self.cache = {}

        for agent_eid, attrs in inputs.items():
            val_in = list(attrs.get('val_in', {}).values())[0]
            p_dc = list(attrs.get('p_dc', {}).values())[0] * 1_000_000

            der_obj = DER_PV()
            der_obj.der_file.NP_P_MAX = 7500
            der_obj.der_file.NP_VA_MAX = 7500
            der_obj.der_file.NP_Q_MAX_ABS = 4500
            der_obj.der_file.NP_Q_MAX_INJ = 4500

            if val_in > 1.00:
                der_obj.update_der_input(v_pu=val_in, f=60, p_dc_w=p_dc)
                P, Q_novo = der_obj.run()

                Q_suave = 0
                Q_novo *= 1e-6
                P_novo = P * 1e-6

                cache[agent_eid] = {
                    'mod': Q_suave,
                    'pot': P_novo,
                }

        return None

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            if eid not in self.agents:
                raise ValueError(f'Unknown entity ID "{eid}"')

            data[eid] = {}
            for attr in attrs:
                if attr not in ('mod', 'pot'):
                    raise ValueError(f'Unknown attribute "{attr}"')
                data[eid][attr] = self.cache.get(eid, {}).get(attr)

        if data and self.output_delay:
            data['time'] = self.time + self.output_delay

        #print(f'SAÍDA: {data}')
        return data


def main():
    return mosaik_api.start_simulation(Controller())


if __name__ == '__main__':
    main()
