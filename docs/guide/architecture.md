# Architecture

Droplegen uses a 3-thread architecture with a central Controller mediator.

## Thread Model

```
┌─────────────────────────────────────────────────┐
│                  Main Thread (Qt)                │
│  ┌───────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Control   │ │ Pipeline │ │    Monitor     │  │
│  │  Panel     │ │  Panel   │ │    Panel       │  │
│  └─────┬─────┘ └────┬─────┘ └───────┬────────┘  │
│        │             │               │           │
│        └─────────────┼───────────────┘           │
│                      │                           │
│              ┌───────┴────────┐                  │
│              │   Controller   │                  │
│              └───────┬────────┘                  │
└──────────────────────┼───────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
   ┌────────────┐ ┌─────────┐ ┌──────────┐
   │ Acquisition│ │Pipeline │ │ Hardware │
   │  Thread    │ │ Engine  │ │ Manager  │
   │ (100ms)    │ │ Thread  │ │          │
   └────────────┘ └─────────┘ └──────────┘
```

### Main Thread
The Qt event loop runs all UI panels. A `QTimer` at 150ms polls the data queue and updates widgets.

### Acquisition Thread
Polls Fluigent sensors every 100ms. Pushes `DataSnapshot` objects into a thread-safe queue. Optionally writes to CSV when recording is active.

### Pipeline Engine Thread
Executes pipeline steps sequentially. Each step sets flow regulation setpoints and evaluates its trigger condition at 200ms intervals. Communicates state changes via `PipelineEvent` objects in a separate queue.

## Controller (Mediator)

The `Controller` class is the central coordinator. It owns:

- **FluigentSDK** — ctypes wrapper around the native Fluigent library
- **HardwareManager** — connection lifecycle, instrument detection
- **ChannelManager** — per-channel flow regulation with pipeline/user priority
- **AcquisitionThread** — sensor polling
- **PipelineEngine** — step execution
- **CsvLogger** — data recording

UI panels never interact with the backend directly. All actions go through the Controller.

## Data Flow

```
Sensors ──► Acquisition ──► DataQueue ──► UI Timer ──► Panels
                │
                └──► CsvLogger (if recording)

User ──► Controller ──► ChannelManager ──► SDK ──► Hardware
                │
Pipeline ──► Controller ──► ChannelManager
```

## Channel Manager Priority

The ChannelManager maintains two setpoint layers:

1. **User setpoint** — set manually from the Control Panel
2. **Pipeline setpoint** — set by the active pipeline step

When a pipeline is running, pipeline setpoints take priority. When the pipeline releases a channel (step completes with `on_complete: "revert"`), the channel reverts to the user's base setpoint.

## Source Structure

```
src/droplegen/
├── __main__.py              # Entry point
├── app.py                   # QApplication setup
├── config.py                # Constants, Step dataclass, built-in pipelines
├── controller.py            # Central mediator
├── backend/
│   ├── sdk_wrapper.py       # Fluigent SDK ctypes wrapper
│   ├── hardware_manager.py  # Connection lifecycle
│   ├── channel_manager.py   # Per-channel regulation
│   └── acquisition.py       # Sensor polling thread
├── pipeline/
│   ├── engine.py            # Pipeline executor thread
│   ├── steps.py             # PipelineStep dataclass
│   └── triggers.py          # Trigger implementations
├── logger/
│   └── csv_logger.py        # CSV data recording
└── ui/
    ├── main_window.py       # Main window layout
    └── panels/
        ├── control_panel.py   # Channel controls
        ├── pipeline_panel.py  # Pipeline management
        ├── monitor_panel.py   # Stats table
        └── plot_panel.py      # Real-time plots
```
