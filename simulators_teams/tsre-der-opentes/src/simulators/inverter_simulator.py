import mosaik_api_v3
import numpy as np
import math

# ==============================================================================
# 1. MODELO FÍSICO DO INVERSOR (Domínio)
# ==============================================================================
class InverterModel:
    """
    Classe que emula o comportamento elétrico e as lógicas de proteção 
    (cut-in/cut-out, eficiência e limites) de um inversor (Potência Total).
    """
    def __init__(self, kVA, priority, eff_curve_x, eff_curve_y, pct_cutin, pct_cutout):
        self.kVA = kVA
        self.priority = priority
        self.eff_curve_x = eff_curve_x
        self.eff_curve_y = eff_curve_y
        self.pct_cutin = pct_cutin
        self.pct_cutout = pct_cutout
        
        self.is_on = False
        
        self.P_dc = 0.0
        self.Q_des = 0.0
        
        self.P_ac = 0.0
        self.Q_ac = 0.0

    def calculate_step(self):
        p_ac = 0.0
        q_ac = 0.0
        
        if self.kVA > 0:
            # Lógica de Cut-in / Cut-out
            p_dc_pct = (self.P_dc / self.kVA) * 100
            
            if not self.is_on:
                if p_dc_pct >= self.pct_cutin:
                    self.is_on = True
            else:
                if p_dc_pct <= self.pct_cutout:
                    self.is_on = False

            # Se estiver LIGADO, prossegue com os cálculos CA totais
            if self.is_on:
                p_pu = self.P_dc / self.kVA
                eff = np.interp(p_pu, self.eff_curve_x, self.eff_curve_y)
                p_ac_uncapped = self.P_dc * eff
                
                if self.priority == 'Active':
                    p_ac = min(p_ac_uncapped, self.kVA) 
                    q_max_avail = math.sqrt(self.kVA**2 - p_ac**2)
                    q_ac = math.copysign(min(abs(self.Q_des), q_max_avail), self.Q_des) if self.Q_des != 0 else 0.0
                    
                elif self.priority == 'Reactive':
                    q_ac = math.copysign(min(abs(self.Q_des), self.kVA), self.Q_des) if self.Q_des != 0 else 0.0
                    p_max_avail = math.sqrt(self.kVA**2 - q_ac**2)
                    p_ac = min(p_ac_uncapped, p_max_avail)
        
        self.P_ac = p_ac
        self.Q_ac = q_ac

# ==============================================================================
# 2. WRAPPER DO SIMULADOR (API Mosaik)
# ==============================================================================
META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'Inverter': {
            'public': True,
            'params': [
                'kVA',         
                'priority',    
                'eff_curve_x', 
                'eff_curve_y', 
                'pct_cutin',
                'pct_cutout'
            ],
            'attrs': [
                'P_dc', 'Q_des', 'P_ac', 'Q_ac'
            ],
        },
    },
}

class InverterSim(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(META)
        self.entities = {} 
        self.step_size = 1

    def init(self, sid, time_resolution=1.0, step_size=1.0):
        self.step_size = int(step_size)
        return self.meta
        
    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = f'{model}_{len(self.entities) + i}'
            
            inv_model = InverterModel(
                kVA=model_params.get('kVA', 1000.0),
                priority=model_params.get('priority', 'Active'),
                eff_curve_x=model_params.get('eff_curve_x', [0.0, 1.0]),
                eff_curve_y=model_params.get('eff_curve_y', [1.0, 1.0]),
                pct_cutin=model_params.get('pct_cutin', 20.0),
                pct_cutout=model_params.get('pct_cutout', 20.0)
            )
            
            self.entities[eid] = inv_model
            entities.append({'eid': eid, 'type': model})
            
        return entities

    def step(self, time, inputs, max_advance):
        for eid, attrs in inputs.items():
            inv = self.entities[eid]
            if 'P_dc' in attrs: 
                inv.P_dc = float(list(attrs['P_dc'].values())[0])
            if 'Q_des' in attrs: 
                inv.Q_des = float(list(attrs['Q_des'].values())[0])

        for eid, inv in self.entities.items():
            inv.calculate_step()

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            inv = self.entities[eid]
            data[eid] = {}
            for attr in attrs:
                if hasattr(inv, attr):
                    data[eid][attr] = getattr(inv, attr)
        return data

if __name__ == '__main__':
    mosaik_api_v3.start_simulation(InverterSim())