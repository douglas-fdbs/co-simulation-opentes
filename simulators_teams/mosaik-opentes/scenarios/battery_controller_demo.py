"""Demo que exercita o agente PADE BatteryController end-to-end via Mosaik.

Fluxo (loop fechado de controle de bateria):

    CSV (curva)  ->  Controller.curve_value
    Battery.SoC  ->  Controller.SoC_in        (time_shifted, quebra o ciclo)
    Controller.P_ref/Q_ref  ->  Battery.P_ref/Q_ref
    Battery + Controller  ->  Collector (CSV de saida)

O Controller roda como agente PADE no container `pade-controller`
(ver controller_agent.py). A bateria e o CSV rodam nos containers do grid.
O objetivo e validar que o agente PADE recebe SoC/curva e devolve P_ref/Q_ref
corretamente atraves do Mosaik.

Rodar:
    docker compose --profile controller-demo up --abort-on-container-exit \
      --exit-code-from mosaik-controller-demo mosaik-controller-demo
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mosaik


CONTAINER_DATA = "/app/src/data/13Bus"
CURVE_CSV = f"{CONTAINER_DATA}/ieee13_shape_pv_5min.csv"
OUTPUT_DIR = Path(os.environ.get("MOSAIK_OUTPUT_DIR", "/app/output/controller_demo"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_CSV = str(OUTPUT_DIR / "result_battery_controller_demo.csv")

START_DATE = os.environ.get("MOSAIK_START_DATE", "2026-01-01 00:00:00")
STEP_SIZE = int(os.environ.get("MOSAIK_STEP_SIZE", "300"))
N_PASSOS = int(os.environ.get("MOSAIK_N_PASSOS", "288"))
END_TIME = N_PASSOS * STEP_SIZE


SIM_CONFIG = {
    "Battery": {"connect": f"{os.environ.get('BATTERY_HOST', 'battery')}:5672"},
    "CSV_Curve": {"connect": f"{os.environ.get('CSV_CURVE_HOST', 'csv-data-1')}:5675"},
    "Controller": {"connect": f"{os.environ.get('CONTROLLER_HOST_M', 'pade-controller')}:5681"},
    "Collector": {"connect": f"{os.environ.get('ELEC_COLLECTOR_HOST', 'elec-collector')}:5673"},
}


def run_scenario():
    with mosaik.World(SIM_CONFIG) as world:
        print("[mosaik] iniciando battery controller demo...")

        battery_sim = world.start("Battery", step_size=STEP_SIZE)
        csv_sim = world.start("CSV_Curve", sim_start=START_DATE, datafile=CURVE_CSV)
        ctrl_sim = world.start("Controller", step_size=STEP_SIZE)
        collector = world.start(
            "Collector",
            start_date=START_DATE,
            output_file=RESULT_CSV,
            print_results=False,
        )

        battery = battery_sim.Battery.create(
            1,
            kw_rated=50.0,
            kwh_rated=200.0,
            kwh_stored=100.0,
            kva_rated=55.0,
        )[0]
        csv_data = csv_sim.Data.create(1)[0]
        ctrl = ctrl_sim.BatteryController.create(
            1,
            kw_rated=50.0,
            charge_trigger=0.2,
            discharge_trigger=0.6,
            pct_charge=100.0,
            pct_discharge=100.0,
            time_charge_trigger=2.0,
        )[0]
        monitor = collector.Monitor()

        # Curva (irradiancia normalizada usada como proxy de demanda 0..1)
        world.connect(csv_data, ctrl, ("my_shape1_irrad", "curve_value"))

        # Comando do controller para a bateria
        world.connect(ctrl, battery, ("P_ref", "P_ref"), ("Q_ref", "Q_ref"))

        # Feedback de SoC (time_shifted quebra o ciclo controller<->battery)
        world.connect(
            battery, ctrl, ("SoC", "SoC_in"),
            time_shifted=True, initial_data={"SoC": 50.0},
        )

        # Monitoramento
        world.connect(battery, monitor, "SoC", "P_out", "Q_out")
        world.connect(ctrl, monitor, "P_ref", "Q_ref")

        print(f"[mosaik] rodando {N_PASSOS} passos x {STEP_SIZE}s")
        world.run(until=END_TIME, print_progress=False)
        print(f"[mosaik] concluido. resultados em {RESULT_CSV}")


if __name__ == "__main__":
    run_scenario()
