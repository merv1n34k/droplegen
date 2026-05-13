"""Pipeline panel: editable step blocks, pipeline save/load, control buttons."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import dropletui as ui

from droplegen.config import PIPELINES, SENSOR_CHANNEL_NAMES, Step
from droplegen.controller import Controller
from droplegen.pipeline.engine import PipelineState, PipelineEvent
from droplegen.pipeline.steps import StepStatus


TRIGGER_TYPES = ["time", "volume", "threshold", "condition"]
ON_COMPLETE_OPTIONS = ["hold", "zero", "revert"]


def _label(text: str, *, kind: str = "muted") -> QLabel:
    return ui.status_label(text, kind=kind)


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

        self._group, group_layout = ui.section("")

        # --- Header row: index, name, on_complete, remove ---
        header = QHBoxLayout()
        header.setSpacing(6)
        idx_label = QLabel(f"{step_idx + 1}.")
        idx_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header.addWidget(idx_label)
        self._idx_label = idx_label

        self._name_input = ui.line_edit(step.name if step else "", placeholder="Step name")
        self._name_input.setPlaceholderText("Step name")
        header.addWidget(self._name_input)

        header.addStretch()

        repeat_lbl = _label("Rep:")
        header.addWidget(repeat_lbl)
        self._repeat_input = ui.line_edit(placeholder="1")
        if step and step.repeat > 1:
            self._repeat_input.setText(str(step.repeat))
        header.addWidget(self._repeat_input)

        group_lbl = _label("Grp:")
        header.addWidget(group_lbl)
        self._group_input = ui.line_edit()
        self._group_input.setPlaceholderText("")
        if step and step.group:
            self._group_input.setText(step.group)
        header.addWidget(self._group_input)

        after_lbl = _label("After:")
        header.addWidget(after_lbl)
        self._on_complete_combo = ui.combo_box(ON_COMPLETE_OPTIONS)
        if step:
            idx = ON_COMPLETE_OPTIONS.index(step.on_complete) if step.on_complete in ON_COMPLETE_OPTIONS else 0
            self._on_complete_combo.setCurrentIndex(idx)
        header.addWidget(self._on_complete_combo)

        remove_btn = ui.button("X", variant="danger", size="inline")
        remove_btn.clicked.connect(self._remove_clicked)
        header.addWidget(remove_btn)
        self._remove_btn = remove_btn

        group_layout.addLayout(header)

        # --- Flow setpoint rows ---
        for ch_idx, ch_name in enumerate(SENSOR_CHANNEL_NAMES):
            row = QHBoxLayout()
            row.setSpacing(4)
            lbl = _label(f"  {ch_name}:", kind="default")
            row.addWidget(lbl)

            inp = ui.line_edit(placeholder="0")
            if step and ch_idx in step.sensor_setpoints:
                val = step.sensor_setpoints[ch_idx]
                inp.setText(f"{val:g}")
            row.addWidget(inp)

            unit = _label("\u00b5l/min")
            row.addWidget(unit)
            row.addStretch()
            self._flow_inputs.append(inp)
            group_layout.addLayout(row)

        # --- Trigger row ---
        trigger_row = QHBoxLayout()
        trigger_row.setSpacing(6)
        trig_lbl = _label("  Trigger:", kind="default")
        trigger_row.addWidget(trig_lbl)

        self._trigger_combo = ui.combo_box(TRIGGER_TYPES)
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
        confirm_lbl = _label("  Confirm:", kind="default")
        confirm_row.addWidget(confirm_lbl)
        self._confirm_msg_input = ui.line_edit(placeholder="empty = no confirmation")
        if step and step.confirm_message:
            self._confirm_msg_input.setText(step.confirm_message)
        confirm_row.addWidget(self._confirm_msg_input, stretch=1)
        group_layout.addLayout(confirm_row)

        # --- Progress bar + status ---
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._status_row = status_row
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        status_row.addWidget(self._progress, stretch=1)

        self._status_label = ui.status_label("PENDING")
        self._status_kind = "muted"
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
        self._params_layout.addWidget(spacer_lbl)

        if trigger_type == "time":
            lbl = _label("Duration:", kind="default")
            self._params_layout.addWidget(lbl)
            self._duration_input = ui.line_edit(placeholder="0")
            if params.get("duration_s") is not None:
                self._duration_input.setText(f"{params['duration_s']:g}")
            self._params_layout.addWidget(self._duration_input)
            unit = _label("s")
            self._params_layout.addWidget(unit)

        elif trigger_type == "volume":
            lbl = _label("Sensor:", kind="default")
            self._params_layout.addWidget(lbl)
            self._vol_sensor_input = ui.line_edit()
            self._vol_sensor_input.setText(str(params.get("sensor_index", 0)))
            self._params_layout.addWidget(self._vol_sensor_input)
            lbl2 = _label("Target:", kind="default")
            self._params_layout.addWidget(lbl2)
            self._vol_target_input = ui.line_edit()
            if params.get("target_volume_ul") is not None:
                self._vol_target_input.setText(f"{params['target_volume_ul']:g}")
            self._params_layout.addWidget(self._vol_target_input)
            unit = _label("\u00b5l")
            self._params_layout.addWidget(unit)

        elif trigger_type == "threshold":
            lbl = _label("Sensor:", kind="default")
            self._params_layout.addWidget(lbl)
            self._thresh_sensor_input = ui.line_edit()
            self._thresh_sensor_input.setText(str(params.get("sensor_index", 0)))
            self._params_layout.addWidget(self._thresh_sensor_input)
            lbl2 = _label("Target:", kind="default")
            self._params_layout.addWidget(lbl2)
            self._thresh_target_input = ui.line_edit()
            if params.get("target") is not None:
                self._thresh_target_input.setText(f"{params['target']:g}")
            self._params_layout.addWidget(self._thresh_target_input)
            lbl3 = _label("\u00b1", kind="default")
            self._params_layout.addWidget(lbl3)
            self._thresh_tol_input = ui.line_edit()
            self._thresh_tol_input.setText(f"{params.get('tolerance_pct', 5):g}")
            self._params_layout.addWidget(self._thresh_tol_input)
            lbl4 = _label("% for", kind="default")
            self._params_layout.addWidget(lbl4)
            self._thresh_dur_input = ui.line_edit()
            self._thresh_dur_input.setText(f"{params.get('stable_duration_s', 10):g}")
            self._params_layout.addWidget(self._thresh_dur_input)
            lbl5 = _label("s")
            self._params_layout.addWidget(lbl5)

        elif trigger_type == "condition":
            lbl = _label("Sensor:", kind="default")
            self._params_layout.addWidget(lbl)
            self._cond_sensor_input = ui.line_edit()
            self._cond_sensor_input.setText(str(params.get("sensor_index", 0)))
            self._params_layout.addWidget(self._cond_sensor_input)
            lbl2 = _label(">=", kind="default")
            self._params_layout.addWidget(lbl2)
            self._cond_min_input = ui.line_edit(placeholder="min")
            if params.get("min_value") is not None:
                self._cond_min_input.setText(f"{params['min_value']:g}")
            self._params_layout.addWidget(self._cond_min_input)
            lbl3 = _label("<=", kind="default")
            self._params_layout.addWidget(lbl3)
            self._cond_max_input = ui.line_edit(placeholder="max")
            if params.get("max_value") is not None:
                self._cond_max_input.setText(f"{params['max_value']:g}")
            self._params_layout.addWidget(self._cond_max_input)
            unit = _label("µl/min")
            self._params_layout.addWidget(unit)

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
                    setpoints[ch_idx] = float(text)
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

        elif trigger_type == "condition":
            try:
                trigger_params["sensor_index"] = int(self._cond_sensor_input.text())
            except (ValueError, AttributeError):
                trigger_params["sensor_index"] = 0
            min_text = self._cond_min_input.text().strip()
            if min_text:
                try:
                    trigger_params["min_value"] = float(min_text)
                except ValueError:
                    pass
            max_text = self._cond_max_input.text().strip()
            if max_text:
                try:
                    trigger_params["max_value"] = float(max_text)
                except ValueError:
                    pass

        on_complete = self._on_complete_combo.currentText()
        confirm_message = self._confirm_msg_input.text().strip()
        try:
            repeat = max(1, int(self._repeat_input.text()))
        except (ValueError, AttributeError):
            repeat = 1
        group = self._group_input.text().strip()
        return Step(
            name=name,
            sensor_setpoints=setpoints,
            trigger_type=trigger_type,
            trigger_params=trigger_params,
            on_complete=on_complete,
            confirm_message=confirm_message,
            repeat=repeat,
            group=group,
        )

    def set_status(self, status: StepStatus, progress: float = 0.0) -> None:
        kinds = {
            StepStatus.PENDING: "muted",
            StepStatus.RUNNING: "warning",
            StepStatus.COMPLETED: "success",
            StepStatus.SKIPPED: "subtle",
            StepStatus.ERROR: "danger",
        }
        text = status.value.upper()
        kind = kinds.get(status, "muted")
        if self._status_kind == kind:
            self._status_label.setText(text)
            self._progress.setValue(int(progress * 1000))
            return
        replacement = ui.status_label(text, kind=kind)
        replacement.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_row.replaceWidget(self._status_label, replacement)
        self._status_label.deleteLater()
        self._status_label = replacement
        self._status_kind = kind
        self._progress.setValue(int(progress * 1000))

    def set_editing(self, enabled: bool) -> None:
        self._name_input.setEnabled(enabled)
        self._on_complete_combo.setEnabled(enabled)
        self._trigger_combo.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)
        self._confirm_msg_input.setEnabled(enabled)
        self._repeat_input.setEnabled(enabled)
        self._group_input.setEnabled(enabled)
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
        self._active_confirm_msg = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Header + state
        header_row = QHBoxLayout()
        header_lbl = QLabel("Pipeline")
        header_lbl.setFont(QFont("", 14, QFont.Weight.Bold))
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        self._state_label = ui.status_label("IDLE")
        self._state_kind = "muted"
        header_row.addWidget(self._state_label)
        self._header_row = header_row
        layout.addLayout(header_row)

        # Pipeline selector
        selector_row = QHBoxLayout()
        sel_lbl = _label("Template:", kind="default")
        selector_row.addWidget(sel_lbl)
        self._pipeline_combo = ui.combo_box()
        self._pipeline_combo.currentTextChanged.connect(self._on_pipeline_changed)
        selector_row.addWidget(self._pipeline_combo, stretch=1)
        layout.addLayout(selector_row)

        # Buttons
        btn_row = QHBoxLayout()

        self._start_btn = ui.button("Start", variant="success")
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        self._pause_btn = ui.button("Pause")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._on_pause)
        btn_row.addWidget(self._pause_btn)

        self._stop_btn = ui.button("Stop", variant="danger")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        self._skip_btn = ui.button("Skip")
        self._skip_btn.setEnabled(False)
        self._skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self._skip_btn)

        self._proceed_btn = ui.button("Proceed", variant="success")
        self._proceed_btn.setEnabled(False)
        self._proceed_btn.clicked.connect(self._on_proceed)
        btn_row.addWidget(self._proceed_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Save row (next to Proceed per user request)
        save_row = QHBoxLayout()
        self._save_name_input = ui.line_edit(placeholder="Pipeline name")
        save_row.addWidget(self._save_name_input, stretch=1)
        self._save_btn = ui.button("Save", variant="primary")
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

        # Confirmation message
        self._confirm_label = ui.status_label("", kind="warning", small=False)
        self._confirm_label.setWordWrap(True)
        self._confirm_label.hide()
        layout.addWidget(self._confirm_label)

        # Add step button
        self._add_step_btn = ui.button("+ Add Step", variant="primary")
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
            if s.repeat > 1:
                d["repeat"] = s.repeat
            if s.group:
                d["group"] = s.group
            steps_data.append(d)
        self._ctrl.save_pipeline(name, steps_data)
        self._refresh_combo()
        # Select the saved pipeline
        idx = self._pipeline_combo.findText(name)
        if idx >= 0:
            self._pipeline_combo.setCurrentIndex(idx)

    def update_from_event(self, event: PipelineEvent) -> None:
        state_kinds = {
            PipelineState.IDLE: "muted",
            PipelineState.RUNNING: "success",
            PipelineState.PAUSED: "warning",
            PipelineState.STOPPING: "warning",
            PipelineState.COMPLETED: "primary",
            PipelineState.ERROR: "danger",
        }
        text = event.state.value.upper()
        kind = state_kinds.get(event.state, "muted")
        if self._state_kind == kind:
            self._state_label.setText(text)
        else:
            replacement = ui.status_label(text, kind=kind)
            self._header_row.replaceWidget(self._state_label, replacement)
            self._state_label.deleteLater()
            self._state_label = replacement
            self._state_kind = kind

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

        # Confirmation UI — track active message across pause/resume
        if event.confirmation_message:
            self._active_confirm_msg = event.confirmation_message
        elif event.state not in (PipelineState.PAUSED,):
            self._active_confirm_msg = ""

        if self._active_confirm_msg and event.state in (PipelineState.RUNNING, PipelineState.PAUSED):
            self._confirm_label.setText(self._active_confirm_msg)
            self._confirm_label.show()
            self._proceed_btn.setEnabled(event.state == PipelineState.RUNNING)
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
