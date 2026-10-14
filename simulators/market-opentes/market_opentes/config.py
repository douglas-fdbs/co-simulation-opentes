"""Configuracao do caso: rede, concentradores e dispositivos de armazenamento.

Le o `force.json` (topologia, ja convertido para OpenDSS na Fase 1) e o
`config.json` do trabalho original (alocacao de RED por no) e monta as
estruturas que os modelos de otimizacao consomem.

Papeis, na nomenclatura da tese (subsecao 6.1.2):
  AP  Agente Prosumidor      -> um por no de baixa tensao
  AC  Agente Concentrador    -> um por transformador de distribuicao
  AD  Agente DSO             -> um, na subestacao
  AM  Agente Mercado         -> um, coordena a decomposicao dual

Armazenamento: o do PROSUMIDOR e programado pelo proprio prosumidor e o DSO so
o influencia por preco; o de REDE e despachado diretamente pelo DSO como
servico ancilar.
"""

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

PKG_DIR = Path(__file__).resolve().parent
# O caso de estudo e a IEEE 13 barras, montada por `gen_ieee13_market.py` com o
# circuito, a alocacao de armazenamento, os perfis, o preco e o reservatorio de
# cenarios na mesma pasta. Dentro dos conteineres o pacote e montado fora da
# arvore do repositorio, entao os dois caminhos sao parametrizaveis.
_CASO = PKG_DIR.parents[1] / "grid-opentes" / "src" / "data" / "13Bus"
DATA_DIR = Path(os.environ.get("MARKET_DATA_DIR", _CASO))
GRID_DIR = Path(os.environ.get("MARKET_GRID_DIR", _CASO))

PERIODS = 96
DT_H = 0.25

# Limites operacionais da rede (subsecao 6.2.2 da tese).
V_MIN = 0.97
V_MAX = 1.03
# Tolerancia para CONTAR violacao. O otimizador do DSO cola a solucao no limite,
# e sem tolerancia o contador acusa violacao a 1e-13 pu de distancia, que e ruido
# de ponto flutuante. A folga aqui e varias ordens de grandeza menor que o erro
# da propria linearizacao (~1e-4 pu), entao nao esconde violacao real.
V_TOL = 1e-9
# Margem de seguranca aplicada aos limites DENTRO do modelo do DSO. A restricao
# de tensao e linearizada, e o otimizador cola a solucao exatamente no limite: o
# erro da linearizacao (1e-4 a 6e-4 pu, medido na validacao de sensitivity.py)
# vira violacao no fluxo de potencia completo. Sem esta margem, a negociacao
# promete 0,9700 pu e o OpenDSS entrega 0,96924.
#
# NAO existe na tese, que usa a mesma restricao linearizada sem recuo. Aparece
# quando a restricao passa a atuar de fato.
V_BACKOFF = float(os.environ.get("MARKET_V_BACKOFF", "1e-3"))

# Limiar de ACAO da fase de operacao, que pode ser mais rigoroso que o limite.
# O limite regulatorio continua sendo V_MIN e V_MAX: e contra eles que o
# resultado final e contado. Este limiar decide apenas QUANDO o DSO intervem.
# Operar com uma banda mais estreita que a norma e pratica de concessionaria,
# agir antes de violar, e aqui serve para exercitar o mecanismo de operacao sem
# afrouxar a margem da restricao. Padrao igual a V_MIN, isto e, sem rigor extra.
V_ACAO_MIN = float(os.environ.get("MARKET_V_ACAO_MIN", str(V_MIN)))
V_ACAO_MAX = float(os.environ.get("MARKET_V_ACAO_MAX", str(V_MAX)))

# Fator de potencia do armazenamento. A Eq. 6.16 supoe dQ = 0, o que vale para um
# dispositivo que nao mexe em reativo. Um inversor comum, porem, opera com fator
# de potencia constante, e ai o reativo acompanha o ativo e a hipotese passa a
# dominar o erro da restricao: medido no `sensitivity.py`, o erro sobe de 2,6e-5
# para 1,0e-3 pu, quarenta vezes.
#
# `none` (padrao) reproduz a tese exatamente, porque o termo dV/dQ zera. Um
# numero entre 0 e 1 liga o termo com tan(acos(pf)).
_pf = os.environ.get("MARKET_STORAGE_PF", "none")
STORAGE_PF = None if _pf.lower() in ("none", "", "0") else float(_pf)
STORAGE_TAN_PHI = 0.0 if STORAGE_PF is None else math.tan(math.acos(STORAGE_PF))

