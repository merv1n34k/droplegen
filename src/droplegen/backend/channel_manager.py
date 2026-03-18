"""Regulation state machine implementing passive control.

Each sensor-pressure pair maintains:
- base_setpoint: persistent user value (never cleared by pipeline)
- active_setpoint: what's currently commanding hardware
- owner: "user" or "pipeline"

Key rules:
- Pipeline ONLY uses set_sensor_regulation (never set_pressure)
- When pipeline stops, channels revert to base_setpoint
- set_pressure is ONLY for emergency stop
"""
import logging
import threading
from dataclasses import dataclass

from droplegen.backend.sdk_wrapper import FluigentSDK

log = logging.getLogger(__name__)


@dataclass
class ChannelState:
    sensor_index: int
    pressure_index: int
    base_setpoint: float = 0.0
    active_setpoint: float = 0.0
    owner: str = "user"  # "user" or "pipeline"
    regulation_active: bool = False
    mode: str = "off"  # "off", "flow", "pressure"
    pressure_setpoint: float = 0.0


class ChannelManager:
    """Thread-safe regulation state machine for sensor-pressure pairs."""

    def __init__(self, sdk: FluigentSDK):
        self._sdk = sdk
        self._lock = threading.Lock()
        self._channels: list[ChannelState] = []

    @property
    def channels(self) -> list[ChannelState]:
        with self._lock:
            return list(self._channels)

    def configure_channels(self, sensor_pressure_pairs: list[tuple[int, int]]) -> None:
        with self._lock:
            self._channels = [
                ChannelState(sensor_index=si, pressure_index=pi)
                for si, pi in sensor_pressure_pairs
            ]
        log.info("Configured %d regulation channels", len(self._channels))

    def user_set_flow_regulation(
        self, channel_idx: int, setpoint: float, activate: bool = True
    ) -> None:
        with self._lock:
            ch = self._channels[channel_idx]
            ch.base_setpoint = setpoint
            ch.pressure_setpoint = 0.0
            if ch.owner == "user":
                ch.active_setpoint = setpoint
                ch.mode = "flow"
                if activate:
                    ch.regulation_active = True
                    self._sdk.set_sensor_regulation(
                        ch.sensor_index, ch.pressure_index, setpoint
                    )
                    log.info(
                        "User flow regulation ch%d: %.2f ul/min",
                        channel_idx, setpoint,
                    )

    def user_set_pressure(self, channel_idx: int, pressure_mbar: float) -> None:
        with self._lock:
            ch = self._channels[channel_idx]
            if ch.owner != "user":
                return
            ch.mode = "pressure"
            ch.pressure_setpoint = pressure_mbar
            ch.base_setpoint = 0.0
            ch.active_setpoint = 0.0
            ch.regulation_active = False
            self._sdk.set_pressure(ch.pressure_index, pressure_mbar)
            log.info(
                "User pressure ch%d: %.1f mbar",
                channel_idx, pressure_mbar,
            )

    def user_stop_regulation(self, channel_idx: int) -> None:
        with self._lock:
            ch = self._channels[channel_idx]
            if ch.owner != "user":
                return
            ch.regulation_active = False
            ch.base_setpoint = 0.0
            ch.active_setpoint = 0.0
            ch.mode = "off"
            ch.pressure_setpoint = 0.0
            self._sdk.set_pressure(ch.pressure_index, 0.0)
            log.info("User stopped regulation ch%d", channel_idx)

    def pipeline_set_setpoint(self, channel_idx: int, setpoint: float) -> None:
        with self._lock:
            ch = self._channels[channel_idx]
            ch.owner = "pipeline"
            ch.active_setpoint = setpoint
            ch.regulation_active = True
            ch.mode = "flow"
            ch.pressure_setpoint = 0.0
            self._sdk.set_sensor_regulation(
                ch.sensor_index, ch.pressure_index, setpoint
            )
            log.info(
                "Pipeline regulation ch%d: %.2f ul/min",
                channel_idx, setpoint,
            )

    def pipeline_release_all(self) -> None:
        with self._lock:
            for i, ch in enumerate(self._channels):
                if ch.owner == "pipeline":
                    ch.owner = "user"
                    ch.active_setpoint = ch.base_setpoint
                    if ch.base_setpoint > 0 or ch.regulation_active:
                        ch.mode = "flow"
                        self._sdk.set_sensor_regulation(
                            ch.sensor_index, ch.pressure_index, ch.base_setpoint
                        )
                        log.info(
                            "Pipeline released ch%d -> base %.2f ul/min",
                            i, ch.base_setpoint,
                        )
                    else:
                        ch.regulation_active = False
                        ch.mode = "off"
                        ch.pressure_setpoint = 0.0

    def emergency_stop_all(self) -> None:
        with self._lock:
            for i, ch in enumerate(self._channels):
                self._sdk.set_pressure(ch.pressure_index, 0.0)
                ch.active_setpoint = 0.0
                ch.regulation_active = False
                ch.owner = "user"
                ch.mode = "off"
                ch.pressure_setpoint = 0.0
                ch.base_setpoint = 0.0
                log.warning("EMERGENCY STOP ch%d", i)
