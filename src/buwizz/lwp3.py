"""LEGO Wire Protocol 3 (LWP3) definitions for use over BuWizz UART ports.

The device-type IDs and message-kind values here are derived from the
**Pybricks** project (``pybricksdev.ble.lwp3.bytecodes``), which maintains a
thorough, well-tested mapping of the LEGO Wire Protocol 3. Pybricks is released
under the MIT license (© 2018-2025 The Pybricks Authors); see ``NOTICE.md`` for
attribution.

Why this lives here: BuWizz 3.0 motor ports 1-4, when set to the ``GENERIC_PWM``
function, become a transparent UART carrying LWP3 frames to/from an attached
LEGO Powered Up device. Reusing Pybricks' battle-tested constants saves us from
re-deriving the LEGO device catalogue and message taxonomy by hand.

Reference: https://github.com/pybricks/pybricksdev (MIT)
"""

from __future__ import annotations

from enum import IntEnum


class LegoDeviceType(IntEnum):
    """LEGO Powered Up I/O device type IDs (LWP3 "I/O type").

    Mirrors Pybricks' ``IODeviceKind``. The same IDs appear in BuWizz status
    reports (the "motor type" byte) and in LWP3 *Hub Attached I/O* messages.
    """

    NONE = 0x00
    MEDIUM_MOTOR = 0x01
    TRAIN_MOTOR = 0x02
    LIGHTS = 0x08
    HUB_BATTERY_VOLTAGE = 0x14
    HUB_BATTERY_CURRENT = 0x15
    HUB_PIEZO = 0x16
    HUB_STATUS_LIGHT = 0x17
    EV3_COLOR_SENSOR = 0x1D
    EV3_ULTRASONIC_SENSOR = 0x1E
    EV3_GYRO_SENSOR = 0x20
    EV3_IR_SENSOR = 0x21
    WEDO_TILT_SENSOR = 0x22
    WEDO_MOTION_SENSOR = 0x23
    WEDO_GENERIC = 0x24
    BOOST_COLOR_DISTANCE_SENSOR = 0x25
    BOOST_INTERACTIVE_MOTOR = 0x26
    BOOST_HUB_MOTOR = 0x27
    BOOST_HUB_ACCEL = 0x28
    DUPLO_TRAIN_MOTOR = 0x29
    DUPLO_TRAIN_BEEPER = 0x2A
    DUPLO_TRAIN_COLOR_SENSOR = 0x2B
    DUPLO_TRAIN_SPEED = 0x2C
    TECHNIC_LARGE_MOTOR = 0x2E
    TECHNIC_XL_MOTOR = 0x2F
    SPIKE_MEDIUM_MOTOR = 0x30
    SPIKE_LARGE_MOTOR = 0x31
    HUB_IMU_GESTURE = 0x36
    REMOTE_BUTTONS = 0x37
    HUB_RSSI = 0x38
    HUB_IMU_ACCEL = 0x39
    HUB_IMU_GYRO = 0x3A
    HUB_IMU_ORIENTATION = 0x3B
    HUB_IMU_TEMPERATURE = 0x3C
    SPIKE_COLOR_SENSOR = 0x3D
    SPIKE_ULTRASONIC_SENSOR = 0x3E
    SPIKE_FORCE_SENSOR = 0x3F
    TECHNIC_MEDIUM_ANGULAR_MOTOR = 0x4B
    TECHNIC_LARGE_ANGULAR_MOTOR = 0x4C


class MessageKind(IntEnum):
    """LWP3 message-kind byte (mirrors Pybricks' ``MessageKind``)."""

    HUB_PROPERTY = 0x01
    HUB_ACTION = 0x02
    HUB_ALERT = 0x03
    HUB_ATTACHED_IO = 0x04
    ERROR = 0x05
    HW_NET_CMD = 0x08
    FW_UPDATE = 0x10
    PORT_INFO_REQ = 0x21
    PORT_MODE_INFO_REQ = 0x22
    PORT_INPUT_FMT_SETUP = 0x41
    PORT_INPUT_FMT_SETUP_COMBO = 0x42
    PORT_INFO = 0x43
    PORT_MODE_INFO = 0x44
    PORT_VALUE = 0x45
    PORT_VALUE_COMBO = 0x46
    PORT_INPUT_FMT = 0x47
    PORT_INPUT_FMT_COMBO = 0x48
    VIRTUAL_PORT_SETUP = 0x61
    PORT_OUTPUT_CMD = 0x81
    PORT_OUTPUT_CMD_FEEDBACK = 0x82


def device_name(type_id: int) -> str:
    """Human-readable name for a LEGO device type id."""
    for device in LegoDeviceType:
        if device.value == type_id:
            return device.name.replace("_", " ").title()
    return f"Unknown (0x{type_id:02X})"


def encode_frame(hub_id: int, kind: int, payload: bytes = b"") -> bytes:
    """Encode a complete LWP3 frame (single-byte length form, <128 bytes).

    Frame = [length][hub_id][message kind][payload...], where ``length`` counts
    the whole frame including itself.
    """
    body = bytes([hub_id & 0xFF, kind & 0xFF]) + payload
    length = len(body) + 1
    if length >= 0x80:
        raise ValueError("use extended length for frames >= 128 bytes")
    return bytes([length]) + body


def port_input_format_setup(
    port: int, mode: int, delta: int = 1, notify: bool = True, hub_id: int = 0
) -> bytes:
    """Build a 'Port Input Format Setup (single)' frame (kind 0x41).

    This is how you tell a LEGO sensor which *mode* to report (e.g. colour vs.
    distance on the colour/distance sensor) and to start streaming values.

    Payload: port, mode, delta interval (uint32 LE), notifications enabled.
    """
    payload = bytes([port & 0xFF, mode & 0xFF])
    payload += int(delta).to_bytes(4, "little")
    payload += bytes([1 if notify else 0])
    return encode_frame(hub_id, MessageKind.PORT_INPUT_FMT_SETUP, payload)
