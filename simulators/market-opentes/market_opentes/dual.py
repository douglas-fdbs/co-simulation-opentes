"""Decomposicao dual da fase de programacao da operacao, (6.24) e (6.30).

Roda o mecanismo inteiro de forma CENTRALIZADA, sem PADE e sem Mosaik. O
objetivo e separar o risco numerico (a decomposicao converge? em quantas
rodadas? quanto custa cada uma?) do risco de comunicacao, que so aparece na
co-simulacao. Se nao convergir aqui, nao vai convergir distribuido.

Sequencia da fase de programacao (Melo, 2022, cap. 6; numeracao de equacoes
de la):
  1. cada Agente Prosumidor programa seu armazenamento (uma vez);
  2. a cada rodada, os Agentes Concentradores e o Agente DSO reotimizam com o
     preco sombra corrente;
  3. o Agente Mercado atualiza o preco sombra pelo subgradiente (6.30) e
     testa a convergencia.

O criterio de parada padrao e relativo: o desacordo |x - y| de cada variavel de
armazenamento, em todo intervalo, abaixo de uma fracao (MARKET_EPS_REL) da
potencia maxima do proprio dispositivo. O criterio de (6.30),
|lambda_w - lambda_w+1| <= eps, fica disponivel com MARKET_CRITERIO=absoluto;
como esse incremento e alpha vezes o residuo em kW, ele afrouxa com alpha
pequeno e aperta com dispositivos grandes. Ver `criterio_parada`.

Uso:

    python -m market_opentes.dual --config CAMINHO/config.json
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from .config import (CRITERIO, DATA_DIR, EPS_REL, FASE, PERIODS,
                     STORAGE_TAN_PHI, V_MAX, V_MIN, V_TOL, load_case)
from .optimization import solve_concentrator, solve_dso, solve_prosumer
from .scenarios import build_scenarios
from .settlement import settle

# Passo do subgradiente, com o residuo de (6.30) em kW. O padrao, 0,6, foi o
# melhor numa varredura de passos; um passo pensado para residuo em W, como 5e-4,
# deixa lambda praticamente parado.
ALPHA = float(os.environ.get("MARKET_ALPHA", "0.6"))
# Precisao desejada em lambda, so no criterio absoluto. E um residuo primal
# escalado pelo passo, entao o mesmo numero significa coisas diferentes sob
# passos diferentes. O docker-compose.yaml fixa 1e-3 (MARKET_EPS).
EPS = float(os.environ.get("MARKET_EPS", "1e-4"))
MAX_ROUNDS = 30


def load_profiles():
    import csv

    def read(path):
        with open(path) as f:
            rows = list(csv.DictReader(f))
        return {int(k): np.array([float(r[k]) for r in rows]) for k in rows[0]}

    load = read(DATA_DIR / "load_kw.csv")
    pv = read(DATA_DIR / "pv_kw.csv")
    with open(DATA_DIR / "spot_price.csv") as f:
        price = np.array([float(r["price"]) for r in csv.DictReader(f)])
    net = {n: load[n] - pv.get(n, np.zeros(PERIODS)) for n in load}
    return net, price


def load_sensitivity():
    """Nos, V0(t) e a sensibilidade EFETIVA de tensao.

    A restricao (6.16) usa so dV/dP, supondo que o dispositivo despachado nao mexe em
    reativo. Um inversor com fator de potencia constante mexe: dQ = tan(phi) . dP.
    Como a mesma variavel de decisao move as duas potencias, o efeito cabe numa
    unica matriz,

        S_efetiva = dV/dP + tan(phi) . dV/dQ

    e todo o resto do modelo continua igual. Com `MARKET_STORAGE_PF=none`, que e
    o padrao, tan(phi) e zero e a matriz e so dV/dP.

    Arquivo de sensibilidade sem `s_q` (dV/dQ) tem o termo ignorado, com aviso,
    em vez de quebrar.

    Com MARKET_FASE=1 a matriz e a `sensitivity_fase.npz`: linhas por (no, fase)
    e colunas pelas portas. O primeiro valor devolvido passa a ser a lista de
    linhas, e nao a de nos.
    """
    if FASE:
        data = np.load(DATA_DIR / "sensitivity_fase.npz")
        rows = [(int(n), int(k)) for n, k in data["rows"]]
        s = data["s"]
        if STORAGE_TAN_PHI and not os.environ.get("MARKET_IGNORE_DQ"):
            s = s + STORAGE_TAN_PHI * data["s_q"]
        return rows, data["v0"], s
    data = np.load(DATA_DIR / "sensitivity_day.npz")
    s = data["s"]
    if os.environ.get("MARKET_IGNORE_DQ"):
        # Chave de EXPERIMENTO, nao de operacao: o dispositivo continua injetando
        # reativo na rede, mas o modelo do DSO finge que nao. E o unico jeito de
        # medir o custo da hipotese dQ = 0 sobre um sistema fisico fixo; comparar
        # "sem reativo" com "com reativo" compararia dois sistemas diferentes.
        print("[sensibilidade] EXPERIMENTO: modelo ignorando dV/dQ enquanto o "
              "dispositivo injeta reativo.", flush=True)
        return [int(x) for x in data["nodes"]], data["v0"], s
    if STORAGE_TAN_PHI:
        if "s_q" in data.files:
            s = s + STORAGE_TAN_PHI * data["s_q"]
        else:
            print("[sensibilidade] AVISO: MARKET_STORAGE_PF pedido, mas o "
                  "sensitivity_day.npz nao tem dV/dQ. Regere com "
                  "`sensitivity.py day`. Seguindo com dQ = 0.")
    return [int(x) for x in data["nodes"]], data["v0"], s


def load_taps():
    """(nomes dos reguladores, derivacoes por intervalo) do ponto da previsao.

    Vem da mesma matriz de sensibilidade em uso, que guarda as derivacoes com que
    cada ponto de operacao foi resolvido. Matriz gerada antes desta chave nao
    as tem: devolve listas vazias, e quem usa decide o que fazer.
    """
    data = np.load(DATA_DIR / ("sensitivity_fase.npz" if FASE else "sensitivity_day.npz"))
    if "taps" not in data.files or "reguladores" not in data.files:
        return [], np.zeros((0, 0))
    return [str(n) for n in data["reguladores"]], np.asarray(data["taps"])


def voltage_of(case, v0, s, p_prosumer, p_network):
    """Tensao prevista pelo modelo linear para uma programacao.

    Uma coluna por linha de `v0`: os nos, ou os pares (no, fase) no modo por fase.
    As chaves dos dicionarios sao as do caso, e `case.columns` diz em que coluna
    da matriz cada uma injeta.
    """
    v = np.array(v0, dtype=float)
    for t in range(PERIODS):
        dp = np.zeros(s.shape[2])
        for d in (p_prosumer, p_network):
            for n, series in d.items():
                for c, w in case.columns(n):
                    dp[c] -= w * series[t]  # carregar consome: injecao negativa
        v[t] = v[t] + s[t] @ dp
    return v


def violations(v):
    return int((v < V_MIN - V_TOL).sum()), int((v > V_MAX + V_TOL).sum())


def criterio_parada(case, keys, residual, d_lam, eps=EPS):
    """A rodada fecha a negociacao? Devolve (parou, medida, descricao).

    `residual` e `d_lam` sao arrays (chaves, periodos) na ordem de `keys`.

    No criterio relativo, a medida e o maior |x - y| / Pmax entre todas as
    variaveis e todos os intervalos: o desacordo, em fracao da potencia do
    proprio dispositivo. No absoluto, e o maior |dlambda|.
    """
    if CRITERIO == "absoluto":
        medida = float(np.abs(d_lam).max())
        return medida <= eps, medida, f"|dlambda| = {medida:.2e} <= {eps:.0e}"
    medida = float((np.abs(residual) / case.potencia_ref(keys)).max())
    return (medida <= EPS_REL, medida,
            f"|x-y|/Pmax = {medida:.2e} <= {EPS_REL:.0e}")


def step_size(alpha, round_, rule):
    """Passo do subgradiente na rodada `round_`.

    `constant` e o passo fixo de (6.30). `diminishing` e alpha / w, a regra
    classica de subgradiente com passo decrescente, para comparacao.

    A diferenca importa: com passo constante o subgradiente nao converge ao
    otimo, converge a uma vizinhanca cujo raio cresce com o passo, o que aparece
    como um ciclo limite no residuo primal.

    ATENCAO ao criterio de parada: |dlambda| <= eps e o passo vezes o residuo.
    Com passo decrescente o teste passa a poder disparar pela queda do PASSO e
    nao pela queda do residuo. Compare sempre pelo residuo primal.
    """
    if rule == "constant":
        return alpha
    if rule == "diminishing":
        return alpha / round_
    raise ValueError(f"regra de passo desconhecida: {rule}")


def run(config_json, alpha=ALPHA, eps=EPS, max_rounds=MAX_ROUNDS, n_scenarios=1,
        step_rule="constant", verbose=True):
    case = load_case(config_json)
    net_demand, price = load_profiles()
    nodes, v0, s = load_sensitivity()
    if nodes != case.rows:
        raise ValueError("ordem das linhas da sensibilidade difere do caso")
    pros, rede = case.prosumer_keys, case.network_keys

    # ---- ciclo 1: cada prosumidor programa seu armazenamento --------------
    t0 = time.time()
    p_init = {}
    contracts = {}
    # TODOS os prosumidores programam e contratam; so os que tem bateria entram
    # na negociacao de lambda, porque so eles tem variavel a acoplar. Os demais
    # continuam no mercado bilateral.
    for node in case.prosumer_nodes:
        if node not in net_demand:
            continue
        scenarios = _scenarios(node, net_demand[node], price, n_scenarios)
        decision = solve_prosumer(scenarios, case.prosumer_storage.get(node))
        contracts[node] = decision
        if node in case.prosumer_storage:
            p_init[node] = decision["storage"]
    t_pros = time.time() - t0
    # A proposta do prosumidor e uma serie por dispositivo: o modelo dele e
    # economico e nao enxerga fase. Por fase, ela e repartida igualmente entre as
    # portas do dispositivo, e o concentrador redistribui a partir dai.
    p_init = {k: p_init[case.node_of(k)] / case.mult(k) for k in pros}

    q_init = {n: np.zeros(PERIODS) for n in rede}
    lam = {n: np.zeros(PERIODS) for n in pros}
    # Passo do subgradiente por chave. Por fase, multiplicado por |F|: o residuo de
    # cada porta e 1/|F| do residuo do dispositivo, e sem isto a iteracao por
    # fase andaria mais devagar que a por no numa rede equilibrada.
    passo_k = np.array([float(case.mult(k)) for k in pros])[:, None] if case.por_porta else 1.0

    v_base = voltage_of(case, v0, s, {n: np.zeros(PERIODS) for n in p_init}, q_init)
    v_prop = voltage_of(case, v0, s, p_init, q_init)
    if verbose:
        print(f"{len(contracts)} prosumidores programados, {len(p_init)} com "
              f"armazenamento, em {t_pros:.1f} s "
              f"({len(scenarios)} cenario(s) por prosumidor)")
        print(f"  carga base           : V {v_base.min():.4f} a {v_base.max():.4f} pu, "
              f"violacoes {violations(v_base)}")
        print(f"  + program. proposta  : V {v_prop.min():.4f} a {v_prop.max():.4f} pu, "
              f"violacoes {violations(v_prop)}")
        print(f"\ncriterio de parada: {CRITERIO}")
        print(f"\n{'rodada':>6} {'|dlambda|max':>13} {'|x-y| max':>11} {'|x-y|/Pmax':>11} "
              f"{'lambda max':>11} {'V min':>8} {'V max':>8} {'viol':>10} {'s':>6}")

    history = []
    # Programacao de cada rodada, por chave: e o que as figuras da negociacao
    # rodada a rodada mostram, e o historico agregado nao guarda.
    trilha_ac, trilha_ad = [], []
    for round_ in range(1, max_rounds + 1):
        t_round = time.time()

        # ---- ciclo 4a: concentradores ------------------------------------
        x = {}
        for c in case.concentrators:
            ks = case.chaves(c.prosumer_storage)
            x.update(solve_concentrator(
                ks, {n: p_init[n] for n in ks}, {n: lam[n] for n in ks},
                case.prosumer_storage, node_of=case.node_of, mult=case.mult))

        # ---- ciclo 4b: DSO ------------------------------------------------
        y, q = solve_dso(case, net_demand, p_init, q_init, lam, v0, s)

        # ---- ciclo 4c: agente de mercado atualiza o preco sombra ----------
        residual = np.array([x[n] - y[n] for n in pros])
        d_lam = step_size(alpha, round_, step_rule) * residual
        if case.por_porta:
            d_lam = d_lam * passo_k
        for i, n in enumerate(pros):
            lam[n] = lam[n] + d_lam[i]

        parou, _, motivo = criterio_parada(case, pros, residual, d_lam, eps)
        trilha_ac.append({n: np.array(x[n]) for n in pros})
        trilha_ad.append({n: np.array(y[n]) for n in pros})

        v_now = voltage_of(case, v0, s, y, q)
        dt = time.time() - t_round
        lam_max = max(np.abs(v).max() for v in lam.values())
        history.append({
            "round": round_,
            "d_lambda_max": float(np.abs(d_lam).max()),
            "residual_max": float(np.abs(residual).max()),
            "residual_rms": float(np.sqrt((residual ** 2).mean())),
            "residual_rel_max": float((np.abs(residual)
                                       / case.potencia_ref(pros)).max()),
            "lambda_max": float(lam_max),
            "v_min": float(v_now.min()),
            "v_max": float(v_now.max()),
            "violations": violations(v_now),
            "seconds": dt,
        })
        if verbose:
            h = history[-1]
            print(f"{round_:>6} {h['d_lambda_max']:>13.3e} {h['residual_max']:>11.4f} "
                  f"{h['residual_rel_max']:>11.2e} {h['lambda_max']:>11.3e} "
                  f"{h['v_min']:>8.4f} {h['v_max']:>8.4f} "
                  f"{str(h['violations']):>10} {dt:>6.1f}")

        if parou:
            if verbose:
                print(f"\nconvergiu em {round_} rodadas ({motivo})")
            break
    else:
        if verbose:
            print(f"\nNAO convergiu em {max_rounds} rodadas")

    return {"case": case, "p_init": p_init, "contracts": contracts,
            "x": x, "y": y, "q": q, "lambda": lam, "history": history,
            "price": price, "net_demand": net_demand,
            "v_base": v_base, "v_prop": v_prop, "v_final": v_now,
            "trilha_ac": trilha_ac, "trilha_ad": trilha_ad,
            "nodes": case.all_nodes}


def _scenarios(node, demand, price, n):
    """Cenarios de demanda e preco para o modelo do prosumidor.

    n = 1 e o caso deterministico (previsao unica, probabilidade 1). n > 1 usa a
    amostragem e a reducao de Kantorovich de `scenarios.py`; com n = 3 saem os
    9 cenarios de preco-potencia.
    """
    return build_scenarios(node, n_reduced=n, deterministic_demand=demand,
                           deterministic_price=price)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True,
                    help="config.json do caso (alocacao do armazenamento)")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    ap.add_argument("--eps", type=float, default=EPS)
    ap.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    ap.add_argument("--scenarios", type=int, default=1)
    ap.add_argument("--step-rule", default="constant",
                    choices=["constant", "diminishing"], dest="step_rule")
    ap.add_argument("--out", default=None, help="grava o historico em JSON")
    ap.add_argument("--settle-dir", default=None, dest="settle_dir",
                    help="grava transacoes, DLMP e flexibilidade neste diretorio")
    ap.add_argument("--ck-eur", type=float, default=None, dest="ck_eur",
                    help="calibracao de Ck em EUR/(kW^2.h); sem isso o DLMP e sinal")
    args = ap.parse_args()

    result = run(args.config, alpha=args.alpha, eps=args.eps,
                 max_rounds=args.max_rounds, n_scenarios=args.scenarios,
                 step_rule=args.step_rule)

    if args.out:
        Path(args.out).write_text(json.dumps(result["history"], indent=1))
        print(f"historico gravado em {args.out}")

    if args.settle_dir:
        settle(result, args.settle_dir, args.ck_eur)


if __name__ == "__main__":
    main()
