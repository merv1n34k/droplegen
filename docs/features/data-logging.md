# Data Logging

Droplegen records experimental data to CSV files and persists channel settings.

## CSV Recording

Click **Record** to start logging data. Each row captures a timestamped snapshot:

```csv
timestamp,p0,p1,p2,s0,s1,s2
1700000000.123,500.0,200.0,200.0,250.1,67.2,66.8
```

- `p0..pN` — pressure channels (mbar)
- `s0..sN` — sensor channels (ul/min)

Files are saved to the `logs/` directory with auto-generated timestamps.

Recording can run independently of pipelines. Start/stop recording at any time while the acquisition thread is active.

## Settings Save / Load

Channel settings (setpoints, calibrations) are persisted to `settings.json`:

```json
{
  "channels": [
    {
      "flow_setpoint": 250.0,
      "calibration": "H2O"
    }
  ]
}
```

Settings are automatically loaded when connecting to hardware if `settings.json` exists.

### Save
Settings are saved from the Control Panel. Each channel's current configuration is captured.

### Load
On connect, the Controller checks for `settings.json` and applies saved values to restore the previous session's configuration.
