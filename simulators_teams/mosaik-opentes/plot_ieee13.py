"""Plot pós-simulação para o cenário IEEE 13 Smart PV.

Adaptado de ``grei-ufc/tsre-der-opentes/src/scenarios/teste_plot.py``
(commit 0e9f4fee4fc6) para o novo layout: o cenário roda dentro do container
``mosaik`` e grava o CSV de resultado em ``/app/output``. Este script lê os
dois CSVs de entrada (irradiância/temperatura), o CSV de saída do Mosaik e
gera um dashboard com 4 painéis. Por default usa o backend Agg e salva em
``output/ieee13_dashboard.png``; passe ``--show`` para abrir interativamente.

Uso típico:

```bash
docker compose run --rm --no-deps mosaik python plot_ieee13.py
```
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib

if "--show" in sys.argv:
    matplotlib.use("WebAgg")
else:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


REPO_DATA_DIR = Path(os.environ.get(
    "GRID_DATA_DIR",
    "/grid-data/13Bus",
))
OUTPUT_DIR = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output"))

CSV_IRRAD_IN = REPO_DATA_DIR / "ieee13_shape_pv_5min.csv"
CSV_TEMP_IN = REPO_DATA_DIR / "ieee13_temperature_5min.csv"
RESULT_CSV = OUTPUT_DIR / "result_run_ieee13_cosim_pv_5min.csv"
DASHBOARD_PNG = OUTPUT_DIR / "ieee13_dashboard.png"


def plot_comprehensive_results(show: bool = False) -> int:
    errors = False
    for p in (CSV_IRRAD_IN, CSV_TEMP_IN, RESULT_CSV):
        if not p.exists():
            print(f"[plot] arquivo nao encontrado: {p}")
            errors = True
    if errors:
        return 1

    print("[plot] carregando datasets...")
    df_irr = pd.read_csv(CSV_IRRAD_IN)
    df_tmp = pd.read_csv(CSV_TEMP_IN)
    df_res = pd.read_csv(RESULT_CSV)

    if df_res.empty:
        print("[plot] arquivo de resultados vazio")
        return 1

    pac_columns = [c for c in df_res.columns if "P_ac" in c]
    raw_vpu_columns = [c for c in df_res.columns if "V1_pu" in c or "V2_pu" in c or "V3_pu" in c]
    vpu_columns = [c for c in raw_vpu_columns if df_res[c].mean() > 0.5]

    fig, axs = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(
        "OpenTES IEEE 13 Co-Simulation Dashboard\n(Weather inputs vs P_ac / V_pu outputs)",
        fontsize=16,
        fontweight="bold",
    )

    irr_cols = [c for c in df_irr.columns if c.lower() not in ("time", "timestamp", "date", "index")]
    for col in irr_cols:
        label = col.replace("my_shape", "PV ").replace("_irrad", "")
        axs[0].plot(df_irr.index, df_irr[col], label=label, linewidth=2)
    axs[0].set_title("Input solar irradiance profiles", fontsize=11, fontweight="bold")
    axs[0].set_ylabel("Irradiance [W/m² ou pu]")
    axs[0].grid(True, linestyle="--", alpha=0.5)
    axs[0].legend(loc="upper right", fontsize=8, frameon=True)

    tmp_cols = [c for c in df_tmp.columns if c.lower() not in ("time", "timestamp", "date", "index")]
    for col in tmp_cols:
        label = col.replace("my_shape", "PV ").replace("_temperature", "")
        axs[1].plot(df_tmp.index, df_tmp[col], label=label, linewidth=2)
    axs[1].set_title("Input module temperature profiles", fontsize=11, fontweight="bold")
    axs[1].set_ylabel("Temperature [°C ou pu]")
    axs[1].grid(True, linestyle="--", alpha=0.5)
    axs[1].legend(loc="upper right", fontsize=8, frameon=True)

    for col in pac_columns:
        label = col.replace(".P_ac", "").replace("InverterSim-", "Inverter ")
        axs[2].plot(df_res.index, df_res[col], label=label, linewidth=2)
    axs[2].set_title("Smart inverters - active power (P_ac)", fontsize=11, fontweight="bold")
    axs[2].set_ylabel("Power [kW ou W]")
    axs[2].grid(True, linestyle="--", alpha=0.5)
    axs[2].legend(loc="upper right", fontsize=8, frameon=True)

    for col in vpu_columns:
        label = (
            col.replace("Bus-", "Bus ")
            .replace(".V1_pu", " - Ph A")
            .replace(".V2_pu", " - Ph B")
            .replace(".V3_pu", " - Ph C")
        )
        axs[3].plot(df_res.index, df_res[col], label=label, linewidth=1.5, linestyle="-.")
    axs[3].set_title("Network voltage profiles (V_pu)", fontsize=11, fontweight="bold")
    axs[3].set_xlabel("Simulation steps (5-minute intervals)", fontsize=12)
    axs[3].set_ylabel("Voltage [pu]")
    axs[3].set_ylim(0.85, 1.10)
    axs[3].grid(True, linestyle="--", alpha=0.5)
    axs[3].legend(loc="lower left", fontsize=8, ncol=4, frameon=True)

    plt.tight_layout()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(DASHBOARD_PNG, dpi=160)
    print(f"[plot] dashboard salvo em {DASHBOARD_PNG}")

    if show:
        plt.show()
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", action="store_true", help="exibe interativamente via WebAgg")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(plot_comprehensive_results(show=args.show))
