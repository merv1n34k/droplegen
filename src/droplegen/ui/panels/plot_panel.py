"""Live scrollable/zoomable time-series plots using pyqtgraph."""
from collections import deque

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from droplegen.backend.acquisition import DataSnapshot
from droplegen.utils import bin_arrays

# 10 min history at 100ms sample rate
_MAX_SAMPLES = 6000
_VISIBLE_WINDOW_S = 60.0

_COLORS = ["#3498db", "#e74c3c", "#2ecc71"]
_LABELS = ["Oil", "Cells", "Beads"]


class LivePlot(pg.PlotWidget):
    """Single live time-series plot with 3 channels."""

    def __init__(self, title: str, y_unit: str, parent=None):
        super().__init__(parent, title=title, labels={"left": y_unit, "bottom": "s"})
        self.setBackground("#1a1a1a")
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setMouseEnabled(x=True, y=False)
        self.enableAutoRange(axis="y")
        self.setAutoVisible(y=True)

        self._times: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._series: list[deque[float]] = [
            deque(maxlen=_MAX_SAMPLES) for _ in range(3)
        ]
        self._curves: list[pg.PlotDataItem] = []
        for i in range(3):
            curve = self.plot(
                [], [], pen=pg.mkPen(_COLORS[i], width=1.5), name=_LABELS[i],
                downsample=1, downsampleMethod="peak",
                clipToView=True,
            )
            self._curves.append(curve)

        self._auto_scroll = True
        self.setXRange(0, _VISIBLE_WINDOW_S, padding=0)

        # Double-click to reset auto-scroll
        self.scene().sigMouseClicked.connect(self._on_click)

    def _on_click(self, event):
        if event.double():
            self._auto_scroll = True
            self._update_x_range()

    def ingest(self, t: float, values: list[float]):
        self._times.append(t)
        for i in range(3):
            self._series[i].append(values[i] if i < len(values) else 0.0)

    def refresh(self, bin_size: float = 0.0):
        if not self._times:
            return
        t_arr = np.array(self._times)
        for i, curve in enumerate(self._curves):
            y_arr = np.array(self._series[i])
            t_out, y_out = bin_arrays(t_arr, y_arr, bin_size)
            curve.setData(t_out, y_out)
        if self._auto_scroll:
            self._update_x_range()

    def _update_x_range(self):
        if self._times:
            x_max = self._times[-1]
            vr = self.viewRange()
            visible = vr[0][1] - vr[0][0]
            self.setXRange(x_max - visible, x_max, padding=0)

    def viewRangeChanged(self, view, ranges):
        # User panned manually → disable auto-scroll
        # (only if not triggered by our own setXRange)
        pass

    def wheelEvent(self, event):
        # Let pyqtgraph handle zoom, but disable auto-scroll on manual zoom
        self._auto_scroll = False
        super().wheelEvent(event)

    def mouseDragEvent(self, event):
        self._auto_scroll = False
        super().mouseDragEvent(event)

    def clear_data(self):
        self._times.clear()
        for s in self._series:
            s.clear()
        for c in self._curves:
            c.setData([], [])
        self._auto_scroll = True
        self.setXRange(0, _VISIBLE_WINDOW_S, padding=0)


class PlotPanel(QWidget):
    """Two side-by-side plots: pressure (left), flow (right)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 0, 4, 0)
        toolbar.addWidget(QLabel("Bin:"))
        self._bin_spin = QDoubleSpinBox()
        self._bin_spin.setRange(0.0, 10.0)
        self._bin_spin.setSingleStep(0.1)
        self._bin_spin.setDecimals(2)
        self._bin_spin.setSuffix(" s")
        self._bin_spin.setSpecialValueText("off")
        self._bin_spin.setValue(0.0)
        self._bin_spin.setFixedWidth(80)
        self._bin_spin.setToolTip("Merge points into time bins (0 = raw data)")
        self._bin_spin.valueChanged.connect(lambda: self.refresh())
        toolbar.addWidget(self._bin_spin)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # Plots
        plots = QHBoxLayout()
        plots.setContentsMargins(0, 0, 0, 0)
        plots.setSpacing(4)
        self._pressure = LivePlot("Pressure", "mbar")
        plots.addWidget(self._pressure)
        self._flow = LivePlot("Flow", "µL/min")
        plots.addWidget(self._flow)
        root.addLayout(plots, stretch=1)

    def ingest_from_snapshot(self, snapshot: DataSnapshot) -> None:
        self._pressure.ingest(snapshot.elapsed_s, snapshot.pressures)
        self._flow.ingest(snapshot.elapsed_s, snapshot.flows)

    def refresh(self) -> None:
        b = self._bin_spin.value()
        self._pressure.refresh(bin_size=b)
        self._flow.refresh(bin_size=b)

    def update_from_snapshot(self, snapshot: DataSnapshot) -> None:
        self._pressure.ingest(snapshot.elapsed_s, snapshot.pressures)
        self._flow.ingest(snapshot.elapsed_s, snapshot.flows)
        self.refresh()

    def clear(self) -> None:
        self._pressure.clear_data()
        self._flow.clear_data()
