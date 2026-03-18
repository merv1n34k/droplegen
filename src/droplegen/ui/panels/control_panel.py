"""Channel control widgets with flow + pressure controls."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from droplegen.controller import Controller
from droplegen.config import SENSOR_CHANNEL_NAMES


class ChannelWidget(QWidget):
    """Grouped channel control: flow value+set, pressure value+set, mode label, stop."""

    def __init__(self, name: str, ch_idx: int,
                 set_flow_cb=None, set_pressure_cb=None, stop_cb=None):
        super().__init__()
        self._ch_idx = ch_idx
        self._set_flow_cb = set_flow_cb
        self._set_pressure_cb = set_pressure_cb
        self._stop_cb = stop_cb

        group = QGroupBox(name)
        group.setStyleSheet(
            "QGroupBox { font-size: 13px; font-weight: bold; border: 1px solid #333; "
            "border-radius: 4px; margin-top: 8px; padding-top: 4px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)

        layout = QVBoxLayout(group)
        layout.setContentsMargins(8, 16, 8, 6)
        layout.setSpacing(4)

        # Header row: mode + stop
        header = QHBoxLayout()
        self._mode_label = QLabel("OFF")
        self._mode_label.setStyleSheet("color: gray; font-size: 12px; font-weight: bold;")
        header.addWidget(self._mode_label)
        header.addStretch()
        stop_btn = QPushButton("Stop")
        stop_btn.setFixedHeight(24)
        stop_btn.setStyleSheet(
            "QPushButton { background-color: #c0392b; border-color: #c0392b; color: white; padding: 2px 8px; }"
            "QPushButton:hover { background-color: #e74c3c; }"
        )
        stop_btn.clicked.connect(self._on_stop)
        header.addWidget(stop_btn)
        layout.addLayout(header)

        # Flow row: value + entry + set
        flow_row = QHBoxLayout()
        flow_row.setSpacing(4)
        flow_lbl = QLabel("Flow:")
        flow_lbl.setStyleSheet("font-size: 11px; color: gray;")
        flow_lbl.setMinimumWidth(38)
        flow_row.addWidget(flow_lbl)
        self._flow_value = QLabel("---")
        self._flow_value.setFont(QFont("Courier", 13))
        self._flow_value.setMinimumWidth(70)
        self._flow_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        flow_row.addWidget(self._flow_value)
        unit = QLabel("\u00b5l/min")
        unit.setStyleSheet("color: gray; font-size: 10px;")
        flow_row.addWidget(unit)
        flow_row.addStretch()
        self._flow_entry = QLineEdit()
        self._flow_entry.setPlaceholderText("0.0")
        self._flow_entry.setFixedWidth(60)
        self._flow_entry.returnPressed.connect(self._on_set_flow)
        flow_row.addWidget(self._flow_entry)
        flow_set = QPushButton("Set")
        flow_set.setFixedHeight(24)
        flow_set.clicked.connect(self._on_set_flow)
        flow_row.addWidget(flow_set)
        layout.addLayout(flow_row)

        # Pressure row: value + entry + set
        press_row = QHBoxLayout()
        press_row.setSpacing(4)
        press_lbl = QLabel("Press:")
        press_lbl.setStyleSheet("font-size: 11px; color: gray;")
        press_lbl.setMinimumWidth(38)
        press_row.addWidget(press_lbl)
        self._press_value = QLabel("---")
        self._press_value.setFont(QFont("Courier", 13))
        self._press_value.setMinimumWidth(70)
        self._press_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        press_row.addWidget(self._press_value)
        unit2 = QLabel("mbar")
        unit2.setStyleSheet("color: gray; font-size: 10px;")
        press_row.addWidget(unit2)
        press_row.addStretch()
        self._press_entry = QLineEdit()
        self._press_entry.setPlaceholderText("0.0")
        self._press_entry.setFixedWidth(60)
        self._press_entry.returnPressed.connect(self._on_set_pressure)
        press_row.addWidget(self._press_entry)
        press_set = QPushButton("Set")
        press_set.setFixedHeight(24)
        press_set.clicked.connect(self._on_set_pressure)
        press_row.addWidget(press_set)
        layout.addLayout(press_row)

    def update_values(self, flow: float, pressure: float) -> None:
        self._flow_value.setText(f"{flow:.2f}")
        self._press_value.setText(f"{pressure:.1f}")

    def set_mode(self, mode: str, owner: str = "user") -> None:
        colors = {"off": "gray", "flow": "#27ae60", "pressure": "#e67e22"}
        if owner == "pipeline":
            color = "#2980b9"
            text = "PIPELINE"
        else:
            color = colors.get(mode, "gray")
            text = mode.upper()
        self._mode_label.setText(text)
        self._mode_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    def _on_set_flow(self) -> None:
        try:
            val = float(self._flow_entry.text())
            if self._set_flow_cb:
                self._set_flow_cb(self._ch_idx, val)
        except ValueError:
            pass

    def _on_set_pressure(self) -> None:
        try:
            val = float(self._press_entry.text())
            if self._set_pressure_cb:
                self._set_pressure_cb(self._ch_idx, val)
        except ValueError:
            pass

    def _on_stop(self) -> None:
        if self._stop_cb:
            self._stop_cb(self._ch_idx)


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

        self._placeholder = QLabel("Not connected")
        self._placeholder.setStyleSheet("color: gray;")
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
            widget = ChannelWidget(
                name=name, ch_idx=i,
                set_flow_cb=self._on_set_flow,
                set_pressure_cb=self._on_set_pressure,
                stop_cb=self._on_stop,
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

    def clear_channels(self) -> None:
        for w in self._channel_widgets:
            w.setParent(None)
        self._channel_widgets.clear()
        if self._placeholder:
            self._placeholder.show()
