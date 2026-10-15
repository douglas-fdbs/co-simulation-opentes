"""Figuras de uma execução do mercado: tensões, demandas, preço sombra, a
negociação rodada a rodada, os dois mercados e a comunicação.

O formato de cada figura (eixos, tipo de gráfico e título interno) segue o das
figuras de resultados de Melo (2022, cap. 6), para que os resultados possam ser
postos lado a lado com os da formulação de referência. No modo por fase, as
figuras de tensão, de preço sombra e do armazenamento de rede têm um painel por
fase.

Todas as entradas saem da mesma pasta de resultados, a que `./run.sh market`
grava (`output/market/`, ou `output/market_por_no/` com MARKET_FASE=0):

  figuras.npz            a negociação centralizada (`./run.sh centralizado`)
  market_series.csv      as transações por intervalo (idem)
  result_negociado.csv   a fase de operação na co-simulação
  msg_trace.csv          o traço de mensagens, com NET_TRACE
  run.json               o registro da negociação distribuída

e a figura de PER lê o `tisch_links.csv` que o servidor 6TiSCH grava junto do
caso.

    python -m market_opentes.figuras --resultados /app/output/market
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

from .config import DT_H, GRID_DIR, PERIODS  # noqa: E402

# Mapa de cor de todas as figuras 3D, com barra de cor à direita.
CMAPA = "jet"

# Nome do arquivo de cada figura, sem extensão. As que detalham um nó recebem o
# número dele no fim: `composicao_no_671.png`.
ARQUIVOS = {
    "per": "per_distancia",
    "tensao_base": "tensao_sem_armazenamento",
    "demanda_base": "demanda_sem_armazenamento",
    "preco_sombra": "preco_sombra",
    "armazenamento_rede": "armazenamento_rede",
    "tensao_negociada": "tensao_negociada",
    "demanda_negociada": "demanda_negociada",
    "tensao_horarios": "tensao_dois_horarios",
    "composicao": "composicao_no",
    "negociacao": "negociacao_no",
    "convergencia": "convergencia",
    "tensao_operacao": "tensao_operacao",
    "demanda_operacao": "demanda_operacao",
    "mercados": "mercados_por_no",
    "precos": "precos_mercados",
    "mensagens": "mensagens",
    "mensagens_dist": "mensagens_distribuicao",
}


def arquivo(out_dir, chave, no=None):
    nome = ARQUIVOS[chave] if no is None else f"{ARQUIVOS[chave]}_{no}"
    return Path(out_dir) / f"{nome}.png"


def hhmm(t):
    m = int(round(t * DT_H * 60))
    return f"{m // 60:02d}:{m % 60:02d}"


# Angulo de camera das figuras 3D. No quadro (a), que mostra a rede inteira, o
# eixo dos nos fica a esquerda quase de perfil e o do tempo raso ao longo da
# base, o que corresponde a azim=-28. Os quadros seguintes, que destacam
# poucos nos ou poucas janelas, ficam melhores no angulo mais aberto: com o eixo
# dos nos de perfil, um recorte de cinco nos vira uma parede estreita.
ELEV, AZIM, AZIM_SEC = 28, -28, -58


def _eixo_tempo(ax, t0, t1, passo, eixo="y"):
    ticks = list(range(t0, t1 + 1, passo))
    getattr(ax, f"set_{eixo}ticks")(ticks)
    getattr(ax, f"set_{eixo}ticklabels")([hhmm(t) for t in ticks], fontsize=6)


# ---------------------------------------------------------------------------
# Pontos, hastes e barras em 3D
# ---------------------------------------------------------------------------

def _eixo_nos(ax, nos):
    """Posiciona os nós no eixo x.

    Quando os nós são numerados densamente (1, 2, 3, ...), o número serve de
    coordenada. Numa rede cujos nós herdam os nomes das barras, como a IEEE 13
    (611, 632, 633, 645, ...), o eixo numérico abriria vãos de dezenas de
    posições vazias entre nós vizinhos, e as marcas cairiam em números que não
    existem. Com nomes esparsos o eixo é CATEGÓRICO: uma posição por nó,
    rotulada com o número real.

    Devolve as coordenadas x a usar, na ordem de `nos`.
    """
    nos = list(nos)
    if not nos:
        return np.array([], dtype=float)
    denso = (max(nos) - min(nos) + 1) <= 1.5 * len(nos)
    if denso:
        x = np.asarray(nos, dtype=float)
        if len(nos) <= 10:
            ax.set_xticks(list(nos))
    else:
        x = np.arange(len(nos), dtype=float)
        ax.set_xticks(x)
        ax.set_xticklabels([str(n) for n in nos], fontsize=6)
    ax.set_xlim(float(x.min()) - 0.5, float(x.max()) + 0.5)
    return x


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

    É o formato das figuras de demanda líquida, e não uma superfície. A
    diferença não é estética: a superfície INTERPOLA entre nós vizinhos em
    número, que não são vizinhos elétricos, e entre intervalos de 15 minutos,
    onde não há dado. O que resulta é uma malha contínua que sugere valores que
    não foram calculados. A haste mostra só o que existe, e por isso o gráfico
    também fica menos poluído.
    """
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    sub = Z[:, t0:t1]
    tempos = np.arange(t0, t1)
    xs = _eixo_nos(ax, nos)
    N, T = np.meshgrid(xs, tempos, indexing="ij")
    n, t, z = N.ravel(), T.ravel(), sub.ravel()
    norm = plt.Normalize(float(sub.min()), float(sub.max()))
    mapa = matplotlib.colormaps[CMAPA]
    segmentos = np.stack([np.column_stack([n, t, np.zeros_like(z)]),
                          np.column_stack([n, t, z])], axis=1)
    ax.add_collection3d(Line3DCollection(segmentos, colors=mapa(norm(z)),
                                         linewidths=0.9))
    ax.set_ylim(t0, t1 - 1)
    ax.set_zlim(min(0.0, float(sub.min())), float(sub.max()))
    _moldura(ax, rotulo_z, titulo, t0, t1, passo_tempo, azim)
    return plt.cm.ScalarMappable(norm=norm, cmap=CMAPA)


