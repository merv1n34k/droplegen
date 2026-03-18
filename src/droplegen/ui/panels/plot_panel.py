"""Live scrollable/zoomable time-series plots using QPainter."""
from collections import deque

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from droplegen.backend.acquisition import DataSnapshot

# 10 min history at 100ms sample rate
_MAX_SAMPLES = 6000
_VISIBLE_WINDOW_S = 60.0

# Colors
_BG = QColor("#1a1a1a")
_TEXT = QColor("#999999")
_GRID = QColor("#2a2a2a")
_AXIS = QColor("#444444")
_COLORS = [QColor("#3498db"), QColor("#e74c3c"), QColor("#2ecc71")]
_LABELS = ["Oil", "Cells", "Beads"]

# Margins (left, right, top, bottom)
_ML, _MR, _MT, _MB = 58, 14, 26, 28


class PlotWidget(QWidget):
    """Single time-series plot with grid, labels, and 3 data lines."""

    def __init__(self, title: str, y_unit: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._y_unit = y_unit

        self._times: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._series: list[deque[float]] = [
            deque(maxlen=_MAX_SAMPLES) for _ in range(3)
        ]

        self._auto_scroll = True
        self._x_min = 0.0
        self._x_max = _VISIBLE_WINDOW_S
        self._y_min = 0.0
        self._y_max = 100.0

        # Drag-pan state
        self._drag_start: int | None = None
        self._drag_x0 = 0.0
        self._drag_x1 = 0.0

        self.setMinimumSize(200, 120)

    # ── coordinate helpers ──

    def _plot_rect(self) -> tuple[float, float, float, float]:
        return _ML, _MT, self.width() - _MR, self.height() - _MB

    def _to_px(self, t: float, v: float) -> tuple[float, float]:
        x0, y0, x1, y1 = self._plot_rect()
        dx = self._x_max - self._x_min
        dy = self._y_max - self._y_min
        px = x0 + (t - self._x_min) / dx * (x1 - x0) if dx else x0
        py = y1 - (v - self._y_min) / dy * (y1 - y0) if dy else y1
        return px, py

    def _px_to_t(self, px: float) -> float:
        x0, _, x1, _ = self._plot_rect()
        pw = x1 - x0
        return self._x_min + (px - x0) / pw * (self._x_max - self._x_min) if pw > 0 else self._x_min

    # ── interaction ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = int(event.position().x())
            self._drag_x0 = self._x_min
            self._drag_x1 = self._x_max

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            return
        x0, _, x1, _ = self._plot_rect()
        pw = x1 - x0
        if pw <= 0:
            return
        dx = int(event.position().x())
        dt = -(dx - self._drag_start) / pw * (self._drag_x1 - self._drag_x0)
        self._x_min = self._drag_x0 + dt
        self._x_max = self._drag_x1 + dt
        self._auto_scroll = False
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_start = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 0.8 if delta > 0 else 1.25
        px = event.position().x()
        center = self._px_to_t(px)
        half = (self._x_max - self._x_min) * factor / 2
        half = max(half, 1.0)
        half = min(half, _MAX_SAMPLES * 0.1 / 2)
        self._x_min = center - half
        self._x_max = center + half
        self._auto_scroll = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        self._auto_scroll = True
        if self._times:
            self._x_max = self._times[-1]
            self._x_min = self._x_max - _VISIBLE_WINDOW_S
        self.update()

    # ── data ──

    def update_data(self, t: float, values: list[float]):
        self._times.append(t)
        for i in range(3):
            self._series[i].append(values[i] if i < len(values) else 0.0)

        if self._auto_scroll and self._times:
            visible = self._x_max - self._x_min
            self._x_max = self._times[-1]
            self._x_min = self._x_max - visible

        self._auto_scale_y()
        self.update()

    def _auto_scale_y(self):
        y_lo = float("inf")
        y_hi = float("-inf")
        for i, t in enumerate(self._times):
            if t < self._x_min or t > self._x_max:
                continue
            for s in self._series:
                if i < len(s):
                    v = s[i]
                    if v < y_lo:
                        y_lo = v
                    if v > y_hi:
                        y_hi = v
        if y_lo == float("inf"):
            y_lo, y_hi = 0.0, 100.0
        pad = max((y_hi - y_lo) * 0.12, 1.0)
        self._y_min = y_lo - pad
        self._y_max = y_hi + pad

    def clear(self):
        self._times.clear()
        for s in self._series:
            s.clear()
        self._auto_scroll = True
        self._x_min = 0.0
        self._x_max = _VISIBLE_WINDOW_S
        self._y_min = 0.0
        self._y_max = 100.0
        self.update()

    # ── painting ──

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        p.fillRect(0, 0, w, h, _BG)

        x0, y0, x1, y1 = self._plot_rect()
        pw = x1 - x0
        ph = y1 - y0
        if pw <= 0 or ph <= 0:
            p.end()
            return

        # Plot area border
        p.setPen(QPen(_AXIS, 1))
        p.drawRect(QRectF(x0, y0, pw, ph))

        # Title
        p.setPen(_TEXT)
        p.setFont(QFont("", 10, QFont.Weight.Bold))
        p.drawText(QRectF(x0, 2, pw, 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self._title)

        # Small font for labels
        small_font = QFont("", 8)
        p.setFont(small_font)

        # Y grid + labels (~5 divisions)
        dy = self._y_max - self._y_min
        grid_pen = QPen(_GRID, 1)
        for i in range(6):
            frac = i / 5
            py = y1 - frac * ph
            val = self._y_min + frac * dy
            p.setPen(grid_pen)
            p.drawLine(QPointF(x0, py), QPointF(x1, py))
            p.setPen(_TEXT)
            p.drawText(QRectF(0, py - 8, x0 - 5, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{val:.0f}")

        # X grid + labels (~6 divisions)
        dx = self._x_max - self._x_min
        for i in range(7):
            frac = i / 6
            px = x0 + frac * pw
            val = self._x_min + frac * dx
            p.setPen(grid_pen)
            p.drawLine(QPointF(px, y0), QPointF(px, y1))
            p.setPen(_TEXT)
            p.drawText(QRectF(px - 25, y1 + 2, 50, 16),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       f"{val:.0f}s")

        # Y-axis unit label
        p.drawText(QRectF(0, y0 - 18, x0 - 5, 16),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                   self._y_unit)

        # Data lines
        p.setClipRect(QRectF(x0, y0, pw, ph))
        for si in range(3):
            self._draw_series(p, si, x0, y0, x1, y1)
        p.setClipping(False)

        # Legend (top-right inside plot)
        p.setFont(QFont("", 8))
        for i in range(3):
            lx = x1 - 10
            ly = y0 + 8 + i * 14
            p.setPen(QPen(_COLORS[i], 2))
            p.drawLine(QPointF(lx - 22, ly), QPointF(lx - 6, ly))
            p.setPen(_COLORS[i])
            p.drawText(QRectF(x0, ly - 6, lx - 28 - x0, 12),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       _LABELS[i])

        p.end()

    def _draw_series(self, p: QPainter, idx: int, x0, y0, x1, y1):
        times = self._times
        data = self._series[idx]
        if len(times) < 2:
            return

        margin = (self._x_max - self._x_min) * 0.01
        lo = self._x_min - margin
        hi = self._x_max + margin

        points = QPolygonF()
        for i, t in enumerate(times):
            if t < lo or t > hi or i >= len(data):
                if len(points) > 0:
                    break
                continue
            px, py = self._to_px(t, data[i])
            py = max(y0, min(y1, py))
            points.append(QPointF(px, py))

        if len(points) >= 2:
            p.setPen(QPen(_COLORS[idx], 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolyline(points)


class PlotPanel(QWidget):
    """Two side-by-side plots: pressure (left), flow (right)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._pressure = PlotWidget("Pressure", "mbar")
        layout.addWidget(self._pressure)

        self._flow = PlotWidget("Flow", "µL/min")
        layout.addWidget(self._flow)

    def update_from_snapshot(self, snapshot: DataSnapshot) -> None:
        self._pressure.update_data(snapshot.elapsed_s, snapshot.pressures)
        self._flow.update_data(snapshot.elapsed_s, snapshot.flows)

    def clear(self) -> None:
        self._pressure.clear()
        self._flow.clear()
