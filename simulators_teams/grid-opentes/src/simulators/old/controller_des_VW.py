# - 'controller_des_VW': com GD adicional, com controle Volt-Watt
import mosaik_api
from opender import DER, DER_PV

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
        self.agents = {}  
        self.output_delay = None
        self.time = 0

    def init(self, sid, time_resolution, output_delay=None):
        self.sid = sid
        self.output_delay = output_delay
        return self.meta

    def create(self, num, model):
        n_agents = len(self.agents)
        entities = []
        for i in range(n_agents, n_agents + num):
            eid = 'Agent_%d' % i
            # Initialize agent data with default values
            self.agents[eid] = {'pot': None, 'mod': 0}
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        self.time = time
        cache = {}

        for agent_eid, attrs in inputs.items():
            val_in_dict = attrs.get('val_in', {})
            p_dc_dict = attrs.get('p_dc', {})

            if not val_in_dict or not p_dc_dict:
                continue

            val_in = list(val_in_dict.values())[0]
            p_dc = list(p_dc_dict.values())[0]
            p_dc_w = p_dc * 1000000  # Converte de MW para W

            der_obj = DER_PV()
            der_obj.der_file.PV_MODE_ENABLE = True

            # Configuração da curva Volt-Watt
            der_obj.der_file.PV_CURVE_V1 = 1.05  # Tensão em pu onde inicia o corte de potência ativa
            der_obj.der_file.PV_CURVE_V2 = 1.06  # Tensão onde a potência é completamente cortada
            der_obj.der_file.NP_P_MAX = 7500
            der_obj.der_file.NP_VA_MAX = 7500
            der_obj.der_file.NP_Q_MAX_ABS = 4500

            # Executa o modelo do OpenDER com os valores de entrada atuais
            der_obj.update_der_input(v_pu=val_in, f=60, p_dc_w=p_dc_w)
            P_calculated_w, Q_calculated_var = der_obj.run()
            P_calculated_mw = P_calculated_w * 0.000001  # Converte para MW

            # Recupera o valor de potência injetada no passo anterior
            P_anterior = self.agents[agent_eid].get('pot')
            p_dc_mw = p_dc_w * 0.000001  # Potência disponível (FV) em MW

            if P_anterior is None:
                P_anterior = P_calculated_mw

            alpha = 0.05  # Fator de suavização para descida da potência

            # Aplica controle com rampa caso o OpenDER solicite corte de potência
            if P_calculated_mw < (p_dc_mw * 0.999):
                # Situação em que o controle Volt-Watt está ativo: aplica suavização
                P_novo = P_anterior + alpha * (P_calculated_mw - P_anterior)
            else:
                # Situação em que não há corte: segue em rampa até a potência máxima disponível
                P_novo = P_anterior + 0.5 * (p_dc_mw - P_anterior)

            # Garante que não se ultrapasse a potência disponível
            P_novo = min(P_novo, p_dc_mw)

            # Neste controlador, a potência reativa é mantida zerada
            Q_suave = 0

            # Armazena os valores suavizados para uso posterior
            self.agents[agent_eid]['pot'] = P_novo
            self.agents[agent_eid]['mod'] = Q_suave

            cache[agent_eid] = {'pot': P_novo, 'mod': Q_suave}

        self.cache_for_get_data = cache
        return None


    def get_data(self, outputs):
        data = {}
        current_cache = getattr(self, 'cache_for_get_data', {})

        for eid, attrs in outputs.items():
            if eid not in self.agents:
                raise ValueError('Unknown entity ID "%s"' % eid)

            data[eid] = {}
            for attr in attrs:
                if attr not in ('mod', 'pot'):
                    raise ValueError('Unknown attribute "%s" for %s' % (attr, eid))

                # Get value from the cache created in the last 'step' call
                if eid in current_cache and attr in current_cache[eid]:
                    data[eid][attr] = current_cache[eid][attr]
                else:
                    # Fallback to stored agent value if not in current step's cache
                    # Or None if it was never set (shouldn't happen ideally)
                    data[eid][attr] = self.agents[eid].get(attr)

        if data and self.output_delay:
            data['time'] = self.time + self.output_delay

        # print(f'SAÍDA ({self.time}): {data}') # Optional: keep for debugging

        return data


def main():
    return mosaik_api.start_simulation(Controller())


if __name__ == '__main__':
    main()