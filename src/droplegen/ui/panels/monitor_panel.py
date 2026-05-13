"""Compact monitor panel: live values table, rolling stats, volume, stability, CSV status."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

import dropletui as ui

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
        self._elapsed_label = ui.status_label("")
        header_row.addWidget(self._elapsed_label)
        layout.addLayout(header_row)

        # CSV status
        csv_row = QHBoxLayout()
        csv_row.addWidget(QLabel("CSV:"))
        self._csv_path_label = ui.status_label("--")
        csv_row.addWidget(self._csv_path_label)
        self._csv_row = csv_row
        self._csv_path_kind = "muted"
        csv_row.addStretch()
        self._csv_rows_label = ui.status_label("", kind="default")
        csv_row.addWidget(self._csv_rows_label)
        layout.addLayout(csv_row)

        # Table
        self._table = QGridLayout()
        self._table.setSpacing(4)
        col_headers = ["Channel", "Value", "Mean", "Std", "Min", "Max", "Volume", "Stable"]
        col_stretches = [3, 2, 2, 2, 2, 2, 2, 1]
        col_min_widths = [90, 55, 55, 45, 55, 55, 55, 40]
        for col, (h, stretch, min_w) in enumerate(zip(col_headers, col_stretches, col_min_widths)):
            lbl = QLabel(h)
            lbl.setFont(QFont("", 11, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.addWidget(lbl, 0, col)
            self._table.setColumnStretch(col, stretch)
            self._table.setColumnMinimumWidth(col, min_w)
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
        labels = {"type": ch_type, "index": index, "row": row_idx}
        name_lbl = ui.status_label(name, kind="default")
        self._table.addWidget(name_lbl, row_idx, 0)

        for col, key in enumerate(["value", "mean", "std", "min", "max"], start=1):
            lbl = ui.status_label("---", kind="default")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.addWidget(lbl, row_idx, col)
            labels[key] = lbl

        # Volume column (only meaningful for sensors)
        vol_lbl = ui.status_label("", kind="default")
        vol_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.addWidget(vol_lbl, row_idx, 6)
        labels["volume"] = vol_lbl

        # Stable column (only meaningful for sensors)
        stable_lbl = ui.status_label("", kind="muted")
        stable_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.addWidget(stable_lbl, row_idx, 7)
        labels["stable"] = stable_lbl
        labels["stable_kind"] = "muted"

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
                        self._set_stable_status(row, "YES", "success")
                    else:
                        self._set_stable_status(row, "no", "muted")

    def update_csv_status(self, filepath: str | None, row_count: int) -> None:
        if filepath:
            name = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
            self._set_csv_path(name, "default")
            self._csv_rows_label.setText(f"{row_count} rows")
        else:
            self._set_csv_path("--", "muted")
            self._csv_rows_label.setText("")

    def _set_stable_status(self, row: dict, text: str, kind: str) -> None:
        if row.get("stable_kind") == kind:
            row["stable"].setText(text)
            return
        replacement = ui.status_label(text, kind=kind)
        replacement.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.replaceWidget(row["stable"], replacement)
        row["stable"].deleteLater()
        row["stable"] = replacement
        row["stable_kind"] = kind

    def _set_csv_path(self, text: str, kind: str) -> None:
        if self._csv_path_kind == kind:
            self._csv_path_label.setText(text)
            return
        replacement = ui.status_label(text, kind=kind)
        self._csv_row.replaceWidget(self._csv_path_label, replacement)
        self._csv_path_label.deleteLater()
        self._csv_path_label = replacement
        self._csv_path_kind = kind

    def clear_channels(self) -> None:
        for row in self._rows:
            for key in ("value", "mean", "std", "min", "max", "volume", "stable"):
                if key in row:
                    row[key].setText("---" if key not in ("volume", "stable") else "")
        self._rows.clear()
