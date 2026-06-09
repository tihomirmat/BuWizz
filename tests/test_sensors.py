"""Unit tests for the sensors helpers (no hardware required)."""

import struct

from buwizz import protocol
from buwizz.sensors import device_name, parse_lwp3_message, read_encoders


def _status_with_motor(type_id, velocity, abs_pos, pos):
    data = bytearray(54)
    data[0] = protocol.Command.STATUS_REPORT
    data[2] = 60
    data[22] = type_id
    data[23] = struct.pack("<b", velocity)[0]
    struct.pack_into("<H", data, 24, abs_pos)
    struct.pack_into("<I", data, 26, pos)
    return protocol.decode_status_report(bytes(data))


def test_device_name_known_and_unknown():
    assert device_name(0x2E) == "Technic Large Motor"
    assert device_name(0xFF) == "Unknown (0xFF)"


def test_read_encoders_skips_empty_ports():
    report = _status_with_motor(0x2E, 5, 90, 1000)
    readings = read_encoders(report)
    assert len(readings) == 1
    r = readings[0]
    assert r.port == 1
    assert r.device == "Technic Large Motor"
    assert r.velocity == 5
    assert r.absolute_position == 90
    assert r.position == 1000


def test_parse_lwp3_message_short():
    assert parse_lwp3_message(b"\x01")["type"] is None


def test_parse_lwp3_message_simple():
    # length=5, hub=0x00, type=0x45 (port value single), payload=2 bytes
    frame = bytes([0x05, 0x00, 0x45, 0x01, 0x02])
    msg = parse_lwp3_message(frame)
    assert msg["length"] == 5
    assert msg["hub_id"] == 0x00
    assert msg["type"] == 0x45
    assert msg["payload"] == b"\x01\x02"
