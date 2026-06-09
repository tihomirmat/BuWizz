"""buwizz - control a BuWizz 3.0 LEGO power brick from Python.

The package is split into:

* :mod:`buwizz.protocol` - pure, hardware-free encoding/decoding of the
  documented BuWizz 3.0 BLE protocol (no Bluetooth dependency).
* :mod:`buwizz.client` - an async, ``bleak``-based controller (:class:`BuWizz`).
* :mod:`buwizz.sensors` - helpers for reading LEGO sensors via BuWizz.

See the project README and ``docs/`` for the protocol reference and a guide to
using Python with LEGO sensors.
"""

from . import lwp3, protocol, sensors
from .protocol import (
    BatteryLevel,
    Command,
    PuPortFunction,
    StatusReport,
    decode_status_report,
)

__all__ = [
    "protocol",
    "sensors",
    "lwp3",
    "BuWizz",
    "Command",
    "PuPortFunction",
    "BatteryLevel",
    "StatusReport",
    "decode_status_report",
]

__version__ = "0.1.0"


def __getattr__(name: str):
    # Lazily import the bleak-dependent client so `import buwizz.protocol`
    # works even without bleak installed.
    if name == "BuWizz":
        from .client import BuWizz

        return BuWizz
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