# Analise POR FASE (padrao, MARKET_FASE=1): o indice l das Eq. 6.18 a 6.30 e o
# par (barra, fase), o DSO vigia a tensao de cada fase e le a matriz
# `sensitivity_fase.npz`. Com 0 volta a formulacao da tese, com uma tensao e um
# preco sombra por no e a media das fases quando a barra e multifasica, que fica
# para comparacao. Ver docs/paginas/mercado.md.
FASE = os.environ.get("MARKET_FASE", "1") == "1"
# Como o armazenamento injeta nas fases, so com MARKET_FASE=1:
#   independente  cada fase e despachada separadamente (tres inversores
#                 monofasicos sobre a mesma bateria, ou inversor de quatro
#                 bracos), com limite Pmax/|F| por fase e um estado de carga so.
#                 E a unica escolha com preco sombra POR FASE.
#   equilibrado   o inversor reparte a potencia igualmente entre as fases, que
#                 e o comportamento da maioria dos inversores trifasicos de tres
#                 bracos. O DSO continua vigiando cada fase, mas a variavel e o
#                 preco sombra voltam a ser um por no.
DISPOSITIVO = os.environ.get("MARKET_DISPOSITIVO", "independente")
if DISPOSITIVO not in ("independente", "equilibrado"):
    raise ValueError(f"MARKET_DISPOSITIVO desconhecido: {DISPOSITIVO}")
LETRA = {1: "A", 2: "B", 3: "C"}

# Regulador de tensao na co-simulacao.
#   previsao  as derivacoes de cada intervalo sao as do ponto de operacao da
#             PREVISAO, as mesmas com que a matriz de sensibilidade foi
#             calculada, e o DSO as envia ao regulador. E o sequenciamento
#             fisicamente correto: o regulador ajusta pela previsao e o mercado
#             decide depois, com a derivacao como condicao de contorno. Sem isso
#             os dois controladores disputam a mesma variavel.
#   neutro    nenhum comando: o simulador OpenDSS trava as derivacoes em 0 ao
#             montar a rede, que era o comportamento antes desta chave. Existe so
#             para comparacao; o DSO negocia contra uma rede e a co-simulacao
#             mede outra.
REGULADOR = os.environ.get("MARKET_REGULADOR", "previsao")
if REGULADOR not in ("previsao", "neutro"):
    raise ValueError(f"MARKET_REGULADOR desconhecido: {REGULADOR}")

# Pesos das funcoes objetivo.
CK = 1.0        # concentrador, Eq. 6.25
A_PROSUMER = 0.2   # DSO, peso do armazenamento de prosumidor (p1 no codigo original)
B_NETWORK = 0.8    # DSO, peso do armazenamento de rede    (p2 no codigo original)
D_ENERGY = 0.8     # Dl da Eq. 6.26 (fixo em 0,8 no codigo original)


@dataclass
class Storage:
    node: int
    size_kwh: float
    max_flow_kw: float
    min_soc_kwh: float
    max_soc_kwh: float


@dataclass
class Concentrator:
    name: str
    mv_node: int
    lv_node: int
    kva: float
    nodes: list
    prosumer_storage: list = field(default_factory=list)
    network_storage: list = field(default_factory=list)


@dataclass
class Case:
    lv_nodes: list
    all_nodes: list                 # todos menos a subestacao, na ordem de S
    concentrators: list
    prosumer_storage: dict          # no -> Storage
    network_storage: dict           # no -> Storage
    # Modo por fase. `rows` sao as linhas da restricao de tensao (os nos, no
    # modo por no; os pares (no, fase), no modo por fase) e `ports` as colunas
    # da matriz por fase, os pares (no, fase) em que ha porta de armazenamento.
    fase: bool = False
    dispositivo: str = "independente"
    rows: list = field(default_factory=list)
    ports: list = field(default_factory=list)

    # ---- variaveis de decisao do armazenamento -------------------------------
    # Uma CHAVE identifica uma variavel de decisao de armazenamento, e e o indice
    # do preco sombra. No modo por no (e no por fase com dispositivo equilibrado)
    # a chave e o proprio no, um inteiro, exatamente como sempre foi. No modo por
    # fase com dispositivo independente e a porta, "671.A".

    @property
    def por_porta(self):
        return self.fase and self.dispositivo == "independente"

    def _portas_do_no(self, node):
        return [k for n, k in self.ports if n == node]

    def chaves(self, nodes):
        """Chaves das variaveis dos dispositivos nos nos dados, na ordem deles."""
        if not self.por_porta:
            return list(nodes)
        return [f"{n}.{LETRA[k]}" for n in nodes for k in self._portas_do_no(n)]

    @property
    def prosumer_keys(self):
        return self.chaves(self.prosumer_storage_nodes)

    @property
    def network_keys(self):
        return self.chaves(self.network_storage_nodes)

    @staticmethod
    def node_of(key):
        return key if isinstance(key, int) else int(str(key).split(".")[0])

    def mult(self, key):
        """Quantas variaveis o dispositivo da chave tem (|F| por porta, 1 por no)."""
        return len(self._portas_do_no(self.node_of(key))) if self.por_porta else 1

    def columns(self, key):
        """[(coluna, peso)] da chave na matriz de sensibilidade em uso.

        Por no: a coluna do no. Por porta: a coluna da porta. Equilibrado: a
        media das colunas das fases do no, que e o efeito de repartir 1 kW
        igualmente entre elas.
        """
        node = self.node_of(key)
        if not self.fase:
            return [(self.all_nodes.index(node), 1.0)]
        if self.por_porta:
            letra = str(key).split(".")[1]
            k = next(k for k, l in LETRA.items() if l == letra)
            return [(self.ports.index((node, k)), 1.0)]
        cols = [self.ports.index((node, k)) for k in self._portas_do_no(node)]
        return [(c, 1.0 / len(cols)) for c in cols]

    def node_columns(self, node):
        """[(coluna, peso)] de uma variacao de demanda no no (carga base).

        Por fase, a carga base nao tem coluna propria: a demanda do Load_n e
        aproximada por injecao igual nas fases das portas do no.
        """
        if not self.fase:
            return [(self.all_nodes.index(node), 1.0)]
        cols = [self.ports.index((node, k)) for k in self._portas_do_no(node)]
        return [(c, 1.0 / len(cols)) for c in cols] if cols else []

    @property
    def prosumer_storage_nodes(self):
        return sorted(self.prosumer_storage)

    @property
    def network_storage_nodes(self):
        return sorted(self.network_storage)

    @property
    def prosumer_nodes(self):
        """TODOS os nos de baixa tensao sob algum concentrador.

        E quem negocia no mercado, com ou sem bateria: o
        `start_pade_agents.py` do trabalho original cria um `ProsumerAgent` por
        no de baixa tensao. Nao confundir com `prosumer_storage_nodes`, que sao
        os que entram na negociacao de lambda, porque so eles tem programacao de
        armazenamento a acoplar.
        """
        return sorted({n for c in self.concentrators for n in c.nodes})


