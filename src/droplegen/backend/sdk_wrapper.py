"""Thin wrapper over the Fluigent fgt-SDK with clean Python types."""
import sys
import os
from dataclasses import dataclass

# Inject fgt-SDK Python path so the Fluigent package can be imported
_SDK_PYTHON_PATH = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, "fgt-SDK", "Python"
)
_SDK_PYTHON_PATH = os.path.normpath(_SDK_PYTHON_PATH)
if _SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, _SDK_PYTHON_PATH)

from Fluigent.SDK import (
    fgt_init,
    fgt_close,
    fgt_create_simulated_instr,
    fgt_remove_simulated_instr,
    fgt_get_controllersInfo,
    fgt_get_pressureChannelCount,
    fgt_get_sensorChannelCount,
    fgt_get_pressureChannelsInfo,
    fgt_get_sensorChannelsInfo,
    fgt_set_pressure,
    fgt_get_pressure,
    fgt_set_sensorRegulation,
    fgt_get_sensorValue,
    fgt_get_pressureRange,
    fgt_get_sensorRange,
    fgt_calibratePressure,
    fgt_set_sensorCalibration,
    fgt_get_sensorCalibration,
    fgt_set_sensorCustomScale,
    fgt_INSTRUMENT_TYPE,
    fgt_SENSOR_TYPE,
    fgt_SENSOR_CALIBRATION,
)


@dataclass
class PressureChannelInfo:
    index: int
    controller_sn: int
    device_sn: int
    position: int
    instr_type: str
    pmin: float = 0.0
    pmax: float = 0.0


@dataclass
class SensorChannelInfo:
    index: int
    controller_sn: int
    device_sn: int
    position: int
    instr_type: str
    sensor_type: str
    smin: float = 0.0
    smax: float = 0.0


class FluigentSDK:
    """Clean Python interface to the Fluigent SDK."""

    def __init__(self):
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def create_simulated_instrument(
        self, instr_type: int, serial: int, firmware: int, config: list[int]
    ) -> None:
        fgt_create_simulated_instr(instr_type, serial, firmware, config)

    def remove_simulated_instrument(self, instr_type: int, serial: int) -> None:
        fgt_remove_simulated_instr(instr_type, serial)

    def init(self, instruments: list[int] | None = None) -> None:
        fgt_init(instruments)
        self._initialized = True

    def close(self) -> None:
        if self._initialized:
            fgt_close()
            self._initialized = False

    def get_controllers_info(self) -> list[dict]:
        controllers = fgt_get_controllersInfo()
        return [
            {
                "sn": c.SN,
                "firmware": c.Firmware,
                "index": c.index,
                "type": str(c.InstrType),
            }
            for c in controllers
        ]

    def get_pressure_channel_count(self) -> int:
        return fgt_get_pressureChannelCount()

    def get_sensor_channel_count(self) -> int:
        return fgt_get_sensorChannelCount()

    def get_pressure_channels_info(self) -> list[PressureChannelInfo]:
        channels = fgt_get_pressureChannelsInfo()
        result = []
        for ch in channels:
            pmin, pmax = fgt_get_pressureRange(ch.index)
            result.append(PressureChannelInfo(
                index=ch.index,
                controller_sn=ch.ControllerSN,
                device_sn=ch.DeviceSN,
                position=ch.position,
                instr_type=str(ch.InstrType),
                pmin=pmin,
                pmax=pmax,
            ))
        return result

    def get_sensor_channels_info(self) -> list[SensorChannelInfo]:
        channels, types = fgt_get_sensorChannelsInfo()
        result = []
        for ch, st in zip(channels, types):
            smin, smax = fgt_get_sensorRange(ch.index)
            result.append(SensorChannelInfo(
                index=ch.index,
                controller_sn=ch.ControllerSN,
                device_sn=ch.DeviceSN,
                position=ch.position,
                instr_type=str(ch.InstrType),
                sensor_type=str(st),
                smin=smin,
                smax=smax,
            ))
        return result

    def set_pressure(self, pressure_index: int, pressure: float) -> None:
        """Set pressure directly. WARNING: breaks any active sensor regulation."""
        fgt_set_pressure(pressure_index, pressure)

    def get_pressure(self, pressure_index: int) -> float:
        return fgt_get_pressure(pressure_index)

    def set_sensor_regulation(
        self, sensor_index: int, pressure_index: int, setpoint: float
    ) -> None:
        fgt_set_sensorRegulation(sensor_index, pressure_index, setpoint)

    def get_sensor_value(self, sensor_index: int) -> float:
        return fgt_get_sensorValue(sensor_index)

    def calibrate_pressure(self, pressure_index: int) -> None:
        fgt_calibratePressure(pressure_index)

    def set_sensor_calibration(self, sensor_index: int, calibration: int) -> None:
        fgt_set_sensorCalibration(sensor_index, fgt_SENSOR_CALIBRATION(calibration))

    def get_sensor_calibration(self, sensor_index: int) -> int:
        return int(fgt_get_sensorCalibration(sensor_index))

    def set_sensor_custom_scale(
        self, sensor_index: int, a: float, b: float = 0.0, c: float = 0.0,
        smax: float | None = None,
    ) -> None:
        fgt_set_sensorCustomScale(sensor_index, a, b, c, smax=smax)
