"""Dashboard COMPLETO do cenario integrado (acoplamento causal Volt/Var).

Reune, num unico painel, os dois dominios da co-simulacao OpenTES — aproveitando
os graficos ja existentes do `star` (rede de comunicacao) e do `ieee13` (rede
eletrica), agora ATRELADOS no mesmo cenario:

  Entrada climatica (5 PVs):     1) irradiancia solar   2) temperatura dos modulos
  Rede eletrica (IEEE 13):       3) geracao FV agregada 4) tensoes p.u. nas barras
  Rede de comunicacao (OMNeT++): 5) integridade de pacotes (entregues x dropados)
                                 6) latencia exata       7) jitter distribuido
  Controle:                      8) efeito Volt/Var (Bus 632: baseline x controle)

Le os CSVs de output/integrated/ e os perfis climaticos de entrada; salva
output/integrated/dashboard_integrated.png.

Uso:
    docker compose run --rm --no-deps -e MOSAIK_OUTPUT_DIR=/app/output/integrated \
      mosaik python plot_integrated.py
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


OUT = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output/integrated"))
DATA = Path(os.environ.get("GRID_DATA_DIR", "/grid-data/13Bus"))
PNG = OUT / "dashboard_integrated.png"


def _load_elec(tag):
    df = pd.read_csv(OUT / f"result_{tag}.csv")
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df = df.set_index("date")
    df["h"] = df.index.hour + df.index.minute / 60.0
    return df


def _bus_vmean(df, bus):
    cs = [c for c in df.columns if f"Bus-{bus}-" in c and "_pu" in c]
    if not cs:
        return None
    return df[cs].where(df[cs] > 0.5).mean(axis=1)


def _bus_list(df):
    buses = []
    for c in df.columns:
        if c.startswith("DSS-0.Bus-") and "_pu" in c:
            name = c.split("Bus-")[1].rsplit("-", 1)[0]
            if name not in buses:
                buses.append(name)
    return buses


def _col(df, key):
    cs = [c for c in df.columns if key in c]
    return df[cs[0]] if cs else None


def _flatten_comm(tag, attr):
    """(hora, valor) de cada pacote a partir de uma coluna '|||'-separada."""
    df = pd.read_csv(OUT / f"comm_trace_{tag}.csv")
    sub = df[df["Atributo"] == attr]
    hs, vs = [], []
    for _, r in sub.iterrows():
        h = int(r["Tempo"]) / 3600.0
        for x in str(r["Valor"]).split("|||"):
            if x not in ("", "nan"):
                try:
                    vs.append(float(x)); hs.append(h)
                except ValueError:
                    pass
    return hs, vs


def _packet_totals(tag):
    df = pd.read_csv(OUT / f"comm_trace_{tag}.csv")
    df = df[df["Atributo"].isin(["packets_sent", "packets_received", "packets_dropped"])].copy()
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    p = df.pivot_table(index="Tempo", columns="Atributo", values="Valor", aggfunc="first")
    return (int(p["packets_sent"].max()), int(p["packets_received"].max()),
            int(p["packets_dropped"].max()))


def main() -> int:
    for tag in ("baseline", "volt_var"):
        if not (OUT / f"result_{tag}.csv").exists():
            print(f"[plot] falta result_{tag}.csv — rode ./run_opentes.sh integrated")
            return 1

    b, v = _load_elec("baseline"), _load_elec("volt_var")
    hv = v["h"].values

    df_irr = pd.read_csv(DATA / "ieee13_shape_pv_5min.csv")
    df_tmp = pd.read_csv(DATA / "ieee13_temperature_5min.csv")
    h_in = [i * 5.0 / 60.0 for i in range(len(df_irr))]

    fig, axs = plt.subplots(4, 2, figsize=(17, 18))
    fig.suptitle(
        "OpenTES — Dashboard da Co-simulação Integrada IEEE 13 Barras (rede elétrica ⟷ comunicação)",
        fontsize=16, fontweight="bold",
    )

    # 1) Irradiancia solar (5 PVs)
    ax = axs[0, 0]
    for c in [c for c in df_irr.columns if "irrad" in c]:
        ax.plot(h_in, df_irr[c], lw=1.5, label=c.replace("my_shape", "PV ").replace("_irrad", ""))
    ax.set_title("1) Irradiância solar (entrada climática — 5 PVs)", fontweight="bold", fontsize=11)
    ax.set_ylabel("Irradiância [pu]"); ax.legend(fontsize=8, ncol=5); ax.grid(alpha=.4)

    # 2) Temperatura dos modulos (5 PVs)
    ax = axs[0, 1]
    for c in [c for c in df_tmp.columns if "temperature" in c]:
        ax.plot(h_in, df_tmp[c], lw=1.5, label=c.replace("my_shape", "PV ").replace("_temperature", ""))
    ax.set_title("2) Temperatura dos módulos (entrada climática — 5 PVs)", fontweight="bold", fontsize=11)
    ax.set_ylabel("Temperatura [pu]"); ax.legend(fontsize=8, ncol=5); ax.grid(alpha=.4)

    # 3) Geracao FV agregada disponivel (5 PVs) = sum_i (Pmpp_i x irradiancia_i).
    # No cenario integrado quem e co-simulado/controlado e o PV2; os demais PVs
    # ficam estaticos no OpenDSS. Por isso a geracao agregada e calculada a partir
    # da irradiancia de entrada (segue o sol), e o PV2 e mostrado em separado.
    ax = axs[1, 0]
    PMPP = {"1": 5000.0, "2": 3000.0, "3": 3000.0, "4": 2000.0, "5": 2000.0}  # ieee13_pv.dss
    gen_agg = None
    for n, pmpp in PMPP.items():
        col = f"my_shape{n}_irrad"
        if col in df_irr.columns:
            contrib = df_irr[col] * pmpp
            gen_agg = contrib if gen_agg is None else gen_agg + contrib
    if gen_agg is not None:
        ax.plot(h_in, gen_agg, color="#d62728", lw=2.0, label="Σ disponível (5 PVs)")
    pdc = _col(v, "PVPanel_0-P_dc")
    if pdc is not None:
        ax.plot(hv, pdc, color="#ff7f0e", lw=1.4, ls="--", label="PV2 co-simulado (P_dc)")
    ax.set_title("3) Geração fotovoltaica agregada disponível", fontweight="bold", fontsize=11)
    ax.set_ylabel("Potência [kW]"); ax.legend(fontsize=8); ax.grid(alpha=.4)

    # 4) Tensoes p.u. nas barras (todas) ao longo do dia (caso Volt/Var)
    ax = axs[1, 1]
    for bus in _bus_list(v):
        s = _bus_vmean(v, bus)
        if s is not None and s.notna().any():
            ax.plot(hv, s, lw=1.0, label=bus)
    ax.axhline(1.05, color="grey", ls=":", lw=0.8); ax.axhline(0.95, color="grey", ls=":", lw=0.8)
    ax.set_title("4) Tensões nas barras (p.u.) — caso Volt/Var (limites ANEEL)", fontweight="bold", fontsize=11)
    ax.set_ylabel("Tensão [pu]"); ax.legend(fontsize=6, ncol=4, loc="lower left"); ax.grid(alpha=.4)

    # 5) Integridade de pacotes (entregues x dropados)
    ax = axs[2, 0]
    sent, rec, drop = _packet_totals("volt_var")
    cores = ["#2ca02c", "#d62728"]
    vals = [rec, drop]
    labels = [f"Entregues ({rec})", f"Dropados ({drop})"]
    if drop == 0:
        ax.barh(["Pacotes"], [rec], color="#2ca02c")
        ax.set_xlim(0, sent * 1.1)
        ax.text(rec / 2, 0, f"{rec} entregues / 0 dropados  (perda 0,0% — ideal)",
                ha="center", va="center", color="white", fontweight="bold")
    else:
        ax.pie(vals, labels=labels, colors=cores, autopct="%1.1f%%", startangle=90,
               wedgeprops={"edgecolor": "black"})
    ax.set_title(f"5) Integridade dos pacotes (enviados: {sent})", fontweight="bold", fontsize=11)

    # 6) Latencia exata (scatter por pacote)
    ax = axs[2, 1]
    hl, lat = _flatten_comm("volt_var", "latencies_out")
    ax.scatter(hl, [x * 1000 for x in lat], s=14, color="#9467bd", alpha=0.6)
    ax.set_title("6) Latência exata por pacote", fontweight="bold", fontsize=11)
    ax.set_ylabel("Latência [ms]"); ax.grid(alpha=.4)

    # 7) Jitter distribuido (scatter por pacote)
    ax = axs[3, 0]
    hj, jit = _flatten_comm("volt_var", "jitters_out")
    ax.scatter(hj, [x * 1000 for x in jit], s=14, color="#8c564b", alpha=0.6)
    ax.set_title("7) Jitter distribuído (atraso estocástico por pacote)", fontweight="bold", fontsize=11)
    ax.set_ylabel("Jitter [ms]"); ax.set_xlabel("Hora do dia"); ax.grid(alpha=.4)

    # 8) Efeito do controle Volt/Var no Bus 632 + reativo
    ax = axs[3, 1]
    vb, vv = _bus_vmean(b, "632"), _bus_vmean(v, "632")
    ax.plot(b["h"], vb, color="#d62728", lw=1.5, label="V632 sem controle")
    ax.plot(hv, vv, color="#2ca02c", lw=1.5, label="V632 com Volt/Var")
    ax.axhline(1.0, color="grey", ls=":", lw=0.8)
    ax.set_ylabel("Tensão [pu]"); ax.set_xlabel("Hora do dia")
    ax.set_title("8) Efeito do Volt/Var no Bus 632 + reativo do agente", fontweight="bold", fontsize=11)
    ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=.4)
    ax2 = ax.twinx()
    q = _col(v, "AgenteB-Q_ref")
    if q is not None:
        ax2.plot(hv, q, color="#1f77b4", lw=1.0, alpha=0.7)
        ax2.set_ylabel("Q [kvar]", color="#1f77b4")
        ax2.tick_params(axis="y", labelcolor="#1f77b4")

    for ax in axs.flat:
        if ax.get_xlabel() == "Hora do dia" or ax in (axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1], axs[2, 1], axs[3, 0]):
            ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 4))

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG, dpi=140)
    print(f"[plot] dashboard salvo em {PNG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
