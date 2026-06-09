"""Tests for the Pybricks-derived LWP3 layer (no hardware required)."""

from buwizz import lwp3
from buwizz.lwp3 import LegoDeviceType, MessageKind, device_name


def test_device_type_ids():
    assert LegoDeviceType.BOOST_COLOR_DISTANCE_SENSOR == 0x25
    assert LegoDeviceType.SPIKE_ULTRASONIC_SENSOR == 0x3E
    assert LegoDeviceType.TECHNIC_LARGE_ANGULAR_MOTOR == 0x4C


def test_device_name_known_and_unknown():
    assert device_name(0x25) == "Boost Color Distance Sensor"
    assert device_name(0x2E) == "Technic Large Motor"
    assert device_name(0x99) == "Unknown (0x99)"


def test_message_kind_values():
    assert MessageKind.PORT_VALUE == 0x45
    assert MessageKind.PORT_INPUT_FMT_SETUP == 0x41
    assert MessageKind.HUB_ATTACHED_IO == 0x04


def test_encode_frame_length_byte_counts_itself():
    frame = lwp3.encode_frame(0x00, MessageKind.PORT_INFO_REQ, b"\x01\x00")
    # length(1) + hub(1) + kind(1) + payload(2) = 5
    assert frame[0] == 5
    assert frame[1] == 0x00
    assert frame[2] == MessageKind.PORT_INFO_REQ
    assert frame[3:] == b"\x01\x00"


def test_port_input_format_setup_frame():
    # Select mode 8 on port 0, delta=5, notifications on.
    frame = lwp3.port_input_format_setup(port=0, mode=8, delta=5, notify=True)
    assert frame[0] == len(frame)
    assert frame[2] == MessageKind.PORT_INPUT_FMT_SETUP
    assert frame[3] == 0      # port
    assert frame[4] == 8      # mode
    assert int.from_bytes(frame[5:9], "little") == 5
    assert frame[9] == 1      # notifications enabled
