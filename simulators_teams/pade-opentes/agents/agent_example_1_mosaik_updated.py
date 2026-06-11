#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agentes do cenario causal Volt/Var (evolucao do first.py).

Mesma estrutura de dois agentes do first.py original (AgenteA <-> AgenteB
trocando mensagens via OMNeT++), mas agora o payload carrega a TENSAO da rede
eletrica e o laco de controle fecha no inversor fotovoltaico (sem bateria):

  AgenteA (medidor):     le a tensao do barramento (V_in) e a publica como
                         mensagem FIPA-ACL na rede de comunicacao (OMNeT++).
  AgenteB (controlador): recebe a tensao JA ATRASADA pela rede e aplica um
                         controle Volt/Var no inversor do PV:
                           - P (ativa)   = potencia solar disponivel (P_avail_in)
                           - Q (reativa) = funcao da tensao (regula a tensao)
                         respeitando a potencia aparente do inversor:
                           S = sqrt(P^2 + Q^2) <= kVA
                         e devolve (P_ref, Q_ref) para o PVSystem -> OpenDSS.

Assim, latencia/jitter/perda de pacotes do OMNeT++ afetam a tensao que o
controlador efetivamente "ve", como exige o benchmark de co-simulacao.

O controle pode ser ligado/desligado por agente (param control_enabled),
permitindo comparar a co-simulacao SEM controle (Q=0, baseline) e COM controle
(Volt/Var).
"""

import json
import math
import os

from pade.acl.aid import AID
from pade.core.agent import Agent
from pade.drivers.mosaik_driver import MosaikCon
from pade.misc.utility import display_message, start_loop


STEP_SIZE = int(os.environ.get('AGENT_STEP_SIZE', '300'))

MOSAIK_MODELS = {
    'api_version': '3.0',
    'type': 'time-based',
    'models': {
        'PadeAgent': {
            'public': True,
            'params': [
                'agent_id',
                'control_enabled',   # 1 = Volt/Var ativo | 0 = baseline (Q=0)
                'kva',               # potencia aparente nominal do inversor
                'v_ref', 'v_deadband', 'v_min', 'v_max', 'q_max_pct',
            ],
            'attrs': [
                'val_in', 'val_out',   # comunicacao (mensagens via OMNeT++)
                'V_in',                # entrada do medidor (tensao do barramento)
                'P_avail_in',          # entrada do controlador (solar disponivel)
                'P_ref', 'Q_ref',      # saida do controlador (setpoint do inversor)
            ],
        },
    },
}

ACTIVE_AGENTS = {}


class MosaikSim(MosaikCon):
    def __init__(self, agent, step_size=STEP_SIZE):
        super().__init__(MOSAIK_MODELS, agent)
        self.step_size = step_size

    def create(self, num, model, agent_id, **params):
        ag = ACTIVE_AGENTS.get(agent_id)
        if ag is not None:
            ag.configurar(**params)
        return [{'eid': agent_id, 'type': model}]

    def step(self, time, inputs, max_advance=0):
        for eid, attrs in inputs.items():
            ag = ACTIVE_AGENTS.get(eid)
            if ag is None:
                continue

            # --- Medidor: le a tensao do barramento (media das fases nao-nulas) ---
            if 'V_in' in attrs:
                valores = [v for v in attrs['V_in'].values()
                           if isinstance(v, (int, float)) and v > 0.1]
                if valores:
                    ag.ao_medir_tensao(sum(valores) / len(valores), time)

            # --- Controlador: solar disponivel (define a ativa P) ---
            if 'P_avail_in' in attrs:
                ag.p_ref = float(list(attrs['P_avail_in'].values())[0])

            # --- Controlador: tensao vinda da rede (define a reativa Q via Volt/Var) ---
            if 'val_in' in attrs:
                bruto = list(attrs['val_in'].values())[0]
                if bruto:
                    for msg in str(bruto).split('|||'):
                        if msg:
                            ag.receber_mensagem_da_rede(msg)

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            ag = ACTIVE_AGENTS.get(eid)
            data[eid] = {}
            for attr in attrs:
                if ag is None:
                    continue
                if attr == 'val_out':
                    data[eid]['val_out'] = ag.val_out
                    ag.val_out = ''
                elif attr == 'P_ref':
                    data[eid]['P_ref'] = ag.p_ref
                elif attr == 'Q_ref':
                    data[eid]['Q_ref'] = ag.q_ref
        return data


class AgenteComunicador(Agent):
    """Agente que pode atuar como medidor (AgenteA) ou controlador Volt/Var
    (AgenteB), conforme seu nome local."""

    def __init__(self, aid, is_sender=False):
        super().__init__(aid=aid, debug=False)
        self.val_out = ''
        self.p_ref = 0.0
        self.q_ref = 0.0
        self.v_seen = 0.0
        self.is_sender = is_sender
        # parametros de controle (preenchidos por configurar() na criacao Mosaik)
        self.control_enabled = True
        self.kva = 3000.0
        self.v_ref = 1.0
        self.v_deadband = 0.01
        self.v_min = 0.95
        self.v_max = 1.05
        self.q_max_pct = 0.44
        if self.is_sender:
            self.mosaik_sim = MosaikSim(self)

    def configurar(self, control_enabled=None, kva=None, v_ref=None,
                   v_deadband=None, v_min=None, v_max=None, q_max_pct=None):
        if control_enabled is not None:
            self.control_enabled = bool(int(control_enabled))
        if kva is not None:
            self.kva = float(kva)
        if v_ref is not None:
            self.v_ref = float(v_ref)
        if v_deadband is not None:
            self.v_deadband = float(v_deadband)
        if v_min is not None:
            self.v_min = float(v_min)
        if v_max is not None:
            self.v_max = float(v_max)
        if q_max_pct is not None:
            self.q_max_pct = float(q_max_pct)

    def on_start(self):
        super().on_start()
        ACTIVE_AGENTS[self.aid.localname] = self
        papel = 'medidor' if self.aid.localname == 'AgenteA' else 'controlador Volt/Var'
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

    # ---- Controlador (AgenteB): Volt/Var a partir da tensao atrasada ----
    def _volt_var_q(self, v):
        """Curva Volt/Var (droop): V alta -> absorve Q (-); V baixa -> injeta Q (+)."""
        if not self.control_enabled:
            return 0.0
        # capacidade reativa: a ativa tem prioridade (limite de potencia aparente)
        q_cap = math.sqrt(max(0.0, self.kva ** 2 - self.p_ref ** 2))
        q_max = min(self.q_max_pct * self.kva, q_cap)
        hi = self.v_ref + self.v_deadband
        lo = self.v_ref - self.v_deadband
        if v > hi:
            frac = min(1.0, (v - hi) / max(1e-6, self.v_max - hi))
            return -q_max * frac        # absorve reativo (baixa a tensao)
        if v < lo:
            frac = min(1.0, (lo - v) / max(1e-6, lo - self.v_min))
            return +q_max * frac        # injeta reativo (sobe a tensao)
        return 0.0

    def receber_mensagem_da_rede(self, json_string):
        try:
            msg = json.loads(json_string)
        except Exception:
            return
        if 'V_meas' not in msg:
            return
        v = float(msg['V_meas'])
        self.v_seen = v
        # P ja foi definido por P_avail_in (solar disponivel); aqui calculamos Q.
        self.q_ref = self._volt_var_q(v)
        modo = 'ON' if self.control_enabled else 'OFF(baseline)'
        display_message(self.aid.localname,
                        f'V={v:.4f} (rede) | controle {modo} -> P={self.p_ref:.0f} kW, Q={self.q_ref:.0f} kvar')


if __name__ == '__main__':
    host = '0.0.0.0'
    port = int(os.environ.get('PADE_PORT', '5678'))
    ams_config = {'name': host, 'port': int(os.environ.get('AMS_PORT', '8000'))}

    aid_a = AID(name=f'AgenteA@{host}:{port}')       # medidor
    aid_b = AID(name=f'AgenteB@{host}:{port + 1}')   # controlador Volt/Var

    agente_a = AgenteComunicador(aid=aid_a, is_sender=True)
    agente_b = AgenteComunicador(aid=aid_b, is_sender=False)
    agente_a.update_ams(ams_config)
    agente_b.update_ams(ams_config)

    start_loop([agente_a, agente_b])
