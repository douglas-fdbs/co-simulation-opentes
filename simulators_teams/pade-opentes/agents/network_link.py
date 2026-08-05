#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Camada de rede para as mensagens FIPA: atraso, perda e telemetria.

Sucessor do `pade.simul` do PADE 2.2, que desviava toda mensagem ACL para um
`SimulAgent` e de la para o servidor ns-3, devolvendo o instante de entrega
(`market-simulation/pade-cosimul/pade/simul/simul_agent.py`). Esse modulo foi
removido no PADE 3.0 junto com o `mode='simulation'`, entao no PADE 3.0 o
`Agent.send` vai direto para `reactor.connectTCP` e nenhuma mensagem passa por
simulador de rede nenhum.

Aqui o desvio e reconstruido SEM tocar no nucleo do PADE, que e compartilhado
com os outros cenarios do repositorio: o `_send` do agente e substituido em
tempo de execucao (`install`), e a entrega passa a ser agendada pelo backend.

BACKENDS
--------
`ideal`    entrega tudo, sem atraso. E o caso de controle da Fase 5.
`lossy`    modelo fenomenologico igual ao do NetworkNode.cc do comm-opentes:
           sorteia a perda, e o atraso e propagacao + transmissao (tamanho da
           mensagem sobre a banda) + jitter exponencial. Permite rodar o
           experimento de perda sem depender do OMNeT++.
`omnet`    cliente ZMQ para o container `comm`. O lado servidor precisa de um
           segundo ponto de entrada no MosaikBridge, que aceite um lote de
           mensagens fora do passo do Mosaik e devolva atraso e descarte por
           mensagem; ate isso existir, este backend levanta NotImplementedError
           com a explicacao, em vez de fingir que funcionou.

