"""Figuras da comunicação entre os agentes, a partir do traço de mensagens.

Duas figuras, no formato das que Melo (2022, cap. 6) usa para a fase de
operação:

  figura_mensagens               cada mensagem contra o tempo de co-simulação:
                                 (a) tamanho em bytes, (b) tempo de recepção.
  figura_mensagens_distribuicao  a distribuição das mesmas duas grandezas:
                                 histograma e acumulada.

Entrada: o `msg_trace.csv` que a camada de rede grava (`NET_TRACE`), com uma
linha por mensagem enviada. O `figuras.py` chama estas funções; rodar este
módulo sozinho serve para inspecionar um traço e imprimir o resumo:

    python -m market_opentes.figuras_mensagens --trace /app/output/market_omnet/msg_trace.csv
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "0.85"

# Um tom por ciclo. Cada ciclo é rotulado pelo agente que o INICIA, e não pelo
# remetente de cada mensagem: as propostas dos prosumidores ficam na cor do ciclo
# aberto pelo AC.
CICLOS = {
    "ciclo1_AC_AP": ("#d81f1f", "Mens. do ciclo iniciado pelo AC"),
    "ciclo2_AD_AC": ("#1f4fd8", "Mens. do ciclo iniciado pelo AD"),
    "ciclo3_AM_AC_AD": ("#1baf7a", "Mens. do ciclo iniciado pelo AM"),
}
# Posição de cada ciclo dentro da janela de 15 min (ver `market_agents.py`).
INICIO_MIN = {"ciclo1_AC_AP": 1.0, "ciclo2_AD_AC": 5.0, "ciclo3_AM_AC_AD": 10.0}
JANELA_MIN = 15.0


def _style(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.set_title(title, color=INK, fontsize=10, loc="left")
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)


def carregar(trace_csv):
    """Lê o traço e reconstrói o tempo de co-simulação de cada mensagem.

    O eixo x é o tempo de co-simulação, reconstruído do intervalo de 15 min em
    curso, da posição do ciclo dentro da janela e do atraso da própria mensagem,
    que é o que produz o rastro ascendente dentro de cada aglomerado.
    """
    df = pd.read_csv(trace_csv)
    df = df[df["ciclo"].isin(CICLOS)]
    # As copias que o PADE manda ao `sniffer` e ao `ams` nao sao trafego da
    # arquitetura e falseiam as duas distribuicoes. O `network_link` ja as
    # exclui; o filtro fica para tracos de outra origem.
    antes = len(df)
    df = df[~df["receiver"].astype(str).str.startswith(("sniffer", "ams"))]
    if len(df) < antes:
        print(f"  descartadas {antes - len(df)} copias de instrumentacao "
              f"(sniffer/ams), que nao sao trafego da arquitetura")
    if "t" not in df or df["t"].isna().all():
        raise SystemExit("traço sem a coluna `t`: rode a fase de operação com "
                         "NET_TRACE ligado")
    df = df[df["t"].notna()].copy()
    df["t"] = df["t"].astype(int)
    df["min"] = (df["t"] * JANELA_MIN
                 + df["ciclo"].map(INICIO_MIN)
                 + df["delay_s"] / 60.0)
    return df


def figura_mensagens(df, out_png, janelas=None):
    """(a) tamanho e (b) tempo de recepção, contra o tempo de co-simulação."""
    if janelas:
        t0 = int(df["t"].min())
        df = df[df["t"] < t0 + janelas]
    fig, axes = plt.subplots(2, 1, figsize=(11.0, 6.0), sharex=True)
    for eixo, coluna, rotulo in ((axes[0], "bytes", "Tamanho das mensagens\n(bytes)"),
                                 (axes[1], "delay_s", "Tempo de recep.\ndas mensagens (s)")):
        for nome, (cor, legenda) in CICLOS.items():
            sub = df[df["ciclo"] == nome]
            if sub.empty:
                continue
            eixo.scatter(sub["min"], sub[coluna], s=14, marker="x",
                         linewidths=0.9, color=cor, label=legenda)
        _style(eixo, "", rotulo, "")
    axes[0].set_title("Tempo de co-simulacao vs. tamanho das mensagens",
                      color=INK, fontsize=10, loc="left")
    axes[1].set_title("Tempo de co-simulacao vs. tempo de recepcao de mensagens",
                      color=INK, fontsize=10, loc="left")
    axes[1].set_xlabel("Tempo de execucao da co-simulacao (min)", color=MUTED,
                       fontsize=9)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    print(f"gravado {out_png}")


def figura_mensagens_distribuicao(df, out_png):
    """Histograma e acumulada de tamanho e de tempo de recepção.

    A acumulada é em CONTAGEM, e não normalizada: o eixo y termina no total de
    mensagens analisadas.
    """
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 6.6))
    for linha, (coluna, unidade, nome) in enumerate(
            (("bytes", "bytes", "tamanho de mensagens"),
             ("delay_s", "s", "tempo de recepcao de mensagens"))):
        v = df[coluna].to_numpy()
        bins = np.histogram_bin_edges(v, bins=24)
        ax = axes[linha][0]
        ax.hist(v, bins=bins, color="#2a78d6", edgecolor="white", linewidth=0.4)
        _style(ax, f"{nome.split()[0].capitalize()} ({unidade})",
               "N de mensagens", f"Dist. de freq. de {nome}")
        ax = axes[linha][1]
        centros = (bins[:-1] + bins[1:]) / 2
        acum = np.cumsum(np.histogram(v, bins=bins)[0])
        ax.bar(centros, acum, width=(bins[1] - bins[0]) * 0.92,
               color="#2a78d6", edgecolor="white", linewidth=0.4)
        _style(ax, f"{nome.split()[0].capitalize()} ({unidade})",
               "N de mensagens", f"Dist. cumulada de {nome}")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    print(f"gravado {out_png}")


def resumo(df):
    """Resumo numérico do traço: tamanhos, atrasos e mensagens por ciclo."""
    n = len(df)
    janelas = df["t"].nunique()
    b, d = df["bytes"].to_numpy(), df["delay_s"].to_numpy()
    print(f"\n  mensagens                  {n}  em {janelas} janelas de 15 min "
          f"({n / janelas:.1f} por janela)")
    print(f"  tamanho                    {b.min():.0f} a {b.max():.0f} B, "
          f"mediana {np.median(b):.0f} B")
    print(f"  abaixo de 500 B            {(b <= 500).sum()} "
          f"({100.0 * (b <= 500).mean():.1f}%)")
    print(f"  entre 1000 e 1500 B        {((b >= 1000) & (b <= 1500)).sum()} "
          f"({100.0 * ((b >= 1000) & (b <= 1500)).mean():.1f}%)")
    print(f"  tempo de recepcao          {d.min():.1f} a {d.max():.1f} s, "
          f"mediana {np.median(d):.1f} s")
    print(f"  abaixo de 40 s             {(d <= 40).sum()} "
          f"({100.0 * (d <= 40).mean():.1f}%)")
    if "dropped" in df:
        print(f"  descartadas                {int(df['dropped'].sum())}")
    print("\n  por ciclo:")
    for nome in CICLOS:
        sub = df[df["ciclo"] == nome]
        if sub.empty:
            continue
        print(f"    {nome:<18} {len(sub):>5} mens  "
              f"{sub['bytes'].median():>6.0f} B mediana  "
              f"{sub['delay_s'].max():>6.1f} s pior atraso")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--trace", required=True, help="o msg_trace.csv de uma execucao")
    p.add_argument("--out-dir", default=None, help="padrao: a pasta do traco")
    p.add_argument("--janelas", type=int, default=5,
                   help="quantas janelas de 15 min a figura de mensagens mostra")
    a = p.parse_args()
    out = Path(a.out_dir) if a.out_dir else Path(a.trace).parent
    df = carregar(a.trace)
    figura_mensagens(df, out / "mensagens.png", a.janelas)
    figura_mensagens_distribuicao(df, out / "mensagens_distribuicao.png")
    resumo(df)
