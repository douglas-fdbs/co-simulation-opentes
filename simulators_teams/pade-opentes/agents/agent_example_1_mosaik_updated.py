#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agentes do cenario causal (evolucao do first.py).

Mesma estrutura de dois agentes do first.py original (AgenteA <-> AgenteB
trocando mensagens via OMNeT++), mas agora o payload carrega informacao
ELETRICA real e fecha o laco de controle com o OpenDSS:

  AgenteA (medidor):   le a tensao do barramento (V_in) e a publica como
                       mensagem FIPA-ACL na rede de comunicacao (OMNeT++).
  AgenteB (controlador): recebe a tensao JA ATRASADA pela rede e aplica uma
                       logica Volt/Watt, devolvendo o setpoint P_ref para a
                       bateria (que injeta no PVSystem -> OpenDSS).

Assim, latencia/jitter/perda de pacotes do OMNeT++ afetam a tensao que o
controlador efetivamente "ve", como exige o benchmark de co-simulacao.

Configuravel por variaveis de ambiente:
  AGENT_STEP_SIZE (default 300s) | V_HIGH (1.02) | V_LOW (0.98) | KW_RATED (50)
"""

import json
import os

from pade.acl.aid import AID
from pade.core.agent import Agent
from pade.drivers.mosaik_driver import MosaikCon
from pade.misc.utility import display_message, start_loop


STEP_SIZE = int(os.environ.get('AGENT_STEP_SIZE', '300'))
V_HIGH = float(os.environ.get('V_HIGH', '1.02'))
V_LOW = float(os.environ.get('V_LOW', '0.98'))
KW_RATED = float(os.environ.get('KW_RATED', '50.0'))

MOSAIK_MODELS = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'PadeAgent': {
            'public': True,
            'params': ['agent_id'],
            'attrs': [
                'val_in', 'val_out',   # comunicacao (mensagens via OMNeT++)
                'V_in',                # entrada do medidor (tensao do barramento)
                'SoC_in',              # feedback do estado de carga da bateria
                'P_ref', 'Q_ref',      # saida do controlador (setpoint)
            ],
        },
    },
}

ACTIVE_AGENTS = {}


class MosaikSim(MosaikCon):
    def __init__(self, agent, step_size=STEP_SIZE):
        super().__init__(MOSAIK_MODELS, agent)
        self.step_size = step_size

    def create(self, num, model, agent_id):
        return [{'eid': agent_id, 'type': model}]

    def step(self, time, inputs, max_advance=0):
        for eid, attrs in inputs.items():
            agente = ACTIVE_AGENTS.get(eid)
            if agente is None:
                continue

            # --- Medidor: le a tensao do barramento (media das fases nao-nulas) ---
            if 'V_in' in attrs:
                valores = [v for v in attrs['V_in'].values()
                           if isinstance(v, (int, float)) and v > 0.1]
                if valores:
                    agente.ao_medir_tensao(sum(valores) / len(valores), time)

            # --- Controlador: mensagens vindas da rede de comunicacao (atrasadas) ---
            if 'val_in' in attrs:
                bruto = list(attrs['val_in'].values())[0]
                if bruto:
                    for msg in str(bruto).split('|||'):
                        if msg:
                            agente.receber_mensagem_da_rede(msg)

            # --- Controlador: feedback de SoC ---
            if 'SoC_in' in attrs:
                agente.soc = list(attrs['SoC_in'].values())[0]

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            agente = ACTIVE_AGENTS.get(eid)
            data[eid] = {}
            for attr in attrs:
                if agente is None:
                    continue
                if attr == 'val_out':
                    data[eid]['val_out'] = agente.val_out
                    agente.val_out = ''
                elif attr == 'P_ref':
                    data[eid]['P_ref'] = agente.p_ref
                elif attr == 'Q_ref':
                    data[eid]['Q_ref'] = agente.q_ref
        return data


class AgenteComunicador(Agent):
    """Agente que pode atuar como medidor (AgenteA) ou controlador (AgenteB),
    conforme seu nome local."""

    def __init__(self, aid, is_sender=False):
        super().__init__(aid=aid, debug=False)
        self.val_out = ''
        self.p_ref = 0.0
        self.q_ref = 0.0
        self.soc = 50.0
        self.v_seen = 0.0
        self.is_sender = is_sender
        if self.is_sender:
            self.mosaik_sim = MosaikSim(self)

    def on_start(self):
        super().on_start()
        ACTIVE_AGENTS[self.aid.localname] = self
        papel = 'medidor' if self.aid.localname == 'AgenteA' else 'controlador'
        display_message(self.aid.localname, f'Agente online ({papel}) ligado ao OMNeT++.')

    # ---- Medidor (AgenteA): publica a tensao na rede de comunicacao ----
    def ao_medir_tensao(self, v_meas, time):
        self.v_seen = v_meas
        msg = {
            'sender': self.aid.localname,
            'receiver': 'AgenteB',
            'ontology': 'medicao_tensao',
            'conversation_id': f'meas-t{time}',
            'V_meas': round(v_meas, 6),
            't': time,
        }
        self.val_out = json.dumps(msg)
        display_message(self.aid.localname, f'medi V={v_meas:.4f} pu -> enviando pela rede')

    # ---- Controlador (AgenteB): recebe a tensao atrasada e decide Volt/Watt ----
    def receber_mensagem_da_rede(self, json_string):
        try:
            msg = json.loads(json_string)
        except Exception:
            return
        if 'V_meas' not in msg:
            return

        v = float(msg['V_meas'])
        self.v_seen = v

        # Logica Volt/Watt:
        #   V alta  -> carrega (absorve P, P_ref < 0) -> tende a baixar a tensao
        #   V baixa -> descarrega (injeta P, P_ref > 0) -> tende a subir a tensao
        if v > V_HIGH:
            self.p_ref = -KW_RATED
            acao = 'CARGA'
        elif v < V_LOW:
            self.p_ref = KW_RATED
            acao = 'DESCARGA'
        else:
            self.p_ref = 0.0
            acao = 'IDLE'

        # Protecao: bateria cheia nao continua carregando
        if self.soc >= 99.99 and self.p_ref < 0:
            self.p_ref = 0.0

        display_message(self.aid.localname,
                        f'recebi V={v:.4f} (atrasada pela rede) -> {acao} P_ref={self.p_ref:.1f} kW')


if __name__ == '__main__':
    host = '0.0.0.0'
    port = int(os.environ.get('PADE_PORT', '5678'))
    ams_config = {'name': host, 'port': int(os.environ.get('AMS_PORT', '8000'))}

    aid_a = AID(name=f'AgenteA@{host}:{port}')       # medidor
    aid_b = AID(name=f'AgenteB@{host}:{port + 1}')   # controlador

    agente_a = AgenteComunicador(aid=aid_a, is_sender=True)
    agente_b = AgenteComunicador(aid=aid_b, is_sender=False)
    agente_a.update_ams(ams_config)
    agente_b.update_ams(ams_config)

    start_loop([agente_a, agente_b])
