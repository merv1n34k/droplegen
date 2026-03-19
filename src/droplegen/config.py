"""Constants, simulated instrument config, and pipeline definitions."""
from dataclasses import dataclass, field

# --- Timing ---
ACQUISITION_INTERVAL_MS = 100
UI_REFRESH_INTERVAL_MS = 150
STATS_WINDOW_SAMPLES = 300  # 30 seconds at 100ms

# --- Stability detection ---
STABILITY_TOLERANCE_UL_MIN = 2.0
STABILITY_DURATION_S = 5.0
STABILITY_WINDOW_SAMPLES = int(STABILITY_DURATION_S / (ACQUISITION_INTERVAL_MS / 1000.0))

# --- Pipeline trigger defaults ---
PIPELINE_TICK_MS = 200

# --- Simulated instrument config ---
# 3 separate LineUP (instr_type=4) instruments, each with 1 Flow EZ module
# Module config: [type=1, serial, firmware, pressure_range, sensor_type, 0,0,0,0,0]
# pressure_range: 5=2000mbar
# sensor_type: 4=Flow_M_dual, 7=Flow_L_dual
SIM_INSTR_TYPE = 4  # LineUP
SIM_INSTRUMENTS = [
    {"serial": 1001, "config": [1, 100, 0, 5, 4, 0, 0, 0, 0, 0]},  # Flow EZ + Flow Unit M
    {"serial": 1002, "config": [1, 101, 0, 5, 4, 0, 0, 0, 0, 0]},  # Flow EZ + Flow Unit M
    {"serial": 1003, "config": [1, 102, 0, 5, 7, 0, 0, 0, 0, 0]},  # Flow EZ + Flow Unit L
]

# --- Channel names (Drop-Seq convention) ---
PRESSURE_CHANNEL_NAMES = [
    "Oil Pressure",
    "Cells Pressure",
    "Beads Pressure",
]
SENSOR_CHANNEL_NAMES = [
    "Oil Flow (M)",
    "Cells Flow (M)",
    "Beads Flow (L)",
]

# --- Pipeline step definition ---
@dataclass
class Step:
    name: str
    sensor_setpoints: dict  # {sensor_index: flow_ul_min}
    trigger_type: str       # "time", "volume", "threshold", "confirmation"
    trigger_params: dict
    on_complete: str = "hold"  # "hold", "zero", "revert"


# --- Named pipelines ---
PIPELINES: dict[str, list[Step]] = {
    "Drop-Seq": [
        Step(
            name="Prime",
            sensor_setpoints={0: 100.0, 1: 50.0, 2: 50.0},
            trigger_type="time",
            trigger_params={"duration_s": 60.0},
        ),
        Step(
            name="Stabilize",
            sensor_setpoints={0: 30.0, 1: 10.0, 2: 10.0},
            trigger_type="threshold",
            trigger_params={
                "sensor_index": 0,
                "target": 30.0,
                "tolerance_pct": 5.0,
                "stable_duration_s": 10.0,
            },
        ),
        Step(
            name="Collect",
            sensor_setpoints={0: 30.0, 1: 10.0, 2: 10.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 1, "target_volume_ul": 500.0},
        ),
        Step(
            name="Flush",
            sensor_setpoints={0: 200.0, 1: 100.0, 2: 100.0},
            trigger_type="time",
            trigger_params={"duration_s": 30.0},
        ),
    ],
    "Priming": [
        Step(
            name="Confirm Prime Oil",
            sensor_setpoints={},
            trigger_type="confirmation",
            trigger_params={"message": "Prime Oil Flow (L) at 250 \u00b5l/min for 40 \u00b5l. Proceed?"},
        ),
        Step(
            name="Prime Oil",
            sensor_setpoints={0: 250.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 0, "target_volume_ul": 40.0},
            on_complete="zero",
        ),
        Step(
            name="Confirm Prime Cells",
            sensor_setpoints={},
            trigger_type="confirmation",
            trigger_params={"message": "Prime Cells Flow (M) at 67 \u00b5l/min for 5 \u00b5l. Proceed?"},
        ),
        Step(
            name="Prime Cells",
            sensor_setpoints={1: 67.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 1, "target_volume_ul": 5.0},
            on_complete="zero",
        ),
        Step(
            name="Confirm Prime Beads",
            sensor_setpoints={},
            trigger_type="confirmation",
            trigger_params={"message": "Prime Beads Flow (M) at 67 \u00b5l/min for 5 \u00b5l. Proceed?"},
        ),
        Step(
            name="Prime Beads",
            sensor_setpoints={2: 67.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 2, "target_volume_ul": 5.0},
            on_complete="zero",
        ),
    ],
}
