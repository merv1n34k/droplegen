# Monitoring

The Monitor Panel displays real-time statistics for all channels.

## Stats Table

Each channel row shows:

| Column | Description |
|--------|-------------|
| Channel | Channel name |
| Flow (ul/min) | Current flow rate |
| Pressure (mbar) | Current pressure |
| Mean | Rolling mean flow rate |
| Std Dev | Rolling standard deviation |
| Volume (ul) | Cumulative dispensed volume |
| Stable | Stability indicator |

Statistics are computed over a rolling window of 300 samples (30 seconds at 100ms acquisition).

## Cumulative Volume

Volume is tracked by integrating flow rate over time in the acquisition thread. Each sensor maintains an independent volume accumulator that resets when acquisition starts.

## Stability Detection

A channel is considered **stable** when its flow rate stays within a tolerance band for a sustained duration:

- **Tolerance**: ±2.0 ul/min
- **Duration**: 5.0 seconds (50 samples)

The stability indicator updates in real-time on the monitor table.

## Real-Time Plots

The Plot Panel shows live graphs of flow rate and pressure for all channels. Data is updated at the UI refresh interval (150ms).

Plots use a scrolling time window showing recent history.
