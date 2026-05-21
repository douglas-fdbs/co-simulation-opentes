import mosaik_api_v3
import numpy as np

class VR_Model(object):
    """
    Lógica de controle baseada no OpenDER_interface.
    """
    def __init__(self, name, Ts, Td_ctrl=30, Td_tap=2, Vref=120, db=2, 
                 PT_Ratio=20, CT_Primary=700, LDC_R=0, LDC_X=0,
                 tap_max=16, tap_min=-16, tap_ini=0, **kwargs):
        self.name = name
        self.Ts = Ts
        self.Td_ctrl = Td_ctrl
        self.Td_tap = Td_tap
        self.Vref = Vref
        self.db = db
        self.PT_Ratio = PT_Ratio
        self.CT_Primary = CT_Primary
        self.LDC_R = LDC_R
        self.LDC_X = LDC_X
        self.tap_max = tap_max
        self.tap_min = tap_min
        self.tap = tap_ini
        
        # Variáveis de estado interno
        self.Ti_ctrl = 0
        self.Ti_tap = Td_tap
        self.state = 'Idle'

        self._z_comp = complex(self.LDC_R, self.LDC_X) / 5
        self._CT = self.CT_Primary/5

    def run(self, V_meas, I_meas=0):
        """
        Calcula a nova posição do tap baseada na tensão medida (V_meas em Volts no secundário ou primário dependendo do PT).
        """
        # Converter para base de 120V se necessário, ou assumir que V_meas já vem escalado pelo PT
        # Se V_meas vier direto da linha (ex: 2400V) e PT_Ratio for 20: Vreg = 2400 / 20 = 120V
        # Vreg = V_meas / self.PT_Ratio if self.PT_Ratio > 0 else V_meas

        # Tensão no secundário do PT
        Vsec = V_meas / self.PT_Ratio if self.PT_Ratio > 0 else V_meas


        # Compensação LDC
        Vdrop = 0
        if self.CT_Primary > 0:
            I_norm = I_meas / self._CT
            Vdrop = I_norm * self._z_comp

        Vreg = abs(Vsec - Vdrop)

        # Lógica de Histerese
        if Vreg > self.Vref + self.db / 2:
            target_state = 'OV'
        elif Vreg < self.Vref - self.db / 2:
            target_state = 'UV'
        else:
            target_state = 'Idle'

        if target_state != 'Idle':
            if self.state == target_state:
                self.Ti_ctrl += self.Ts
            else:
                self.state = target_state
                self.Ti_ctrl= 0
        else:
            self.state = 'Idle'
            self.Ti_ctrl = 0

        self.Ti_tap += self.Ts

        # Atuação
        if self.Ti_ctrl > self.Td_ctrl:
            if self.Ti_tap >= self.Td_tap:
                if self.state == 'OV' and self.tap > self.tap_min:
                    self.tap -= 1
                    self.Ti_tap = 0
                elif self.state == 'UV' and self.tap < self.tap_max:
                    self.tap += 1
                    self.Ti_tap = 0

        return int(self.tap)

# --- Wrapper do Mosaik ---

META = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'RegController': {
            'public': True,
            'params': ['vreg', 'band', 'pt_ratio', 'ct_primary', 'R', 'X', 'delay', 'tap_delay', 'tap_ini'],
            'attrs': ['v_meas', 'i_meas', 'tap_cmd'], # v_meas (entrada), tap_cmd (saída)
        },
    },
}

class RegulatorSimulator(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(META)
        self.controllers = {}
        self.step_size = None

    def init(self, sid, time_resolution, step_size=60):
        self.sid = sid
        self.step_size = step_size
        return self.meta

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = f"Ctrl-{len(self.controllers)}"
            
            # Instancia a lógica Python pura
            logic = VR_Model(
                name=eid,
                Ts=self.step_size, # Importante: O passo de tempo define a velocidade de reação
                Td_ctrl=model_params.get('delay', 30),
                Td_tap=model_params.get('tap_delay', 2),
                Vref=model_params.get('vreg', 120),
                db=model_params.get('band', 2),
                PT_Ratio=model_params.get('pt_ratio', 1),
                CT_Primary=model_params.get('ct_primary', 0),
                LDC_R=model_params.get('R', 0),
                LDC_X=model_params.get('X', 0),
                tap_ini=model_params.get('tap_ini', 0)
            )
            
            self.controllers[eid] = logic
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        for eid, logic in self.controllers.items():
            # 1. Ler entrada (Tensão)
            # O input vem como: inputs[eid]['v_meas'][src_eid] = valor
            # if eid in inputs and 'v_meas' in inputs[eid]:
            #     v_dict = inputs[eid]['v_meas']
            #     if v_dict:
            #         v_val = list(v_dict.values())[0] # Pega o primeiro valor
            v = list(inputs[eid]['v_meas'].values())[0] if 'v_meas' in inputs.get(eid, {}) else 0
            i = list(inputs[eid]['i_meas'].values())[0] if 'i_meas' in inputs.get(eid, {}) else 0        

            if time < 2400:
                print(f"[{time}s] {eid}: V_pri={v:.1f}V | I_pri={i:.1f}A | Tap={logic.tap}")
                    # 2. Executar Lógica
            logic.run(V_meas=v, I_meas=i)
        
        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            logic = self.controllers.get(eid)
            if logic and 'tap_cmd' in attrs:
                data[eid] = {'tap_cmd': logic.tap}
        return data
    
if __name__ == '__main__':
    mosaik_api_v3.start_simulation(RegulatorSimulator())