# Getting Started

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Fluigent SDK (bundled in `fgt-SDK/`)

### macOS (Apple Silicon)

The Fluigent native library (`libfgt_SDK.dylib`) is x86_64 only. On Apple Silicon Macs, the app runs under Rosetta 2 using an x86_64 Python interpreter:

```bash
uv python install 3.12-x86_64
UV_PYTHON=3.12-x86_64 uv venv
```

## Installation

```bash
make setup
```

This runs `uv sync` to install all dependencies into a virtual environment.

## Running the App

```bash
make dev
```

This launches the PyQt6 GUI. On startup you can connect to hardware or use simulated mode.

## Simulated Mode

Droplegen supports Fluigent's simulated instruments for development and testing without physical hardware. When connecting, choose the **Simulated** option.

Simulated mode creates three virtual LineUP instruments:

| Channel | Sensor Type | Role |
|---------|-------------|------|
| Oil | Flow Unit L | Carrier oil |
| Cells | Flow Unit M | Cell suspension |
| Beads | Flow Unit M | Barcoded beads |

All pipeline features, monitoring, and data logging work identically in simulated mode. Sensor readings are scaled to match real hardware ranges (L: 0-5000 ul/min, M: 0-80 ul/min).

## Development Workflow

The intended workflow is to develop on macOS and run on a Windows/Linux machine with actual Fluigent hardware connected:

1. Develop and test with simulated instruments on macOS
2. Push to GitHub
3. Pull and run on the hardware machine

## Next Steps

- [Architecture](/guide/architecture) — understand the 3-thread model
- [Configuration](/guide/configuration) — tune timing, sensors, and calibration
- [Control Panel](/features/control-panel) — manual channel control
- [Pipelines](/features/pipelines) — automated step sequences
