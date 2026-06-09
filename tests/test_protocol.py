"""Unit tests for the hardware-free protocol layer.

These run without any Bluetooth hardware or the ``bleak`` dependency.
"""

import struct

import pytest

from buwizz import protocol
from buwizz.protocol import (
    BatteryLevel,
    Command,
    PuPortFunction,
)


def test_service_and_char_uuids():
    assert protocol.SERVICE_UUID == "50050000-74fb-4481-88b3-9919b1676e93"
    assert protocol.CHAR_APPLICATION == "50052901-74fb-4481-88b3-9919b1676e93"
    assert protocol.CHAR_BOOTLOADER == "50058000-74fb-4481-88b3-9919b1676e93"
    assert protocol.CHAR_UART_CH1 == "50053901-74fb-4481-88b3-9919b1676e93"
    assert protocol.CHAR_UART_CH4 == "50053904-74fb-4481-88b3-9919b1676e93"


def test_set_motor_data_floats_and_ints():
    pkt = protocol.set_motor_data([1.0, -1.0, 0.0, 0.5])
    assert pkt[0] == Command.SET_MOTOR_DATA
    assert pkt[1] == 127           # 1.0 -> 127
    assert pkt[2] == (-127 & 0xFF)  # -1.0 -> -127
    assert pkt[3] == 0
    assert pkt[4] == 64            # 0.5 -> 64
    assert len(pkt) == 1 + 6 + 2   # cmd + 6 motors + brake + lut


def test_set_motor_data_clamps():
    pkt = protocol.set_motor_data([5.0, -9.0])
    assert pkt[1] == 127
    assert pkt[2] == (-127 & 0xFF)


def test_set_motor_data_rejects_too_many():
    with pytest.raises(ValueError):
        protocol.set_motor_data([0] * 7)


def test_set_data_period_bounds():
    assert protocol.set_data_period(50) == bytes([0x32, 50])
    for bad in (0, 19, 256):
        with pytest.raises(ValueError):
            protocol.set_data_period(bad)


def test_set_pu_port_function():
    pkt = protocol.set_pu_port_function(
        [PuPortFunction.PU_SPEED_SERVO, PuPortFunction.GENERIC_PWM]
    )
    assert pkt[0] == Command.SET_PU_PORT_FUNCTION
    assert pkt[1] == 0x14
    assert pkt[2] == 0x00
    assert pkt[3] == 0x10  # padded default
    assert len(pkt) == 5


def test_set_servo_reference_packs_int32():
    pkt = protocol.set_servo_reference([1000, -2000, 0, 0])
    assert pkt[0] == Command.SET_SERVO_REFERENCE
    assert struct.unpack("<i", pkt[1:5])[0] == 1000
    assert struct.unpack("<i", pkt[5:9])[0] == -2000


def test_set_device_name_padding():
    pkt = protocol.set_device_name("Rover")
    assert pkt[0] == Command.SET_DEVICE_NAME
    assert pkt[1:6] == b"Rover"
    assert pkt[6:] == b"\x00" * 7
    assert len(pkt) == 13


def test_set_led_status_default_and_colors():
    assert protocol.set_led_status([]) == bytes([0x36])
    pkt = protocol.set_led_status([(255, 0, 0)])
    assert pkt[0:4] == bytes([0x36, 255, 0, 0])


def _build_status(**over):
    """Build a synthetic 54-byte status report for decoding tests."""
    data = bytearray(54)
    data[0] = Command.STATUS_REPORT
    data[1] = over.get("flags", 0)
    data[2] = over.get("vbat_raw", 60)        # 9 + 60*0.05 = 12.0 V
    for i in range(6):
        data[3 + i] = over.get("currents", [0] * 6)[i]
    data[9] = over.get("temp", 30)
    # accelerometer z = +0.5g (within the 12-bit signed range): 0.5/0.488mg -> <<4
    raw = (round(0.5 * 1000 / 0.488) & 0x0FFF) << 4
    data[14] = raw & 0xFF
    data[15] = (raw >> 8) & 0xFF
    data[21] = over.get("charge", 0)
    # one motor on port 1
    data[22] = over.get("motor_type", 0x2E)   # Technic Large Motor
    data[23] = struct.pack("<b", over.get("velocity", -10))[0]
    struct.pack_into("<H", data, 24, over.get("abs_pos", 180))
    struct.pack_into("<I", data, 26, over.get("pos", 123456))
    return bytes(data)


def test_decode_status_report_basic():
    report = protocol.decode_status_report(_build_status(flags=0b0110_1001))
    # bit6 usb=1, bit5 charging=1, bits3-4 level=01 (LOW), bit0 error=1
    assert report.status.usb_connected is True
    assert report.status.battery_charging is True
    assert report.status.battery_level == BatteryLevel.LOW
    assert report.status.error is True
    assert report.battery_voltage == 12.0
    assert report.temperature == 30
    # accel z close to +0.5g
    assert abs(report.accelerometer[2] - 0.5) < 0.02


def test_decode_status_report_motor():
    report = protocol.decode_status_report(_build_status())
    m = report.powered_up_motors[0]
    assert m.motor_type == 0x2E
    assert m.velocity == -10
    assert m.absolute_position == 180
    assert m.position == 123456


def test_decode_status_report_rejects_wrong_command():
    with pytest.raises(ValueError):
        protocol.decode_status_report(bytes([0x99, 0, 0]))


def test_accel_axis_sign_extension():
    # negative value: -0.5g
    raw = (round(-0.5 * 1000 / 0.488) & 0x0FFF) << 4
    lo, hi = raw & 0xFF, (raw >> 8) & 0xFF
    val = protocol._decode_accel_axis(lo, hi)
    assert abs(val - (-0.5)) < 0.02