def _storage(node, params):
    return Storage(node=node,
                   size_kwh=float(params["size"]),
                   max_flow_kw=float(params["max_energy_flow"]),
                   min_soc_kwh=float(params["min_soc"]),
                   max_soc_kwh=float(params["max_soc"]))


def load_case(config_json):
    """Monta o caso a partir do force.json (rede) e do config.json (dispositivos)."""
    force = json.loads((GRID_DIR / "force.json").read_text())
    config = json.loads(Path(config_json).read_text())

    lv_nodes = [n["name"] for n in force["nodes"] if n["voltage_level"] == "low voltage"]
    all_nodes = [n["name"] for n in force["nodes"] if n["name"] != 0]

    prosumer_storage = {int(k): _storage(int(k), v)
                        for k, v in config["devices"]["storage_device"]["params"].items()}
    network_storage = {int(k): _storage(int(k), v)
                       for k, v in config["devices"]["dso_storage_device"]["params"].items()}

    concentrators = []
    for t in force["transformers"]:
        nodes = [n for n in t["nodes"] if n in lv_nodes]
        concentrators.append(Concentrator(
            name=t["name"],
            mv_node=t["source"],
            lv_node=t["target"],
            kva=float(t["power"]),
            nodes=nodes,
            prosumer_storage=[n for n in nodes if n in prosumer_storage],
            network_storage=[n for n in nodes if n in network_storage],
        ))

    # Um no de armazenamento que nao caia sob nenhum transformador ficaria fora
    # da negociacao sem ninguem perceber: o force.json tem casos assim (o
    # trafo_6_55 lista o no 54, que pertence ao trafo_5_35).
    assigned = {n for c in concentrators for n in c.prosumer_storage}
    orphans = set(prosumer_storage) - assigned
    if orphans:
        raise ValueError(f"nos com armazenamento de prosumidor sem concentrador: {sorted(orphans)}")

    case = Case(lv_nodes=lv_nodes, all_nodes=all_nodes, concentrators=concentrators,
                prosumer_storage=prosumer_storage, network_storage=network_storage,
                rows=list(all_nodes))
    if FASE:
        arq = DATA_DIR / "sensitivity_fase.npz"
        if not arq.exists():
            raise FileNotFoundError(
                f"MARKET_FASE=1 precisa de {arq}: gere com `sensitivity.py day --por-fase`")
        z = np.load(arq)
        case.fase, case.dispositivo = True, DISPOSITIVO
        case.rows = [(int(n), int(k)) for n, k in z["rows"]]
        case.ports = [(int(n), int(k)) for n, k in z["ports"]]
        sem_porta = [n for n in set(prosumer_storage) | set(network_storage)
                     if not case._portas_do_no(n)]
        if sem_porta:
            raise ValueError(f"nos com armazenamento sem porta por fase: {sorted(sem_porta)}")
    return case


def describe(case):
    print(f"{len(case.lv_nodes)} prosumidores em {len(case.concentrators)} concentradores")
    print(f"{len(case.prosumer_storage)} armazenamentos de prosumidor, "
          f"{len(case.network_storage)} de rede")
    for c in case.concentrators:
        print(f"  {c.name:<14} {c.kva:>6.1f} kVA  {len(c.nodes):>2} nos  "
              f"armaz. prosumidor {len(c.prosumer_storage):>2}  rede {len(c.network_storage):>2}")
