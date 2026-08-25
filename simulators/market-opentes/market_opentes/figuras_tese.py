"""Reprodução fiel das Figuras 42 a 55 da tese de referência.

Cada figura sai com o MESMO formato da original: os mesmos eixos, os mesmos nós
destacados, o mesmo tipo de gráfico (superfície ou barra em 3D onde a tese usa
3D) e o mesmo título interno. O arquivo recebe o nome da legenda da figura, e não
um `figNN_*`, para que a correspondência seja lida sem tabela auxiliar.

O objetivo aqui é comparar FORMA, não número: se a nossa figura tem o mesmo
formato da dela, a diferença que sobrar é de resultado e pode ser discutida. Com
formatos diferentes não dá para dizer nem isso.

Entradas:
  data/figuras.npz              o que a negociação produziu (settlement.py)
  data/tisch_links.csv          levantamento de enlaces do 6TiSCH (Figura 42)
  output/market/result_*.csv    a fase de operação (Figuras 54 e 55)

    python -m market_opentes.figuras_tese --out-dir data/figuras_tese
"""

import argparse
import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .config import DT_H, PERIODS  # noqa: E402

# A tese usa o mapa `jet` em todas as figuras 3D, com barra de cor à direita.
CMAPA = "jet"
PER_THRESHOLD = 0.5

# Legenda de cada figura, que vira o nome do arquivo. Mantida literal para que a
# correspondência com o documento seja direta.
LEGENDAS = {
    42: "PER versus distancia usando o modelo de propagacao de Pister-Hack",
    43: "Niveis de tensao na rede para cada um dos nos",
    44: "Demanda liquida em kW para cada um dos nos e para os nos 17 a 21",
    45: "Preco adicional encontrado no processo de programacao da operacao",
    46: "Programacao dos dispositivos de armazenamento de rede definida pelo AD",
    47: "Niveis de tensao na rede apos insercao dos dispositivos de armazenamento",
    48: "Demanda liquida em kW apos a insercao dos dispositivos de armazenamento",
    49: "Niveis de tensoes em pu com e sem armazenamento ao longo dos nos da rede",
    50: "Graficos de composicao de demandas em kW e de tensoes em pu para o no 74",
    51: "Programacoes de demanda em kW ao longo do tempo para o no 74",
    52: "Programacoes de demanda em kW ao longo do tempo para o no 25",
    53: "Programacoes de demanda em kW para os nos 74 e 25 ao longo da negociacao",
    54: "Niveis de tensao na rede para cada um dos nos na fase de operacao",
    55: "Demanda liquida em kW obtida no processo de co-simulacao para a fase de operacao",
    56: "Valores de energia adquiridos no mercado futuro bilateral e no mercado SPOT "
        "para quatro nos da rede eletrica 15 24 32 e 52",
    57: "Valores de energia no mercado SPOT de tempo real e no mercado de futuro bilateral",
    58: "Graficos representando cada uma das mensagens trocadas pelos agentes durante a co-simulacao",
    59: "Graficos de analise das mensagens trocadas pelos agentes durante a co-simulacao",
}


def arquivo(out_dir, n):
    return Path(out_dir) / (LEGENDAS[n].lower().replace(" ", "_") + ".png")


def hhmm(t):
    m = int(round(t * DT_H * 60))
    return f"{m // 60:02d}:{m % 60:02d}"


# Angulo de camera das figuras 3D. No quadro (a), que mostra a rede inteira, a
# tese poe o eixo dos nos a esquerda quase de perfil e o do tempo raso ao longo
# da base, o que corresponde a azim=-28. Os quadros seguintes, que destacam
# poucos nos ou poucas janelas, ficam melhores no angulo mais aberto: com o eixo
# dos nos de perfil, um recorte de cinco nos vira uma parede estreita.
ELEV, AZIM, AZIM_SEC = 28, -28, -58


def _eixo_tempo(ax, t0, t1, passo, eixo="y"):
    ticks = list(range(t0, t1 + 1, passo))
    getattr(ax, f"set_{eixo}ticks")(ticks)
    getattr(ax, f"set_{eixo}ticklabels")([hhmm(t) for t in ticks], fontsize=6)


# ---------------------------------------------------------------------------
# Superfície e barra em 3D, que é o formato dominante da tese
# ---------------------------------------------------------------------------

