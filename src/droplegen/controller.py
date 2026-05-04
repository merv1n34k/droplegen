"""Mediator between UI, pipeline, and backend."""
import json
import logging
from pathlib import Path
from queue import Queue

from droplegen.backend.sdk_wrapper import FluigentSDK
from droplegen.backend.hardware_manager import HardwareManager, HardwareState
from droplegen.backend.channel_manager import ChannelManager
from droplegen.backend.acquisition import AcquisitionThread, DataSnapshot
from droplegen.logger.csv_logger import CsvLogger
from droplegen.pipeline.engine import PipelineEngine, PipelineEvent, PipelineState
from droplegen.pipeline.steps import PipelineStep
from droplegen.pipeline.triggers import create_trigger
from droplegen.config import PIPELINES, PIPELINE_DIR, Step

log = logging.getLogger(__name__)


class Controller:
    """Central coordinator: wires backend, pipeline, and UI data queues."""

    def __init__(self):
        self.sdk = FluigentSDK()
        self.hw_manager = HardwareManager(self.sdk)
        self.channel_manager = ChannelManager(self.sdk)
        self.csv_logger = CsvLogger()
        self.data_queue: Queue[DataSnapshot] = Queue(maxsize=50)
        self.pipeline_queue: Queue[PipelineEvent] = Queue(maxsize=50)
        self._acquisition: AcquisitionThread | None = None
        self._pipeline: PipelineEngine | None = None
        self._recording = False
        self._corrected_sensors: set[int] = set()

    # --- Hardware ---
    def connect(self, simulated: bool = False) -> HardwareState:
        state = self.hw_manager.connect(simulated=simulated)
        # Configure channel manager with sensor-pressure pairs
        n_sensors = len(state.sensor_channels)
        n_pressure = len(state.pressure_channels)
        pairs = []
        for i in range(min(n_sensors, n_pressure)):
            pairs.append((state.sensor_channels[i].index, state.pressure_channels[i].index))
        self.channel_manager.configure_channels(pairs)
        # In simulated mode, sensor ranges are already corrected by HardwareManager
        if simulated:
            self._corrected_sensors = {ch.index for ch in state.sensor_channels}
        else:
            self._corrected_sensors = set()
        # Auto-start polling so live values appear immediately
        self.start_polling()
        return state

    def disconnect(self) -> None:
        self.stop_recording()
        self.stop_polling()
        self.stop_pipeline()
        self.hw_manager.disconnect()

    # --- Polling (acquisition without CSV) ---
    def start_polling(self) -> None:
        if self._acquisition and self._acquisition.is_alive():
            return
        state = self.hw_manager.state
        self._acquisition = AcquisitionThread(
            sdk=self.sdk,
            pressure_count=len(state.pressure_channels),
            sensor_count=len(state.sensor_channels),
            data_queue=self.data_queue,
            csv_logger=self.csv_logger if self._recording else None,
        )
        self._acquisition.start()
        log.info("Polling started")

    def stop_polling(self) -> None:
        if self._acquisition and self._acquisition.is_alive():
            self._acquisition.stop()
            self._acquisition.join(timeout=2.0)
            self._acquisition = None
        log.info("Polling stopped")

    @property
    def polling_active(self) -> bool:
        return self._acquisition is not None and self._acquisition.is_alive()

    # --- Recording (CSV only) ---
    def start_recording(self) -> str:
        if self._recording:
            return self.csv_logger.filepath or ""
        state = self.hw_manager.state
        filepath = self.csv_logger.start(
            len(state.pressure_channels), len(state.sensor_channels)
        )
        self._recording = True
        # Re-attach CSV logger to running acquisition
        if self._acquisition:
            self._acquisition._csv_logger = self.csv_logger
        log.info("Recording started -> %s", filepath)
        return filepath

    def stop_recording(self) -> None:
        if self._recording:
            self._recording = False
            # Detach CSV logger from acquisition
            if self._acquisition:
                self._acquisition._csv_logger = None
            self.csv_logger.stop()
            log.info("Recording stopped")

    @property
    def recording_active(self) -> bool:
        return self._recording

    # --- Backwards compat ---
    @property
    def acquisition_running(self) -> bool:
        return self.polling_active

    # --- Flow regulation (user) ---
    def set_flow_setpoint(self, channel_idx: int, setpoint: float) -> None:
        self.channel_manager.user_set_flow_regulation(channel_idx, setpoint)

    # --- Pressure control (user) ---
    def set_pressure_setpoint(self, channel_idx: int, pressure_mbar: float) -> None:
        self.channel_manager.user_set_pressure(channel_idx, pressure_mbar)

    def stop_regulation(self, channel_idx: int) -> None:
        self.channel_manager.user_stop_regulation(channel_idx)

    # --- Sensor calibration ---
    def set_sensor_calibration(self, sensor_index: int, calibration: int) -> None:
        self.sdk.set_sensor_calibration(sensor_index, calibration)
        self._corrected_sensors.add(sensor_index)
        log.info("Sensor %d calibration set to %d", sensor_index, calibration)

    def set_sensor_custom_scale(
        self, sensor_index: int, a: float, b: float = 0.0, c: float = 0.0
    ) -> None:
        self.sdk.set_sensor_custom_scale(sensor_index, a, b, c)
        self._corrected_sensors.add(sensor_index)
        log.info("Sensor %d custom scale: a=%.4f b=%.4f c=%.4f", sensor_index, a, b, c)

    def set_regulation_response(self, channel_idx: int, response_time: int) -> None:
        sensor_index = self.channel_manager.channels[channel_idx].sensor_index
        self.sdk.set_sensor_regulation_response(sensor_index, response_time)
        log.info("Sensor %d regulation response set to %d s", sensor_index, response_time)

    def get_uncorrected_sensors(self) -> list[int]:
        state = self.hw_manager.state
        if not state.connected:
            return []
        return [ch.index for ch in state.sensor_channels if ch.index not in self._corrected_sensors]

    # --- Emergency ---
    def emergency_stop(self) -> None:
        log.warning("EMERGENCY STOP triggered")
        self.stop_pipeline()
        self.channel_manager.emergency_stop_all()

    # --- Pipeline ---
    def get_pipeline_names(self) -> list[str]:
        return list(PIPELINES.keys())

    def build_pipeline(self, name: str) -> list[PipelineStep]:
        defns = PIPELINES.get(name)
        if defns is None:
            raise ValueError(f"Unknown pipeline: {name}")
        return self.build_pipeline_from_steps(defns)

    def start_pipeline(self, name: str | None = None, steps: list[PipelineStep] | None = None) -> None:
        if self._pipeline and self._pipeline.is_alive():
            log.warning("Pipeline already running")
            return
        if steps is None:
            pipeline_name = name or next(iter(PIPELINES))
            steps = self.build_pipeline(pipeline_name)

        # Map sensor_index -> channel_manager index
        sensor_to_channel = {}
        for ch_idx, ch in enumerate(self.channel_manager.channels):
            sensor_to_channel[ch.sensor_index] = ch_idx

        self._pipeline = PipelineEngine(
            steps=steps,
            channel_manager=self.channel_manager,
            acquisition=self._acquisition,
            event_queue=self.pipeline_queue,
            sensor_to_channel=sensor_to_channel,
        )
        self._pipeline.start()

    def stop_pipeline(self) -> None:
        if self._pipeline and self._pipeline.is_alive():
            self._pipeline.stop()
            self._pipeline.join(timeout=3.0)
        self._pipeline = None

    def pause_pipeline(self) -> None:
        if self._pipeline:
            self._pipeline.pause()

    def resume_pipeline(self) -> None:
        if self._pipeline:
            self._pipeline.resume()

    def skip_pipeline_step(self) -> None:
        if self._pipeline:
            self._pipeline.skip_step()

    def confirm_pipeline_step(self) -> None:
        """Confirm the current pipeline step's pre-step confirmation gate."""
        if self._pipeline:
            self._pipeline.confirm_pending()
            log.info("Confirmed pipeline step %d", self._pipeline.current_step_index)

    @property
    def pipeline_state(self) -> PipelineState:
        if self._pipeline:
            return self._pipeline.state
        return PipelineState.IDLE

    @property
    def pipeline_steps(self) -> list[PipelineStep] | None:
        if self._pipeline:
            return self._pipeline.steps
        return None

    def _expand_steps(self, steps: list[Step]) -> list[Step]:
        """Expand repeat/group into a flat list of steps."""
        expanded = []
        i = 0
        while i < len(steps):
            s = steps[i]
            if s.group:
                # Collect consecutive steps with the same group tag
                group_steps = []
                group_repeat = 1
                while i < len(steps) and steps[i].group == s.group:
                    group_steps.append(steps[i])
                    group_repeat = max(group_repeat, steps[i].repeat)
                    i += 1
                for _ in range(group_repeat):
                    expanded.extend(group_steps)
            else:
                for _ in range(max(1, s.repeat)):
                    expanded.append(s)
                i += 1
        return expanded

    def build_pipeline_from_steps(self, steps: list[Step]) -> list[PipelineStep]:
        expanded = self._expand_steps(steps)
        result = []
        for defn in expanded:
            trigger = create_trigger(defn.trigger_type, defn.trigger_params)
            result.append(PipelineStep(
                name=defn.name,
                sensor_setpoints=dict(defn.sensor_setpoints),
                trigger=trigger,
                on_complete=defn.on_complete,
                confirm_message=defn.confirm_message,
            ))
        return result

    # --- Settings save/load ---
    SETTINGS_FILE = Path("settings.json")

    def save_settings(self, data: list[dict]) -> None:
        with open(self.SETTINGS_FILE, "w") as f:
            json.dump({"channels": data}, f, indent=2)
        log.info("Settings saved -> %s", self.SETTINGS_FILE)

    def load_settings(self) -> list[dict] | None:
        if not self.SETTINGS_FILE.exists():
            return None
        try:
            with open(self.SETTINGS_FILE) as f:
                return json.load(f).get("channels")
        except (json.JSONDecodeError, KeyError):
            log.warning("Failed to load settings from %s", self.SETTINGS_FILE)
            return None

    # --- Pipeline save/load ---
    def _pipeline_dir(self) -> Path:
        d = Path(PIPELINE_DIR)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_pipeline(self, name: str, steps: list[dict]) -> None:
        path = self._pipeline_dir() / f"{name}.json"
        with open(path, "w") as f:
            json.dump(steps, f, indent=2)
        log.info("Saved pipeline %r -> %s", name, path)

    def load_saved_pipeline(self, name: str) -> list[Step]:
        path = self._pipeline_dir() / f"{name}.json"
        with open(path) as f:
            data = json.load(f)
        steps = []
        for d in data:
            steps.append(Step(
                name=d["name"],
                sensor_setpoints={int(k): v for k, v in d["sensor_setpoints"].items()},
                trigger_type=d["trigger_type"],
                trigger_params=d["trigger_params"],
                on_complete=d.get("on_complete", "hold"),
                confirm_message=d.get("confirm_message", ""),
                repeat=d.get("repeat", 1),
                group=d.get("group", ""),
            ))
        return steps

    def list_saved_pipelines(self) -> list[str]:
        d = self._pipeline_dir()
        return sorted(p.stem for p in d.glob("*.json"))

    def get_all_pipeline_names(self) -> tuple[list[str], list[str]]:
        return list(PIPELINES.keys()), self.list_saved_pipelines()
