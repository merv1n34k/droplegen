# Control Panel

The Control Panel provides manual control over each hardware channel.

## Channel Widgets

Each channel has a dedicated widget with:

- **Flow setpoint** — target flow rate in ul/min (uses `fgt_set_sensorRegulation`)
- **Pressure setpoint** — direct pressure in mbar (uses `fgt_set_pressure`)
- **Stop button** — stops regulation on that channel
- **Current readings** — live flow rate and pressure values

Flow and pressure controls are mutually exclusive per channel. Setting a flow setpoint engages sensor regulation; setting pressure directly bypasses it.

## Scrollable Inputs

Setpoint inputs support mouse scroll wheel adjustment for fine-tuning values without typing.

## Sensor Calibration

Each channel's sensor can be calibrated for different fluids:

- Select a built-in calibration (H2O, IPA, HFE, FC40, Oil)
- Or apply custom polynomial scaling coefficients

See [Configuration](/guide/configuration) for available calibration values.

## Custom Scale

For non-standard fluids, set custom polynomial coefficients `(a, b, c)`:

```
scaled_flow = a * raw + b * raw² + c * raw³
```

This is applied via `fgt_set_sensor_custom_scale` in the SDK.

## Emergency Stop

The emergency stop button immediately:

1. Stops any running pipeline
2. Sets all channels to zero pressure
3. Disables all sensor regulation

Use this for any unsafe condition.
