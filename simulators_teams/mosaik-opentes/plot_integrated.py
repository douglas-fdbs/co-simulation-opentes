"""Dashboard do cenario INTEGRADO (acoplamento causal Volt/Var).

Junta, num unico painel, os DOIS dominios da co-simulacao OpenTES — para deixar
visivel que a rede eletrica e a rede de comunicacao estao acopladas:

  1. Tensao no Barramento 632: SEM controle (baseline) vs COM controle (Volt/Var).
  2. Potencia do inversor PV2: ativa P (solar) e reativa Q (decisao do agente).
  3. Rede de comunicacao (OMNeT++): latencia/jitter das mensagens que levaram a
     tensao ate o agente — o "grafico de trafego" no contexto do controle do PV.

Le os CSVs em output/integrated/ e salva output/integrated/dashboard_integrated.png.

Uso:
    docker compose run --rm --no-deps mosaik python plot_integrated.py
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


OUT = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output/integrated"))
PNG = OUT / "dashboard_integrated.png"


def _load_elec(tag):
    df = pd.read_csv(OUT / f"result_{tag}.csv")
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df = df.set_index("date")
    df["h"] = df.index.hour + df.index.minute / 60.0
    return df


def _vmean(df):
    vc = [c for c in df.columns if "Bus-632" in c and "_pu" in c]
    return df[vc].where(df[vc] > 0.5).mean(axis=1)


def _col(df, key):
    cs = [c for c in df.columns if key in c]
    return df[cs[0]] if cs else None


def _comm_series(tag, attr):
    """Media por passo de um atributo de telemetria ('|||'-separado) do comm_trace."""
    df = pd.read_csv(OUT / f"comm_trace_{tag}.csv")
    sub = df[df["Atributo"] == attr]
    out = {}
    for _, r in sub.iterrows():
        vals = [float(x) for x in str(r["Valor"]).split("|||") if x not in ("", "nan")]
        if vals:
            out[int(r["Tempo"])] = sum(vals) / len(vals)
    s = pd.Series(out).sort_index()
    s.index = s.index / 3600.0  # segundos -> hora do dia
    return s


def main() -> int:
    for tag in ("baseline", "volt_var"):
        if not (OUT / f"result_{tag}.csv").exists():
            print(f"[plot] falta result_{tag}.csv — rode ./run_opentes.sh integrated")
            return 1

    b, v = _load_elec("baseline"), _load_elec("volt_var")
    vb, vv = _vmean(b), _vmean(v)
    hv = v["h"].values
    p = _col(v, "AgenteB-P_ref")
    q = _col(v, "AgenteB-Q_ref")

    fig, axs = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    fig.suptitle(
        "OpenTES — Co-simulação integrada IEEE 13 (Bus 632): rede elétrica ⟷ comunicação",
        fontsize=15, fontweight="bold",
    )

    # 1) Tensao: baseline vs Volt/Var
    axs[0].plot(b["h"], vb, color="#d62728", lw=1.6, label="SEM controle (baseline)")
    axs[0].plot(hv, vv, color="#2ca02c", lw=1.6, label="COM controle (Volt/Var)")
    axs[0].axhline(1.0, color="grey", ls=":", lw=0.8)
    axs[0].set_title("1) Tensão no Barramento 632 — efeito do controle", fontsize=11, fontweight="bold")
    axs[0].set_ylabel("Tensão [pu]")
    axs[0].grid(alpha=0.4); axs[0].legend(loc="upper right", fontsize=9)

    # 2) Potencia do inversor PV2: P (solar) e Q (reativo do agente)
    if p is not None:
        axs[1].plot(hv, p, color="#ff7f0e", lw=1.8, label="P ativa (solar disponível) [kW]")
    if q is not None:
        axs[1].plot(hv, q, color="#1f77b4", lw=1.8, label="Q reativa (decisão Volt/Var) [kvar]")
    axs[1].axhline(0, color="grey", ls=":", lw=0.8)
    axs[1].set_title("2) Injeção do inversor PV2 — ativa e reativa", fontsize=11, fontweight="bold")
    axs[1].set_ylabel("Potência [kW / kvar]")
    axs[1].grid(alpha=0.4); axs[1].legend(loc="upper right", fontsize=9)

    # 3) Rede de comunicacao (OMNeT++): latencia e jitter das mensagens de tensao
    try:
        lat = _comm_series("volt_var", "latencies_out")
        jit = _comm_series("volt_var", "jitters_out")
        axs[2].plot(lat.index, lat.values * 1000, color="#9467bd", lw=1.4, label="Latência média [ms]")
        axs[2].plot(jit.index, jit.values * 1000, color="#8c564b", lw=1.0, alpha=0.8, label="Jitter médio [ms]")
        axs[2].set_title("3) Rede de comunicação OMNeT++ — atraso das mensagens (tensão → agente)",
                         fontsize=11, fontweight="bold")
        axs[2].set_ylabel("Tempo [ms]")
        axs[2].grid(alpha=0.4); axs[2].legend(loc="upper right", fontsize=9)
    except Exception as e:  # noqa: BLE001
        axs[2].text(0.5, 0.5, f"telemetria indisponível: {e}", ha="center")

    axs[2].set_xlabel("Hora do dia")
    axs[2].set_xlim(0, 24); axs[2].set_xticks(range(0, 25, 2))

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=150)
    print(f"[plot] dashboard salvo em {PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