def pontos(ax, nos, t0, t1, Z, rotulo_z, titulo, passo_tempo=None,
           azim=AZIM):
    """Um marcador por par (nó, intervalo).

    É o formato das figuras de tensão. Cada intervalo de 15 minutos é
    uma fileira de pontos separada, sem nada desenhado entre elas, que é o que
    deixa visível quantos pontos existem de fato.
    """
    sub = Z[:, t0:t1]
    tempos = np.arange(t0, t1)
    xs = _eixo_nos(ax, nos)
    N, T = np.meshgrid(xs, tempos, indexing="ij")
    norm = plt.Normalize(float(sub.min()), float(sub.max()))
    disp = ax.scatter(N.ravel(), T.ravel(), sub.ravel(), c=sub.ravel(),
                      cmap=CMAPA, norm=norm, s=5.0, linewidths=0, depthshade=False)
    ax.set_ylim(t0, t1 - 1)
    _moldura(ax, rotulo_z, titulo, t0, t1, passo_tempo, azim)
    return disp


def barras3d(ax, nos, Z, rotulo_z, titulo, corte=1e-9, so_positivo=False,
             norm=None, zlim=None):
    """Barras verticais valor(nó, tempo). Formato das figuras de preço sombra
    e do armazenamento de rede, em que o dado é esparso e uma superfície
    esconderia os picos.

    `so_positivo` mostra só a potência de SAÍDA, omitindo os intervalos de
    carga, que é como a figura do armazenamento de rede é lida.
    """
    ii, jj = np.nonzero((Z > corte) if so_positivo else (np.abs(Z) > corte))
    if len(ii) == 0:
        ax.text2D(0.5, 0.5, "sem valores não nulos", ha="center",
                  transform=ax.transAxes)
        return None
    v = Z[ii, jj]
    # `norm` e `zlim` vem de fora quando varios paineis precisam da MESMA escala,
    # como os tres do preco sombra por fase: com escala propria por painel, uma
    # barra de 200 numa fase e uma de 1000 noutra teriam a mesma cor.
    norm = plt.Normalize(v.min(), v.max()) if norm is None else norm
    cores = matplotlib.colormaps[CMAPA](norm(v))
    xs = _eixo_nos(ax, nos)
    ax.bar3d(xs[ii], jj.astype(float),
             np.zeros_like(v), 0.8, 0.8, v, color=cores, shade=True)
    # O `bar3d` nao estende o eixo z para baixo de zero, e as barras negativas
    # sairiam penduradas abaixo do piso da caixa. Com sobretensao o preco sombra
    # fica negativo, e a figura precisa mostrar os dois lados. So se mexe no
    # limite quando ha valor negativo.
    if zlim is not None:
        ax.set_zlim(*zlim)
    elif float(v.min()) < 0.0:
        ax.set_zlim(float(v.min()), max(float(v.max()), 0.0))
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
# Modo por fase (MARKET_FASE=1)
# ---------------------------------------------------------------------------

