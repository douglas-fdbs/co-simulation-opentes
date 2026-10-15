"""Registro de transacoes e preco locacional (DLMP).

O DESENHO DE MERCADO
--------------------
Dois ambientes de contratacao (Melo, 2022, secao 6.1.1): um mercado futuro
bilateral, de preco fixo, em que o prosumidor so pode COMPRAR, e um mercado spot
de tempo real, em que pode comprar e vender. Este modulo registra a energia de
cada um, por no e por intervalo, com o preco de cada contrato.

Na formulacao de referencia, lambda e lido como variavel de controle, e nao
como valor financeiro (secao 6.1.4.4 da referencia). Aqui a conversao em preco e
feita, mas so tem significado monetario com a calibracao abaixo.

A UNIDADE DE LAMBDA
-------------------
Isso nao e detalhe: lambda **nao esta em unidade monetaria** nesta formulacao. No
otimo do concentrador, derivando `Ck (x - x_init)^2 + lambda x` em x:

    2 Ck (x - x_init) + lambda = 0   =>   lambda = 2 Ck (x_init - x)

ou seja, lambda tem unidade de `Ck` vezes potencia. Com o `Ck = 1`
adimensional, lambda e numericamente um desvio de potencia, nao um preco.

Para virar preco, o peso da funcao objetivo precisa ser calibrado em moeda:
`Ck` em EUR/(kW^2 . h). Dai lambda sai em EUR/(kW.h) e o DLMP e

    DLMP(t,l) = preco_spot(t) + lambda(t,l) / dt * 1000     [EUR/MWh]

`CK_EUR` expoe essa calibracao. Com o padrao (None) o DLMP e reportado com a
conversao aplicada sobre `Ck = 1`, e o resultado deve ser lido como SINAL, e nao
como dinheiro. As colunas de preco saem com o sufixo `_signal`.
"""

import csv
import os
from pathlib import Path

import numpy as np

from .config import DT_H, PERIODS

BILATERAL_PRICE = 38.0     # EUR/MWh, preco do contrato bilateral
# Calibracao do peso da funcao objetivo em moeda. None = Ck = 1 adimensional,
# caso em que o DLMP e sinal e nao preco.
CK_EUR = os.environ.get("MARKET_CK_EUR")
CK_EUR = float(CK_EUR) if CK_EUR else None


def dlmp(spot_price, lam, ck_eur=None):
    """Preco locacional por no e por intervalo, em EUR/MWh.

    Args:
        spot_price: array[96] com o preco spot do sistema.
        lam: {no: array[96]} multiplicador de Lagrange da negociacao.
        ck_eur: calibracao de Ck em EUR/(kW^2.h). None usa Ck = 1, adimensional.

    Returns:
        ({no: array[96]}, calibrado) com o preco por no e um sinalizador dizendo
        se a conversao tem significado monetario.
    """
    ck = ck_eur if ck_eur is not None else (CK_EUR if CK_EUR is not None else 1.0)
    calibrado = (ck_eur is not None) or (CK_EUR is not None)
    factor = ck / DT_H * 1000.0
    return ({n: np.asarray(spot_price, dtype=float) + np.asarray(v) * factor
             for n, v in lam.items()}, calibrado)


def transactions(contracts, spot_price, bilateral_price=BILATERAL_PRICE):
    """Transacoes de cada prosumidor nos dois mercados.

    Devolve uma lista de dicionarios, um por no e por mercado, com energia e
    custo. Convencao: energia positiva e compra, negativa e venda.
    """
    rows = []
    for node, decision in sorted(contracts.items()):
        bilateral_kwh = float(np.sum(decision["bilateral"]) * DT_H)
        spot_series = np.asarray(decision["spot"], dtype=float)
        spot_kwh = float(np.sum(spot_series) * DT_H)
        # O bilateral tem preco fixo; o spot e liquidado intervalo a intervalo.
        spot_cost = float(np.sum(spot_series * np.asarray(spot_price) * DT_H) / 1000.0)
        rows.append({"node": node, "market": "bilateral",
                     "energy_kwh": bilateral_kwh,
                     "price_eur_mwh": bilateral_price,
                     "cost_eur": bilateral_kwh * bilateral_price / 1000.0})
        rows.append({"node": node, "market": "spot",
                     "energy_kwh": spot_kwh,
                     "price_eur_mwh": float(np.mean(spot_price)),
                     "cost_eur": spot_cost})
    return rows


def flexibility(p_init, y, prices, calibrado=False):
    """Quanto de flexibilidade cada prosumidor entregou, e a que preco.

    A negociacao move a programacao do armazenamento de `p_init`, proposta pelo
    prosumidor, para `y`, aceita pelo DSO. A diferenca e o servico prestado. Ela
    e valorada ao preco locacional do proprio no: o sinal de preco e o que
    remunera quem cede flexibilidade.
    """
    u = "eur" if calibrado else "signal"
    rows = []
    for node in sorted(p_init):
        delta = np.asarray(y[node]) - np.asarray(p_init[node])
        price = np.asarray(prices[node])
        rows.append({
            **_no_fase(node),
            "energy_shifted_kwh": float(np.sum(np.abs(delta)) * DT_H),
            "net_shift_kwh": float(np.sum(delta) * DT_H),
            f"value_{u}": float(np.sum(-delta * price * DT_H) / 1000.0),
            f"dlmp_mean_{u}": float(np.mean(price)),
            f"dlmp_max_{u}": float(np.max(price)),
        })
    return rows