def _moldura(ax, rotulo_z, titulo, t0, t1, passo_tempo, azim=AZIM):
    ax.set_xlabel("Nós", fontsize=7, labelpad=-2)
    ax.set_ylabel("Tempo", fontsize=7, labelpad=2)
    ax.set_zlabel(rotulo_z, fontsize=7, labelpad=2, rotation=90)
    ax.tick_params(labelsize=6)
    _eixo_tempo(ax, t0, t1 - 1, passo_tempo or max(1, (t1 - t0) // 4))
    ax.set_title(titulo, fontsize=8)
    ax.view_init(elev=ELEV, azim=azim)


def hastes(ax, nos, t0, t1, Z, rotulo_z, titulo, passo_tempo=None,
           azim=AZIM):
    """Uma haste vertical por par (nó, intervalo), do zero até o valor.

    É o formato das Figuras 44, 48 e 55 da tese, e não uma superfície. A
    diferença não é estética: a superfície INTERPOLA entre nós vizinhos em
    número, que não são vizinhos elétricos, e entre intervalos de 15 minutos,
    onde não há dado. O que resulta é uma malha contínua que sugere valores que
    não foram calculados. A haste mostra só o que existe, e por isso o gráfico
    também fica menos poluído.
    """
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    sub = Z[:, t0:t1]
    tempos = np.arange(t0, t1)
    N, T = np.meshgrid(np.asarray(nos, dtype=float), tempos, indexing="ij")
    n, t, z = N.ravel(), T.ravel(), sub.ravel()
    norm = plt.Normalize(float(sub.min()), float(sub.max()))
    mapa = matplotlib.colormaps[CMAPA]
    segmentos = np.stack([np.column_stack([n, t, np.zeros_like(z)]),
                          np.column_stack([n, t, z])], axis=1)
    ax.add_collection3d(Line3DCollection(segmentos, colors=mapa(norm(z)),
                                         linewidths=0.9))
    ax.set_xlim(min(nos) - 0.5, max(nos) + 0.5)
    ax.set_ylim(t0, t1 - 1)
    ax.set_zlim(min(0.0, float(sub.min())), float(sub.max()))
    if len(nos) <= 10:
        ax.set_xticks(list(nos))
    _moldura(ax, rotulo_z, titulo, t0, t1, passo_tempo, azim)
    return plt.cm.ScalarMappable(norm=norm, cmap=CMAPA)


def pontos(ax, nos, t0, t1, Z, rotulo_z, titulo, passo_tempo=None,
           azim=AZIM):
    """Um marcador por par (nó, intervalo).

    É o formato das Figuras 43, 47 e 54 da tese. Cada intervalo de 15 minutos é
    uma fileira de pontos separada, sem nada desenhado entre elas, que é o que
    deixa visível quantos pontos existem de fato.
    """
    sub = Z[:, t0:t1]
    tempos = np.arange(t0, t1)
    N, T = np.meshgrid(np.asarray(nos, dtype=float), tempos, indexing="ij")
    norm = plt.Normalize(float(sub.min()), float(sub.max()))
    disp = ax.scatter(N.ravel(), T.ravel(), sub.ravel(), c=sub.ravel(),
                      cmap=CMAPA, norm=norm, s=5.0, linewidths=0, depthshade=False)
    ax.set_xlim(min(nos) - 0.5, max(nos) + 0.5)
    ax.set_ylim(t0, t1 - 1)
    if len(nos) <= 10:
        ax.set_xticks(list(nos))
    _moldura(ax, rotulo_z, titulo, t0, t1, passo_tempo, azim)
    return disp


def barras3d(ax, nos, Z, rotulo_z, titulo, corte=1e-9, so_positivo=False):
    """Barras verticais valor(nó, tempo). Formato das Figuras 45 e 46, em que o
    dado é esparso e uma superfície esconderia os picos.

    `so_positivo` reproduz a convenção da Figura 46, que mostra a potência de
    SAÍDA do armazenamento de rede ("valores de potência de saída dos
    dispositivos", subseção 6.2.2) e portanto omite os intervalos de carga.
    """
    ii, jj = np.nonzero((Z > corte) if so_positivo else (np.abs(Z) > corte))
    if len(ii) == 0:
        ax.text2D(0.5, 0.5, "sem valores não nulos", ha="center",
                  transform=ax.transAxes)
        return None
    v = Z[ii, jj]
    norm = plt.Normalize(v.min(), v.max())
    cores = matplotlib.colormaps[CMAPA](norm(v))
    ax.bar3d(np.asarray(nos, dtype=float)[ii], jj.astype(float),
             np.zeros_like(v), 0.8, 0.8, v, color=cores, shade=True)
    ax.set_xlabel("Nós", fontsize=7, labelpad=-2)
    ax.set_ylabel("Tempo", fontsize=7, labelpad=2)
    ax.set_zlabel(rotulo_z, fontsize=7, labelpad=2, rotation=90)
    ax.tick_params(labelsize=6)
    _eixo_tempo(ax, 0, PERIODS - 1, 24)
    ax.set_title(titulo, fontsize=8)
    ax.view_init(elev=ELEV, azim=AZIM)
    return plt.cm.ScalarMappable(norm=norm, cmap=CMAPA)


def _barra_cor(fig, ax, mapeavel):
    if mapeavel is not None:
        cb = fig.colorbar(mapeavel, ax=ax, shrink=0.55, pad=0.14)
        cb.ax.tick_params(labelsize=6)


# ---------------------------------------------------------------------------
# Figura 42
# ---------------------------------------------------------------------------

def figura_42(links_csv, out, max_distance=1000.0):
    """PER por distância.

    A tese desenha uma LINHA ligando os pares ordenados por distância, e não uma
    nuvem de pontos. Como o PER de dois pares vizinhos em distância salta entre
    valores muito distintos, por causa do desvio de 0 a 40 dB sorteado por enlace
    no Pister-Hack, a linha vira um traço quase vertical em cada par. É essa a
    aparência da figura dela, e com pontos o gráfico fica ilegível.
    """
    d, per = [], []
    for r in csv.DictReader(open(links_csv)):
        if float(r["distance_m"]) <= 0:
            continue
        d.append(float(r["distance_m"])); per.append(float(r["per"]))
    d, per = np.array(d), np.array(per)
    m = d <= max_distance
    d, per = d[m], per[m]
    ordem = np.argsort(d)
    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    ax.plot(d[ordem], per[ordem], color="#1f77b4", linewidth=0.8)
    ax.set_xlabel("distance in meters", fontsize=9)
    ax.set_ylabel("per", fontsize=9)
    # Margem nos dois eixos. Com os limites colados em 0 e em 1,0 os traços que
    # chegam ao topo e os que ficam no piso encostam na moldura e somem: o
    # gráfico é feito de traços verticais, e é justamente a ponta deles que se
    # quer ler.
    ax.set_xlim(-0.015 * max_distance, 1.015 * max_distance)
    ax.set_ylim(-0.05, 1.10)
    ax.grid(True, color="0.8", linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}  ({len(d)} pares ate {max_distance:.0f} m)")


# ---------------------------------------------------------------------------
# Figuras 43, 47 e 54: tensão em 3D
# ---------------------------------------------------------------------------

def _figura_tensao(nos, V, janelas, out, titulo="Níveis de Tensão ao longo da rede elétrica"):
    n = len(janelas)
    fig = plt.figure(figsize=(5.6 * min(n, 2), 4.6 * ((n + 1) // 2)))
    for k, (t0, t1, passo) in enumerate(janelas, start=1):
        ax = fig.add_subplot((n + 1) // 2, min(n, 2), k, projection="3d")
        sup = pontos(ax, nos, t0, t1, V.T, "Tensão em pu", titulo, passo,
                     azim=AZIM if k == 1 else AZIM_SEC)
        _barra_cor(fig, ax, sup)
        ax.text2D(0.5, -0.06, f"({chr(96 + k)})", transform=ax.transAxes,
                  ha="center", fontsize=9)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    print(f"gravado {out.name}")


def _figura_demanda(nos, D, quadros, out):
    titulo = "Valores de Potência Líquida ao longo da rede elétrica"
    fig = plt.figure(figsize=(5.6 * len(quadros), 4.6))
    for k, (sel, t0, t1, passo) in enumerate(quadros, start=1):
        ax = fig.add_subplot(1, len(quadros), k, projection="3d")
        idx = [i for i, n in enumerate(nos) if n in sel] if sel else list(range(len(nos)))
        sup = hastes(ax, [nos[i] for i in idx], t0, t1, D[idx],
                     "Demanda Líquida em kW", titulo, passo,
                     azim=AZIM if k == 1 else AZIM_SEC)
        _barra_cor(fig, ax, sup)
        ax.text2D(0.5, -0.06, f"({chr(96 + k)})", transform=ax.transAxes,
                  ha="center", fontsize=9)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    print(f"gravado {out.name}")


# ---------------------------------------------------------------------------
# Figura 49: barras por nó, em dois horários
# ---------------------------------------------------------------------------

def figura_49(nos, v_sem, v_com, out, horarios=(71, 40)):
    fig, axes = plt.subplots(2, 1, figsize=(9.0, 5.6))
    for ax, t in zip(axes, horarios):
        ax.bar(nos, v_sem[t], width=0.85, color="#1f77b4", label="Sem armazenamento")
        ax.bar(nos, v_com[t], width=0.55, color="#ff7f0e", label="Com armazenamento")
        lo = min(v_sem[t].min(), v_com[t].min())
        hi = max(v_sem[t].max(), v_com[t].max())
        ax.set_ylim(lo - 0.005, hi + 0.005)
        ax.set_title(f"Tensões no sistema para as {hhmm(t)}h", fontsize=11)
        ax.set_xlabel("Nós", fontsize=9); ax.set_ylabel("Tensão em pu", fontsize=9)
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(True, color="0.85", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")


# ---------------------------------------------------------------------------
# Figura 50: composição do nó 74
# ---------------------------------------------------------------------------

def figura_50(no, carga, armaz, v_sem, v_com, out):
    t = np.arange(PERIODS)
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 6.0))
    ax = axes[0]
    ax.bar(t, carga, width=0.85, color="#1f77b4", label="Demanda de carga + geração")
    # A parcela do armazenamento EMPILHA sobre a de carga, para cima ou para
    # baixo: e o que faz o topo da barra coincidir com a linha da demanda
    # liquida, como na figura da tese.
    ax.bar(t, armaz, width=0.85, bottom=carga,
           color="#ff7f0e", label="Demanda de armazenamento")
    ax.plot(t, carga + armaz, color="black", linewidth=1.2, label="Demanda Líquida")
    ax.set_title(f"Demanda líquida no nó {no} ao longo do tempo", fontsize=11)
    ax.set_ylabel("Demanda Líquida em kW", fontsize=9)
    ax.legend(fontsize=7, ncol=3, loc="lower left")

    ax = axes[1]
    ax.bar(t, v_sem, width=0.85, color="#1f77b4", label="Sem armazenamento")
    ax.bar(t, v_com, width=0.55, color="#ff7f0e", label="Com armazenamento")
    ax.plot(t, v_sem, color="black", linewidth=1.0, label="tensão res. sem armaz.")
    ax.plot(t, v_com, color="#d81f1f", linewidth=1.0, label="tensão res. com armaz.")
    ax.set_ylim(min(v_sem.min(), v_com.min()) - 0.005,
                max(v_sem.max(), v_com.max()) + 0.005)
    ax.set_title(f"Tensões no nó {no} ao longo do tempo", fontsize=11)
    ax.set_ylabel("Tensão em pu", fontsize=9); ax.set_xlabel("Tempo", fontsize=9)
    ax.legend(fontsize=7, ncol=2, loc="lower left")
    for a in axes:
        a.set_xticks(range(0, PERIODS + 1, 8))
        a.set_xticklabels([hhmm(x) for x in range(0, PERIODS + 1, 8)],
                          rotation=45, fontsize=7)
        a.grid(True, color="0.85", linewidth=0.6); a.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")


# ---------------------------------------------------------------------------
# Figuras 51 e 52: a programação de um nó, rodada a rodada
# ---------------------------------------------------------------------------

def figura_iteracoes(no, base, trilha_ad, trilha_ac, out, n_iter=8):
    t = np.arange(PERIODS)
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 5.6), sharex=True)
    for ax, trilha, quem in ((axes[0], trilha_ad, "AD"), (axes[1], trilha_ac, "AC")):
        for k in range(min(n_iter, len(trilha))):
            ax.step(t, base + trilha[k], where="post", linewidth=1.0,
                    label=f"iter.: {k + 1}")
        ax.set_title(f"Demanda Liq. no nó {no} ao longo do tempo vista pelo {quem}",
                     fontsize=11)
        ax.set_ylabel("Dem. Liq. em kW", fontsize=9)
        ax.legend(fontsize=6, ncol=2, loc="lower left")
        ax.grid(True, color="0.85", linewidth=0.6); ax.set_axisbelow(True)
    axes[1].set_xticks(range(0, PERIODS + 1, 8))
    axes[1].set_xticklabels([hhmm(x) for x in range(0, PERIODS + 1, 8)],
                            rotation=45, fontsize=7)
    axes[1].set_xlabel("Tempo", fontsize=9)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")


# ---------------------------------------------------------------------------
# Figura 53: convergência num instante
# ---------------------------------------------------------------------------

def figura_53(casos, out):
    fig, axes = plt.subplots(len(casos), 1, figsize=(8.6, 2.9 * len(casos)))
    axes = np.atleast_1d(axes)
    for ax, (no, t, ac, ad) in zip(axes, casos):
        it = np.arange(len(ac))
        ax.plot(it, ac, "-o", color="#1f77b4", markersize=4,
                label="valor programado pelo AC")
        ax.plot(it, ad, "-o", color="#ff7f0e", markersize=4,
                label="valor programado pelo AD")
        ax.set_title(f"Demanda programada em kW vs. Iterações de negociação "
                     f"no nó {no} as {hhmm(t)}h", fontsize=10)
        ax.set_xlabel("número de iterações", fontsize=9)
        ax.set_ylabel("Dem. prog. em kW", fontsize=9)
        ax.legend(fontsize=8); ax.grid(True, color="0.85", linewidth=0.6)
        ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")



# ---------------------------------------------------------------------------
# Figuras 56 e 57: os dois mercados
# ---------------------------------------------------------------------------

def figura_56(series_csv, out, nodes=(15, 24, 32, 52)):
    """Energia negociada em cada mercado, por intervalo, para os quatro nós que
    a tese destaca. Positivo é compra, negativo é venda; o bilateral só compra."""
    import pandas as pd
    df = pd.read_csv(series_csv)
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 6.4), sharex=True)
    for ax, no in zip(axes.ravel(), nodes):
        sub = df[df["node"] == no].sort_values("t")
        if sub.empty:
            ax.text(0.5, 0.5, f"no {no} sem transacoes", ha="center",
                    transform=ax.transAxes)
            continue
        ax.bar(sub["t"], sub["bilateral_kw"], width=0.9, color="#1f77b4",
               label="bilateral-kw")
        ax.bar(sub["t"], sub["spot_kw"], width=0.9, color="#ff7f0e",
               label="spot-kw")
        ax.set_title(f"Val. neg. em kW para o no {no} em 24h", fontsize=10)
        ax.set_ylabel("Val. neg. em kW", fontsize=9)
        ax.set_xticks(range(0, PERIODS + 1, 12))
        ax.set_xticklabels([hhmm(x) for x in range(0, PERIODS + 1, 12)],
                           rotation=45, fontsize=7)
        ax.legend(frameon=True, fontsize=7, loc="lower left")
        ax.grid(True, color="0.85", linewidth=0.6); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")


def figura_57(series_csv, out):
    """Preço spot ao longo do dia contra o preço fixo do mercado bilateral."""
    import pandas as pd
    df = pd.read_csv(series_csv).drop_duplicates("t").sort_values("t")
    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    ax.bar(df["t"], df["spot_eur_mwh"], width=0.9, color="#2f7d32",
           label="preco no mercado SPOT")
    ax.axhline(float(df["bilateral_eur_mwh"].iloc[0]), color="#d81f1f",
               linewidth=1.4, label="preco no mercado BILATERAL")
    ax.set_title("Valores de energia negociados nos mercados SPOT e BILATERAL",
                 fontsize=11)
    ax.set_xlabel("Tempo", fontsize=9); ax.set_ylabel("Precos em u.m/Mwh", fontsize=9)
    ax.set_xticks(range(0, PERIODS + 1, 8))
    ax.set_xticklabels([hhmm(x) for x in range(0, PERIODS + 1, 8)],
                       rotation=45, fontsize=7)
    ax.legend(frameon=True, fontsize=8, loc="lower left")
    ax.grid(True, color="0.85", linewidth=0.6); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")


# ---------------------------------------------------------------------------
# Leitura da fase de operação
# ---------------------------------------------------------------------------

def _operacao(result_csv):
    """Tensão e demanda líquida por nó, da co-simulação da operação."""
    linhas = list(csv.reader(open(result_csv)))
    cab, dados = linhas[0], [l for l in linhas[1:] if l]
    v, p = {}, {}
    for i, h in enumerate(cab):
        m = re.search(r"Bus-n(\d+)-V1_pu", h)
        if m:
            v[int(m.group(1))] = np.array([float(l[i]) for l in dados])
        m = re.search(r"node_(\d+)-P_kw", h)
        if m:
            p[int(m.group(1))] = np.array([float(l[i]) for l in dados])
    return v, p


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--npz", default="data/figuras.npz")
    ap.add_argument("--links", default="data/tisch_links.csv")
    ap.add_argument("--operacao", default="/app/output/market/result_negociado.csv")
    ap.add_argument("--series", default="data/market_series.csv")
    ap.add_argument("--trace", default="data/msg_trace.csv")
    ap.add_argument("--run-json", default="data/run/run.json", dest="run_json",
                    help="procedencia da execucao, para avisar se o traco esta "
                         "no modo de tamanho errado para as Figuras 58 e 59")
    ap.add_argument("--out-dir", default="data/figuras_tese")
    a = ap.parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)

    d = np.load(a.npz)
    nos = [int(x) for x in d["nodes"]]
    pros = [int(x) for x in d["prosumer_nodes"]]
    rede = [int(x) for x in d["network_nodes"]]
    v_base, v_final = d["v_base"], d["v_final"]         # (96, n_nos)
    demanda, y, q, lam = d["demanda"], d["y"], d["q"], d["lam"]

    # janelas que a tese destaca
    NOITE = (71, 78, 1)          # 17:45 a 19:15
    MANHA = (40, 45, 1)          # 10:00 a 11:00
    DIA = (0, PERIODS, 24)
    # Nos que a tese destaca nos quadros (b) das Figuras 44, 48 e 55. A legenda
    # dela diz "nos 9 a 12", mas o eixo das figuras mostra de 16,5 a 21,5, ou
    # seja os nos 17 a 21. Seguimos o eixo, que e o que esta desenhado.
    DESTAQUE = {17, 18, 19, 20, 21}

    if Path(a.links).exists():
        figura_42(a.links, arquivo(out, 42))
    _figura_tensao(nos, v_base, [DIA, NOITE], arquivo(out, 43))
    _figura_demanda(nos, demanda, [(None, 0, PERIODS, 24),
                                   (DESTAQUE, 0, PERIODS, 24)],
                    arquivo(out, 44))
    fig = plt.figure(figsize=(6.4, 5.0)); ax = fig.add_subplot(111, projection="3d")
    # A tese exclui os nos de shadow price nulo (Tabela 8). O nosso lambda nao
    # zera exatamente em lugar nenhum, entao o corte e relativo, de 1% do maximo,
    # e fica declarado aqui: e limiar de EXIBICAO, o dado continua denso.
    _barra_cor(fig, ax, barras3d(ax, pros, lam, "Valor", "Shadow Price",
                                 corte=0.01 * np.abs(lam).max()))
    fig.tight_layout(); fig.savefig(arquivo(out, 45), dpi=160); plt.close(fig)
    print(f"gravado {arquivo(out, 45).name}")

    fig = plt.figure(figsize=(6.4, 5.0)); ax = fig.add_subplot(111, projection="3d")
    _barra_cor(fig, ax, barras3d(ax, rede, -q, "Potência em kW",
                                 "Programação do armazenamento de rede",
                                 so_positivo=True))
    fig.tight_layout(); fig.savefig(arquivo(out, 46), dpi=160); plt.close(fig)
    print(f"gravado {arquivo(out, 46).name}")

    _figura_tensao(nos, v_final, [DIA, NOITE, MANHA], arquivo(out, 47))

    idx = {n: i for i, n in enumerate(nos)}
    dep = demanda.copy()
    for k, n in enumerate(pros):
        dep[idx[n]] += y[k]
    for k, n in enumerate(rede):
        dep[idx[n]] += q[k]
    _figura_demanda(nos, dep, [(None, 0, PERIODS, 24),
                               (DESTAQUE, 0, PERIODS, 24)],
                    arquivo(out, 48))
    figura_49(nos, v_base, v_final, arquivo(out, 49))

    no50 = 74 if 74 in idx else pros[-1]
    i50 = idx[no50]
    arm = y[pros.index(no50)] if no50 in pros else np.zeros(PERIODS)
    figura_50(no50, demanda[i50], arm, v_base[:, i50], v_final[:, i50],
              arquivo(out, 50))

    ac, ad = d["trilha_ac"], d["trilha_ad"]      # (rodadas, n_pros, 96)
    for fign, no in ((51, 74), (52, 25)):
        if no not in pros:
            print(f"  no {no} nao tem armazenamento aqui; pulando a Figura {fign}")
            continue
        k = pros.index(no)
        figura_iteracoes(no, demanda[idx[no]], ad[:, k], ac[:, k],
                         arquivo(out, fign))

    casos = []
    for no, t in ((74, 71), (25, 78)):
        if no in pros:
            k = pros.index(no)
            base = demanda[idx[no]][t]
            casos.append((no, t, base + ac[:, k, t], base + ad[:, k, t]))
    if casos:
        figura_53(casos, arquivo(out, 53))

    if Path(a.operacao).exists():
        vop, pop = _operacao(a.operacao)
        nos_op = sorted(n for n in vop if n in idx)
        V = np.array([vop[n] for n in nos_op]).T
        _figura_tensao(nos_op, V, [DIA, NOITE, MANHA], arquivo(out, 54))
        if pop:
            nos_p = sorted(pop)
            P = np.array([pop[n] for n in nos_p])
            _figura_demanda(nos_p, P, [(None, 0, PERIODS, 24),
                                       (DESTAQUE, 0, PERIODS, 24)],
                            arquivo(out, 55))
    else:
        print(f"sem {a.operacao}; pulando as Figuras 54 e 55")

    if Path(a.series).exists():
        figura_56(a.series, arquivo(out, 56))
        figura_57(a.series, arquivo(out, 57))
    else:
        print(f"sem {a.series}; pulando as Figuras 56 e 57")

    # As Figuras 58 e 59 saem do traco por mensagem, que e outro produto: elas
    # ficam em `plot_msgs`, e aqui so recebem o nome da legenda da tese.
    if Path(a.trace).exists():
        from .plot_msgs import carregar, figura_58, figura_59
        # As Figuras 58 e 59 da tese sao de tamanhos DECLARADOS: ela plota o que
        # o `set_message_length()` informa ao ns-3, e nao o conteudo. Gerar as
        # nossas a partir de um traco em modo `real` compara duas grandezas
        # diferentes e destroi a semelhanca de forma. Ja aconteceu.
        cfg = {}
        rj = Path(a.run_json)
        if rj.exists():
            try:
                cfg = json.loads(rj.read_text()).get("config", {})
            except Exception:
                cfg = {}
        if cfg.get("message_size") == "real":
            print("  ATENCAO: o traco e de NET_MESSAGE_SIZE=real. As Figuras 58 "
                  "e 59 da tese sao de tamanhos declarados; para comparar forma "
                  "a forma, rode com NET_MESSAGE_SIZE=thesis.")
        df = carregar(a.trace)
        # As duas analisam o MESMO conjunto de mensagens. A tese usa 5 janelas
        # de 15 min nas duas (775 mensagens na acumulada da Figura 59); passar o
        # dia inteiro so para a 59 punha as duas em escalas diferentes e
        # inflava a contagem por um fator de 19.
        janelas = 5
        t0 = int(df["t"].min())
        recorte = df[df["t"] < t0 + janelas]
        figura_58(recorte, arquivo(out, 58))
        figura_59(recorte, arquivo(out, 59))
    else:
        print(f"sem {a.trace}; pulando as Figuras 58 e 59")


if __name__ == "__main__":
    main()
