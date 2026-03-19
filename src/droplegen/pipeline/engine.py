"""Pipeline executor thread with pause/resume/stop/skip support."""
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue

from droplegen.backend.channel_manager import ChannelManager
from droplegen.backend.acquisition import AcquisitionThread
from droplegen.pipeline.steps import PipelineStep, StepStatus
from droplegen.config import PIPELINE_TICK_MS

log = logging.getLogger(__name__)


class PipelineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PipelineEvent:
    state: PipelineState
    current_step: int
    total_steps: int
    step_name: str = ""
    progress: float = 0.0
    error_msg: str = ""
    step_volumes: dict[int, float] = field(default_factory=dict)
    confirmation_message: str = ""


class PipelineEngine(threading.Thread):
    """Executes pipeline steps sequentially in a background thread."""

    def __init__(
        self,
        steps: list[PipelineStep],
        channel_manager: ChannelManager,
        acquisition: AcquisitionThread | None,
        event_queue: Queue,
        sensor_to_channel: dict[int, int],  # sensor_index -> channel_manager index
    ):
        super().__init__(daemon=True, name="PipelineEngine")
        self._steps = steps
        self._channel_manager = channel_manager
        self._acquisition = acquisition
        self._event_queue = event_queue
        self._sensor_to_channel = sensor_to_channel

        self._state = PipelineState.IDLE
        self._current_step_idx = 0
        self._step_start_volumes: dict[int, float] = {}

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially
        self._skip_event = threading.Event()
        self._confirm_event = threading.Event()  # for pre-step confirmation

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def current_step_index(self) -> int:
        return self._current_step_idx

    @property
    def steps(self) -> list[PipelineStep]:
        return self._steps

    def pause(self) -> None:
        if self._state == PipelineState.RUNNING:
            self._pause_event.clear()
            self._state = PipelineState.PAUSED
            self._emit_event()
            log.info("Pipeline paused")

    def resume(self) -> None:
        if self._state == PipelineState.PAUSED:
            self._pause_event.set()
            self._state = PipelineState.RUNNING
            self._emit_event()
            log.info("Pipeline resumed")

    def confirm_pending(self) -> None:
        """Confirm pre-step confirmation gate."""
        self._confirm_event.set()

    def stop(self) -> None:
        log.info("Pipeline stop requested")
        self._state = PipelineState.STOPPING
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused
        self._confirm_event.set()  # unblock pre-step confirmation

    def skip_step(self) -> None:
        self._skip_event.set()
        self._confirm_event.set()  # unblock pre-step confirmation
        log.info("Skip requested for step %d", self._current_step_idx)

    def run(self) -> None:
        self._state = PipelineState.RUNNING
        self._emit_event()
        log.info("Pipeline started with %d steps", len(self._steps))

        try:
            for idx, step in enumerate(self._steps):
                if self._stop_event.is_set():
                    break

                self._current_step_idx = idx
                self._execute_step(step)

                if self._stop_event.is_set():
                    break

            if not self._stop_event.is_set():
                self._state = PipelineState.COMPLETED
                log.info("Pipeline completed")
        except Exception as e:
            self._state = PipelineState.ERROR
            log.exception("Pipeline error")
            self._emit_event(error_msg=str(e))
        finally:
            self._channel_manager.pipeline_release_all()
            self._emit_event()

    def _execute_step(self, step: PipelineStep) -> None:
        step.status = StepStatus.RUNNING

        # Pre-step confirmation gate
        if step.confirm_message:
            self._confirm_event.clear()
            self._emit_event(confirmation_message=step.confirm_message)
            log.info("Step '%s' waiting for confirmation", step.name)
            while not self._stop_event.is_set() and not self._skip_event.is_set():
                if self._confirm_event.wait(timeout=0.2):
                    break
            if self._stop_event.is_set():
                step.status = StepStatus.SKIPPED
                self._emit_event()
                return
            if self._skip_event.is_set():
                self._skip_event.clear()
                step.status = StepStatus.SKIPPED
                log.info("Step '%s' skipped (confirmation)", step.name)
                self._emit_event()
                return

        # Record start volumes for this step
        self._step_start_volumes.clear()
        if self._acquisition:
            for sensor_idx in step.sensor_setpoints:
                self._step_start_volumes[sensor_idx] = self._acquisition.get_volume(sensor_idx)

        self._emit_event()
        log.info("Step '%s' starting", step.name)

        # Set flow setpoints for this step
        for sensor_idx, setpoint in step.sensor_setpoints.items():
            ch_idx = self._sensor_to_channel.get(sensor_idx)
            if ch_idx is not None:
                self._channel_manager.pipeline_set_setpoint(ch_idx, setpoint)

        # Reset and start trigger evaluation
        step.trigger.reset()
        tick_s = PIPELINE_TICK_MS / 1000.0

        while not self._stop_event.is_set() and not self._skip_event.is_set():
            # Handle pause
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            # Check trigger
            triggered = step.trigger.check(
                get_flow=self._get_flow,
                get_volume=self._get_volume,
            )

            # Compute step volumes
            step_volumes = self._compute_step_volumes()

            self._emit_event(
                progress=step.trigger.progress(),
                step_volumes=step_volumes,
            )

            if triggered:
                step.status = StepStatus.COMPLETED
                log.info("Step '%s' completed (trigger satisfied)", step.name)
                self._apply_on_complete(step)
                self._emit_event(step_volumes=step_volumes)
                return

            self._stop_event.wait(tick_s)

        if self._skip_event.is_set():
            self._skip_event.clear()
            step.status = StepStatus.SKIPPED
            log.info("Step '%s' skipped", step.name)
        else:
            step.status = StepStatus.SKIPPED

        self._emit_event()

    def _apply_on_complete(self, step: PipelineStep) -> None:
        if step.on_complete == "hold":
            return
        for sensor_idx in step.sensor_setpoints:
            ch_idx = self._sensor_to_channel.get(sensor_idx)
            if ch_idx is None:
                continue
            if step.on_complete == "zero":
                self._channel_manager.pipeline_set_setpoint(ch_idx, 0.0)
                log.info("Step on_complete=zero: ch%d -> 0", ch_idx)
            elif step.on_complete == "revert":
                self._channel_manager.pipeline_release_channel(ch_idx)
                log.info("Step on_complete=revert: ch%d -> base", ch_idx)

    def _get_flow(self, sensor_index: int) -> float:
        if self._acquisition:
            return self._acquisition._sdk.get_sensor_value(sensor_index)
        return 0.0

    def _get_volume(self, sensor_index: int) -> float:
        if self._acquisition:
            return self._acquisition.get_volume(sensor_index)
        return 0.0

    def _compute_step_volumes(self) -> dict[int, float]:
        result = {}
        if self._acquisition:
            for sensor_idx, start_vol in self._step_start_volumes.items():
                current = self._acquisition.get_volume(sensor_idx)
                result[sensor_idx] = current - start_vol
        return result

    def _emit_event(
        self,
        progress: float = 0.0,
        error_msg: str = "",
        step_volumes: dict[int, float] | None = None,
        confirmation_message: str = "",
    ) -> None:
        step_name = ""
        if 0 <= self._current_step_idx < len(self._steps):
            step_name = self._steps[self._current_step_idx].name
            if progress == 0.0:
                progress = self._steps[self._current_step_idx].trigger.progress()

        event = PipelineEvent(
            state=self._state,
            current_step=self._current_step_idx,
            total_steps=len(self._steps),
            step_name=step_name,
            progress=progress,
            error_msg=error_msg,
            step_volumes=step_volumes or {},
            confirmation_message=confirmation_message,
        )
        if not self._event_queue.full():
            self._event_queue.put(event)
