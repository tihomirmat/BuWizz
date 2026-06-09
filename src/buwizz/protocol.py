"""BuWizz 3.0 BLE protocol definitions.

This module is a clean-room implementation of the publicly documented
BuWizz 3.0 communication protocol. All values are taken from the official
BuWizz 3.0 API document (BuWizz_3.0_API_3.x), published by BuWizz at
https://buwizz.com/ .

Nothing here talks to Bluetooth directly: the module only *describes* the
protocol (UUIDs, command op-codes) and provides pure functions that build
command packets (``bytes``) and decode status reports. That keeps it easy to
unit-test without hardware and lets any BLE backend (``bleak``, Web Bluetooth,
Android, ...) reuse the same encoding logic.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Sequence, Tuple

# ---------------------------------------------------------------------------
# GATT service & characteristics
# ---------------------------------------------------------------------------
# The BuWizz application service uses 128-bit UUIDs of the form
# ``5005XXXX-74fb-4481-88b3-9919b1676e93`` where ``XXXX`` is the 16-bit short
# UUID listed in the API document.
_BASE_UUID = "5005{:04x}-74fb-4481-88b3-9919b1676e93"

SERVICE_UUID = "50050000-74fb-4481-88b3-9919b1676e93"

# Characteristic short UUIDs (from the API "Data exchange" table).
CHAR_APPLICATION = _BASE_UUID.format(0x2901)  # Write + Notify (main app channel)
CHAR_BOOTLOADER = _BASE_UUID.format(0x8000)  # Write + Notify (OTA / firmware update)
CHAR_UART_CH1 = _BASE_UUID.format(0x3901)  # Write + Notify (motor port 1 UART)
CHAR_UART_CH2 = _BASE_UUID.format(0x3902)
CHAR_UART_CH3 = _BASE_UUID.format(0x3903)
CHAR_UART_CH4 = _BASE_UUID.format(0x3904)

UART_CHARACTERISTICS = (CHAR_UART_CH1, CHAR_UART_CH2, CHAR_UART_CH3, CHAR_UART_CH4)


# ---------------------------------------------------------------------------
# Application command op-codes (first byte of each packet)
# ---------------------------------------------------------------------------
class Command(IntEnum):
    """Application-mode command op-codes (BuWizz 3.0 API)."""

    STATUS_REPORT = 0x01          # device -> host periodic status (notify)
    SET_DEVICE_NAME = 0x20
    SET_MOTION_WAKEUP = 0x21
    SET_ACCEL_CALIBRATION = 0x22
    READ_ACCEL_CALIBRATION = 0x23
    SET_MOTOR_DATA = 0x30         # 6x int8 PWM + brake + LUT flags
    SET_MOTOR_DATA_EXT = 0x31     # ports 1-4 as 32-bit refs (PU servo) + ports 5-6
    SET_DATA_PERIOD = 0x32
    SET_RAMP_RATES = 0x33
    SET_MOTOR_TIMEOUT = 0x34
    ACTIVATE_WATCHDOG = 0x35
    SET_LED_STATUS = 0x36
    SET_ACCEL_LPF = 0x37
    SET_CURRENT_LIMITS = 0x38
    UART_BAUDRATE = 0x40
    SET_PU_PORT_FUNCTION = 0x50
    ENABLE_PID_REPORT = 0x51
    SET_SERVO_REFERENCE = 0x52
    SET_SERVO_PID_PARAMS = 0x53
    SHELF_MODE = 0xA1
    CHECK_CHARGER = 0xAC


class PuPortFunction(IntEnum):
    """Powered Up port function selectors (command 0x50).

    The first four motor ports can drive plain LEGO Power Functions motors
    (``GENERIC_PWM``) or LEGO Powered Up devices with closed-loop control.
    ``GENERIC_PWM`` (0x00) is also the only mode in which the raw UART
    pass-through on that port is available.
    """

    GENERIC_PWM = 0x00       # plain PWM output; raw UART available on this port
    PU_SIMPLE_PWM = 0x10     # default for PU motors
    PU_SPEED_SERVO = 0x14
    PU_POSITION_SERVO = 0x15
    PU_ABSOLUTE_POSITION_SERVO = 0x16


class BatteryLevel(IntEnum):
    EMPTY = 0   # motors disabled
    LOW = 1
    MEDIUM = 2
    FULL = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clamp_pwm(value: float) -> int:
    """Convert a motor command to a signed byte in -127..127.

    Floats are treated as a normalised throttle (``-1.0..1.0``) and scaled by
    127; ints are taken as raw -127..127 values. Either way the result is
    clamped to the valid range.
    """
    if isinstance(value, float):
        value = round(value * 127)
    value = int(value)
    return max(-127, min(127, value))


def _int8_bytes(value: int) -> int:
    """Return the unsigned byte representation of a signed 8-bit value."""
    return value & 0xFF


# ---------------------------------------------------------------------------
# Command builders -> bytes
# ---------------------------------------------------------------------------
def set_motor_data(
    speeds: Sequence[float],
    brake_flags: int = 0,
    disable_lut_flags: int = 0,
) -> bytes:
    """Build a 0x30 'Set motor data' packet.

    ``speeds`` is up to 6 values, one per motor output. Each value may be a
    float in ``-1.0..1.0`` or an int in ``-127..127``:
    ``-127`` = full backwards, ``0`` = stop, ``127`` = full forwards.

    ``brake_flags`` / ``disable_lut_flags`` are bit-mapped (bit 0 = motor 1 ...
    bit 5 = motor 6). A set brake bit uses slow-decay braking; a set LUT bit
    disables the output linearisation look-up table on that port.
    """
    if len(speeds) > 6:
        raise ValueError("BuWizz 3 has at most 6 motor outputs")
    payload = bytearray([Command.SET_MOTOR_DATA])
    values = list(speeds) + [0] * (6 - len(speeds))
    payload += bytes(_int8_bytes(_clamp_pwm(v)) for v in values)
    payload.append(brake_flags & 0x3F)
    payload.append(disable_lut_flags & 0x3F)
    return bytes(payload)


def set_motor_data_ext(
    pu_references: Sequence[int],
    pf_speeds: Sequence[float] = (0, 0),
    brake_flags: int = 0,
    disable_lut_flags: int = 0,
) -> bytes:
    """Build a 0x31 'Set motor data (extended/PU)' packet.

    ``pu_references`` are 4 signed 32-bit references for ports 1-4. Their
    meaning depends on each port's function (PWM, speed, or position servo).
    ``pf_speeds`` are the 2 plain int8 outputs for ports 5-6.
    """
    refs = list(pu_references) + [0] * (4 - len(pu_references))
    if len(refs) != 4:
        raise ValueError("pu_references must contain at most 4 values")
    payload = bytearray([Command.SET_MOTOR_DATA_EXT])
    for r in refs:
        payload += struct.pack("<i", int(r))
    pf = list(pf_speeds) + [0] * (2 - len(pf_speeds))
    payload += bytes(_int8_bytes(_clamp_pwm(v)) for v in pf[:2])
    payload.append(brake_flags & 0x3F)
    payload.append(disable_lut_flags & 0x3F)
    return bytes(payload)


def set_data_period(period_ms: int) -> bytes:
    """Build a 0x32 packet setting the status report period (20-255 ms)."""
    if not 20 <= period_ms <= 255:
        raise ValueError("period_ms must be in 20..255")
    return bytes([Command.SET_DATA_PERIOD, period_ms])


def set_pu_port_function(functions: Sequence[PuPortFunction]) -> bytes:
    """Build a 0x50 packet configuring the function of PU ports 1-4."""
    funcs = list(functions) + [PuPortFunction.PU_SIMPLE_PWM] * (4 - len(functions))
    if len(funcs) != 4:
        raise ValueError("functions must contain at most 4 entries")
    return bytes([Command.SET_PU_PORT_FUNCTION] + [int(f) for f in funcs])


def set_servo_reference(references: Sequence[int]) -> bytes:
    """Build a 0x52 packet with 4 signed 32-bit servo references (ports 1-4)."""
    refs = list(references) + [0] * (4 - len(references))
    payload = bytearray([Command.SET_SERVO_REFERENCE])
    for r in refs[:4]:
        payload += struct.pack("<i", int(r))
    return bytes(payload)


def enable_pid_report(port_index: int) -> bytes:
    """Build a 0x51 packet. ``port_index`` 1..4 enables, 0 disables."""
    if not 0 <= port_index <= 4:
        raise ValueError("port_index must be 0..4")
    return bytes([Command.ENABLE_PID_REPORT, port_index])


def set_led_status(colors: Sequence[Tuple[int, int, int]]) -> bytes:
    """Build a 0x36 'Set LED status' packet for the 4 RGB LEDs.

    Pass an empty sequence to restore the default LED behaviour.
    """
    if not colors:
        return bytes([Command.SET_LED_STATUS])
    payload = bytearray([Command.SET_LED_STATUS])
    leds = list(colors) + [(0, 0, 0)] * (4 - len(colors))
    for r, g, b in leds[:4]:
        payload += bytes([r & 0xFF, g & 0xFF, b & 0xFF])
    return bytes(payload)


def set_device_name(name: str) -> bytes:
    """Build a 0x20 'Set device name' packet (max 12 chars, NUL padded)."""
    raw = name.encode("ascii")[:12]
    raw = raw + b"\x00" * (12 - len(raw))
    return bytes([Command.SET_DEVICE_NAME]) + raw


def activate_watchdog(timeout_s: int) -> bytes:
    """Build a 0x35 watchdog packet (0 disables)."""
    return bytes([Command.ACTIVATE_WATCHDOG, timeout_s & 0xFF])


def set_motor_timeout(config: int) -> bytes:
    """Build a 0x34 motor-timeout packet.

    0 = stop immediately with brakes, 1 = stop immediately and coast,
    2..254 = coast to stop after N-1 seconds of no commands.
    """
    return bytes([Command.SET_MOTOR_TIMEOUT, config & 0xFF])


# ---------------------------------------------------------------------------
# Status report decoding (command 0x01)
# ---------------------------------------------------------------------------
@dataclass
class StatusFlags:
    usb_connected: bool
    battery_charging: bool
    battery_level: BatteryLevel
    ble_long_range: bool
    motion_wakeup_enabled: bool
    error: bool


@dataclass
class PoweredUpMotor:
    motor_type: int
    velocity: int          # signed 8-bit
    absolute_position: int  # unsigned 16-bit
    position: int          # unsigned 32-bit


@dataclass
class StatusReport:
    status: StatusFlags
    battery_voltage: float          # volts
    motor_currents: List[float]     # amps, 6 outputs
    temperature: int                # deg C
    accelerometer: Tuple[float, float, float]  # g, (x, y, z)
    battery_charge_current: int     # mA
    powered_up_motors: List[PoweredUpMotor]


def _decode_status_flags(b: int) -> StatusFlags:
    return StatusFlags(
        usb_connected=bool(b >> 6 & 0x1),
        battery_charging=bool(b >> 5 & 0x1),
        battery_level=BatteryLevel(b >> 3 & 0x3),
        ble_long_range=bool(b >> 2 & 0x1),
        motion_wakeup_enabled=bool(b >> 1 & 0x1),
        error=bool(b & 0x1),
    )


def _decode_accel_axis(lo: int, hi: int) -> float:
    """Decode a left-aligned 12-bit signed accelerometer axis to g.

    The two bytes hold a left-aligned 12-bit signed value at 0.488 mg/digit.
    """
    raw = (hi << 8) | lo
    value = raw >> 4              # drop the 4 unused low bits (left aligned)
    if value & 0x800:            # sign-extend the 12-bit value
        value -= 0x1000
    return round(value * 0.488 / 1000.0, 4)


def decode_status_report(data: bytes) -> StatusReport:
    """Decode a 0x01 device status report notification.

    Raises ``ValueError`` if the packet is not a status report or is too short.
    """
    if not data or data[0] != Command.STATUS_REPORT:
        raise ValueError("not a status report packet")
    if len(data) < 16:
        raise ValueError("status report too short")

    accel = (
        _decode_accel_axis(data[10], data[11]),
        _decode_accel_axis(data[12], data[13]),
        _decode_accel_axis(data[14], data[15]),
    )

    motors: List[PoweredUpMotor] = []
    # PoweredUp motor data is a 32-byte block (4x 8 bytes) starting at byte 22.
    if len(data) >= 54:
        for i in range(4):
            off = 22 + i * 8
            chunk = data[off:off + 8]
            motors.append(
                PoweredUpMotor(
                    motor_type=chunk[0],
                    velocity=struct.unpack("<b", chunk[1:2])[0],
                    absolute_position=struct.unpack("<H", chunk[2:4])[0],
                    position=struct.unpack("<I", chunk[4:8])[0],
                )
            )

    return StatusReport(
        status=_decode_status_flags(data[1]),
        battery_voltage=round(9.0 + data[2] * 0.05, 2),
        motor_currents=[round(c * 0.015, 3) for c in data[3:9]],
        temperature=data[9],
        accelerometer=accel,
        battery_charge_current=data[21] if len(data) > 21 else 0,
        powered_up_motors=motors,
    )
