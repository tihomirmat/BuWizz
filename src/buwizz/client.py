"""High-level async client for the BuWizz 3.0 brick.

Built on `bleak <https://github.com/hbldh/bleak>`_ so it runs on Windows,
macOS, Linux and Raspberry Pi from the same code. The client wraps the raw
protocol in :mod:`buwizz.protocol` with convenient, well-named coroutines.

Example
-------
.. code-block:: python

    import asyncio
    from buwizz import BuWizz

    async def main():
        async with BuWizz() as bw:          # scans & connects to first BuWizz
            await bw.set_motors([1.0, 0, 0, 0])   # port 1 full forward
            await asyncio.sleep(2)
            await bw.stop()

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, Sequence

from . import protocol
from .protocol import PuPortFunction, StatusReport

try:  # bleak is an optional import so the protocol layer can be used standalone
    from bleak import BleakClient, BleakScanner
    from bleak.backends.device import BLEDevice
except ImportError:  # pragma: no cover - exercised only without bleak installed
    BleakClient = BleakScanner = BLEDevice = None  # type: ignore


StatusCallback = Callable[[StatusReport], None]


class BuWizz:
    """Asynchronous controller for a single BuWizz 3.0 device."""

    #: Default name prefix advertised by BuWizz 3 devices.
    NAME_PREFIX = "BuWizz"

    def __init__(self, device: "Optional[BLEDevice | str]" = None):
        if BleakClient is None:
            raise RuntimeError(
                "bleak is required for the BuWizz client. Install with "
                "`pip install bleak`."
            )
        self._device = device
        self._client: Optional[BleakClient] = None
        self._status_cb: Optional[StatusCallback] = None
        self._last_status: Optional[StatusReport] = None

    # -- discovery / connection ------------------------------------------
    @classmethod
    async def discover(cls, timeout: float = 8.0) -> "list[BLEDevice]":
        """Return all advertising BuWizz devices found within ``timeout``."""
        devices = await BleakScanner.discover(timeout=timeout)
        return [
            d
            for d in devices
            if (d.name or "").startswith(cls.NAME_PREFIX)
            or protocol.SERVICE_UUID.lower()
            in [u.lower() for u in (getattr(d, "metadata", {}) or {}).get("uuids", [])]
        ]

    async def connect(self, timeout: float = 8.0) -> "BuWizz":
        """Connect to the configured device, scanning for one if needed."""
        device = self._device
        if device is None:
            found = await self.discover(timeout)
            if not found:
                raise RuntimeError("no BuWizz device found")
            device = found[0]
        self._client = BleakClient(device)
        await self._client.connect()
        # Enable status notifications (writing to CCCD is handled by bleak).
        await self._client.start_notify(
            protocol.CHAR_APPLICATION, self._on_notify
        )
        return self

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self.stop()
            finally:
                await self._client.disconnect()
                self._client = None

    async def __aenter__(self) -> "BuWizz":
        return await self.connect()

    async def __aexit__(self, *exc) -> None:
        await self.disconnect()

    # -- notifications ----------------------------------------------------
    def on_status(self, callback: Optional[StatusCallback]) -> None:
        """Register a callback invoked on every decoded status report."""
        self._status_cb = callback

    @property
    def last_status(self) -> Optional[StatusReport]:
        return self._last_status

    def _on_notify(self, _char, data: bytearray) -> None:
        if data and data[0] == protocol.Command.STATUS_REPORT:
            try:
                report = protocol.decode_status_report(bytes(data))
            except ValueError:
                return
            self._last_status = report
            if self._status_cb is not None:
                self._status_cb(report)

    # -- low level --------------------------------------------------------
    async def _write(self, packet: bytes, *, response: bool = False) -> None:
        if self._client is None:
            raise RuntimeError("not connected")
        await self._client.write_gatt_char(
            protocol.CHAR_APPLICATION, packet, response=response
        )

    # -- high level commands ---------------------------------------------
    async def set_data_period(self, period_ms: int) -> None:
        await self._write(protocol.set_data_period(period_ms))

    async def set_motors(
        self,
        speeds: Sequence[float],
        brake_flags: int = 0,
        disable_lut_flags: int = 0,
    ) -> None:
        """Drive motor outputs. ``speeds`` are floats -1.0..1.0 per port."""
        await self._write(
            protocol.set_motor_data(speeds, brake_flags, disable_lut_flags)
        )

    async def stop(self) -> None:
        """Set all motor outputs to zero."""
        await self._write(protocol.set_motor_data([0, 0, 0, 0, 0, 0]))

    async def set_pu_port_functions(
        self, functions: Sequence[PuPortFunction]
    ) -> None:
        await self._write(protocol.set_pu_port_function(functions))

    async def set_servo_references(self, references: Sequence[int]) -> None:
        await self._write(protocol.set_servo_reference(references))

    async def set_leds(self, colors) -> None:
        await self._write(protocol.set_led_status(colors))

    async def set_name(self, name: str) -> None:
        await self._write(protocol.set_device_name(name))

    async def activate_watchdog(self, timeout_s: int) -> None:
        await self._write(protocol.activate_watchdog(timeout_s))

    async def wait_for_status(self, timeout: float = 2.0) -> StatusReport:
        """Wait for the next status report and return it."""
        fut: "asyncio.Future[StatusReport]" = asyncio.get_event_loop().create_future()

        def _cb(report: StatusReport) -> None:
            if not fut.done():
                fut.set_result(report)

        prev = self._status_cb
        self._status_cb = _cb
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._status_cb = prev
