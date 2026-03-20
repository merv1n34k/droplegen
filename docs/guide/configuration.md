# Configuration

All configuration constants are defined in `src/droplegen/config.py`.

## Timing

| Constant | Default | Description |
|----------|---------|-------------|
| `ACQUISITION_INTERVAL_MS` | 100 | Sensor polling interval (ms) |
| `UI_REFRESH_INTERVAL_MS` | 150 | UI update timer interval (ms) |
| `STATS_WINDOW_SAMPLES` | 300 | Rolling statistics window (30s at 100ms) |
| `PIPELINE_TICK_MS` | 200 | Pipeline trigger evaluation interval (ms) |

## Stability Detection

Stability detection determines when a flow rate has settled to a target value.

| Constant | Default | Description |
|----------|---------|-------------|
| `STABILITY_TOLERANCE_UL_MIN` | 2.0 | Tolerance band (ul/min) |
| `STABILITY_DURATION_S` | 5.0 | Required stable duration (s) |
| `STABILITY_WINDOW_SAMPLES` | 50 | Computed from duration / interval |

## Hardware Channels

Three channels follow the Drop-Seq convention:

| Index | Pressure Name | Sensor Name | Sensor Type |
|-------|--------------|-------------|-------------|
| 0 | Oil Pressure | Oil Flow (L) | Flow Unit L |
| 1 | Cells Pressure | Cells Flow (M) | Flow Unit M |
| 2 | Beads Pressure | Beads Flow (M) | Flow Unit M |

## Sensor Calibration

Built-in calibration fluids (from `fgt_SENSOR_CALIBRATION` enum):

| Name | Value | Description |
|------|-------|-------------|
| None | 0 | No calibration |
| H2O | 1 | Water |
| IPA | 2 | Isopropyl alcohol |
| HFE | 3 | Hydrofluoroether |
| FC40 | 4 | Fluorinert FC-40 |
| Oil | 5 | Mineral oil |

Custom scaling is also supported via polynomial coefficients `(a, b, c)` where `scaled = a * raw + b * raw^2 + c * raw^3`.

## Sensor Ranges (Simulated Mode)

In simulated mode, sensor readings are scaled to match real hardware ranges:

| Sensor Type | Max Flow (ul/min) |
|-------------|-------------------|
| Flow Unit L | 5000.0 |
| Flow Unit M | 80.0 |

## Simulated Instruments

Three LineUP instruments are created for simulated mode, each containing one Flow EZ module:

```python
SIM_INSTRUMENTS = [
    {"serial": 1001, "config": [1, 100, 0, 5, 7, ...]},  # Flow EZ + Flow Unit L (Oil)
    {"serial": 1002, "config": [1, 101, 0, 5, 4, ...]},  # Flow EZ + Flow Unit M (Cells)
    {"serial": 1003, "config": [1, 102, 0, 5, 4, ...]},  # Flow EZ + Flow Unit M (Beads)
]
```

Config array format: `[type=1, serial, firmware, pressure_range, sensor_type, 0,0,0,0,0]`
- `pressure_range=5` → 2000 mbar
- `sensor_type=7` → Flow_L_dual, `sensor_type=4` → Flow_M_dual
