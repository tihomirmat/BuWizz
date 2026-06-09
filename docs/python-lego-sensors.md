# Using Python with LEGO sensors via BuWizz

This is the practical guide you asked for: how to read and act on **LEGO
sensors** from Python through a BuWizz 3.0 brick, plus a roadmap of concrete
"updates" (improvements) to grow this from motor control toward full sensor
support.

## TL;DR

```python
import asyncio
from buwizz import BuWizz
from buwizz.sensors import read_encoders

async def main():
    async with BuWizz() as bw:           # scan + connect
        await bw.set_data_period(50)     # 20 Hz telemetry
        report = await bw.wait_for_status()
        for s in read_encoders(report):  # one entry per attached LEGO device
            print(s.port, s.device, "pos=", s.absolute_position)

asyncio.run(main())
```

Install the dependency first: `pip install bleak` (or `pip install -e .` from
the repo root).

## Two ways to read LEGO sensors

BuWizz 3 supports LEGO Powered Up (PU) devices on its four PU ports. There are
two access levels, and you should prefer the first.

### 1. Decoded telemetry — recommended, works today

When a PU port is in a servo mode, the brick **already decodes** the attached
device and includes its data in every status report: device *type*, *velocity*,
*absolute position* (0-359°) and a cumulative *running position*. For motors
with built-in encoders and for rotation sensors, that is exactly the sensor
reading you want, and it needs no special protocol work.

```python
from buwizz import BuWizz
from buwizz.sensors import read_encoders

async with BuWizz() as bw:
    # Put port 1 in absolute-position servo mode so its encoder is reported.
    from buwizz.protocol import PuPortFunction
    await bw.set_pu_port_functions([PuPortFunction.PU_ABSOLUTE_POSITION_SERVO])
    await bw.set_data_period(50)

    while True:
        report = await bw.wait_for_status()
        for s in read_encoders(report):
            print(f"{s.device}: vel={s.velocity} abs={s.absolute_position}")
```

This is what [`examples/read_lego_sensor.py`](../examples/read_lego_sensor.py)
demonstrates.

### 2. Raw UART / LWP3 — advanced, for richer sensors

Sensors like the Boost/SPIKE colour & distance sensor expose multiple "modes"
(colour, reflected light, distance, RGB...) that aren't all surfaced in the
status report. To reach those you switch the port to **`GENERIC_PWM` (0x00)**,
which turns motor ports 1-4 into a **transparent UART** on the dedicated GATT
characteristics (`0x3901`-`0x3904`), then speak the **LEGO Wire Protocol 3
(LWP3)** directly to the device.

`buwizz.sensors.UartSensorPort` gives you the plumbing, and
`buwizz.lwp3` supplies the LEGO device catalogue and LWP3 frame builders:

```python
from buwizz import BuWizz
from buwizz.sensors import UartSensorPort, parse_lwp3_message

async with BuWizz() as bw:
    port = UartSensorPort(bw._client, port=1)        # bleak client
    await port.open(on_frame=lambda f: print(parse_lwp3_message(f)))
    # Select a sensor mode and start streaming (e.g. distance mode on the
    # Boost colour/distance sensor). Mode numbers come from the device's mode
    # table — the Pybricks docs are an excellent reference.
    await port.set_mode(mode=8, delta=1)
    # Streamed PORT_VALUE frames arrive in the on_frame callback.
```

### Where the LEGO sensor data comes from: Pybricks

Rather than re-deriving LEGO's device catalogue and LWP3 message taxonomy by
hand, `buwizz.lwp3` reuses the **Pybricks** project's well-maintained mapping
(`pybricksdev.ble.lwp3.bytecodes`), which is MIT-licensed. From it we get:

- `LegoDeviceType` — every Powered Up / Technic / SPIKE / BOOST / WeDo / EV3
  device id, so a status report's "motor type" byte becomes a readable name;
- `MessageKind` — the full set of LWP3 message kinds (attached-IO, port value,
  input-format setup, etc.) used to interpret UART frames;
- frame builders such as `port_input_format_setup()` for selecting a sensor
  mode.

See `NOTICE.md` for attribution. Pybricks' per-device **mode tables** (which
mode number returns colour vs. distance vs. reflected light, and the value
scaling) are the natural next thing to fold in — that's roadmap item #1.

> The per-device LWP3 handshake (mode setup, value scaling) is still
> sensor-specific. The envelope parsing and frame building are done; mapping
> each sensor's modes to physical units is the main area to build out.

## Why a higher-level Python API matters here

The community `bleak`-based library this repo imports
(`third_party/buwizz-pro3-bluetooth-python`) is a great starting point but is
explicitly early-stage ("Quickstart: tbd", several `TODO`s, and a note that the
accelerometer sign handling was unfinished). The `buwizz` package in this repo
addresses those gaps with:

- a **hardware-free protocol layer** (`buwizz.protocol`) that is fully unit
  tested, so encoding/decoding can be validated in CI without a brick;
- correct **signed accelerometer** decoding and a typed `StatusReport`;
- an ergonomic **async client** with context-manager connect/disconnect,
  status callbacks, and `wait_for_status()`;
- first-class **sensor helpers** (`read_encoders`, `UartSensorPort`).

## Suggested updates / roadmap

Concrete, incremental improvements — ordered roughly by value-to-effort:

1. **Sensor mode library for LWP3 (port Pybricks' mode tables).** Build on the
   `buwizz.lwp3` constants by importing Pybricks' per-device mode tables, so
   each sensor (Boost/SPIKE colour-distance, force, ultrasonic) knows which
   mode returns which quantity and how to scale it. This turns mechanism #2
   above into a one-liner like `await port.read_color()`.
2. **Auto-detect attached devices.** Use the status report's device-type byte
   (and LWP3 attached-IO messages) to enumerate what is plugged into each port
   and pick sensible defaults.
3. **Servo convenience API.** Wrap `0x50/0x52/0x53` into
   `await bw.run_to_angle(port, degrees)` and `await bw.run_at_speed(...)`
   with sane default PID parameters from the API's default table.
4. **Synchronous + event-loop-friendly facades.** Offer a small blocking
   wrapper for classroom/REPL use, and an `async for status in bw.stream():`
   iterator for reactive control loops.
5. **Recording & replay.** Log status reports to CSV/Parquet for plotting
   sensor data (great for physics/robotics lessons).
6. **CLI tool.** `python -m buwizz scan|status|drive` for quick diagnostics
   without writing code.
7. **Type-checked + CI.** Add `mypy`, ruff, and a GitHub Actions workflow that
   runs the existing `pytest` suite on every push.
8. **BuWizz 2.0 support.** The older brick uses a different, simpler command
   set (e.g. `0x10` set speed, `0x11` set mode — visible in the official
   Android demo). A `buwizz.protocol_v2` module would broaden hardware support.
9. **Firmware-update tooling (careful).** A diagnostic that reads the
   bootloader response fields from the status report and reports current
   firmware version from the advertisement data — *without* implementing an
   actual flash, which should stay with the official app for safety.

## References

- Official BuWizz API & downloads: <https://buwizz.com/>
- Community library (imported here, MIT):
  <https://github.com/neozenith/buwizz-pro3-bluetooth-python>
- Official Android demo (referenced): <https://github.com/BuWizz/BuWizz-Android-Demo>
- LEGO Wire Protocol 3 (LWP3) is documented by LEGO and mirrored by the
  Pybricks project: <https://github.com/pybricks>
- `bleak` cross-platform BLE library: <https://github.com/hbldh/bleak>
