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
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QLabel,
)

from droplegen.controller import Controller
from droplegen.config import UI_REFRESH_INTERVAL_MS
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
        root_layout.setContentsMargins(6, 6, 6, 0)
        root_layout.setSpacing(6)

        # -- Top toolbar --
        toolbar = QWidget()
        toolbar.setFixedHeight(44)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(6, 4, 6, 4)
        tb_layout.setSpacing(6)

        title = QLabel("Droplegen")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        tb_layout.addWidget(title)

        self._sim_cb = QCheckBox("Sim")
        self._sim_cb.setChecked(True)
        tb_layout.addWidget(self._sim_cb)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setFixedHeight(28)
        self._connect_btn.clicked.connect(self._on_connect)
        tb_layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setFixedHeight(28)
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        tb_layout.addWidget(self._disconnect_btn)

        self._rec_btn = QPushButton("Record")
        self._rec_btn.setFixedHeight(28)
        self._rec_btn.setEnabled(False)
        self._rec_btn.clicked.connect(self._toggle_recording)
        tb_layout.addWidget(self._rec_btn)

        tb_layout.addStretch()

        self._estop_btn = QPushButton("E-STOP")
        self._estop_btn.setFixedHeight(28)
        self._estop_btn.setFont(QFont("", 13, QFont.Weight.Bold))
        self._estop_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; border-color: #c0392b; color: white; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        self._estop_btn.clicked.connect(self._on_emergency_stop)
        tb_layout.addWidget(self._estop_btn)

        root_layout.addWidget(toolbar)

        # -- Body: splitters --
        # Vertical splitter: top panels | bottom plots
        body_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top row: horizontal splitter -> control | (pipeline / monitor)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.control_panel = ControlPanel(controller)
        top_splitter.addWidget(self.control_panel)

        # Right column: vertical splitter -> pipeline | monitor
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.pipeline_panel = PipelinePanel(controller)
        right_splitter.addWidget(self.pipeline_panel)

        self.monitor_panel = MonitorPanel()
        right_splitter.addWidget(self.monitor_panel)

        right_splitter.setStretchFactor(0, 1)
        right_splitter.setStretchFactor(1, 1)

        top_splitter.addWidget(right_splitter)
        top_splitter.setStretchFactor(0, 2)
        top_splitter.setStretchFactor(1, 3)

        body_splitter.addWidget(top_splitter)

        # Bottom: plot panel
        self.plot_panel = PlotPanel()
        body_splitter.addWidget(self.plot_panel)

        body_splitter.setStretchFactor(0, 3)
        body_splitter.setStretchFactor(1, 2)

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

            mode = "simulated" if state.simulated else "hardware"
            self._status_bar.setStyleSheet("color: #27ae60;")
            self._status_bar.showMessage(
                f"Connected ({mode})  |  {n_p} pressure + {n_s} sensor channels"
            )
        except Exception as e:
            self._status_bar.setStyleSheet("color: #e74c3c;")
            self._status_bar.showMessage(f"Connection error: {e}")

    def _on_disconnect(self) -> None:
        try:
            self._ctrl.disconnect()
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)
            self._rec_btn.setEnabled(False)
            self._rec_btn.setText("Record")
            self.control_panel.clear_channels()
            self.plot_panel.clear()
            self._status_bar.setStyleSheet("color: #888888;")
            self._status_bar.showMessage("Disconnected")
        except Exception as e:
            self._status_bar.setStyleSheet("color: #e74c3c;")
            self._status_bar.showMessage(f"Disconnect error: {e}")

    def _toggle_recording(self) -> None:
        if self._ctrl.recording_active:
            self._ctrl.stop_recording()
            self._rec_btn.setText("Record")
        else:
            self._ctrl.start_recording()
            self._rec_btn.setText("Stop Rec")

    def _on_emergency_stop(self) -> None:
        self._ctrl.emergency_stop()
        self._status_bar.setStyleSheet("color: #e74c3c;")
        self._status_bar.showMessage("EMERGENCY STOP - all pressures set to 0")

    # -- Polling --
    def _poll(self) -> None:
        try:
            while not self._ctrl.data_queue.empty():
                snapshot = self._ctrl.data_queue.get_nowait()
                self.control_panel.update_from_snapshot(snapshot)
                self.monitor_panel.update_from_snapshot(snapshot)
                self.plot_panel.update_from_snapshot(snapshot)
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
