"""Pipeline panel: editable step blocks, pipeline save/load, control buttons."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from droplegen.config import PIPELINES, SENSOR_CHANNEL_NAMES, Step
from droplegen.controller import Controller
from droplegen.pipeline.engine import PipelineState, PipelineEvent
from droplegen.pipeline.steps import StepStatus


TRIGGER_TYPES = ["time", "volume", "threshold"]
ON_COMPLETE_OPTIONS = ["hold", "zero", "revert"]


class StepBlock(QWidget):
    """Editable grouped block for a single pipeline step."""

    def __init__(self, step_idx: int, step: Step | None = None, on_remove=None):
        super().__init__()
        self._step_idx = step_idx
        self._on_remove = on_remove
        self._flow_inputs: list[QLineEdit] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._group = QGroupBox()
        self._group.setStyleSheet(
            "QGroupBox { border: 1px solid #333; border-radius: 4px; "
            "margin-top: 0px; padding: 6px 8px; }"
        )
        group_layout = QVBoxLayout(self._group)
        group_layout.setContentsMargins(8, 8, 8, 6)
        group_layout.setSpacing(4)

        # --- Header row: index, name, on_complete, remove ---
        header = QHBoxLayout()
        header.setSpacing(6)
        idx_label = QLabel(f"{step_idx + 1}.")
        idx_label.setFont(QFont("", 12, QFont.Weight.Bold))
        idx_label.setFixedWidth(24)
        header.addWidget(idx_label)
        self._idx_label = idx_label

        self._name_input = QLineEdit(step.name if step else "")
        self._name_input.setPlaceholderText("Step name")
        self._name_input.setFixedHeight(24)
        self._name_input.setMaximumWidth(180)
        header.addWidget(self._name_input)

        header.addStretch()

        after_lbl = QLabel("After:")
        after_lbl.setStyleSheet("font-size: 11px; color: gray;")
        header.addWidget(after_lbl)
        self._on_complete_combo = QComboBox()
        self._on_complete_combo.addItems(ON_COMPLETE_OPTIONS)
        self._on_complete_combo.setFixedHeight(24)
        self._on_complete_combo.setFixedWidth(80)
        if step:
            idx = ON_COMPLETE_OPTIONS.index(step.on_complete) if step.on_complete in ON_COMPLETE_OPTIONS else 0
            self._on_complete_combo.setCurrentIndex(idx)
        header.addWidget(self._on_complete_combo)

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet(
            "QPushButton { background: #3a2020; border: 1px solid #552222; "
            "color: #cc4444; font-weight: bold; border-radius: 3px; padding: 0; }"
            "QPushButton:hover { background: #552222; color: #ff4444; }"
        )
        remove_btn.clicked.connect(self._remove_clicked)
        header.addWidget(remove_btn)
        self._remove_btn = remove_btn

        group_layout.addLayout(header)

        # --- Flow setpoint rows ---
        for ch_idx, ch_name in enumerate(SENSOR_CHANNEL_NAMES):
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(f"  {ch_name}:")
            lbl.setStyleSheet("font-size: 11px;")
            lbl.setFixedWidth(120)
            row.addWidget(lbl)

            inp = QLineEdit()
            inp.setFixedHeight(22)
            inp.setFixedWidth(80)
            inp.setPlaceholderText("0")
            if step and ch_idx in step.sensor_setpoints:
                val = step.sensor_setpoints[ch_idx]
                inp.setText(f"{val:g}")
            row.addWidget(inp)

            unit = QLabel("\u00b5l/min")
            unit.setStyleSheet("font-size: 10px; color: gray;")
            row.addWidget(unit)
            row.addStretch()
            self._flow_inputs.append(inp)
            group_layout.addLayout(row)

        # --- Trigger row ---
        trigger_row = QHBoxLayout()
        trigger_row.setSpacing(6)
        trig_lbl = QLabel("  Trigger:")
        trig_lbl.setStyleSheet("font-size: 11px;")
        trig_lbl.setFixedWidth(120)
        trigger_row.addWidget(trig_lbl)

        self._trigger_combo = QComboBox()
        self._trigger_combo.addItems(TRIGGER_TYPES)
        self._trigger_combo.setFixedHeight(22)
        self._trigger_combo.setFixedWidth(120)
        if step:
            idx = TRIGGER_TYPES.index(step.trigger_type) if step.trigger_type in TRIGGER_TYPES else 0
            self._trigger_combo.setCurrentIndex(idx)
        self._trigger_combo.currentTextChanged.connect(self._on_trigger_type_changed)
        trigger_row.addWidget(self._trigger_combo)
        trigger_row.addStretch()
        group_layout.addLayout(trigger_row)

        # --- Trigger params container ---
        self._params_container = QWidget()
        self._params_layout = QHBoxLayout(self._params_container)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._params_layout.setSpacing(6)
        group_layout.addWidget(self._params_container)

        # Create param widgets (will be shown/hidden based on trigger type)
        self._build_trigger_params(step)

        # --- Confirmation row (non-empty = ask before running) ---
        confirm_row = QHBoxLayout()
        confirm_row.setSpacing(6)
        confirm_lbl = QLabel("  Confirm:")
        confirm_lbl.setStyleSheet("font-size: 11px;")
        confirm_lbl.setFixedWidth(120)
        confirm_row.addWidget(confirm_lbl)
        self._confirm_msg_input = QLineEdit()
        self._confirm_msg_input.setFixedHeight(22)
        self._confirm_msg_input.setPlaceholderText("empty = no confirmation")
        if step and step.confirm_message:
            self._confirm_msg_input.setText(step.confirm_message)
        confirm_row.addWidget(self._confirm_msg_input, stretch=1)
        group_layout.addLayout(confirm_row)

        # --- Progress bar + status ---
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        status_row.addWidget(self._progress, stretch=1)

        self._status_label = QLabel("PENDING")
        self._status_label.setStyleSheet("color: gray; font-size: 10px;")
        self._status_label.setFixedWidth(70)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self._status_label)
        group_layout.addLayout(status_row)

        main_layout.addWidget(self._group)

    def _build_trigger_params(self, step: Step | None = None) -> None:
        # Clear existing
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        trigger_type = self._trigger_combo.currentText()
        params = step.trigger_params if step else {}

        spacer_lbl = QLabel("")
        spacer_lbl.setFixedWidth(120)
        self._params_layout.addWidget(spacer_lbl)

        if trigger_type == "time":
            lbl = QLabel("Duration:")
            lbl.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl)
            self._duration_input = QLineEdit()
            self._duration_input.setFixedSize(80, 22)
            self._duration_input.setPlaceholderText("0")
            if params.get("duration_s") is not None:
                self._duration_input.setText(f"{params['duration_s']:g}")
            self._params_layout.addWidget(self._duration_input)
            unit = QLabel("s")
            unit.setStyleSheet("font-size: 10px; color: gray;")
            self._params_layout.addWidget(unit)

        elif trigger_type == "volume":
            lbl = QLabel("Sensor:")
            lbl.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl)
            self._vol_sensor_input = QLineEdit()
            self._vol_sensor_input.setFixedSize(40, 22)
            self._vol_sensor_input.setText(str(params.get("sensor_index", 0)))
            self._params_layout.addWidget(self._vol_sensor_input)
            lbl2 = QLabel("Target:")
            lbl2.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl2)
            self._vol_target_input = QLineEdit()
            self._vol_target_input.setFixedSize(80, 22)
            if params.get("target_volume_ul") is not None:
                self._vol_target_input.setText(f"{params['target_volume_ul']:g}")
            self._params_layout.addWidget(self._vol_target_input)
            unit = QLabel("\u00b5l")
            unit.setStyleSheet("font-size: 10px; color: gray;")
            self._params_layout.addWidget(unit)

        elif trigger_type == "threshold":
            lbl = QLabel("Sensor:")
            lbl.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl)
            self._thresh_sensor_input = QLineEdit()
            self._thresh_sensor_input.setFixedSize(40, 22)
            self._thresh_sensor_input.setText(str(params.get("sensor_index", 0)))
            self._params_layout.addWidget(self._thresh_sensor_input)
            lbl2 = QLabel("Target:")
            lbl2.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl2)
            self._thresh_target_input = QLineEdit()
            self._thresh_target_input.setFixedSize(60, 22)
            if params.get("target") is not None:
                self._thresh_target_input.setText(f"{params['target']:g}")
            self._params_layout.addWidget(self._thresh_target_input)
            lbl3 = QLabel("\u00b1")
            lbl3.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl3)
            self._thresh_tol_input = QLineEdit()
            self._thresh_tol_input.setFixedSize(40, 22)
            self._thresh_tol_input.setText(f"{params.get('tolerance_pct', 5):g}")
            self._params_layout.addWidget(self._thresh_tol_input)
            lbl4 = QLabel("% for")
            lbl4.setStyleSheet("font-size: 11px;")
            self._params_layout.addWidget(lbl4)
            self._thresh_dur_input = QLineEdit()
            self._thresh_dur_input.setFixedSize(40, 22)
            self._thresh_dur_input.setText(f"{params.get('stable_duration_s', 10):g}")
            self._params_layout.addWidget(self._thresh_dur_input)
            lbl5 = QLabel("s")
            lbl5.setStyleSheet("font-size: 10px; color: gray;")
            self._params_layout.addWidget(lbl5)

        self._params_layout.addStretch()

    def _on_trigger_type_changed(self, _text: str) -> None:
        self._build_trigger_params(None)

    def _remove_clicked(self) -> None:
        if self._on_remove:
            self._on_remove(self._step_idx)

    def update_index(self, idx: int) -> None:
        self._step_idx = idx
        self._idx_label.setText(f"{idx + 1}.")

    def to_step(self) -> Step:
        name = self._name_input.text().strip() or f"Step {self._step_idx + 1}"
        setpoints = {}
        for ch_idx, inp in enumerate(self._flow_inputs):
            text = inp.text().strip()
            if text:
                try:
                    val = float(text)
                    if val != 0:
                        setpoints[ch_idx] = val
                except ValueError:
                    pass

        trigger_type = self._trigger_combo.currentText()
        trigger_params = {}

        if trigger_type == "time":
            try:
                trigger_params["duration_s"] = float(self._duration_input.text())
            except (ValueError, AttributeError):
                trigger_params["duration_s"] = 0

        elif trigger_type == "volume":
            try:
                trigger_params["sensor_index"] = int(self._vol_sensor_input.text())
            except (ValueError, AttributeError):
                trigger_params["sensor_index"] = 0
            try:
                trigger_params["target_volume_ul"] = float(self._vol_target_input.text())
            except (ValueError, AttributeError):
                trigger_params["target_volume_ul"] = 0

        elif trigger_type == "threshold":
            try:
                trigger_params["sensor_index"] = int(self._thresh_sensor_input.text())
            except (ValueError, AttributeError):
                trigger_params["sensor_index"] = 0
            try:
                trigger_params["target"] = float(self._thresh_target_input.text())
            except (ValueError, AttributeError):
                trigger_params["target"] = 0
            try:
                trigger_params["tolerance_pct"] = float(self._thresh_tol_input.text())
            except (ValueError, AttributeError):
                trigger_params["tolerance_pct"] = 5.0
            try:
                trigger_params["stable_duration_s"] = float(self._thresh_dur_input.text())
            except (ValueError, AttributeError):
                trigger_params["stable_duration_s"] = 10.0

        on_complete = self._on_complete_combo.currentText()
        confirm_message = self._confirm_msg_input.text().strip()
        return Step(
            name=name,
            sensor_setpoints=setpoints,
            trigger_type=trigger_type,
            trigger_params=trigger_params,
            on_complete=on_complete,
            confirm_message=confirm_message,
        )

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
        self._status_label.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._progress.setValue(int(progress * 1000))

    def set_editing(self, enabled: bool) -> None:
        self._name_input.setEnabled(enabled)
        self._on_complete_combo.setEnabled(enabled)
        self._trigger_combo.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)
        self._confirm_msg_input.setEnabled(enabled)
        for inp in self._flow_inputs:
            inp.setEnabled(enabled)
        # Enable/disable all QLineEdit in params container
        for child in self._params_container.findChildren(QLineEdit):
            child.setEnabled(enabled)


class PipelinePanel(QWidget):
    def __init__(self, controller: Controller):
        super().__init__()
        self._ctrl = controller
        self._step_blocks: list[StepBlock] = []

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
        sel_lbl = QLabel("Template:")
        sel_lbl.setStyleSheet("font-size: 12px;")
        selector_row.addWidget(sel_lbl)
        self._pipeline_combo = QComboBox()
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

        # Save row (next to Proceed per user request)
        save_row = QHBoxLayout()
        self._save_name_input = QLineEdit()
        self._save_name_input.setPlaceholderText("Pipeline name")
        self._save_name_input.setFixedHeight(28)
        save_row.addWidget(self._save_name_input, stretch=1)
        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedHeight(28)
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        # Confirmation message
        self._confirm_label = QLabel("")
        self._confirm_label.setStyleSheet(
            "color: #f39c12; font-size: 12px; padding: 4px; "
            "border: 1px solid #f39c12; border-radius: 3px;"
        )
        self._confirm_label.setWordWrap(True)
        self._confirm_label.hide()
        layout.addWidget(self._confirm_label)

        # Add step button
        self._add_step_btn = QPushButton("+ Add Step")
        self._add_step_btn.setFixedHeight(26)
        self._add_step_btn.clicked.connect(self._on_add_step)
        layout.addWidget(self._add_step_btn)

        # Scroll area for step blocks
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._steps_widget = QWidget()
        self._steps_layout = QVBoxLayout(self._steps_widget)
        self._steps_layout.setSpacing(4)
        self._steps_layout.setContentsMargins(0, 0, 0, 0)
        self._steps_layout.addStretch()
        self._scroll.setWidget(self._steps_widget)

        layout.addWidget(self._scroll, stretch=1)

        self._refresh_combo()
        # Load the first pipeline
        if self._pipeline_combo.count() > 0:
            self._on_pipeline_changed(self._pipeline_combo.currentText())

    def _refresh_combo(self) -> None:
        self._pipeline_combo.blockSignals(True)
        current = self._pipeline_combo.currentText()
        self._pipeline_combo.clear()
        built_in, saved = self._ctrl.get_all_pipeline_names()
        for name in built_in:
            self._pipeline_combo.addItem(name)
        if saved:
            self._pipeline_combo.insertSeparator(self._pipeline_combo.count())
            for name in saved:
                self._pipeline_combo.addItem(name)
        # Restore selection if possible
        idx = self._pipeline_combo.findText(current)
        if idx >= 0:
            self._pipeline_combo.setCurrentIndex(idx)
        self._pipeline_combo.blockSignals(False)

    def _build_step_blocks(self, steps: list[Step]) -> None:
        # Remove existing blocks
        for w in self._step_blocks:
            w.setParent(None)
            w.deleteLater()
        self._step_blocks.clear()

        for i, step in enumerate(steps):
            block = StepBlock(i, step, on_remove=self._on_remove_step)
            # Insert before the stretch
            self._steps_layout.insertWidget(self._steps_layout.count() - 1, block)
            self._step_blocks.append(block)

    def _on_pipeline_changed(self, name: str) -> None:
        state = self._ctrl.pipeline_state
        if state not in (PipelineState.IDLE, PipelineState.COMPLETED, PipelineState.ERROR):
            return
        if not name:
            return
        # Load from built-in or saved
        built_in, saved = self._ctrl.get_all_pipeline_names()
        if name in PIPELINES:
            steps = PIPELINES[name]
        elif name in saved:
            try:
                steps = self._ctrl.load_saved_pipeline(name)
            except Exception:
                return
        else:
            return
        self._build_step_blocks(steps)

    def _on_add_step(self) -> None:
        idx = len(self._step_blocks)
        blank = Step(name="", sensor_setpoints={}, trigger_type="time", trigger_params={"duration_s": 0})
        block = StepBlock(idx, blank, on_remove=self._on_remove_step)
        self._steps_layout.insertWidget(self._steps_layout.count() - 1, block)
        self._step_blocks.append(block)

    def _on_remove_step(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._step_blocks):
            return
        block = self._step_blocks.pop(idx)
        block.setParent(None)
        block.deleteLater()
        # Re-index remaining blocks
        for i, b in enumerate(self._step_blocks):
            b.update_index(i)

    def _on_save(self) -> None:
        name = self._save_name_input.text().strip()
        if not name:
            return
        steps_data = []
        for block in self._step_blocks:
            s = block.to_step()
            d = {
                "name": s.name,
                "sensor_setpoints": {str(k): v for k, v in s.sensor_setpoints.items()},
                "trigger_type": s.trigger_type,
                "trigger_params": s.trigger_params,
                "on_complete": s.on_complete,
            }
            if s.confirm_message:
                d["confirm_message"] = s.confirm_message
            steps_data.append(d)
        self._ctrl.save_pipeline(name, steps_data)
        self._refresh_combo()
        # Select the saved pipeline
        idx = self._pipeline_combo.findText(name)
        if idx >= 0:
            self._pipeline_combo.setCurrentIndex(idx)

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
        self._add_step_btn.setEnabled(not running)
        self._save_btn.setEnabled(not running)
        self._save_name_input.setEnabled(not running)

        # Toggle editing on blocks
        for block in self._step_blocks:
            block.set_editing(not running)

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
                if i < len(self._step_blocks):
                    progress = event.progress if i == event.current_step else (
                        1.0 if step.status == StepStatus.COMPLETED else 0.0
                    )
                    self._step_blocks[i].set_status(step.status, progress)

        if event.state in (PipelineState.COMPLETED, PipelineState.ERROR, PipelineState.IDLE):
            self._start_btn.setEnabled(True)
            self._pipeline_combo.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._pause_btn.setText("Pause")
            self._stop_btn.setEnabled(False)
            self._skip_btn.setEnabled(False)
            self._proceed_btn.setEnabled(False)
            self._confirm_label.hide()
            self._add_step_btn.setEnabled(True)
            self._save_btn.setEnabled(True)
            self._save_name_input.setEnabled(True)
            for block in self._step_blocks:
                block.set_editing(True)

    def _on_start(self) -> None:
        if not self._ctrl.hw_manager.connected:
            return
        # Read steps from blocks
        step_defs = [block.to_step() for block in self._step_blocks]
        if not step_defs:
            return
        # Reset status on all blocks
        for block in self._step_blocks:
            block.set_status(StepStatus.PENDING, 0.0)
        pipeline_steps = self._ctrl.build_pipeline_from_steps(step_defs)
        self._ctrl.start_pipeline(steps=pipeline_steps)

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