TEMPO
-----
O atraso e aplicado no relogio do reactor do Twisted, porque a negociacao inteira
acontece DENTRO de um passo do Mosaik, com o relogio da co-simulacao parado.
`time_scale` comprime esse atraso: a rede LPWA da tese entrega entre 10 e 90 s
por mensagem, o que faria cada rodada levar minutos de relogio real. Com
`time_scale = 0.01` o padrao temporal e preservado e o experimento fica viavel.
O valor NAO simulado (o atraso nominal) e o que vai para a telemetria.
"""

import csv
import json
import os
import random
import time

from twisted.internet import reactor

# Parametros do canal, com os mesmos defaults do comm-opentes/omnetpp.ini.
BANDWIDTH_BPS = float(os.environ.get("NET_BANDWIDTH_BPS", "50000"))
DROP_PROBABILITY = float(os.environ.get("NET_DROP_PROBABILITY", "0.0"))
JITTER_MEAN_S = float(os.environ.get("NET_JITTER_MEAN", "0.05"))
PROPAGATION_S = float(os.environ.get("NET_PROPAGATION", "0.010"))
TIME_SCALE = float(os.environ.get("NET_TIME_SCALE", "1.0"))
SEED = int(os.environ.get("NET_SEED", "0"))


class IdealBackend:
    """Canal perfeito: nada se perde, nada atrasa."""

    name = "ideal"

    def transmit(self, size_bytes):
        return 0.0, False


class LossyBackend:
    """Perda por sorteio e atraso de propagacao, transmissao e jitter."""

    name = "lossy"

    def __init__(self, drop_probability=DROP_PROBABILITY, bandwidth_bps=BANDWIDTH_BPS,
                 jitter_mean=JITTER_MEAN_S, propagation=PROPAGATION_S, seed=SEED):
        self.drop_probability = drop_probability
        self.bandwidth_bps = bandwidth_bps
        self.jitter_mean = jitter_mean
        self.propagation = propagation
        self.rng = random.Random(seed)

    def transmit(self, size_bytes):
        if self.rng.random() < self.drop_probability:
            return 0.0, True
        transmission = (size_bytes * 8.0) / self.bandwidth_bps
        jitter = self.rng.expovariate(1.0 / self.jitter_mean) if self.jitter_mean > 0 else 0.0
        return self.propagation + transmission + jitter, False


class OmnetBackend:
    """Cliente do container `comm`; o lado servidor ainda nao existe."""

    name = "omnet"

    def __init__(self, host=None, port=None):
        self.host = host or os.environ.get("OMNET_HOST", "comm")
        self.port = int(port or os.environ.get("OMNET_NET_PORT", "5556"))

    def transmit(self, size_bytes):
        raise NotImplementedError(
            "O backend 'omnet' precisa de um segundo ponto de entrada no "
            "MosaikBridge (porta {}), que aceite um lote de mensagens fora do "
            "passo do Mosaik e devolva atraso e descarte por mensagem. "
            "Enquanto isso nao existir, use NET_BACKEND=lossy, que reproduz o "
            "mesmo modelo fenomenologico do NetworkNode.cc em Python.".format(self.port))


BACKENDS = {"ideal": IdealBackend, "lossy": LossyBackend, "omnet": OmnetBackend}


class NetworkLink:
    """Desvia o envio de mensagens dos agentes para o modelo de rede."""

    def __init__(self, backend, trace_path=None, time_scale=TIME_SCALE):
        self.backend = backend
        self.time_scale = time_scale
        self.sent = 0
        self.dropped = 0
        self.delays = []
        self._trace = None
        self._writer = None
        if trace_path:
            self._trace = open(trace_path, "w", newline="")
            self._writer = csv.writer(self._trace)
            self._writer.writerow(["wall_time", "sender", "receiver", "performative",
                                   "bytes", "delay_s", "dropped"])

    def _size(self, message):
        size = getattr(message, "message_length", None)
        if size:
            return int(size)
        content = message.content or ""
        return len(content.encode("utf-8")) if isinstance(content, str) else len(content)

    def route(self, agent, original_send, message, receivers):
        """Chamado no lugar do `Agent._send`."""
        for receiver in receivers:
            size = self._size(message)
            delay, dropped = self.backend.transmit(size)
            self.sent += 1
            if self._writer:
                self._writer.writerow([
                    f"{time.time():.6f}",
                    getattr(message.sender, "localname", "?"),
                    getattr(receiver, "localname", "?"),
                    message.performative, size, f"{delay:.6f}", int(dropped)])
                self._trace.flush()
            if dropped:
                self.dropped += 1
                continue
            self.delays.append(delay)
            if delay <= 0.0:
                original_send(message, [receiver])
            else:
                reactor.callLater(delay * self.time_scale, original_send,
                                  message, [receiver])

    def summary(self):
        delivered = self.sent - self.dropped
        return {
            "backend": self.backend.name,
            "sent": self.sent,
            "delivered": delivered,
            "dropped": self.dropped,
            "drop_rate": self.dropped / self.sent if self.sent else 0.0,
            "delay_mean_s": sum(self.delays) / len(self.delays) if self.delays else 0.0,
            "delay_max_s": max(self.delays) if self.delays else 0.0,
        }

    def close(self):
        if self._trace:
            self._trace.close()


def install(agents, backend_name=None, trace_path=None, time_scale=TIME_SCALE):
    """Instala a camada de rede nos agentes dados.

    Substitui `agent._send` por uma versao que consulta o backend. Nao toca no
    `pade/core/agent.py`, que e compartilhado com os cenarios `star`, `ieee13` e
    `integrated`.
    """
    backend_name = backend_name or os.environ.get("NET_BACKEND", "ideal")
    if backend_name not in BACKENDS:
        raise ValueError(f"backend de rede desconhecido: {backend_name}")
    link = NetworkLink(BACKENDS[backend_name](), trace_path, time_scale)

    for agent in agents:
        original = agent._send

        def routed(message, receivers, _agent=agent, _original=original):
            link.route(_agent, _original, message, receivers)

        agent._send = routed

    print(f"[rede] backend={backend_name} time_scale={time_scale}"
          + (f" trace={trace_path}" if trace_path else ""), flush=True)
    return link
