"""Hardware auto-detection, initialization, and simulated mode management."""
import logging
from dataclasses import dataclass, field

from droplegen.backend.sdk_wrapper import FluigentSDK, PressureChannelInfo, SensorChannelInfo
from droplegen.config import SIM_INSTR_TYPE, SIM_INSTRUMENTS

log = logging.getLogger(__name__)


@dataclass
class HardwareState:
    connected: bool = False
    simulated: bool = False
    controllers: list[dict] = field(default_factory=list)
    pressure_channels: list[PressureChannelInfo] = field(default_factory=list)
    sensor_channels: list[SensorChannelInfo] = field(default_factory=list)


class HardwareManager:
    """Manages Fluigent hardware lifecycle: detect, init, calibrate, close."""

    def __init__(self, sdk: FluigentSDK):
        self._sdk = sdk
        self.state = HardwareState()

    @property
    def connected(self) -> bool:
        return self.state.connected

    def connect(self, simulated: bool = False) -> HardwareState:
        if self.state.connected:
            self.disconnect()

        self.state.simulated = simulated

        if simulated:
            for instr in SIM_INSTRUMENTS:
                log.info(
                    "Creating simulated instrument (type=%d, serial=%d)",
                    SIM_INSTR_TYPE, instr["serial"],
                )
                self._sdk.create_simulated_instrument(
                    SIM_INSTR_TYPE, instr["serial"], 0, instr["config"]
                )

        log.info("Initializing Fluigent SDK...")
        self._sdk.init()

        self._detect_channels()
        self.state.connected = True
        log.info(
            "Connected: %d pressure channels, %d sensor channels",
            len(self.state.pressure_channels),
            len(self.state.sensor_channels),
        )
        return self.state

    def disconnect(self) -> None:
        if not self.state.connected:
            return
        log.info("Closing Fluigent SDK...")
        self._sdk.close()

        if self.state.simulated:
            for instr in SIM_INSTRUMENTS:
                try:
                    self._sdk.remove_simulated_instrument(
                        SIM_INSTR_TYPE, instr["serial"]
                    )
                except Exception:
                    pass

        self.state = HardwareState()
        log.info("Disconnected.")

    def calibrate(self, pressure_index: int) -> None:
        if not self.state.connected:
            raise RuntimeError("Not connected")
        log.info("Calibrating pressure channel %d...", pressure_index)
        self._sdk.calibrate_pressure(pressure_index)

    def calibrate_all(self) -> None:
        for ch in self.state.pressure_channels:
            self.calibrate(ch.index)

    def _detect_channels(self) -> None:
        self.state.controllers = self._sdk.get_controllers_info()
        self.state.pressure_channels = self._sdk.get_pressure_channels_info()
        self.state.sensor_channels = self._sdk.get_sensor_channels_info()