def _no_fase(key):
    """Colunas de identificacao de uma chave: so `node` por no; `node` e `fase`
    por porta ("671.A"). O modo por no mantem o formato de sempre."""
    if isinstance(key, str) and "." in key:
        no, fase = key.split(".")
        return {"node": int(no), "fase": fase}
    return {"node": key}


def write_csv(rows, path):
    """Grava um CSV limpo, sem linha de comentario.

    Uma primeira linha comecando por '#' quebra qualquer leitor padrao: o
    `csv.DictReader` a toma como cabecalho. A ressalva sobre a unidade do DLMP
    vai no NOME DA COLUNA (`dlmp_signal` contra `dlmp_eur_mwh`), que e
    auto-explicativo e continua legivel por maquina.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"gravado {path} ({len(rows)} linhas)")


def settle(result, out_dir, ck_eur=None):
    """Liquida a negociacao e grava os tres arquivos economicos."""
    out_dir = Path(out_dir)
    spot_price = result["price"]
    prices, calibrado = dlmp(spot_price, result["lambda"], ck_eur)

    if calibrado:
        print(f"[liquidacao] DLMP calibrado com Ck = {ck_eur or CK_EUR} "
              "EUR/(kW^2.h): as colunas estao em EUR.")
    else:
        print("[liquidacao] ATENCAO: com Ck = 1, lambda NAO esta em "
              "unidade monetaria. As colunas de preco saem como '_signal' e "
              "devem ser lidas como SINAL, nao como dinheiro. Calibre com "
              "MARKET_CK_EUR para obter preco.")

    write_csv(transactions(result["contracts"], spot_price),
              out_dir / "transactions.csv")

    # Serie por intervalo. O `transactions.csv` so tem o total do dia por no, e
    # com ele nao da para ver em que horario cada mercado e usado.
    serie = []
    for node, decision in sorted(result["contracts"].items()):
        bil = np.asarray(decision["bilateral"], dtype=float)
        spo = np.asarray(decision["spot"], dtype=float)
        for t in range(len(spo)):
            serie.append({"node": node, "t": t,
                          "bilateral_kw": float(bil[t]),
                          "spot_kw": float(spo[t]),
                          "spot_eur_mwh": float(spot_price[t]),
                          "bilateral_eur_mwh": BILATERAL_PRICE})
    write_csv(serie, out_dir / "market_series.csv")

    u = "eur_mwh" if calibrado else "signal"
    dlmp_rows = []
    for node, series in sorted(prices.items()):
        for t, value in enumerate(series):
            dlmp_rows.append({**_no_fase(node), "t": t,
                              f"dlmp_{u}": float(value),
                              "spot_eur_mwh": float(spot_price[t]),
                              f"adder_{u}": float(value - spot_price[t])})
    write_csv(dlmp_rows, out_dir / "dlmp.csv")

    write_csv(flexibility(result["p_init"], result["y"], prices, calibrado),
              out_dir / "flexibility.csv")

    _dump_figuras(result, out_dir)
    return {"dlmp": prices, "calibrado": calibrado}


def _dump_figuras(result, out_dir):
    """Grava, num npz, tudo o que as figuras da negociacao consomem.

    Sem isto cada figura teria de reexecutar a negociacao inteira. O arquivo tem
    as tres tensoes (base, proposta e negociada), a demanda liquida, as
    programacoes dos dois armazenamentos, o preco sombra e a trilha de cada
    rodada por chave.
    """
    case = result["case"]
    nos = list(result["nodes"])
    def matriz(d, chaves=None):
        chaves = nos if chaves is None else chaves
        return np.array([np.asarray(d.get(n, np.zeros(PERIODS)), dtype=float)
                         for n in chaves])
    pros = case.prosumer_keys
    rede = case.network_keys
    np.savez_compressed(
        Path(out_dir) / "figuras.npz",
        nodes=np.array(nos),
        prosumer_nodes=np.array(pros),
        network_nodes=np.array(rede),
        demanda=matriz(result["net_demand"]),
        v_base=np.asarray(result["v_base"]),
        v_prop=np.asarray(result["v_prop"]),
        v_final=np.asarray(result["v_final"]),
        y=matriz(result["y"], pros),
        q=matriz(result["q"], rede),
        lam=matriz(result["lambda"], pros),
        preco=np.asarray(result["price"]),
        trilha_ac=np.array([[r[n] for n in pros] for r in result["trilha_ac"]]),
        trilha_ad=np.array([[r[n] for n in pros] for r in result["trilha_ad"]]),
        # Modo por fase: as tensoes sao por (no, fase), uma coluna por linha de
        # `rows`, e as chaves do armazenamento sao portas "671.A".
        fase=np.array(case.fase),
        rows=np.array(case.rows),
    )
    print(f"gravado {Path(out_dir) / 'figuras.npz'}")
