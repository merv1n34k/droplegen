# Pipelines

Pipelines automate multi-step flow control sequences for Drop-Seq experiments.

## Step Definition

Each step defines:

```python
Step(
    name="Prerun",
    sensor_setpoints={0: 250.0, 1: 67.0, 2: 67.0},
    trigger_type="volume",
    trigger_params={"sensor_index": 0, "target_volume_ul": 75.0},
    on_complete="zero",
    confirm_message="",
    repeat=1,
    group="",
)
```

| Field | Description |
|-------|-------------|
| `name` | Display name for the step |
| `sensor_setpoints` | Map of sensor index to flow rate (ul/min) |
| `trigger_type` | When the step completes: `time`, `volume`, `threshold`, `condition` |
| `trigger_params` | Parameters for the trigger (varies by type) |
| `on_complete` | What happens when the step finishes |
| `confirm_message` | If set, pauses for user confirmation before running |
| `repeat` | Repeat this step N times |
| `group` | Group tag for repeating multiple steps as a unit |

## Trigger Types

### Time
Completes after a fixed duration.

```python
trigger_type="time"
trigger_params={"duration_s": 30.0}
```

### Volume
Completes after dispensing a target volume on a sensor channel.

```python
trigger_type="volume"
trigger_params={"sensor_index": 0, "target_volume_ul": 75.0}
```

### Threshold
Completes when a flow rate stays within a tolerance band for a duration.

```python
trigger_type="threshold"
trigger_params={
    "sensor_index": 0,
    "target": 250.0,
    "tolerance_pct": 5.0,
    "stable_duration_s": 10.0,
}
```

### Condition
Fires once a sensor reading enters a value range.

```python
trigger_type="condition"
trigger_params={"sensor_index": 0, "min_value": 125.0}
# Optional: "max_value": 300.0
```

## On Complete Actions

| Action | Behavior |
|--------|----------|
| `hold` | Keep current setpoints (default) |
| `zero` | Set all step channels to 0 ul/min |
| `revert` | Return channels to user's base setpoint |

## Confirmation Gates

If `confirm_message` is set, the pipeline pauses before executing the step and shows the message in the UI. The user must click **Confirm** to proceed, or **Skip** to skip the step.

## Groups and Repeat

Steps can be grouped and repeated as a unit:

```python
Step(name="Run-prestab", ..., group="run", repeat=3),
Step(name="Run-stab", ..., group="run", repeat=3),
```

Consecutive steps with the same `group` tag are collected and repeated together. The repeat count is the maximum `repeat` value in the group. The above produces 6 steps: prestab, stab, prestab, stab, prestab, stab.

## Built-in Pipelines

### Drop-Seq
1. **Prerun** — all channels at target flow, volume trigger (75 ul Oil), then zero
2. **Run-prestab** (x3) — Oil only, condition trigger (>= 125 ul/min), confirmation gate
3. **Run-stab** (x3) — all channels, volume trigger (250 ul Oil), then zero

### Priming
Three sequential steps to prime each channel individually with confirmation gates.

## Pipeline Controls

- **Start** — begin executing from step 1
- **Pause** — zero all channels, hold position
- **Resume** — restore setpoints, continue
- **Skip** — skip current step
- **Stop** — abort pipeline, release all channels

## Save / Load

Pipelines can be saved to and loaded from JSON files in the `pipelines/` directory. The pipeline panel allows editing steps inline before saving.
