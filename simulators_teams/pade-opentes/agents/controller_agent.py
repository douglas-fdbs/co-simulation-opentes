"""Agente PADE BatteryController.

Migração do simulador Mosaik ``BatteryControllerSim`` (originalmente em
``grid-opentes/src/simulators/controller_sim.py``). A lógica de controle
charge/discharge/time-charge permanece idêntica; o agente PADE adiciona
capacidade de troca de mensagens FIPA-ACL para coordenação distribuída futura.

A ponte com o Mosaik é feita pela classe ``BatteryControllerMosaik`` que herda
de ``pade.drivers.mosaik_driver.MosaikCon``. O agente expõe o modelo
``BatteryController`` com os mesmos atributos do simulador antigo
(``SoC_in``, ``curve_value`` como entradas; ``P_ref``, ``Q_ref`` como saídas).

Entry-point: rodar ``python agents/controller_agent.py`` dentro do container
``pade``. Por padrão escuta em ``0.0.0.0:5681`` (Mosaik conecta nessa porta).
"""

import os

from pade.acl.aid import AID
from pade.core.agent import Agent
from pade.drivers.mosaik_driver import MosaikCon
from pade.misc.utility import display_message, start_loop


MOSAIK_MODELS = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'BatteryController': {
            'public': True,
            'params': [
                'kw_rated',
                'charge_trigger',
                'discharge_trigger',
                'pct_charge',
                'pct_discharge',
                'time_charge_trigger',
            ],
            'attrs': [
                'SoC_in',
                'curve_value',
                'P_ref',
                'Q_ref',
            ],
        },
    },
}


ACTIVE_CONTROLLERS: dict[str, dict] = {}


class BatteryControllerMosaik(MosaikCon):
    """Ponte Mosaik <-> agente PADE para o controle de bateria."""

    def __init__(self, agent, step_size: int = 900):
        super().__init__(MOSAIK_MODELS, agent)
        self.step_size = step_size

    def init(self, sid, time_resolution=1.0, step_size=None):
        if step_size is not None:
            self.step_size = int(step_size)
        return super().init(sid, time_resolution=time_resolution)

    def create(self, num, model, **model_params):
        entities = []
        for i in range(num):
            eid = f'Ctrl_{i}'
            ACTIVE_CONTROLLERS[eid] = {
                'kw_rated': float(model_params.get('kw_rated', 50.0)),
                'charge_trigger': float(model_params.get('charge_trigger', 0.2)),
                'discharge_trigger': float(model_params.get('discharge_trigger', 0.6)),
                'pct_charge': float(model_params.get('pct_charge', 100.0)),
                'pct_discharge': float(model_params.get('pct_discharge', 100.0)),
                'time_charge_trigger': float(model_params.get('time_charge_trigger', 2.0)),
                'P_ref': 0.0,
                'Q_ref': 0.0,
                'is_time_charging': False,
                'curve_value': 0.0,
            }
            entities.append({'eid': eid, 'type': model})
        return entities

    def step(self, time, inputs, max_advance):
        hour_of_day = (time % 86400) / 3600.0
        step_hours = self.step_size / 3600.0

        for eid, ctrl in ACTIVE_CONTROLLERS.items():
            current_soc = None
            curve_value = 0.0

            if eid in inputs:
                if 'SoC_in' in inputs[eid]:
                    current_soc = list(inputs[eid]['SoC_in'].values())[0]
                if 'curve_value' in inputs[eid]:
                    curve_value = list(inputs[eid]['curve_value'].values())[0]

            ctrl['curve_value'] = curve_value
            p_charge_kw = -(ctrl['pct_charge'] / 100.0) * ctrl['kw_rated']
            p_discharge_kw = (ctrl['pct_discharge'] / 100.0) * ctrl['kw_rated']

            if curve_value > ctrl['discharge_trigger']:
                ctrl['P_ref'] = p_discharge_kw
                ctrl['is_time_charging'] = False
            elif curve_value < ctrl['charge_trigger']:
                ctrl['P_ref'] = p_charge_kw
            else:
                trigger_h = ctrl['time_charge_trigger']
                if trigger_h >= 0 and trigger_h <= hour_of_day < (trigger_h + step_hours):
                    ctrl['is_time_charging'] = True
                ctrl['P_ref'] = p_charge_kw if ctrl['is_time_charging'] else 0.0

            if current_soc is not None and current_soc >= 99.99 and ctrl['P_ref'] < 0:
                ctrl['P_ref'] = 0.0
                ctrl['is_time_charging'] = False

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr in ACTIVE_CONTROLLERS[eid]:
                    data[eid][attr] = ACTIVE_CONTROLLERS[eid][attr]
        return data


class BatteryControllerAgent(Agent):
    """Agente PADE que envelopa a ponte Mosaik do controle de bateria.

    Ainda não troca mensagens FIPA-ACL ativamente: o objetivo desta migração
    inicial é preservar a interface Mosaik existente. A integração via ACL com
    outros agentes (DSO, agregadores) fica como evolução natural quando os
    cenários transativos forem implementados.
    """

    def __init__(self, aid: AID, step_size: int = 900):
        super().__init__(aid=aid, debug=False)
        self.mosaik_sim = BatteryControllerMosaik(self, step_size=step_size)

    def on_start(self):
        super().on_start()
        display_message(self.aid.localname, 'BatteryControllerAgent online (ponte Mosaik ativa).')


if __name__ == '__main__':
    host = os.environ.get('CONTROLLER_HOST', '0.0.0.0')
    port = int(os.environ.get('CONTROLLER_PORT', '5681'))
    ams_host = os.environ.get('AMS_HOST', host)
    ams_port = int(os.environ.get('AMS_PORT', '8002'))
    step_size = int(os.environ.get('CONTROLLER_STEP_SIZE', '900'))

    aid_ctrl = AID(name=f'AgenteController@{host}:{port}')
    agente = BatteryControllerAgent(aid=aid_ctrl, step_size=step_size)
    agente.update_ams({'name': ams_host, 'port': ams_port})

    start_loop([agente])