def _barra_cor_lateral(fig, mapeavel):
    """Barra de cor num eixo proprio, a direita dos tres paineis. Pendurada no
    ultimo painel, ela encolhia so aquele, e a fase C saia menor que as outras."""
    fig.subplots_adjust(left=0.02, right=0.90, wspace=0.08)
    cax = fig.add_axes([0.92, 0.25, 0.010, 0.5])
    cb = fig.colorbar(mapeavel, cax=cax)
    cb.ax.tick_params(labelsize=6)


def _por_no(chaves, M, eixo=0):
    """Soma as portas "671.A", "671.B", ... de cada no. Devolve (nos, matriz)."""
    nos = []
    for k in chaves:
        n = int(k.split(".")[0])
        if n not in nos:
            nos.append(n)
    M = np.asarray(M)
    partes = [np.take(M, [i for i, k in enumerate(chaves) if int(k.split(".")[0]) == n],
                      axis=eixo).sum(axis=eixo) for n in nos]
    return nos, np.stack(partes, axis=eixo)


def _barras_por_fase(chaves, Z, rotulo_z, titulo, out, corte=1e-9, so_positivo=False):
    """Barras 3D em tres paineis, um por fase, com a MESMA escala de cor
    e o mesmo eixo vertical, para que valores iguais tenham a mesma cor."""
    Z = np.asarray(Z)
    sel = (Z > corte) if so_positivo else (np.abs(Z) > corte)
    v = Z[sel] if sel.any() else np.zeros(1)
    lo, hi = float(min(v.min(), 0.0)), float(max(v.max(), 0.0))
    norm = plt.Normalize(float(v.min()), float(v.max()))
    fig = plt.figure(figsize=(15.0, 5.0))
    for j, f in enumerate("ABC"):
        idx = [i for i, k in enumerate(chaves) if k.endswith("." + f)]
        ax = fig.add_subplot(1, 3, j + 1, projection="3d")
        if not idx:
            ax.text2D(0.5, 0.5, "sem portas nesta fase", ha="center", transform=ax.transAxes)
            continue
        barras3d(ax, [int(chaves[i].split(".")[0]) for i in idx], Z[idx], rotulo_z,
                 f"{titulo}: fase {f}", corte=corte, so_positivo=so_positivo,
                 norm=norm, zlim=(lo, hi))
    _barra_cor_lateral(fig, plt.cm.ScalarMappable(norm=norm, cmap=CMAPA))
    fig.savefig(out, dpi=160); plt.close(fig)
    print(f"gravado {out.name}")


