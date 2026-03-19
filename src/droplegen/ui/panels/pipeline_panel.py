"""Pipeline panel: pipeline selector, step rows, progress, control buttons, confirmation UI."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from droplegen.controller import Controller
from droplegen.pipeline.engine import PipelineState, PipelineEvent
from droplegen.pipeline.steps import StepStatus


class StepRow(QWidget):
    """Compact single-row step display."""

    def __init__(self, step_idx: int, name: str, trigger_desc: str):
        super().__init__()
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        self._name_label = QLabel(f"{step_idx + 1}. {name}")
        self._name_label.setFont(QFont("", 12, QFont.Weight.Bold))
        self._name_label.setMinimumWidth(60)
        layout.addWidget(self._name_label)

        self._trigger_label = QLabel(trigger_desc)
        self._trigger_label.setStyleSheet("color: gray; font-size: 10px;")
        self._trigger_label.setWordWrap(True)
        layout.addWidget(self._trigger_label, stretch=1)

        self._progress = QProgressBar()
        self._progress.setFixedSize(80, 8)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._status_label = QLabel("PENDING")
        self._status_label.setStyleSheet("color: gray; font-size: 11px;")
        self._status_label.setFixedWidth(70)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

    def set_status(self, status: StepStatus, progress: float = 0.0) -> None:
        colors = {
            StepStatus.PENDING: "gray",
            StepStatus.RUNNING: "#f39c12",
            StepStatus.COMPLETED: "#27ae60",
            StepStatus.SKIPPED: "#7f8c8d",
            StepStatus.ERROR: "#e74c3c",
        }
        color = colors.get(status, "gray")
        self._status_label.setText(status.value.upper())
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._progress.setValue(int(progress * 1000))


class PipelinePanel(QWidget):
    def __init__(self, controller: Controller):
        super().__init__()
        self._ctrl = controller
        self._step_rows: list[StepRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Header + state
        header_row = QHBoxLayout()
        header_lbl = QLabel("Pipeline")
        header_lbl.setFont(QFont("", 14, QFont.Weight.Bold))
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        self._state_label = QLabel("IDLE")
        self._state_label.setStyleSheet("color: gray; font-size: 12px;")
        header_row.addWidget(self._state_label)
        layout.addLayout(header_row)

        # Pipeline selector
        selector_row = QHBoxLayout()
        sel_lbl = QLabel("Pipeline:")
        sel_lbl.setStyleSheet("font-size: 12px;")
        selector_row.addWidget(sel_lbl)
        self._pipeline_combo = QComboBox()
        for name in self._ctrl.get_pipeline_names():
            self._pipeline_combo.addItem(name)
        self._pipeline_combo.currentTextChanged.connect(self._on_pipeline_changed)
        selector_row.addWidget(self._pipeline_combo, stretch=1)
        layout.addLayout(selector_row)

        # Buttons
        btn_row = QHBoxLayout()

        self._start_btn = QPushButton("Start")
        self._start_btn.setFixedHeight(28)
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setFixedHeight(28)
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause)
        btn_row.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedHeight(28)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; border-color: #c0392b; color: white; }"
            "QPushButton:hover { background-color: #e74c3c; }"
            "QPushButton:disabled { background-color: #222222; border-color: #2a2a2a; color: #555555; }"
        )
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setFixedHeight(28)
        self._skip_btn.setEnabled(False)
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        self._proceed_btn = QPushButton("Proceed")
        self._proceed_btn.setFixedHeight(28)
        self._proceed_btn.setEnabled(False)
        self._proceed_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; border-color: #27ae60; color: white; }"
            "QPushButton:hover { background-color: #2ecc71; }"
            "QPushButton:disabled { background-color: #222222; border-color: #2a2a2a; color: #555555; }"
        )
        self._proceed_btn.clicked.connect(self._on_proceed)
        btn_row.addWidget(self._proceed_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Confirmation message
        self._confirm_label = QLabel("")
        self._confirm_label.setStyleSheet(
            "color: #f39c12; font-size: 12px; padding: 4px; "
            "border: 1px solid #f39c12; border-radius: 3px;"
        )
        self._confirm_label.setWordWrap(True)
        self._confirm_label.hide()
        layout.addWidget(self._confirm_label)

        # Step rows container
        self._steps_layout = QVBoxLayout()
        self._steps_layout.setSpacing(2)
        layout.addLayout(self._steps_layout)
        layout.addStretch()

        self._build_step_rows()

    def _build_step_rows(self) -> None:
        for w in self._step_rows:
            w.setParent(None)
        self._step_rows.clear()

        name = self._pipeline_combo.currentText()
        if not name:
            return
        steps = self._ctrl.build_pipeline(name)
        for i, step in enumerate(steps):
            row = StepRow(i, step.name, step.trigger.description())
            self._steps_layout.addWidget(row)
            self._step_rows.append(row)

    def update_from_event(self, event: PipelineEvent) -> None:
        state_colors = {
            PipelineState.IDLE: "gray",
            PipelineState.RUNNING: "#27ae60",
            PipelineState.PAUSED: "#f39c12",
            PipelineState.STOPPING: "#e67e22",
            PipelineState.COMPLETED: "#2980b9",
            PipelineState.ERROR: "#e74c3c",
        }
        color = state_colors.get(event.state, "gray")
        self._state_label.setText(event.state.value.upper())
        self._state_label.setStyleSheet(f"color: {color}; font-size: 12px;")

        running = event.state in (PipelineState.RUNNING, PipelineState.PAUSED)
        self._start_btn.setEnabled(not running)
        self._pipeline_combo.setEnabled(not running)
        self._pause_btn.setEnabled(running)
        self._pause_btn.setText(
            "Resume" if event.state == PipelineState.PAUSED else "Pause"
        )
        self._stop_btn.setEnabled(running)
        self._skip_btn.setEnabled(event.state == PipelineState.RUNNING)

        # Confirmation UI
        if event.confirmation_message and event.state == PipelineState.RUNNING:
            self._confirm_label.setText(event.confirmation_message)
            self._confirm_label.show()
            self._proceed_btn.setEnabled(True)
        else:
            self._confirm_label.hide()
            self._proceed_btn.setEnabled(False)

        steps = self._ctrl.pipeline_steps
        if steps:
            for i, step in enumerate(steps):
                if i < len(self._step_rows):
                    progress = event.progress if i == event.current_step else (
                        1.0 if step.status == StepStatus.COMPLETED else 0.0
                    )
                    self._step_rows[i].set_status(step.status, progress)

        if event.state in (PipelineState.COMPLETED, PipelineState.ERROR, PipelineState.IDLE):
            self._start_btn.setEnabled(True)
            self._pipeline_combo.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._pause_btn.setText("Pause")
            self._stop_btn.setEnabled(False)
            self._skip_btn.setEnabled(False)
            self._proceed_btn.setEnabled(False)
            self._confirm_label.hide()

    def _on_pipeline_changed(self, name: str) -> None:
        state = self._ctrl.pipeline_state
        if state in (PipelineState.IDLE, PipelineState.COMPLETED, PipelineState.ERROR):
            self._build_step_rows()

    def _on_start(self) -> None:
        if not self._ctrl.hw_manager.connected:
            return
        self._build_step_rows()
        name = self._pipeline_combo.currentText()
        self._ctrl.start_pipeline(name=name)

    def _on_pause(self) -> None:
        if self._ctrl.pipeline_state == PipelineState.PAUSED:
            self._ctrl.resume_pipeline()
        else:
            self._ctrl.pause_pipeline()

    def _on_stop(self) -> None:
        self._ctrl.stop_pipeline()

    def _on_skip(self) -> None:
        self._ctrl.skip_pipeline_step()

    def _on_proceed(self) -> None:
        self._ctrl.confirm_pipeline_step()
