"""Auto-named CSV writer for acquisition data."""
import csv
from datetime import datetime
from pathlib import Path


class CsvLogger:
    """Writes acquisition data rows to a timestamped CSV file."""

    def __init__(self, log_dir: str = "logs"):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._file = None
        self._writer = None
        self._row_count = 0
        self._filepath: str | None = None

    @property
    def filepath(self) -> str | None:
        return self._filepath

    @property
    def row_count(self) -> int:
        return self._row_count

    def start(self, pressure_count: int, sensor_count: int) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"droplegen_{timestamp}.csv"
        self._filepath = str(self._log_dir / filename)

        self._file = open(self._filepath, "w", newline="")
        headers = ["timestamp", "elapsed_s"]
        for i in range(pressure_count):
            headers.append(f"pressure_{i}_mbar")
        for i in range(sensor_count):
            headers.append(f"flow_{i}_ul_min")
        for i in range(sensor_count):
            headers.append(f"volume_{i}_ul")
        for i in range(sensor_count):
            headers.append(f"stable_{i}")
        self._writer = csv.writer(self._file)
        self._writer.writerow(headers)
        self._row_count = 0
        return self._filepath

    def write_row(
        self,
        timestamp: str,
        elapsed_s: float,
        pressures: list[float],
        flows: list[float],
        volumes: list[float] | None = None,
        stability: list[bool] | None = None,
    ) -> None:
        if self._writer is None:
            return
        row = [timestamp, f"{elapsed_s:.3f}"]
        row.extend(f"{p:.2f}" for p in pressures)
        row.extend(f"{f:.3f}" for f in flows)
        if volumes:
            row.extend(f"{v:.3f}" for v in volumes)
        if stability:
            row.extend("1" if s else "0" for s in stability)
        self._writer.writerow(row)
        self._row_count += 1
        # Flush every 10 rows for near-real-time logging
        if self._row_count % 10 == 0 and self._file:
            self._file.flush()

    def stop(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None