def _figura_tensao_fases(rows, V, out, titulo="Níveis de Tensão ao longo da rede elétrica"):
    """Tensao por fase: um painel por fase, o dia inteiro, mesma
    escala de cor nos tres."""
    V = np.asarray(V)
    norm_lo, norm_hi = float(V.min()), float(V.max())
    fig = plt.figure(figsize=(15.0, 4.8))
    for j, f in enumerate("ABC"):
        idx = [i for i, (n, k) in enumerate(rows) if k == j + 1]
        ax = fig.add_subplot(1, 3, j + 1, projection="3d")
        sub = V[:, idx].T
        xs = _eixo_nos(ax, [rows[i][0] for i in idx])
        tempos = np.arange(PERIODS)
        N, T = np.meshgrid(xs, tempos, indexing="ij")
        disp = ax.scatter(N.ravel(), T.ravel(), sub.ravel(), c=sub.ravel(), cmap=CMAPA,
                          norm=plt.Normalize(norm_lo, norm_hi), s=5.0, linewidths=0,
                          depthshade=False)
        ax.set_zlim(norm_lo, norm_hi)
        _moldura(ax, "Tensão em pu", f"{titulo}: fase {f}", 0, PERIODS, 24)
    _barra_cor_lateral(fig, disp)
    fig.savefig(out, dpi=150); plt.close(fig)
    print(f"gravado {out.name}")


# ---------------------------------------------------------------------------
# PER dos enlaces de rádio
# ---------------------------------------------------------------------------

