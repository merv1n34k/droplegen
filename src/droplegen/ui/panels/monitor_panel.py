"""Compact monitor panel: live values table, rolling stats, volume, stability, CSV status."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from droplegen.config import PRESSURE_CHANNEL_NAMES, SENSOR_CHANNEL_NAMES
from droplegen.backend.acquisition import DataSnapshot


class MonitorPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Header row
        header_row = QHBoxLayout()
        header_lbl = QLabel("Monitor")
        header_lbl.setFont(QFont("", 14, QFont.Weight.Bold))
        header_row.addWidget(header_lbl)
        header_row.addStretch()
        self._elapsed_label = QLabel("")
        self._elapsed_label.setStyleSheet("color: gray; font-size: 11px;")
        header_row.addWidget(self._elapsed_label)
        layout.addLayout(header_row)

        # CSV status
        csv_row = QHBoxLayout()
        csv_row.addWidget(QLabel("CSV:"))
        self._csv_path_label = QLabel("--")
        self._csv_path_label.setStyleSheet("color: gray; font-size: 11px;")
        csv_row.addWidget(self._csv_path_label)
        csv_row.addStretch()
        self._csv_rows_label = QLabel("")
        self._csv_rows_label.setStyleSheet("font-size: 11px;")
        csv_row.addWidget(self._csv_rows_label)
        layout.addLayout(csv_row)

        # Table
        self._table = QGridLayout()
        self._table.setSpacing(2)
        col_headers = ["Channel", "Value", "Mean", "Std", "Min", "Max", "Volume", "Stable"]
        col_stretches = [3, 2, 2, 2, 2, 2, 2, 1]
        for col, (h, stretch) in enumerate(zip(col_headers, col_stretches)):
            lbl = QLabel(h)
            lbl.setFont(QFont("", 11, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.addWidget(lbl, 0, col)
            self._table.setColumnStretch(col, stretch)
        layout.addLayout(self._table)
        layout.addStretch()

        self._next_row_idx = 1

    def setup_channels(self, pressure_count: int, sensor_count: int) -> None:
        self._rows.clear()
        self._next_row_idx = 1
        for i in range(pressure_count):
            name = PRESSURE_CHANNEL_NAMES[i] if i < len(PRESSURE_CHANNEL_NAMES) else f"P{i}"
            row = self._create_row(self._next_row_idx, name, "pressure", i)
            self._rows.append(row)
            self._next_row_idx += 1
        for i in range(sensor_count):
            name = SENSOR_CHANNEL_NAMES[i] if i < len(SENSOR_CHANNEL_NAMES) else f"S{i}"
            row = self._create_row(self._next_row_idx, name, "sensor", i)
            self._rows.append(row)
            self._next_row_idx += 1

    def _create_row(self, row_idx: int, name: str, ch_type: str, index: int) -> dict:
        labels = {"type": ch_type, "index": index}
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 11px;")
        self._table.addWidget(name_lbl, row_idx, 0)

        for col, key in enumerate(["value", "mean", "std", "min", "max"], start=1):
            lbl = QLabel("---")
            lbl.setStyleSheet("font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.addWidget(lbl, row_idx, col)
            labels[key] = lbl

        # Volume column (only meaningful for sensors)
        vol_lbl = QLabel("")
        vol_lbl.setStyleSheet("font-size: 11px;")
        vol_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.addWidget(vol_lbl, row_idx, 6)
        labels["volume"] = vol_lbl

        # Stable column (only meaningful for sensors)
        stable_lbl = QLabel("")
        stable_lbl.setStyleSheet("font-size: 11px;")
        stable_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.addWidget(stable_lbl, row_idx, 7)
        labels["stable"] = stable_lbl

        return labels

    def update_from_snapshot(self, snapshot: DataSnapshot) -> None:
        self._elapsed_label.setText(
            f"{snapshot.elapsed_s:.1f}s  {snapshot.timestamp}"
        )
        for row in self._rows:
            idx = row["index"]
            if row["type"] == "pressure" and idx < len(snapshot.pressures):
                val = snapshot.pressures[idx]
                s = snapshot.pressure_stats[idx]
                row["value"].setText(f"{val:.1f}")
                row["mean"].setText(f"{s.mean:.1f}")
                row["std"].setText(f"{s.std:.1f}")
                row["min"].setText(f"{s.min:.1f}")
                row["max"].setText(f"{s.max:.1f}")
                row["volume"].setText("")
                row["stable"].setText("")
            elif row["type"] == "sensor" and idx < len(snapshot.flows):
                val = snapshot.flows[idx]
                s = snapshot.flow_stats[idx]
                row["value"].setText(f"{val:.2f}")
                row["mean"].setText(f"{s.mean:.2f}")
                row["std"].setText(f"{s.std:.2f}")
                row["min"].setText(f"{s.min:.2f}")
                row["max"].setText(f"{s.max:.2f}")
                # Volume
                if idx < len(snapshot.volumes_ul):
                    row["volume"].setText(f"{snapshot.volumes_ul[idx]:.1f}")
                # Stability
                if idx < len(snapshot.stability):
                    if snapshot.stability[idx]:
                        row["stable"].setText("YES")
                        row["stable"].setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
                    else:
                        row["stable"].setText("no")
                        row["stable"].setStyleSheet("color: gray; font-size: 11px;")

    def update_csv_status(self, filepath: str | None, row_count: int) -> None:
        if filepath:
            name = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
            self._csv_path_label.setText(name)
            self._csv_path_label.setStyleSheet("color: white; font-size: 11px;")
            self._csv_rows_label.setText(f"{row_count} rows")
        else:
            self._csv_path_label.setText("--")
            self._csv_path_label.setStyleSheet("color: gray; font-size: 11px;")
            self._csv_rows_label.setText("")

    def clear_channels(self) -> None:
        for row in self._rows:
            for key in ("value", "mean", "std", "min", "max", "volume", "stable"):
                if key in row:
                    row[key].setText("---" if key not in ("volume", "stable") else "")
        self._rows.clear()
