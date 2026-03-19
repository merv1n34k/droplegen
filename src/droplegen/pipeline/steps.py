"""Pipeline step dataclass."""
from dataclasses import dataclass, field
from enum import Enum

from droplegen.pipeline.triggers import Trigger


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class PipelineStep:
    name: str
    sensor_setpoints: dict[int, float]  # {sensor_index: flow_ul_min}
    trigger: Trigger
    on_complete: str = "hold"  # "hold", "zero", "revert"
    status: StepStatus = StepStatus.PENDING
    error_msg: str = ""
