"""Figuras de resultado do mercado transativo (Fase 7).

Tres figuras, uma por pergunta:

  tensao_mercado.png    a negociacao resolve a violacao na rede real?
  operacao.png          a fase de operacao corrige o desvio da previsao?
  comunicacao.png       quanto a perda de pacotes custa a negociacao?

A convergencia da decomposicao dual fica em `plot_convergence.py`, que ja existe.

Cores: slots 1 a 3 da paleta de referencia, em ordem fixa. Uma escala por eixo,
legenda sempre que houver duas ou mais series, grade recessiva.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .config import V_MAX  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "0.85"


def _style(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)


def _hours(n):
    return np.arange(n) * 0.25


def plot_voltage(output_dir, out_path):
    """Tensao maxima da rede ao longo do dia, com e sem negociacao."""
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (tag, label) in enumerate([("baseline", "sem negociacao"),
                                      ("negociado", "com negociacao")]):
        df = pd.read_csv(Path(output_dir) / f"result_{tag}.csv", index_col=0)
        cols = [c for c in df.columns if c.endswith("V1_pu")]
        v = df[cols].values
        # A linha de base fica por cima: e nela que estao as excursoes acima do
        # limite, e o caso negociado a cobriria em quase todo o dia.
        ax.plot(_hours(len(v)), v.max(axis=1), linewidth=2, color=SERIES[i],
                label=label, zorder=3 if tag == "baseline" else 2)

    ax.axhline(V_MAX, color=MUTED, linestyle="--", linewidth=1)
    ax.annotate(f"limite {V_MAX:.2f} pu", xy=(0.4, V_MAX), xytext=(0.4, V_MAX + 0.0012),
                color=MUTED, fontsize=8)
    _style(ax, "hora do dia", "tensao maxima da rede [pu]",
           "Fluxo de potencia completo (OpenDSS) sobre a programacao acordada")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"gravado {out_path}")


def plot_operation(log_path, out_path):
    """Fase de operacao: violacao antes e depois da intervencao."""
    log = json.loads(Path(log_path).read_text())
    t = np.array([r["t"] for r in log]) * 0.25
    before = np.array([r["v_max_before"] for r in log])
    after = np.array([r["v_max_after"] for r in log])
    acted = [r for r in log if r["level"] != "-"]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(t, before, linewidth=2, color=SERIES[1], label="antes da intervencao")
    ax.plot(t, after, linewidth=2, color=SERIES[0], label="depois")
    ax.axhline(V_MAX, color=MUTED, linestyle="--", linewidth=1)

    # Os marcadores dizem QUEM agiu, nao QUAL serie: por isso distinguem-se pela
    # forma e ficam em tinta neutra. Reusar a cor de uma serie para outro
    # significado quebraria a leitura por cor.
    for level, marker in (("rede", "o"), ("leilao", "^")):
        pts = [r for r in acted if r["level"] == level]
        if pts:
            ax.scatter([r["t"] * 0.25 for r in pts],
                       [r["v_max_before"] for r in pts],
                       s=44, marker=marker, facecolor="white", edgecolor=INK,
                       linewidth=1.3, zorder=4,
                       label=("nivel 1: armazenamento de rede" if level == "rede"
                              else "nivel 2: leilao de operacao"))

    _style(ax, "hora do dia", "tensao maxima da rede [pu]",
           "Fase de operacao: desvio da previsao e correcao a cada 15 min")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"gravado {out_path}")


def plot_communication(rows, out_path):
    """Custo da perda de pacotes: rodadas concluidas e retransmissoes."""
    fig, ax = plt.subplots(figsize=(7, 4))
    losses = [r["loss"] * 100 for r in rows]
    rounds = [r["rounds"] for r in rows]
    colors = [SERIES[0] if r["converged"] else SERIES[1] for r in rows]

    bars = ax.bar([f"{l:.0f}%" for l in losses], rounds, color=colors, width=0.55)
    for bar, row in zip(bars, rows):
        estado = "convergiu" if row["converged"] else "nao convergiu"
        ax.annotate(f"{row['rounds']}\n{estado}",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8, color=MUTED)

    ax.axhline(17, color=MUTED, linestyle="--", linewidth=1)
    ax.annotate("17 rodadas: canal ideal", xy=(-0.4, 17.4), fontsize=8, color=MUTED)
    _style(ax, "perda de pacotes", "rodadas concluidas",
           "Negociacao sob perda, com retransmissao (3 tentativas)")
    ax.set_ylim(0, 22)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"gravado {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="../../output/market",
                    help="pasta com result_baseline.csv e result_negociado.csv")
    ap.add_argument("--operation-log", default="data/operation_log.json")
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    plot_voltage(args.output_dir, out / "tensao_mercado.png")
    plot_operation(args.operation_log, out / "operacao.png")
    # Medido nas corridas da Fase 5 (backend lossy, 3 retransmissoes).
    plot_communication([
        {"loss": 0.00, "rounds": 17, "converged": True},
        {"loss": 0.02, "rounds": 17, "converged": True},
        {"loss": 0.05, "rounds": 16, "converged": False},
        {"loss": 0.10, "rounds": 3, "converged": False},
    ], out / "comunicacao.png")


if __name__ == "__main__":
    main()
