"""Figura do experimento de SENSIBILIDADE do Volt/Var a perda de pacotes.

Le output/sensibilidade_perda/result_<tag>.csv (+ comm_trace_<tag>.csv) e mostra
como o controle distribuido degrada conforme a comunicacao piora. Com a faixa
densa (0/25/30/35/40/45/50/75/100%), os paineis quantitativos sao CURVAS vs % de
perda — o ponto em que o "benefico" cruza zero e o LIMIAR onde o controle deixa
de ajudar e passa a atrapalhar.

  baseline -> sem controle (referencia, piso de tensao)
  lossNNN  -> Volt/Var com NNN% de perda de pacotes

Salva sensibilidade_perda.png. Uso:
  docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/sensibilidade_perda \
    mosaik python plot_loss_sweep.py
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
import numpy as np
import pandas as pd


OUT = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output/sensibilidade_perda"))
CRIT = "652"  # barra PV mais critica (subtensao)
PV_BUSES = ["646", "632", "634", "645", "652"]
# tags de Volt/Var por % de perda (alem do baseline, sem controle)
LOSS_TAGS = [("loss000", 0), ("loss025", 25), ("loss030", 30), ("loss035", 35),
             ("loss040", 40), ("loss045", 45), ("loss050", 50),
             ("loss075", 75), ("loss100", 100)]
CMAP = plt.get_cmap("RdYlGn_r")  # 0% -> verde, 100% -> vermelho


def _color(p):
    return CMAP(p / 100.0)


def _load(tag):
    df = pd.read_csv(OUT / f"result_{tag}.csv")
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df["h"] = df["date"].dt.hour + df["date"].dt.minute / 60.0
    return df


def _vmean(df, bus):
    cs = [c for c in df.columns if f"Bus-{bus}-" in c and "_pu" in c]
    s = df[cs].apply(pd.to_numeric, errors="coerce")
    return s.where(s > 0.5).mean(axis=1)


def _q_total(df):
    cs = [c for c in df.columns if "Q_meas" in c]
    return df[cs].apply(pd.to_numeric, errors="coerce").abs().sum(axis=1)


def _delivered_pct(tag):
    """entregue% = entregues/tentativas. No trace, packets_sent espelha
    packets_received e ambos contam os ENTREGUES; packets_dropped e a parte.
    Logo tentativas = sent + dropped e entregue% = sent/(sent+drop)."""
    f = OUT / f"comm_trace_{tag}.csv"
    if not f.exists():
        return np.nan
    ct = pd.read_csv(f)
    t = ct[ct["Atributo"].isin(["packets_sent", "packets_dropped"])].copy()
    t["Valor"] = pd.to_numeric(t["Valor"], errors="coerce")
    piv = t.pivot_table(index="Tempo", columns="Atributo", values="Valor", aggfunc="first")
    sent = piv["packets_sent"].max()
    drop = piv["packets_dropped"].max() if "packets_dropped" in piv else 0
    tot = sent + drop
    return 100.0 * sent / tot if tot else np.nan


def _threshold(M, eps=0.2):
    """faixa de perda onde o lift faz a PRIMEIRA virada de ajuda (>0) para
    atrapalho (<0), varrendo por perda crescente. Ignora o lift~0 do 100%
    (controle inerte = baseline), que nao e uma virada de sinal."""
    Ms = M.sort_values("loss").reset_index(drop=True)
    for i in range(1, len(Ms)):
        if Ms.loc[i - 1, "lift_med"] >= eps and Ms.loc[i, "lift_med"] < -eps:
            return Ms.loc[i - 1, "loss"], Ms.loc[i, "loss"]
    return None


def main() -> int:
    runs = [(t, p) for t, p in LOSS_TAGS if (OUT / f"result_{t}.csv").exists()]
    if not runs:
        print(f"[plot] nenhum result_loss*.csv em {OUT} — rode ./run_loss_sweep.sh")
        return 1
    data = {t: _load(t) for t, _ in runs}
    has_base = (OUT / "result_baseline.csv").exists()
    Vb = None
    if has_base:
        data["baseline"] = _load("baseline")
        Vb = _vmean(data["baseline"], CRIT)
    base_mean = Vb.mean() if Vb is not None else np.nan
    base_min = Vb.min() if Vb is not None else np.nan

    rows = []
    for t, p in runs:
        V = _vmean(data[t], CRIT)
        rows.append(dict(
            tag=t, loss=p, vmean=V.mean(), vmin=V.min(),
            lift_med=1000 * (V.mean() - base_mean),
            lift_min=1000 * (V.min() - base_min),
            tbelow=100 * (V < 0.95).mean(),
            q=_q_total(data[t]).mean(), deliv=_delivered_pct(t)))
    M = pd.DataFrame(rows).sort_values("loss").reset_index(drop=True)

    print("\n=== Sensibilidade do Volt/Var a perda de pacotes (Bus 652) ===")
    print(M[["loss", "deliv", "vmean", "lift_med", "vmin", "tbelow", "q"]].to_string(
        index=False, float_format=lambda x: f"{x:8.3f}"))
    th = _threshold(M)
    if th:
        print(f"  >> limiar (lift cruza 0) entre {th[0]:.0f}% e {th[1]:.0f}% de perda")

    fig, axs = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("OpenTES — Sensibilidade do controle Volt/Var à perda de pacotes (Bus 652)",
                 fontsize=15, fontweight="bold")

    # 1) tensao da barra critica ao longo do dia (leque por % de perda)
    ax = axs[0, 0]
    if has_base:
        ax.plot(data["baseline"]["h"], Vb, color="black", ls=":", lw=1.8, label="sem controle", zorder=6)
    for t, p in runs:
        ax.plot(data[t]["h"], _vmean(data[t], CRIT), color=_color(p), lw=1.3)
    ax.axhline(0.95, color="#999", ls="--", lw=1, label="ANEEL 0,95")
    sm = ScalarMappable(norm=Normalize(0, 100), cmap=CMAP); sm.set_array([])
    fig.colorbar(sm, ax=ax, label="perda de pacotes [%]")
    ax.set_title("Tensão da barra 652 ao longo do dia", fontweight="bold", fontsize=11)
    ax.set_xlabel("Hora do dia"); ax.set_ylabel("Tensão [pu]")
    ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 4)); ax.grid(alpha=.3)
    ax.legend(fontsize=8, loc="lower center")

    pts = dict(s=70, zorder=3, edgecolor="black", linewidths=0.6)
    cols = [_color(p) for p in M["loss"]]

    # 2) BENEFICIO (lift medio) vs perda — onde cruza 0 e o limiar
    ax = axs[0, 1]
    ax.axhline(0, color="black", lw=1)
    if th:
        ax.axvspan(th[0], th[1], color="grey", alpha=0.15)
        ax.text((th[0] + th[1]) / 2, ax.get_ylim()[1], "limiar", ha="center",
                va="top", fontsize=9, style="italic")
    ax.plot(M["loss"], M["lift_med"], "-", color="#555", lw=1.2, zorder=1)
    ax.scatter(M["loss"], M["lift_med"], c=cols, **pts)
    ax.set_title("Benefício do controle (lift médio vs baseline)", fontweight="bold", fontsize=11)
    ax.set_xlabel("perda de pacotes [%]")
    ax.set_ylabel("Δ tensão média [mV]   (+ ajuda / − atrapalha)")
    ax.grid(alpha=.3)

    # 3) ESFORCO (Q injetado) vs perda
    ax = axs[1, 0]
    ax.plot(M["loss"], M["q"], "-", color="#555", lw=1.2, zorder=1)
    ax.scatter(M["loss"], M["q"], c=cols, **pts)
    ax.set_title("Esforço de controle — reativo injetado (médio)", fontweight="bold", fontsize=11)
    ax.set_xlabel("perda de pacotes [%]"); ax.set_ylabel("Σ|Q| médio [kvar]")
    ax.grid(alpha=.3)

    # 4) INFORMACAO entregue vs perda
    ax = axs[1, 1]
    ax.plot(M["loss"], M["deliv"], "-", color="#555", lw=1.2, zorder=1)
    ax.scatter(M["loss"], M["deliv"], c=cols, **pts)
    ax.set_title("Informação entregue ao controlador", fontweight="bold", fontsize=11)
    ax.set_xlabel("perda de pacotes [%]"); ax.set_ylabel("Entregues [%]")
    ax.set_ylim(0, 105); ax.grid(alpha=.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(OUT / "sensibilidade_perda.png", dpi=150)
    print(f"\n[plot] {OUT / 'sensibilidade_perda.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
