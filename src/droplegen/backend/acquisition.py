"""100ms data polling thread with volume integration, stability detection, and rolling statistics."""
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from queue import Queue

from droplegen.backend.sdk_wrapper import FluigentSDK
from droplegen.logger.csv_logger import CsvLogger
from droplegen.config import (
    ACQUISITION_INTERVAL_MS,
    STATS_WINDOW_SAMPLES,
    STABILITY_TOLERANCE_UL_MIN,
    STABILITY_WINDOW_SAMPLES,
)

log = logging.getLogger(__name__)


@dataclass
class ChannelStats:
    mean: float = 0.0
    std: float = 0.0
    min: float = 0.0
    max: float = 0.0


@dataclass
class DataSnapshot:
    timestamp: str
    elapsed_s: float
    pressures: list[float]
    flows: list[float]
    volumes_ul: list[float]
    pressure_stats: list[ChannelStats]
    flow_stats: list[ChannelStats]
    stability: list[bool] = field(default_factory=list)


class AcquisitionThread(threading.Thread):
    """Polls all pressure and flow channels at 100ms, computes stats, optionally logs CSV."""

    def __init__(
        self,
        sdk: FluigentSDK,
        pressure_count: int,
        sensor_count: int,
        data_queue: Queue,
        csv_logger: CsvLogger | None = None,
    ):
        super().__init__(daemon=True, name="AcquisitionThread")
        self._sdk = sdk
        self._pressure_count = pressure_count
        self._sensor_count = sensor_count
        self._data_queue = data_queue
        self._csv_logger = csv_logger
        self._stop_event = threading.Event()
        self._start_time: float = 0.0

        # Rolling windows for statistics
        self._pressure_history: list[deque] = [
            deque(maxlen=STATS_WINDOW_SAMPLES) for _ in range(pressure_count)
        ]
        self._flow_history: list[deque] = [
            deque(maxlen=STATS_WINDOW_SAMPLES) for _ in range(sensor_count)
        ]

        # Stability detection
        self._stability_history: list[deque] = [
            deque(maxlen=STABILITY_WINDOW_SAMPLES) for _ in range(sensor_count)
        ]

        # Volume integration (cumulative)
        self._volumes_ul: list[float] = [0.0] * sensor_count
        self._lock = threading.Lock()

    def get_volume(self, sensor_index: int) -> float:
        with self._lock:
            if 0 <= sensor_index < len(self._volumes_ul):
                return self._volumes_ul[sensor_index]
            return 0.0

    def reset_volumes(self) -> None:
        with self._lock:
            self._volumes_ul = [0.0] * self._sensor_count

    def run(self) -> None:
        self._start_time = time.monotonic()
        interval = ACQUISITION_INTERVAL_MS / 1000.0
        log.info("Acquisition started (interval=%.0fms)", ACQUISITION_INTERVAL_MS)

        while not self._stop_event.is_set():
            loop_start = time.monotonic()
            try:
                self._poll_once()
            except Exception:
                log.exception("Acquisition poll error")
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)

        log.info("Acquisition stopped.")

    def stop(self) -> None:
        self._stop_event.set()

    def _poll_once(self) -> None:
        now = datetime.now()
        elapsed_s = time.monotonic() - self._start_time
        timestamp = now.strftime("%H:%M:%S.%f")[:-3]

        pressures = [
            self._sdk.get_pressure(i) for i in range(self._pressure_count)
        ]
        flows = [
            self._sdk.get_sensor_value(i) for i in range(self._sensor_count)
        ]

        # Update history
        for i, p in enumerate(pressures):
            self._pressure_history[i].append(p)
        for i, f in enumerate(flows):
            self._flow_history[i].append(f)
            self._stability_history[i].append(f)

        # Integrate volume: flow (ul/min) * dt (min)
        dt_min = (ACQUISITION_INTERVAL_MS / 1000.0) / 60.0
        with self._lock:
            for i, f in enumerate(flows):
                self._volumes_ul[i] += abs(f) * dt_min
            volumes_snapshot = list(self._volumes_ul)

        # Compute stability per sensor
        stability = []
        for i in range(self._sensor_count):
            h = self._stability_history[i]
            if len(h) >= STABILITY_WINDOW_SAMPLES:
                window_range = max(h) - min(h)
                stable = window_range <= 2 * STABILITY_TOLERANCE_UL_MIN
            else:
                stable = False
            stability.append(stable)

        # Compute stats
        pressure_stats = [self._compute_stats(h) for h in self._pressure_history]
        flow_stats = [self._compute_stats(h) for h in self._flow_history]

        snapshot = DataSnapshot(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            pressures=pressures,
            flows=flows,
            volumes_ul=volumes_snapshot,
            pressure_stats=pressure_stats,
            flow_stats=flow_stats,
            stability=stability,
        )

        # Write CSV (only if logger is attached and started)
        if self._csv_logger:
            self._csv_logger.write_row(
                timestamp, elapsed_s, pressures, flows,
                volumes=volumes_snapshot, stability=stability,
            )

        # Push to UI queue (non-blocking, drop if full)
        if not self._data_queue.full():
            self._data_queue.put(snapshot)

    @staticmethod
    def _compute_stats(history: deque) -> ChannelStats:
        if not history:
            return ChannelStats()
        vals = list(history)
        n = len(vals)
        mean = sum(vals) / n
        min_v = min(vals)
        max_v = max(vals)
        if n > 1:
            variance = sum((v - mean) ** 2 for v in vals) / (n - 1)
            std = variance ** 0.5
        else:
            std = 0.0
        return ChannelStats(mean=mean, std=std, min=min_v, max=max_v)
