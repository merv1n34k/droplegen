"""Single-window layout - all controls visible at once.

Layout:
  +---------------------------------------------------------------+
  | [Droplegen] [Sim] [Connect] [Disconnect] [Rec]        [ESTOP] |
  +---------------------------------------------------------------+
  |  Channel Control (left)    |  Pipeline (right top)             |
  |  ┌ Oil Flow (M) ────────┐ |  Pipeline: [Drop-Seq v]      IDLE |
  |  │ Flow: 123  [__] Set  │ |  [Start][Pause][Stop][Skip][Proc] |
  |  │ Press: 456 [__] Set  │ |  1. Prime    PENDING  ====        |
  |  └──────────────────────┘  |  2. Stabilize ...                 |
  |                            +-----------------------------------+
  |                            |  Monitor (right bottom)           |
  |                            |  Channel Value Mean .. Vol Stable |
  +---------------------------------------------------------------+
  | [Pressure plot]            | [Flow plot]                       |
  +---------------------------------------------------------------+
  | Status: Connected (simulated) | 3P + 3S                       |
  +---------------------------------------------------------------+
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

import dropletui as ui

from droplegen.controller import Controller
from droplegen.config import UI_REFRESH_INTERVAL_MS, SENSOR_CHANNEL_NAMES
from droplegen.ui.panels.control_panel import ControlPanel
from droplegen.ui.panels.monitor_panel import MonitorPanel
from droplegen.ui.panels.pipeline_panel import PipelinePanel
from droplegen.ui.panels.plot_panel import PlotPanel


class MainWindow(QMainWindow):
    def __init__(self, controller: Controller):
        super().__init__()
        self._ctrl = controller
        self.setWindowTitle("Droplegen - Drop-Seq Control")
        self.resize(1400, 850)
        self.setMinimumSize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(ui.Theme.WINDOW_PADDING, ui.Theme.WINDOW_PADDING, ui.Theme.WINDOW_PADDING, 0)
        root_layout.setSpacing(ui.Theme.SPACE_2)

        # -- Top toolbar --
        self._sim_cb = ui.check_box("Simulated", checked=True)

        self._connect_btn = ui.button("Connect", variant="success")
        self._connect_btn.clicked.connect(self._on_connect)

        self._disconnect_btn = ui.button("Disconnect", variant="danger")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)

        self._rec_btn = ui.button("Record")
        self._rec_btn.setEnabled(False)
        self._rec_btn.clicked.connect(self._toggle_recording)

        self._save_settings_btn = ui.button("Save Settings")
        self._save_settings_btn.setEnabled(False)
        self._save_settings_btn.clicked.connect(self._on_save_settings)

        self._examine_logs_btn = ui.button("Examine Logs")
        self._examine_logs_btn.clicked.connect(self._on_examine_logs)

        self._estop_btn = ui.button("E-STOP", variant="danger", size="large")
        self._estop_btn.clicked.connect(self._on_emergency_stop)

        toolbar = ui.toolbar(
            "Droplegen",
            self._sim_cb,
            self._connect_btn,
            self._disconnect_btn,
            self._rec_btn,
            self._save_settings_btn,
            self._examine_logs_btn,
        )
        toolbar.layout().addWidget(self._estop_btn)

        root_layout.addWidget(toolbar)

        # -- Body: splitters --
        # Vertical splitter: top panels | bottom plots
        # Top row: horizontal splitter -> control | (pipeline / monitor)
        self.control_panel = ControlPanel(controller)

        # Right column: vertical splitter -> pipeline | monitor
        self.pipeline_panel = PipelinePanel(controller)
        self.monitor_panel = MonitorPanel()
        right_splitter = ui.vertical_splitter(
            self.pipeline_panel,
            self.monitor_panel,
            stretch=(1, 1),
            collapse_index=1,
        )
        top_splitter = ui.horizontal_splitter(
            self.control_panel,
            right_splitter,
            stretch=(2, 3),
            collapse_index=0,
        )

        # Bottom: plot panel
        self.plot_panel = PlotPanel()
        body_splitter = ui.vertical_splitter(
            top_splitter,
            self.plot_panel,
            stretch=(3, 2),
            collapse_index=1,
        )

        root_layout.addWidget(body_splitter, stretch=1)

        # -- Status bar --
        self._status_bar = self.statusBar()
        self._status_bar.showMessage("Disconnected")

        # -- Polling timer --
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(UI_REFRESH_INTERVAL_MS)

    # -- System controls --
    def _on_connect(self) -> None:
        try:
            state = self._ctrl.connect(simulated=self._sim_cb.isChecked())
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
            self._rec_btn.setEnabled(True)

            n_p = len(state.pressure_channels)
            n_s = len(state.sensor_channels)
            self.control_panel.setup_channels(n_p, n_s)
            self.monitor_panel.setup_channels(n_p, n_s)
            self._save_settings_btn.setEnabled(True)

            # Auto-load saved settings
            settings = self._ctrl.load_settings()
            if settings:
                self.control_panel.apply_settings(settings)
                # Apply saved regulation response times
                for i, ch_settings in enumerate(settings):
                    resp = ch_settings.get("reg_response", "")
                    if resp and i < len(self._ctrl.channel_manager.channels):
                        try:
                            self._ctrl.set_regulation_response(i, int(resp))
                        except (ValueError, IndexError):
                            pass

            mode = "simulated" if state.simulated else "hardware"
            self._check_sensor_corrections()
            self._status_bar.showMessage(
                f"Connected ({mode})  |  {n_p} pressure + {n_s} sensor channels"
            )
        except Exception as e:
            self._status_bar.showMessage(f"Connection error: {e}")

    def _on_disconnect(self) -> None:
        try:
            self._ctrl.disconnect()
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._rec_btn.setEnabled(False)
            self._rec_btn.setText("Record")
            self._save_settings_btn.setEnabled(False)
            self.control_panel.clear_channels()
            self.plot_panel.clear()
            self._status_bar.showMessage("Disconnected")
        except Exception as e:
            self._status_bar.showMessage(f"Disconnect error: {e}")

    def _toggle_recording(self) -> None:
        if self._ctrl.recording_active:
            self._ctrl.stop_recording()
            self._rec_btn.setText("Record")
        else:
            self._ctrl.start_recording()
            self._rec_btn.setText("Stop Rec")

    def _on_save_settings(self) -> None:
        data = self.control_panel.get_settings()
        self._ctrl.save_settings(data)
        self._status_bar.showMessage("Settings saved", 3000)

    def _on_examine_logs(self) -> None:
        if not hasattr(self, "_log_viewer"):
            from droplegen.ui.log_viewer import LogViewerWindow
            self._log_viewer = LogViewerWindow(self)
        self._log_viewer.show_and_raise()

    def _on_emergency_stop(self) -> None:
        self._ctrl.emergency_stop()
        self._status_bar.showMessage("EMERGENCY STOP - all pressures set to 0")

    def _check_sensor_corrections(self) -> None:
        uncorrected = self._ctrl.get_uncorrected_sensors()
        if not uncorrected:
            return
        names = []
        for idx in uncorrected:
            if idx < len(SENSOR_CHANNEL_NAMES):
                names.append(SENSOR_CHANNEL_NAMES[idx])
            else:
                names.append(f"Sensor {idx}")
        self._status_bar.showMessage(
            f"Warning: no flow correction applied to {', '.join(names)}"
        )

    # -- Polling --
    def _poll(self) -> None:
        try:
            latest = None
            while not self._ctrl.data_queue.empty():
                snapshot = self._ctrl.data_queue.get_nowait()
                latest = snapshot
                # Ingest data into plots without repainting each time
                self.plot_panel.ingest_from_snapshot(snapshot)
            if latest:
                # Update text panels with latest values only
                self.control_panel.update_from_snapshot(latest)
                self.monitor_panel.update_from_snapshot(latest)
                # Single repaint for all ingested data
                self.plot_panel.refresh()
            self.monitor_panel.update_csv_status(
                self._ctrl.csv_logger.filepath,
                self._ctrl.csv_logger.row_count,
            )
        except Exception:
            pass
        try:
            while not self._ctrl.pipeline_queue.empty():
                event = self._ctrl.pipeline_queue.get_nowait()
                self.pipeline_panel.update_from_event(event)
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self._ctrl.disconnect()
        event.accept()
