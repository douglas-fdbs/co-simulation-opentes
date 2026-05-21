"""Compatibility probe for the TSCC Mosaik adapters.

This script intentionally uses the real TSCC Mosaik-side adapter
(`omnet_wrapper.OmnetAdapter`) and collector, but replaces OMNeT++ and PADE with
small in-process fakes. It verifies that the adapter contract used by TSCC works
with the Mosaik version installed in the integration venv.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading

import argparse
import mosaik
import mosaik_api_v3 as mosaik_api
import zmq


def _find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "simulators_teams" / "tscc-com-opentes").exists():
            return parent
    raise RuntimeError("Could not find the OpenTES integration repository root")


REPO_ROOT = _find_repo_root()
TSCC_MOSAIK_DIR = REPO_ROOT / "simulators_teams" / "tscc-com-opentes" / "mosaik-dir"
sys.path.insert(0, str(TSCC_MOSAIK_DIR))

from collector import Coletor  # noqa: E402
from omnet_wrapper import OmnetAdapter  # noqa: E402


FAKE_PADE_META = {
    "type": "time-based",
    "models": {
        "PadeAgent": {
            "public": True,
            "params": ["agent_id"],
            "attrs": ["val_in", "val_out"],
        },
    },
}


class FakePadeSim(mosaik_api.Simulator):
    """Minimal PADE stand-in with the same public Mosaik surface as TSCC."""

    def __init__(self):
        super().__init__(FAKE_PADE_META)
        self.agents: dict[str, str] = {}
        self.outputs: dict[str, str] = {}

    def init(self, sid, time_resolution):
        self.sid = sid
        return self.meta

    def create(self, num, model, agent_id):
        self.agents[agent_id] = ""
        self.outputs[agent_id] = ""
        return [{"eid": agent_id, "type": model}]

    def step(self, time, inputs, max_advance):
        for eid, attrs in inputs.items():
            if "val_in" in attrs:
                delivered = list(attrs["val_in"].values())[0]
                self.agents[eid] = delivered

        self.outputs["AgenteCentral"] = json.dumps(
            {
                "sender": "AgenteCentral",
                "receivers": ["AgenteP_1"],
                "content": f"probe-t{time}",
            }
        )
        return time + 1

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.outputs.get(eid, "") if attr == "val_out" else None
        return data


def _start_fake_omnet_server() -> tuple[threading.Thread, threading.Event, int]:
    context = zmq.Context.instance()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.RCVTIMEO, 200)
    port = socket.bind_to_random_port("tcp://127.0.0.1")
    stop_event = threading.Event()

    def server_loop():
        while not stop_event.is_set():
            try:
                payload = socket.recv_json()
            except zmq.Again:
                continue

            action = payload.get("action")
            if action in {"create", "connect"}:
                socket.send_json({"status": "ok"})
            elif action == "step":
                time = payload["time"]
                socket.send_json(
                    {
                        "status": "ok",
                        "mosaik_step": time,
                        "data": {
                            "node_0": {
                                "val_out": f"network-delivery-t{time}",
                                "status": "ok",
                                "packets_sent": 1,
                                "packets_received": 1,
                                "packets_dropped": 0,
                                "packet_sizes_out": [128],
                                "latencies_out": [0.01],
                                "jitters_out": [0.0],
                            }
                        },
                    }
                )
            else:
                socket.send_json({"status": "error", "reason": f"unknown action {action}"})

        socket.close(0)

    thread = threading.Thread(target=server_loop, daemon=True)
    thread.start()
    return thread, stop_event, port


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pade-connect",
        help=(
            "Use a real remote PADE/Mosaik server instead of the in-process fake, "
            "for example 127.0.0.1:5678."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    thread, stop_event, omnet_port = _start_fake_omnet_server()

    sim_config = {
        "OmnetSim": {"python": "omnet_wrapper:OmnetAdapter"},
        "ColetorSim": {"python": "collector:Coletor"},
    }
    if args.pade_connect:
        sim_config["PadeSim"] = {"connect": args.pade_connect}
    else:
        sim_config["PadeSim"] = {"python": f"{__name__}:FakePadeSim"}

    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="opentes-tscc-mosaik-") as tmpdir:
        os.chdir(tmpdir)
        try:
            with mosaik.World(sim_config) as world:
                omnet_sim = world.start("OmnetSim", host="127.0.0.1", port=omnet_port)
                collector = world.start("ColetorSim")
                pade_sim = world.start("PadeSim")

                network = omnet_sim.NetworkNode(node_type="NetworkNode")
                monitor = collector.Monitor()
                central = pade_sim.PadeAgent(agent_id="AgenteCentral")
                peripheral = pade_sim.PadeAgent(agent_id="AgenteP_1")

                world.connect(central, network, ("val_out", "val_in"))
                world.connect(
                    network,
                    central,
                    ("val_out", "val_in"),
                    time_shifted=True,
                    initial_data={"val_out": ""},
                )
                world.connect(peripheral, network, ("val_out", "val_in"))
                world.connect(
                    network,
                    peripheral,
                    ("val_out", "val_in"),
                    time_shifted=True,
                    initial_data={"val_out": ""},
                )
                world.connect(
                    network,
                    monitor,
                    "status",
                    "packets_sent",
                    "packets_received",
                    "packets_dropped",
                    "packet_sizes_out",
                    "latencies_out",
                    "jitters_out",
                    "val_out",
                )

                world.run(until=3, print_progress=False)

            results_file = Path(tmpdir) / "results.csv"
            if not results_file.exists() or "network-delivery" not in results_file.read_text():
                raise RuntimeError("collector did not receive fake OMNeT++ data")
        finally:
            os.chdir(old_cwd)
            stop_event.set()
            thread.join(timeout=1)

    pade_mode = f"remote PADE at {args.pade_connect}" if args.pade_connect else "fake PADE"
    print(f"TSCC Mosaik compatibility OK with mosaik {mosaik.__version__} ({pade_mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