def figura_per(links_csv, out, max_distance=1000.0):
    """PER por distância, para os enlaces do modelo 6TiSCH.

    Uma LINHA liga os pares ordenados por distância, e não uma nuvem de pontos.
    Como o PER de dois pares vizinhos em distância salta entre valores muito
    distintos, por causa do desvio de 0 a 40 dB sorteado por enlace no
    Pister-Hack, a linha vira um traço quase vertical em cada par.
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
# Tensão e demanda líquida em 3D
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
# Tensão por nó em dois horários, com e sem armazenamento
# ---------------------------------------------------------------------------

def figura_tensao_dois_horarios(nos, v_sem, v_com, out, horarios):
    # Mesmo motivo do eixo 3D: com nomes de barra esparsos (611, 632, 645, ...) o
    # eixo numérico espalha as barras por vãos vazios. Uma posição por nó.
    nos = list(nos)
    # Por fase os rotulos sao "671A": sempre categoricos.
    denso = (all(isinstance(n, (int, np.integer)) for n in nos)
             and (max(nos) - min(nos) + 1) <= 1.5 * len(nos))
    x = np.asarray(nos, dtype=float) if denso else np.arange(len(nos), dtype=float)
    fig, axes = plt.subplots(2, 1, figsize=(9.0, 5.6))
    for ax, t in zip(axes, horarios):
        ax.bar(x, v_sem[t], width=0.85, color="#1f77b4", label="Sem armazenamento")
        ax.bar(x, v_com[t], width=0.55, color="#ff7f0e", label="Com armazenamento")
        if not denso:
            ax.set_xticks(x)
            ax.set_xticklabels([str(n) for n in nos], fontsize=8 if len(nos) <= 16 else 6,
                               rotation=0 if len(nos) <= 16 else 90)
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
# Composição da demanda e tensão de um nó
# ---------------------------------------------------------------------------

def figura_composicao(no, carga, armaz, v_sem, v_com, out, fases=None):
    t = np.arange(PERIODS)
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 6.0))
    ax = axes[0]
    ax.bar(t, carga, width=0.85, color="#1f77b4", label="Demanda de carga + geração")
    # A parcela do armazenamento EMPILHA sobre a de carga, para cima ou para
    # baixo: e o que faz o topo da barra coincidir com a linha da demanda
    # liquida.
    ax.bar(t, armaz, width=0.85, bottom=carga,
           color="#ff7f0e", label="Demanda de armazenamento")
    ax.plot(t, carga + armaz, color="black", linewidth=1.2, label="Demanda Líquida")
    ax.set_title(f"Demanda líquida no nó {no} ao longo do tempo", fontsize=11)
    ax.set_ylabel("Demanda Líquida em kW", fontsize=9)
    ax.legend(fontsize=7, ncol=3, loc="lower left")

    ax = axes[1]
    if fases is None:
        ax.bar(t, v_sem, width=0.85, color="#1f77b4", label="Sem armazenamento")
        ax.bar(t, v_com, width=0.55, color="#ff7f0e", label="Com armazenamento")
        ax.plot(t, v_sem, color="black", linewidth=1.0, label="tensão res. sem armaz.")
        ax.plot(t, v_com, color="#d81f1f", linewidth=1.0, label="tensão res. com armaz.")
    else:
        # Por fase: uma linha por fase, tracejada sem armazenamento e continua
        # com. Barras sobrepostas de tres fases ficariam ilegiveis.
        cores = {"A": "#1f77b4", "B": "#ff7f0e", "C": "#2f7d32"}
        for k, f in enumerate(fases):
            ax.plot(t, v_sem[:, k], color=cores[f], linewidth=1.0, linestyle="--",
                    label=f"fase {f} sem armaz.")
            ax.plot(t, v_com[:, k], color=cores[f], linewidth=1.4,
                    label=f"fase {f} com armaz.")
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
# A programação de um nó, rodada a rodada
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
# Convergência num instante
# ---------------------------------------------------------------------------

def figura_convergencia(casos, out):
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
# Os dois mercados
# ---------------------------------------------------------------------------

def figura_mercados_por_no(series_csv, out, nodes):
    """Energia negociada em cada mercado, por intervalo, para quatro nós.
    Positivo é compra, negativo é venda; o bilateral só compra."""
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


def figura_precos(series_csv, out):
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

def _operacao(result_csv, por_tensao_fase=False):
    """Tensão e demanda líquida por nó, da co-simulação da operação.

    O coletor grava `Bus-611-V1_pu` (ou `Bus-n5-V1_pu`, em redes cujas barras
    se chamam `n<no>`). Por barra, a tensão do nó é a MÉDIA das fases presentes,
    que é o que o modelo do DSO enxerga nessa formulação; com `por_tensao_fase`,
    cada fase sai separada.
    """
    linhas = list(csv.reader(open(result_csv)))
    cab, dados = linhas[0], [l for l in linhas[1:] if l]
    fases, p, por_fase = {}, {}, {}
    for i, h in enumerate(cab):
        m = re.search(r"Bus-n?(\d+)-V([123])_pu", h)
        if m:
            col = np.array([float(l[i]) for l in dados])
            # Fase inexistente na barra sai como zero; entra só o que existe.
            if np.nanmax(col) > 0.5:
                fases.setdefault(int(m.group(1)), []).append(col)
                por_fase[(int(m.group(1)), int(m.group(2)))] = col
        m = re.search(r"node_(\d+)-P_kw", h)
        if m:
            n = int(m.group(1))
            p[n] = p.get(n, 0.0) + np.array([float(l[i]) for l in dados])
        # Por fase, o armazenamento vai pelas portas: a demanda liquida do no e a
        # carga do Load_n mais a soma das portas dele.
        m = re.search(r"port_(\d+)_[123]-P_kw", h)
        if m:
            n = int(m.group(1))
            p[n] = p.get(n, 0.0) + np.array([float(l[i]) for l in dados])
    v = {n: np.mean(cols, axis=0) for n, cols in fases.items()}
    if por_tensao_fase:
        return por_fase, p
    return v, p


# ---------------------------------------------------------------------------
# Escolha de nos e janelas
# ---------------------------------------------------------------------------
# Os nos e horarios em destaque saem dos DADOS de cada execucao, sempre por um
# criterio declarado em cada funcao, para que as figuras mostrem o que de fato
# importa na rede simulada.

def _mais_ativos(nos, matriz, quantos):
    """Os `quantos` nos de maior amplitude na matriz (nos x periodos)."""
    amp = np.ptp(np.asarray(matriz), axis=1)
    return [nos[i] for i in np.argsort(-amp)[:quantos]]


def escolher_destaque(nos, demanda):
    """Nos do quadro (b) das figuras de demanda: os de maior amplitude."""
    return set(_mais_ativos(nos, demanda, min(5, len(nos))))


def escolher_detalhe(pros, y, quantos=2):
    """Nos das figuras de detalhe (composicao, negociacao e convergencia): os
    que mais mexem no proprio armazenamento."""
    ordem = np.argsort(-np.abs(np.asarray(y)).sum(axis=1))
    return [pros[i] for i in ordem[:quantos]]


def escolher_horarios(v_base):
    """Horarios da figura de tensao em dois horarios: onde a tensao base bate
    no minimo e no maximo."""
    v = np.asarray(v_base)
    t_min = int(np.unravel_index(np.argmin(v), v.shape)[0])
    t_max = int(np.unravel_index(np.argmax(v), v.shape)[0])
    return (t_min, t_max) if t_min != t_max else (t_min, min(t_min + 8, PERIODS - 1))


def escolher_janelas(v_base, largura=7):
    """Janelas de destaque dos quadros (b) e (c) das figuras de tensão: em
    torno dos instantes em que a tensão base bate no máximo e no mínimo."""
    v = np.asarray(v_base)
    t_max = int(np.unravel_index(np.argmax(v), v.shape)[0])
    t_min = int(np.unravel_index(np.argmin(v), v.shape)[0])
    def janela(t):
        t0 = max(0, min(t - largura // 2, PERIODS - largura))
        return (t0, t0 + largura, 1)
    return janela(t_max), janela(t_min)


def escolher_mercado(series_csv, quantos=4):
    """Nos da figura dos mercados: os que mais energia movimentam nos dois."""
    import pandas as pd
    df = pd.read_csv(series_csv)
    total = (df.assign(e=df["bilateral_kw"].abs() + df["spot_kw"].abs())
               .groupby("node")["e"].sum().sort_values(ascending=False))
    return tuple(int(x) for x in total.index[:quantos])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--resultados", default="/app/output/market",
                    help="pasta com os resultados de ./run.sh market e centralizado")
    ap.add_argument("--links", default=str(GRID_DIR / "tisch_links.csv"))
    ap.add_argument("--out-dir", default=None,
                    help="padrao: <resultados>/figuras")
    a = ap.parse_args()
    r = Path(a.resultados)
    a.npz, a.series = r / "figuras.npz", r / "market_series.csv"
    a.operacao, a.trace, a.run_json = r / "result_negociado.csv", r / "msg_trace.csv", r / "run.json"
    out = Path(a.out_dir) if a.out_dir else r / "figuras"
    out.mkdir(parents=True, exist_ok=True)

    d = np.load(a.npz)
    nos = [int(x) for x in d["nodes"]]
    v_base, v_final = d["v_base"], d["v_final"]         # (96, linhas)
    demanda, y, q, lam = d["demanda"], d["y"], d["q"], d["lam"]
    ac, ad = d["trilha_ac"], d["trilha_ad"]              # (rodadas, chaves, 96)
    # Modo por fase: as tensoes sao por (no, fase) e as chaves do armazenamento
    # sao portas "671.A". As figuras por no (demanda e detalhe) usam o total do
    # dispositivo, somando as portas; as de tensao e de preco sombra mostram as
    # tres fases.
    fase = bool(d["fase"]) if "fase" in d.files else False
    if fase:
        rows = [(int(n), int(k)) for n, k in d["rows"]]
        rotulos = [f"{n}{'ABC'[k - 1]}" for n, k in rows]
        chaves_p = [str(x) for x in d["prosumer_nodes"]]
        chaves_q = [str(x) for x in d["network_nodes"]]
        pros, y_no = _por_no(chaves_p, y)
        rede, q_no = _por_no(chaves_q, q)
        _, ac_no = _por_no(chaves_p, ac, eixo=1)
        _, ad_no = _por_no(chaves_p, ad, eixo=1)
    else:
        pros = [int(x) for x in d["prosumer_nodes"]]
        rede = [int(x) for x in d["network_nodes"]]
        y_no, q_no, ac_no, ad_no = y, q, ac, ad

    # Nos e horarios em destaque: saem dos dados, por um criterio declarado em
    # cada `escolher_*`.
    DIA = (0, PERIODS, 24)
    DESTAQUE = escolher_destaque(nos, demanda)
    DETALHE = escolher_detalhe(pros, y_no)
    MERCADO = escolher_mercado(a.series) if Path(a.series).exists() else tuple(DETALHE)
    HORARIOS = escolher_horarios(v_base)
    NOITE, MANHA = escolher_janelas(v_base)
    print(f"  quadro (b) com {sorted(DESTAQUE)}, figuras por no {DETALHE}, mercado "
          f"{list(MERCADO)}, dois horarios em {[hhmm(t) for t in HORARIOS]}, janelas em "
          f"{hhmm(NOITE[0])}-{hhmm(NOITE[1] - 1)} e {hhmm(MANHA[0])}-{hhmm(MANHA[1] - 1)}")

    if Path(a.links).exists():
        figura_per(a.links, arquivo(out, "per"))
    if fase:
        _figura_tensao_fases(rows, v_base, arquivo(out, "tensao_base"))
    else:
        _figura_tensao(nos, v_base, [DIA, NOITE], arquivo(out, "tensao_base"))
    _figura_demanda(nos, demanda, [(None, 0, PERIODS, 24),
                                   (DESTAQUE, 0, PERIODS, 24)],
                    arquivo(out, "demanda_base"))
    # Nos de preco sombra nulo ficam fora da figura. O lambda nao zera exatamente
    # em lugar nenhum, entao o corte e relativo, de 1% do maximo: e limiar de
    # EXIBICAO, o dado continua denso.
    if fase:
        _barras_por_fase(chaves_p, lam, "Valor", "Shadow Price",
                         arquivo(out, "preco_sombra"), corte=0.01 * np.abs(lam).max())
        _barras_por_fase(chaves_q, -q, "Potência em kW",
                         "Programação do armazenamento de rede",
                         arquivo(out, "armazenamento_rede"), so_positivo=True)
    else:
        fig = plt.figure(figsize=(6.4, 5.0)); ax = fig.add_subplot(111, projection="3d")
        _barra_cor(fig, ax, barras3d(ax, pros, lam, "Valor", "Shadow Price",
                                     corte=0.01 * np.abs(lam).max()))
        fig.tight_layout(); fig.savefig(arquivo(out, "preco_sombra"), dpi=160); plt.close(fig)
        print(f"gravado {arquivo(out, 'preco_sombra').name}")

        fig = plt.figure(figsize=(6.4, 5.0)); ax = fig.add_subplot(111, projection="3d")
        _barra_cor(fig, ax, barras3d(ax, rede, -q, "Potência em kW",
                                     "Programação do armazenamento de rede",
                                     so_positivo=True))
        fig.tight_layout(); fig.savefig(arquivo(out, "armazenamento_rede"), dpi=160); plt.close(fig)
        print(f"gravado {arquivo(out, 'armazenamento_rede').name}")

    if fase:
        _figura_tensao_fases(rows, v_final, arquivo(out, "tensao_negociada"))
    else:
        _figura_tensao(nos, v_final, [DIA, NOITE, MANHA], arquivo(out, "tensao_negociada"))

    idx = {n: i for i, n in enumerate(nos)}
    dep = demanda.copy()
    for k, n in enumerate(pros):
        dep[idx[n]] += y_no[k]
    for k, n in enumerate(rede):
        dep[idx[n]] += q_no[k]
    _figura_demanda(nos, dep, [(None, 0, PERIODS, 24),
                               (DESTAQUE, 0, PERIODS, 24)],
                    arquivo(out, "demanda_negociada"))
    figura_tensao_dois_horarios(rotulos if fase else nos, v_base, v_final,
                                arquivo(out, "tensao_horarios"), horarios=HORARIOS)

    no50 = DETALHE[0]
    i50 = idx[no50]
    arm = y_no[pros.index(no50)] if no50 in pros else np.zeros(PERIODS)
    if fase:
        cols = [i for i, (n, _) in enumerate(rows) if n == no50]
        figura_composicao(no50, demanda[i50], arm, v_base[:, cols], v_final[:, cols],
                          arquivo(out, "composicao", no50),
                          fases=["ABC"[rows[i][1] - 1] for i in cols])
    else:
        figura_composicao(no50, demanda[i50], arm, v_base[:, i50], v_final[:, i50],
                          arquivo(out, "composicao", no50))

    for no in DETALHE:
        if no not in pros:
            print(f"  no {no} nao tem armazenamento aqui; pulando a figura da negociacao")
            continue
        k = pros.index(no)
        figura_iteracoes(no, demanda[idx[no]], ad_no[:, k], ac_no[:, k],
                         arquivo(out, "negociacao", no))

    casos = []
    # Cada no e mostrado no instante em que o proprio armazenamento dele mais
    # trabalha, que e onde AC e AD mais discordam.
    for no, t in zip(DETALHE, [int(np.argmax(np.abs(y_no[pros.index(nn)])))
                               if nn in pros else 0 for nn in DETALHE]):
        if no in pros:
            k = pros.index(no)
            base = demanda[idx[no]][t]
            casos.append((no, t, base + ac_no[:, k, t], base + ad_no[:, k, t]))
    if casos:
        figura_convergencia(casos, arquivo(out, "convergencia"))

    if Path(a.operacao).exists():
        vop, pop = _operacao(a.operacao, por_tensao_fase=fase)
        if fase:
            linhas_op = [r for r in rows if r in vop]
            V = np.array([vop[r] for r in linhas_op]).T
            _figura_tensao_fases(linhas_op, V, arquivo(out, "tensao_operacao"))
        else:
            nos_op = sorted(n for n in vop if n in idx)
            V = np.array([vop[n] for n in nos_op]).T
            _figura_tensao(nos_op, V, [DIA, NOITE, MANHA], arquivo(out, "tensao_operacao"))
        if pop:
            nos_p = sorted(pop)
            P = np.array([pop[n] for n in nos_p])
            _figura_demanda(nos_p, P, [(None, 0, PERIODS, 24),
                                       (DESTAQUE, 0, PERIODS, 24)],
                            arquivo(out, "demanda_operacao"))
    else:
        print(f"sem {a.operacao}; pulando as figuras da operacao")

    if Path(a.series).exists():
        figura_mercados_por_no(a.series, arquivo(out, "mercados"), nodes=MERCADO)
        figura_precos(a.series, arquivo(out, "precos"))
    else:
        print(f"sem {a.series}; pulando as figuras dos mercados")

    # As figuras de comunicacao saem do traco por mensagem, que e outro produto:
    # ficam em `figuras_mensagens`.
    if Path(a.trace).exists():
        from .figuras_mensagens import (carregar, figura_mensagens,
                                        figura_mensagens_distribuicao)
        # As figuras de referencia sao de tamanhos DECLARADOS, e nao do conteudo
        # serializado. Comparar com elas um traco em modo `real` compara duas
        # grandezas diferentes.
        cfg = {}
        rj = Path(a.run_json)
        if rj.exists():
            try:
                cfg = json.loads(rj.read_text()).get("config", {})
            except Exception:
                cfg = {}
        if cfg.get("message_size") == "real":
            print("  nota: traco com NET_MESSAGE_SIZE=real (tamanho do conteudo). "
                  "Para comparar com as figuras de referencia, que usam tamanhos "
                  "declarados, rode com NET_MESSAGE_SIZE=declarado.")
        df = carregar(a.trace)
        # As duas analisam o MESMO conjunto de mensagens: as 5 primeiras janelas
        # de 15 min da operacao. Passar o dia inteiro so para a distribuicao
        # poria as duas em escalas diferentes.
        janelas = 5
        t0 = int(df["t"].min())
        recorte = df[df["t"] < t0 + janelas]
        figura_mensagens(recorte, arquivo(out, "mensagens"))
        figura_mensagens_distribuicao(recorte, arquivo(out, "mensagens_dist"))
    else:
        print(f"sem {a.trace}; pulando as figuras de comunicacao")


if __name__ == "__main__":
    main()
