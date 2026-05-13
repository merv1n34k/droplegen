"""Channel control widgets with flow + pressure controls."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import dropletui as ui

from droplegen.controller import Controller
from droplegen.config import SENSOR_CHANNEL_NAMES, SENSOR_CALIBRATIONS


def _small_label(text: str) -> QLabel:
    return ui.status_label(text, kind="muted")


def _spin_text(widget: QDoubleSpinBox | QSpinBox) -> str:
    return f"{widget.value():g}"


class ChannelWidget(QWidget):
    """Grouped channel control: flow value+set, pressure value+set, calibration, mode, stop."""

    def __init__(self, name: str, ch_idx: int,
                 set_flow_cb=None, set_pressure_cb=None, stop_cb=None,
                 set_calibration_cb=None, set_custom_scale_cb=None,
                 set_reg_response_cb=None,
                 flow_step: float = 1.0):
        super().__init__()
        self._ch_idx = ch_idx
        self._set_flow_cb = set_flow_cb
        self._set_pressure_cb = set_pressure_cb
        self._stop_cb = stop_cb
        self._set_calibration_cb = set_calibration_cb
        self._set_custom_scale_cb = set_custom_scale_cb
        self._set_reg_response_cb = set_reg_response_cb

        group, layout = ui.section(name)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)

        # Header row: mode + stop
        header = QHBoxLayout()
        self._mode_label = ui.status_label("OFF", kind="muted", small=False)
        self._mode_kind = "muted"
        header.addWidget(self._mode_label)
        self._header_layout = header
        header.addStretch()
        stop_btn = ui.button("Stop", variant="danger")
        stop_btn.clicked.connect(self._on_stop)
        header.addWidget(stop_btn)
        layout.addLayout(header)

        # Flow row: value + entry + set
        flow_row = QHBoxLayout()
        flow_row.setSpacing(4)
        flow_lbl = _small_label("Flow:")
        flow_row.addWidget(flow_lbl)
        self._flow_value = QLabel("---")
        flow_font = QFont()
        ui.configure_monospace_font(flow_font, 13)
        self._flow_value.setFont(flow_font)
        self._flow_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        flow_row.addWidget(self._flow_value)
        unit = _small_label("\u00b5l/min")
        flow_row.addWidget(unit)
        flow_row.addStretch()
        self._flow_entry = ui.double_box(maximum=1_000_000.0, step=flow_step, decimals=3)
        self._flow_entry.lineEdit().returnPressed.connect(self._on_set_flow)
        flow_row.addWidget(self._flow_entry)
        flow_set = ui.button("Set", size="inline")
        flow_set.clicked.connect(self._on_set_flow)
        flow_row.addWidget(flow_set)
        layout.addLayout(flow_row)

        # Pressure row: value + entry + set
        press_row = QHBoxLayout()
        press_row.setSpacing(4)
        press_lbl = _small_label("Press:")
        press_row.addWidget(press_lbl)
        self._press_value = QLabel("---")
        press_font = QFont()
        ui.configure_monospace_font(press_font, 13)
        self._press_value.setFont(press_font)
        self._press_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        press_row.addWidget(self._press_value)
        unit2 = _small_label("mbar")
        press_row.addWidget(unit2)
        press_row.addStretch()
        self._press_entry = ui.double_box(maximum=1_000_000.0, step=10.0, decimals=1)
        self._press_entry.lineEdit().returnPressed.connect(self._on_set_pressure)
        press_row.addWidget(self._press_entry)
        press_set = ui.button("Set", size="inline")
        press_set.clicked.connect(self._on_set_pressure)
        press_row.addWidget(press_set)
        layout.addLayout(press_row)

        # Calibration row: Fluid [combo] a:[__] b:[__] c:[__] [Apply]
        cal_row = QHBoxLayout()
        cal_row.setSpacing(4)
        cal_lbl = _small_label("Fluid:")
        cal_row.addWidget(cal_lbl)
        self._fluid_combo = ui.combo_box(SENSOR_CALIBRATIONS.keys())
        self._fluid_combo.currentTextChanged.connect(self._on_fluid_changed)
        cal_row.addWidget(self._fluid_combo)
        for coeff in ("a", "b", "c"):
            lbl = _small_label(f"{coeff}:")
            cal_row.addWidget(lbl)
            inp = ui.line_edit()
            inp.setPlaceholderText("1" if coeff == "a" else "0")
            cal_row.addWidget(inp)
            setattr(self, f"_scale_{coeff}", inp)
        apply_btn = ui.button("Apply", size="inline")
        apply_btn.clicked.connect(self._on_apply_custom_scale)
        cal_row.addWidget(apply_btn)
        layout.addLayout(cal_row)

        # Regulation response row: Resp: [__] s [Set]
        resp_row = QHBoxLayout()
        resp_row.setSpacing(4)
        resp_lbl = _small_label("Resp:")
        resp_row.addWidget(resp_lbl)
        self._resp_entry = ui.int_box(minimum=2, maximum=3600, value=2)
        self._resp_entry.lineEdit().returnPressed.connect(self._on_set_reg_response)
        resp_row.addWidget(self._resp_entry)
        resp_unit = _small_label("s")
        resp_row.addWidget(resp_unit)
        resp_row.addStretch()
        resp_set = ui.button("Set", size="inline")
        resp_set.clicked.connect(self._on_set_reg_response)
        resp_row.addWidget(resp_set)
        layout.addLayout(resp_row)

    def update_values(self, flow: float, pressure: float) -> None:
        self._flow_value.setText(f"{flow:.2f}")
        self._press_value.setText(f"{pressure:.1f}")

    def set_mode(self, mode: str, owner: str = "user") -> None:
        kinds = {"off": "muted", "flow": "success", "pressure": "warning"}
        if owner == "pipeline":
            kind = "primary"
            text = "PIPELINE"
        else:
            kind = kinds.get(mode, "muted")
            text = mode.upper()
        if self._mode_kind == kind:
            self._mode_label.setText(text)
            return
        replacement = ui.status_label(text, kind=kind, small=False)
        self._header_layout.replaceWidget(self._mode_label, replacement)
        self._mode_label.deleteLater()
        self._mode_label = replacement
        self._mode_kind = kind

    def _on_set_flow(self) -> None:
        try:
            val = self._flow_entry.value()
            if self._set_flow_cb:
                self._set_flow_cb(self._ch_idx, val)
        except ValueError:
            pass

    def _on_set_pressure(self) -> None:
        try:
            val = self._press_entry.value()
            if self._set_pressure_cb:
                self._set_pressure_cb(self._ch_idx, val)
        except ValueError:
            pass

    def _on_stop(self) -> None:
        if self._stop_cb:
            self._stop_cb(self._ch_idx)

    def _on_fluid_changed(self, fluid_name: str) -> None:
        if self._set_calibration_cb:
            cal_value = SENSOR_CALIBRATIONS.get(fluid_name, 0)
            self._set_calibration_cb(self._ch_idx, cal_value)

    def get_settings(self) -> dict:
        return {
            "flow": _spin_text(self._flow_entry),
            "pressure": _spin_text(self._press_entry),
            "fluid": self._fluid_combo.currentText(),
            "scale_a": self._scale_a.text(),
            "scale_b": self._scale_b.text(),
            "scale_c": self._scale_c.text(),
            "reg_response": _spin_text(self._resp_entry),
        }

    def apply_settings(self, d: dict) -> None:
        try:
            if d.get("flow"):
                self._flow_entry.setValue(float(d["flow"]))
            if d.get("pressure"):
                self._press_entry.setValue(float(d["pressure"]))
        except ValueError:
            pass
        fluid = d.get("fluid", "")
        idx = self._fluid_combo.findText(fluid)
        if idx >= 0:
            self._fluid_combo.setCurrentIndex(idx)
        self._scale_a.setText(d.get("scale_a", ""))
        self._scale_b.setText(d.get("scale_b", ""))
        self._scale_c.setText(d.get("scale_c", ""))
        try:
            if d.get("reg_response"):
                self._resp_entry.setValue(int(d["reg_response"]))
        except ValueError:
            pass

    def _on_set_reg_response(self) -> None:
        try:
            val = self._resp_entry.value()
            if self._set_reg_response_cb:
                self._set_reg_response_cb(self._ch_idx, val)
        except ValueError:
            pass

    def _on_apply_custom_scale(self) -> None:
        if not self._set_custom_scale_cb:
            return
        try:
            a = float(self._scale_a.text() or "1")
            b = float(self._scale_b.text() or "0")
            c = float(self._scale_c.text() or "0")
        except ValueError:
            return
        self._set_custom_scale_cb(self._ch_idx, a, b, c)


class ControlPanel(QWidget):
    def __init__(self, controller: Controller):
        super().__init__()
        self._ctrl = controller
        self._channel_widgets: list[ChannelWidget] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)

        header = QLabel("Channel Control")
        header.setFont(QFont("", 14, QFont.Weight.Bold))
        self._layout.addWidget(header)

        self._placeholder = ui.status_label("Not connected", kind="muted", small=False)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._placeholder)

        self._layout.addStretch()

    def setup_channels(self, pressure_count: int, sensor_count: int) -> None:
        if self._placeholder:
            self._placeholder.hide()
        for w in self._channel_widgets:
            w.setParent(None)
        self._channel_widgets.clear()

        n_pairs = min(pressure_count, sensor_count)
        for i in range(n_pairs):
            name = SENSOR_CHANNEL_NAMES[i] if i < len(SENSOR_CHANNEL_NAMES) else f"Ch {i}"
            flow_step = 1.0 if "(L)" in name else 0.5
            widget = ChannelWidget(
                name=name, ch_idx=i,
                set_flow_cb=self._on_set_flow,
                set_pressure_cb=self._on_set_pressure,
                stop_cb=self._on_stop,
                set_calibration_cb=self._on_set_calibration,
                set_custom_scale_cb=self._on_set_custom_scale,
                set_reg_response_cb=self._on_set_reg_response,
                flow_step=flow_step,
            )
            # Insert before the stretch
            self._layout.insertWidget(self._layout.count() - 1, widget)
            self._channel_widgets.append(widget)

    def update_from_snapshot(self, snapshot) -> None:
        channels = self._ctrl.channel_manager.channels
        for i, widget in enumerate(self._channel_widgets):
            flow = snapshot.flows[i] if i < len(snapshot.flows) else 0.0
            pressure = snapshot.pressures[i] if i < len(snapshot.pressures) else 0.0
            widget.update_values(flow, pressure)
            if i < len(channels):
                ch = channels[i]
                widget.set_mode(ch.mode, ch.owner)

    def _on_set_flow(self, ch_idx: int, value: float) -> None:
        self._ctrl.set_flow_setpoint(ch_idx, value)

    def _on_set_pressure(self, ch_idx: int, value: float) -> None:
        self._ctrl.set_pressure_setpoint(ch_idx, value)

    def _on_stop(self, ch_idx: int) -> None:
        self._ctrl.stop_regulation(ch_idx)

    def _on_set_calibration(self, ch_idx: int, cal_value: int) -> None:
        if self._ctrl.hw_manager.connected:
            sensor_idx = self._ctrl.channel_manager.channels[ch_idx].sensor_index
            self._ctrl.set_sensor_calibration(sensor_idx, cal_value)

    def _on_set_custom_scale(self, ch_idx: int, a: float, b: float, c: float) -> None:
        if self._ctrl.hw_manager.connected:
            sensor_idx = self._ctrl.channel_manager.channels[ch_idx].sensor_index
            self._ctrl.set_sensor_custom_scale(sensor_idx, a, b, c)

    def _on_set_reg_response(self, ch_idx: int, response_time: int) -> None:
        if self._ctrl.hw_manager.connected:
            self._ctrl.set_regulation_response(ch_idx, response_time)

    def get_settings(self) -> list[dict]:
        return [w.get_settings() for w in self._channel_widgets]

    def apply_settings(self, channels: list[dict]) -> None:
        for i, d in enumerate(channels):
            if i < len(self._channel_widgets):
                self._channel_widgets[i].apply_settings(d)

    def clear_channels(self) -> None:
        for w in self._channel_widgets:
            w.setParent(None)
        self._channel_widgets.clear()
        if self._placeholder:
            self._placeholder.show()
