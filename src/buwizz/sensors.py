"""Reading LEGO sensors through a BuWizz 3.0 brick from Python.

BuWizz 3 exposes LEGO devices on its four "Powered Up" (PU) ports in two ways,
and this module covers both:

1. **Decoded telemetry (fully supported).** When a PU port runs in a servo
   mode, the periodic status report already carries each motor's *type*,
   *velocity*, *absolute position* and *running position*. For rotation
   sensors and motor encoders this is all you need and it works out of the
   box - see :func:`read_encoders`.

2. **Raw UART pass-through (advanced).** When a PU port function is set to
   ``GENERIC_PWM`` (0x00), motor ports 1-4 expose a transparent UART channel
   on the dedicated GATT characteristics (``0x3901``-``0x3904``). Over that
   channel you can speak the LEGO Wire Protocol 3 (LWP3) to richer sensors
   (colour & distance sensor, etc.). :class:`UartSensorPort` gives you the
   plumbing; the LWP3 message parsing is intentionally minimal and documented
   as a starting point because the per-device handshake varies by sensor.

The first mechanism is the recommended path for most projects and is what the
examples use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from . import protocol
from .lwp3 import LegoDeviceType, MessageKind, device_name, port_input_format_setup
from .protocol import PuPortFunction, StatusReport

# The LEGO device catalogue and LWP3 message taxonomy come from the Pybricks
# project (see buwizz.lwp3 and NOTICE.md). ``device_name`` and the
# ``LegoDeviceType`` enum are re-exported here for convenience.
__all__ = [
    "LegoDeviceType",
    "MessageKind",
    "device_name",
    "EncoderReading",
    "read_encoders",
    "UartSensorPort",
    "parse_lwp3_message",
]


@dataclass
class EncoderReading:
    """A single PU port's motion telemetry, decoded from a status report."""

    port: int                 # 1..4
    device: str               # human-readable device name
    type_id: int
    velocity: int             # signed, device units
    absolute_position: int    # 0..359 typically (degrees)
    position: int             # cumulative running position


def read_encoders(report: StatusReport) -> List[EncoderReading]:
    """Extract per-port encoder/velocity readings from a status report.

    Ports with no device attached report a type id of 0 and are skipped.
    """
    readings: List[EncoderReading] = []
    for i, motor in enumerate(report.powered_up_motors, start=1):
        if motor.motor_type == 0:
            continue
        readings.append(
            EncoderReading(
                port=i,
                device=device_name(motor.motor_type),
                type_id=motor.motor_type,
                velocity=motor.velocity,
                absolute_position=motor.absolute_position,
                position=motor.position,
            )
        )
    return readings


# ---------------------------------------------------------------------------
# Advanced: raw UART pass-through for LWP3 sensors
# ---------------------------------------------------------------------------
class UartSensorPort:
    """Transparent UART access to a LEGO device on PU ports 1-4.

    Set the port to :attr:`PuPortFunction.GENERIC_PWM` first so the brick stops
    managing the port itself and forwards bytes verbatim. Then subscribe to
    notifications on the matching UART characteristic and write LWP3 frames.

    This is a thin, backend-agnostic helper: pass any object exposing
    ``write_gatt_char(uuid, data)`` and ``start_notify(uuid, cb)`` coroutines
    (a :class:`bleak.BleakClient` works directly).
    """

    def __init__(self, ble_client, port: int):
        if not 1 <= port <= 4:
            raise ValueError("UART pass-through is only available on ports 1-4")
        self._client = ble_client
        self._port = port
        self._char = protocol.UART_CHARACTERISTICS[port - 1]
        self._on_frame: Optional[Callable[[bytes], None]] = None

    async def open(self, on_frame: Optional[Callable[[bytes], None]] = None) -> None:
        """Enable raw UART on this port and start receiving frames."""
        self._on_frame = on_frame
        # The brick must be told to stop driving this port (function 0x00) so
        # the UART channel becomes transparent.
        await self._client.write_gatt_char(
            protocol.CHAR_APPLICATION,
            protocol.set_pu_port_function(
                [PuPortFunction.GENERIC_PWM if p == self._port - 1
                 else PuPortFunction.PU_SIMPLE_PWM for p in range(4)]
            ),
        )
        await self._client.start_notify(self._char, self._handle)

    def _handle(self, _char, data: bytearray) -> None:
        if self._on_frame is not None:
            self._on_frame(bytes(data))

    async def send(self, frame: bytes) -> None:
        """Write a raw LWP3 frame to the device on this port."""
        await self._client.write_gatt_char(self._char, frame)

    async def set_mode(self, mode: int, delta: int = 1, notify: bool = True) -> None:
        """Select a sensor mode and start streaming its values.

        Builds an LWP3 'Port Input Format Setup' frame (via
        :func:`buwizz.lwp3.port_input_format_setup`) and writes it to the port.
        For example, on the Boost colour/distance sensor different modes return
        colour index, reflected light, or distance. Consult the device's mode
        table (the Pybricks docs are a good reference) for the mode numbers.
        """
        frame = port_input_format_setup(
            self._port - 1, mode, delta=delta, notify=notify
        )
        await self.send(frame)


def parse_lwp3_message(frame: bytes) -> dict:
    """Minimal LEGO Wire Protocol 3 frame parser.

    LWP3 frames begin with a length byte (or extended length), a hub id byte
    (``0x00``) and a message-type byte, followed by a type-specific payload.
    This returns the high-level envelope so callers can dispatch on the
    message type; payload decoding is left to the caller because it is
    sensor-specific. See the LWP3 specification for message-type values.
    """
    if len(frame) < 3:
        return {"length": len(frame), "type": None, "payload": b""}
    length = frame[0]
    offset = 1
    if length & 0x80:  # extended (2-byte) length
        length = (length & 0x7F) | (frame[1] << 7)
        offset = 2
    hub_id = frame[offset]
    msg_type = frame[offset + 1]
    payload = frame[offset + 2:]
    try:
        kind = MessageKind(msg_type)
    except ValueError:
        kind = None
    return {
        "length": length,
        "hub_id": hub_id,
        "type": msg_type,
        "kind": kind,
        "payload": payload,
    }
