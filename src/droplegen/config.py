"""Constants, simulated instrument config, and pipeline definitions."""
from dataclasses import dataclass

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
PIPELINE_DIR = "pipelines"

# --- Simulated instrument config ---
# 3 separate LineUP (instr_type=4) instruments, each with 1 Flow EZ module
# Module config: [type=1, serial, firmware, pressure_range, sensor_type, 0,0,0,0,0]
# pressure_range: 5=2000mbar
# sensor_type: 4=Flow_M_dual, 7=Flow_L_dual
SIM_INSTR_TYPE = 4  # LineUP
SIM_INSTRUMENTS = [
    {"serial": 1001, "config": [1, 100, 0, 5, 7, 0, 0, 0, 0, 0]},  # Flow EZ + Flow Unit L (Oil)
    {"serial": 1002, "config": [1, 101, 0, 5, 4, 0, 0, 0, 0, 0]},  # Flow EZ + Flow Unit M (Cells)
    {"serial": 1003, "config": [1, 102, 0, 5, 4, 0, 0, 0, 0, 0]},  # Flow EZ + Flow Unit M (Beads)
]

# --- Real sensor ranges (µl/min) for simulated mode override ---
# Keyed by fgt_SENSOR_TYPE enum name substring
SENSOR_REAL_SMAX = {
    "Flow_L": 5000.0,
    "Flow_M": 80.0,
}

# --- Channel names (Drop-Seq convention) ---
PRESSURE_CHANNEL_NAMES = [
    "Oil Pressure",
    "Cells Pressure",
    "Beads Pressure",
]
SENSOR_CHANNEL_NAMES = [
    "Oil Flow (L)",
    "Cells Flow (M)",
    "Beads Flow (M)",
]

# --- Sensor calibration ---
# Built-in calibration tables (fgt_SENSOR_CALIBRATION enum values)
SENSOR_CALIBRATIONS = {
    "None": 0,
    "H2O": 1,
    "IPA": 2,
    "HFE": 3,
    "FC40": 4,
    "Oil": 5,
}

# --- Pipeline step definition ---
@dataclass
class Step:
    name: str
    sensor_setpoints: dict  # {sensor_index: flow_ul_min}
    trigger_type: str       # "time", "volume", "threshold", "condition"
    trigger_params: dict
    on_complete: str = "hold"  # "hold", "zero", "revert"
    confirm_message: str = ""  # if set, requires confirmation before step runs
    repeat: int = 1           # repeat this step (or group) N times
    group: str = ""           # group tag — steps with same tag repeat as a unit


# --- Named pipelines ---
PIPELINES: dict[str, list[Step]] = {
    "Drop-Seq": [
        Step(
            name="Prerun",
            sensor_setpoints={0: 250.0, 1: 67.0, 2: 67.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 0, "target_volume_ul": 75.0},
            on_complete="zero",
        ),
        Step(
            name="Run-prestab",
            sensor_setpoints={0: 250.0, 1: 0.0, 2: 0.0},
            trigger_type="condition",
            trigger_params={"sensor_index": 0, "min_value": 125.0},
            confirm_message="Prerun complete. Start stabilization?",
            group="run",
            repeat=3,
        ),
        Step(
            name="Run-stab",
            sensor_setpoints={0: 250.0, 1: 67.0, 2: 67.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 0, "target_volume_ul": 250.0},
            on_complete="zero",
            group="run",
            repeat=3,
        ),
    ],
    "Priming": [
        Step(
            name="Prime Oil",
            sensor_setpoints={0: 250.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 0, "target_volume_ul": 40.0},
            on_complete="zero",
            confirm_message="Prime Oil Flow (L) at 250 \u00b5l/min for 40 \u00b5l. Proceed?",
        ),
        Step(
            name="Prime Cells",
            sensor_setpoints={1: 67.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 1, "target_volume_ul": 5.0},
            on_complete="zero",
            confirm_message="Prime Cells Flow (M) at 67 \u00b5l/min for 5 \u00b5l. Proceed?",
        ),
        Step(
            name="Prime Beads",
            sensor_setpoints={2: 67.0},
            trigger_type="volume",
            trigger_params={"sensor_index": 2, "target_volume_ul": 5.0},
            on_complete="zero",
            confirm_message="Prime Beads Flow (M) at 67 \u00b5l/min for 5 \u00b5l. Proceed?",
        ),
    ],
}
