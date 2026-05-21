import mosaik_api 
from simulators.battery_model import OpenDSSBattery

META = {
    'type': 'time-based',
    'models': {
        'Battery': {
            'public': True,
            'params': [
                'kw_rated', 
                'kwh_rated', 
                'kwh_stored',       # Absoluto
                'pct_reserve',      # Porcentagem
                'pct_eff_charge',   # Porcentagem
                'pct_eff_discharge',# Porcentagem
                'pct_idling_kw',    # Porcentagem
                'kva_rated'
            ],
            'attrs': [
                'P_ref',  # Input: Referência de P desejada
                'Q_ref',  # Input: Referência de Q desejada
                'P_out',  # Output: P real calculado
                'Q_out',  # Output: Q real calculado
                'SoC',    # Output: Estado de carga
                'State'   # Output: String de estado
            ],
        },
    },
}

class BatterySim(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(META)
        self.sid = None
        self.batteries = {}
        self.step_size = None

    def init(self, sid, time_resolution=1., step_size=900):
        self.sid = sid
        self.step_size = step_size
        return self.meta

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            # O ID da entidade deve facilitar o mapeamento com o OpenDSS (ex: Battery_0)
            eid = f'Battery_{i}'
            
            # Inicializa o modelo físico
            self.batteries[eid] = OpenDSSBattery(
                name=eid,
                kw_rated=model_params.get('kw_rated'),
                kwh_rated=model_params.get('kwh_rated'),
                kwh_stored=model_params.get('kwh_stored'),
                pct_reserve=model_params.get('pct_reserve', 20.0),
                pct_eff_charge=model_params.get('pct_eff_charge', 90.0),
                pct_eff_discharge=model_params.get('pct_eff_discharge', 90.0),
                pct_idling_kw=model_params.get('pct_idling_kw', 2.0),
                kva_rated=model_params.get('kva_rated')
            )
            
            # Buffers de input padrão
            self.batteries[eid].p_ref_buffer = 0.0
            self.batteries[eid].q_ref_buffer = 0.0
            
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        dt_seconds = self.step_size
        
        for eid, bat in self.batteries.items():
            # 1. Ler Inputs (Referências de Controle)
            if eid in inputs:
                attrs = inputs[eid]
                if 'P_ref' in attrs:
                    # Assume que vem de um controlador, pega o valor mais recente
                    bat.p_ref_buffer = list(attrs['P_ref'].values())[0]
                if 'Q_ref' in attrs:
                    bat.q_ref_buffer = list(attrs['Q_ref'].values())[0]
            
            # 2. Executar Física
            bat.calculate_step(bat.p_ref_buffer, bat.q_ref_buffer, dt_seconds)
            
        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            bat = self.batteries[eid]
            data[eid] = {}
            for attr in attrs:
                if attr == 'P_out':
                    data[eid][attr] = bat.p_out_kw
                elif attr == 'Q_out':
                    data[eid][attr] = bat.q_out_kvar
                elif attr == 'SoC':
                    data[eid][attr] = (bat.kwh_stored / bat.kwh_rated) * 100
                elif attr == 'State':
                    data[eid][attr] = bat.get_state_str()
        return data

if __name__ == '__main__':
    mosaik_api.start_simulation(BatterySim())