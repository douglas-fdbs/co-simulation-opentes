import mosaik_api

META = {
    'type': 'time-based',
    'models': {
        'Controller': {
            'public': True,
            'params': [
                'target_battery', 
                'kw_rated',
                'charge_trigger', 
                'discharge_trigger', 
                'pct_charge', 
                'pct_discharge', 
                'time_charge_trigger'
            ],
            'attrs': [
                'SoC_in',       # Entrada: SoC atual vindo do simulador de bateria
                'curve_value',  # Entrada: Valor da curva vindo do CSV
                'P_ref',        # Saída: Comando de P para a bateria
                'Q_ref'         # Saída: Comando de Q para a bateria
            ],
        },
    },
}

class BatteryControllerSim(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(META)
        self.controllers = {}
        self.step_size = None

    def init(self, sid, time_resolution=1., step_size=900):
        self.step_size = step_size
        return self.meta

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = f'Ctrl_{i}'
            self.controllers[eid] = {
                'kw_rated': float(model_params.get('kw_rated', 50.0)),
                'charge_trigger': float(model_params.get('charge_trigger', 0.2)),
                'discharge_trigger': float(model_params.get('discharge_trigger', 0.6)),
                'pct_charge': float(model_params.get('pct_charge', 100.0)),
                'pct_discharge': float(model_params.get('pct_discharge', 100.0)),
                'time_charge_trigger': float(model_params.get('time_charge_trigger', 2.0)), # 2 AM default
                
                'P_ref': 0.0,
                'Q_ref': 0.0,
                'is_time_charging': False,
                'curve_value': 0.0
            }
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        # Converte o tempo do mosaik (segundos) para a hora do dia (0.0 a 23.99)
        hour_of_day = (time % 86400) / 3600.0
        step_hours = self.step_size / 3600.0
        
        for eid, ctrl in self.controllers.items():
            current_soc = None
            curve_value = 0.0 # Idling por padrão se não receber curva
            
            # Leitura dos Inputs
            if eid in inputs:
                if 'SoC_in' in inputs[eid]:
                    current_soc = list(inputs[eid]['SoC_in'].values())[0]
                if 'curve_value' in inputs[eid]:
                    curve_value = list(inputs[eid]['curve_value'].values())[0]

            ctrl['curve_value'] = curve_value
            # Potências constantes baseadas em %
            p_charge_kw = - (ctrl['pct_charge'] / 100.0) * ctrl['kw_rated']
            p_discharge_kw = (ctrl['pct_discharge'] / 100.0) * ctrl['kw_rated']
            
            # --- LÓGICA MODO DEFAULT OPENDSS ---
            
            # 1. Discharge Trigger tem prioridade máxima (Se a curva excede, descarrega)
            if curve_value > ctrl['discharge_trigger']:
                ctrl['P_ref'] = p_discharge_kw
                ctrl['is_time_charging'] = False # Cancela o carregamento noturno se a demanda subir
                
            # 2. Charge Trigger (Se a curva for muito baixa, carrega)
            elif curve_value < ctrl['charge_trigger']:
                ctrl['P_ref'] = p_charge_kw
                
            # 3. Time Charge Trigger (Regra de horário para forçar carga)
            else:
                trigger_h = ctrl['time_charge_trigger']
                if trigger_h >= 0:
                    # Verifica se cruzamos a hora do gatilho NESTE step exato
                    if trigger_h <= hour_of_day < (trigger_h + step_hours):
                        ctrl['is_time_charging'] = True
                        
                # Se estamos na janela de carregamento por tempo, comanda carga
                if ctrl['is_time_charging']:
                    ctrl['P_ref'] = p_charge_kw
                else:
                    ctrl['P_ref'] = 0.0 # Nenhuma condição atingida, Idling

            # --- PROTEÇÕES DO CONTROLADOR ---
            # O controlador percebe que a bateria encheu e para de pedir carga.
            # (A bateria física já bloquearia, mas isso encerra a flag is_time_charging)
            if current_soc is not None:
                if current_soc >= 99.99 and ctrl['P_ref'] < 0:
                    ctrl['P_ref'] = 0.0
                    ctrl['is_time_charging'] = False # Atingiu 100%, encerra o time charge
                    
                # Nota: A proteção de reserva na descarga (SoC <= %reserve) é operada
                # inerentemente pela nossa classe OpenDSSBattery (física). 
                # Portanto, o controlador continuará pedindo descarga, mas a física retornará P_out = 0.

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr in self.controllers[eid]:
                    data[eid][attr] = self.controllers[eid][attr]
        return data

if __name__ == '__main__':
    mosaik_api.start_simulation(BatteryControllerSim())