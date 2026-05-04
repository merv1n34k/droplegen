"""Native Qt log viewer using pyqtgraph."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pyqtgraph as pg

from droplegen.utils import bin_arrays
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

CHANNELS = {0: "Oil", 1: "Cells", 2: "Beads"}

LOG_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#17becf",
]

METRIC_COLS = {
    "Pressure": "pressure_{}_mbar",
    "Flow": "flow_{}_ul_min",
    "Volume": "volume_{}_ul",
}

# QPen styles: solid=1, dash=2, dot=3
METRIC_PEN_STYLE = {"Pressure": Qt.PenStyle.SolidLine, "Flow": Qt.PenStyle.DashLine, "Volume": Qt.PenStyle.DotLine}


def _short_name(path: Path) -> str:
    m = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})", path.stem)
    if m:
        return f"{m.group(2)}{m.group(3)}_{m.group(4)}{m.group(5)}"
    return path.stem


def _load_csv(path: Path) -> tuple[pd.DataFrame, int]:
    df = pd.read_csv(path)
    n_channels = sum(1 for c in df.columns if c.startswith("pressure_") and c.endswith("_mbar"))
    return df, n_channels


class LogViewerWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Viewer")
        self.resize(1200, 700)
        self.setMinimumSize(800, 500)

        # State
        self._logs: list[tuple[str, Path, pd.DataFrame, int]] = []  # (name, path, df, n_ch)
        self._log_cbs: list[QCheckBox] = []
        self._metric_cbs: dict[str, QCheckBox] = {}
        self._channel_cbs: dict[int, QCheckBox] = {}

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # -- Left sidebar --
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(8)

        load_btn = QPushButton("Load Files...")
        load_btn.setFixedHeight(32)
        load_btn.clicked.connect(self._load_files)
        sb_layout.addWidget(load_btn)

        # Logs group (scrollable)
        self._logs_group = QGroupBox("LOGS")
        self._logs_group.setFont(QFont("", 10, QFont.Weight.Bold))
        self._logs_layout = QVBoxLayout()
        self._logs_layout.setContentsMargins(4, 4, 4, 4)
        self._logs_layout.setSpacing(2)
        self._logs_group.setLayout(self._logs_layout)

        scroll = QScrollArea()
        scroll.setWidget(self._logs_group)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        sb_layout.addWidget(scroll)

        # Metrics group
        metrics_group = QGroupBox("METRICS")
        metrics_group.setFont(QFont("", 10, QFont.Weight.Bold))
        m_layout = QVBoxLayout()
        m_layout.setContentsMargins(4, 4, 4, 4)
        m_layout.setSpacing(2)
        for metric in METRIC_COLS:
            cb = QCheckBox(metric)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_filter_changed)
            m_layout.addWidget(cb)
            self._metric_cbs[metric] = cb
        metrics_group.setLayout(m_layout)
        sb_layout.addWidget(metrics_group)

        # Channels group
        channels_group = QGroupBox("CHANNELS")
        channels_group.setFont(QFont("", 10, QFont.Weight.Bold))
        c_layout = QVBoxLayout()
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(2)
        for idx, name in CHANNELS.items():
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_filter_changed)
            c_layout.addWidget(cb)
            self._channel_cbs[idx] = cb
        channels_group.setLayout(c_layout)
        sb_layout.addWidget(channels_group)

        # Axis limits group
        limits_group = QGroupBox("LIMITS")
        limits_group.setFont(QFont("", 10, QFont.Weight.Bold))
        lim_layout = QVBoxLayout()
        lim_layout.setContentsMargins(4, 4, 4, 4)
        lim_layout.setSpacing(4)

        self._limit_spins = {}
        for axis, label in [("x", "X"), ("y", "Y")]:
            for bound in ["min", "max"]:
                row = QHBoxLayout()
                row.setSpacing(4)
                row.addWidget(QLabel(f"{label} {bound}"))
                spin = QDoubleSpinBox()
                spin.setDecimals(1)
                spin.setRange(-1e6, 1e6)
                spin.setSpecialValueText("auto")
                spin.setValue(spin.minimum())  # show "auto"
                spin.editingFinished.connect(self._apply_limits)
                row.addWidget(spin)
                lim_layout.addLayout(row)
                self._limit_spins[f"{axis}_{bound}"] = spin

        # Bin size
        bin_row = QHBoxLayout()
        bin_row.setSpacing(4)
        bin_row.addWidget(QLabel("Bin"))
        self._bin_spin = QDoubleSpinBox()
        self._bin_spin.setRange(0.0, 60.0)
        self._bin_spin.setSingleStep(0.1)
        self._bin_spin.setDecimals(2)
        self._bin_spin.setSuffix(" s")
        self._bin_spin.setSpecialValueText("off")
        self._bin_spin.setValue(0.0)
        self._bin_spin.setToolTip("Merge points into time bins (0 = raw)")
        self._bin_spin.valueChanged.connect(self._on_filter_changed)
        bin_row.addWidget(self._bin_spin)
        lim_layout.addLayout(bin_row)

        reset_btn = QPushButton("Reset Limits")
        reset_btn.clicked.connect(self._reset_limits)
        lim_layout.addWidget(reset_btn)

        limits_group.setLayout(lim_layout)
        sb_layout.addWidget(limits_group)

        sb_layout.addStretch()
        layout.addWidget(sidebar)

        # -- Plot area --
        pg.setConfigOptions(antialias=True, background="#1a1a1a", foreground="#d4d4d4")
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self._plot_widget.setLabel("bottom", "Elapsed", units="s")
        self._plot_widget.setLabel("left", "Value")
        self._plot_widget.addLegend(offset=(10, 10))
        layout.addWidget(self._plot_widget, stretch=1)

        # Crosshair
        self._vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#888", width=1, style=Qt.PenStyle.DotLine))
        self._hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("#888", width=1, style=Qt.PenStyle.DotLine))
        self._plot_widget.addItem(self._vline, ignoreBounds=True)
        self._plot_widget.addItem(self._hline, ignoreBounds=True)

        self._cursor_label = pg.TextItem(anchor=(0, 1), color="#ccc")
        self._plot_widget.addItem(self._cursor_label, ignoreBounds=True)

        # Reference marker (click to pin)
        self._ref_point: tuple[float, float] | None = None
        self._ref_marker = pg.ScatterPlotItem(
            [], [], pen=pg.mkPen("#ff0"), brush=pg.mkBrush("#ff0"), size=8, symbol="+"
        )
        self._plot_widget.addItem(self._ref_marker, ignoreBounds=True)
        self._ref_label = pg.TextItem(anchor=(0, 0), color="#ff0")
        self._plot_widget.addItem(self._ref_label, ignoreBounds=True)

        self._plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self._plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Status bar
        self._status = self.statusBar()
        self._status.showMessage("No logs loaded")

    def _load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Log CSVs", "logs", "CSV Files (*.csv)"
        )
        if paths:
            self._add_paths([Path(p) for p in paths])

    def _on_filter_changed(self):
        self._rebuild()

    def _on_mouse_moved(self, pos):
        vb = self._plot_widget.getPlotItem().vb
        if not vb.sceneBoundingRect().contains(pos):
            return
        pt = vb.mapSceneToView(pos)
        x, y = pt.x(), pt.y()
        self._vline.setPos(x)
        self._hline.setPos(y)

        text = f"t={x:.2f}s  y={y:.2f}"
        if self._ref_point is not None:
            rx, ry = self._ref_point
            text += f"\nΔt={x - rx:.2f}s  Δy={y - ry:.2f}"
        self._cursor_label.setText(text)
        self._cursor_label.setPos(x, y)

    def _on_mouse_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not event.double():
            vb = self._plot_widget.getPlotItem().vb
            pt = vb.mapSceneToView(event.scenePos())
            x, y = pt.x(), pt.y()
            self._ref_point = (x, y)
            self._ref_marker.setData([x], [y])
            self._ref_label.setText(f"ref: {x:.2f}s, {y:.2f}")
            self._ref_label.setPos(x, y)
        elif event.double():
            self._ref_point = None
            self._ref_marker.setData([], [])
            self._ref_label.setText("")

    def _rebuild(self):
        self._plot_widget.clear()
        # Re-add overlay items after clear
        for item in (self._vline, self._hline, self._cursor_label, self._ref_marker, self._ref_label):
            self._plot_widget.addItem(item, ignoreBounds=True)

        if not self._logs:
            self._status.showMessage("No logs loaded")
            return

        bin_size = self._bin_spin.value()

        legend = self._plot_widget.addLegend(offset=(10, 10))
        legend.clear()

        total_points = 0
        legend_shown = set()  # track which metrics got a legend entry

        for log_idx, (name, _path, df, n_ch) in enumerate(self._logs):
            if not self._log_cbs[log_idx].isChecked():
                continue

            color = LOG_COLORS[log_idx % len(LOG_COLORS)]

            for ch_idx in range(min(n_ch, len(CHANNELS))):
                if ch_idx not in self._channel_cbs or not self._channel_cbs[ch_idx].isChecked():
                    continue

                ch_name = CHANNELS.get(ch_idx, f"Ch{ch_idx}")

                for metric, col_tmpl in METRIC_COLS.items():
                    if not self._metric_cbs[metric].isChecked():
                        continue

                    col = col_tmpl.format(ch_idx)
                    if col not in df.columns:
                        continue

                    x_raw = df["elapsed_s"].values
                    y_raw = df[col].values
                    x, y = bin_arrays(x_raw, y_raw, bin_size)
                    total_points += len(y)

                    pen = pg.mkPen(color=color, width=1.5, style=METRIC_PEN_STYLE[metric])

                    # Legend: one entry per metric
                    legend_name = metric if metric not in legend_shown else None
                    if legend_name:
                        legend_shown.add(metric)

                    item = pg.PlotDataItem(
                        x, y, pen=pen, name=legend_name,
                    )
                    item.setToolTip(f"{name} · {ch_name} · {metric}")
                    self._plot_widget.addItem(item)

                    # Stability markers on flow (only when not binning)
                    if metric == "Flow" and bin_size <= 0:
                        stable_col = f"stable_{ch_idx}"
                        if stable_col in df.columns:
                            mask = df[stable_col].values == 1
                            if np.any(mask):
                                scatter = pg.ScatterPlotItem(
                                    x_raw[mask], y_raw[mask],
                                    pen=None, brush=pg.mkBrush(color + "66"),
                                    size=5,
                                )
                                scatter.setToolTip(f"{name} · {ch_name} · stable")
                                self._plot_widget.addItem(scatter)
                                total_points += int(np.sum(mask))

        n_visible = sum(1 for cb in self._log_cbs if cb.isChecked())
        msg = f"{n_visible} log(s) · {total_points:,} points"
        if bin_size > 0:
            msg += f" · bin {bin_size:.2g}s"
        self._status.showMessage(msg)

    def _apply_limits(self):
        plot = self._plot_widget.getPlotItem()
        for axis, key in [("bottom", "x"), ("left", "y")]:
            lo = self._limit_spins[f"{key}_min"]
            hi = self._limit_spins[f"{key}_max"]
            lo_auto = lo.value() == lo.minimum()
            hi_auto = hi.value() == hi.minimum()
            if lo_auto and hi_auto:
                plot.enableAutoRange(axis={"bottom": pg.ViewBox.XAxis, "left": pg.ViewBox.YAxis}[axis])
            else:
                vb = plot.getViewBox()
                cur = vb.viewRange()
                idx = 0 if axis == "bottom" else 1
                lo_val = cur[idx][0] if lo_auto else lo.value()
                hi_val = cur[idx][1] if hi_auto else hi.value()
                if axis == "bottom":
                    plot.setXRange(lo_val, hi_val, padding=0)
                else:
                    plot.setYRange(lo_val, hi_val, padding=0)

    def _reset_limits(self):
        for spin in self._limit_spins.values():
            spin.setValue(spin.minimum())
        self._plot_widget.getPlotItem().enableAutoRange()

    def _autoload_logs(self):
        logs_dir = Path("logs")
        if not logs_dir.is_dir():
            return
        csvs = sorted(logs_dir.glob("*.csv"))
        if not csvs:
            return
        self._add_paths(csvs)

    def _add_paths(self, paths):
        for path in paths:
            path = Path(path)
            name = _short_name(path)
            if any(entry[1] == path for entry in self._logs):
                continue
            try:
                df, n_ch = _load_csv(path)
            except Exception:
                continue
            self._logs.append((name, path, df, n_ch))

            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_filter_changed)
            color = LOG_COLORS[(len(self._logs) - 1) % len(LOG_COLORS)]
            cb.setStyleSheet(f"QCheckBox {{ color: {color}; }}")
            self._logs_layout.addWidget(cb)
            self._log_cbs.append(cb)

        self._rebuild()

    def show_and_raise(self):
        first_show = not self._logs
        self.show()
        self.raise_()
        self.activateWindow()
        if first_show:
            self._autoload_logs()
