# BuWizz — firmware references & Python control library

Control a **BuWizz 3.0** LEGO® power brick — motors, servos and LEGO sensors —
from Python over Bluetooth Low Energy, plus curated, properly-attributed
references to the publicly available BuWizz firmware/software.

> BuWizz is a Bluetooth battery+motor controller for models built from LEGO®
> bricks. This is an independent, community project and is not affiliated with
> or endorsed by BuWizz d.o.o. or the LEGO Group.

## What's in this repo

| Path | What it is |
|------|------------|
| `src/buwizz/` | **Original** Python library: pure protocol layer + async `bleak` client + LEGO sensor helpers (`buwizz.lwp3` reuses Pybricks' LEGO device catalogue) |
| `examples/` | Runnable scripts: scan, drive motors, stream status, read LEGO sensors |
| `tests/` | Hardware-free unit tests for the protocol/sensor layers (`pytest`) |
| `docs/firmware.md` | BuWizz 3.0 firmware architecture & OTA-update mechanism (from the public API) |
| `docs/ble-protocol.md` | Condensed BLE protocol reference |
| `docs/python-lego-sensors.md` | **Guide + roadmap: using Python with LEGO sensors** |
| `docs/ios-ble-latency-software.md` | iOS 26 BLE-lag fix plan for the **app** developer (Flutter) |
| `docs/ios-ble-latency-firmware.md` | iOS 26 BLE-lag fix plan for the **firmware** team |
| `third_party/` | Imported MIT-licensed community library (with its license preserved) |
| `NOTICE.md` | Provenance & licensing of all imported/referenced material |

## On "firmware and software"

- **Software (imported):** the MIT-licensed community library
  [`buwizz-pro3-bluetooth-python`](https://github.com/neozenith/buwizz-pro3-bluetooth-python)
  is vendored under `third_party/` (license preserved). On top of it, this repo
  adds an original, tested `buwizz` package.
- **Firmware:** the brick's firmware (Nordic nRF52833 + "Tajnik" co-processor)
  is **proprietary/closed-source** and is delivered only as signed OTA images
  through the official BuWizz app — there is no public firmware source to
  import. `docs/firmware.md` documents its architecture and the public OTA
  protocol instead. See `NOTICE.md` for the full rationale.
- **LEGO sensor data:** the LEGO device catalogue and LWP3 message taxonomy in
  `buwizz.lwp3` are derived from the MIT-licensed
  [Pybricks](https://github.com/pybricks/pybricksdev) project.

## Quick start

```bash
pip install -e .          # installs the `buwizz` package + bleak
python examples/scan.py   # find your brick
python examples/read_lego_sensor.py
```

```python
import asyncio
from buwizz import BuWizz
from buwizz.protocol import PuPortFunction
from buwizz.sensors import read_encoders

async def main():
    async with BuWizz() as bw:                 # scan + connect to first BuWizz
        await bw.set_pu_port_functions([PuPortFunction.PU_ABSOLUTE_POSITION_SERVO])
        await bw.set_data_period(50)           # 20 Hz telemetry
        await bw.set_motors([0.5, 0, 0, 0])    # port 1 half speed forward

        report = await bw.wait_for_status()
        print("battery:", report.battery_voltage, "V")
        for s in read_encoders(report):
            print(s.port, s.device, "angle=", s.absolute_position)

        await bw.stop()

asyncio.run(main())
```

## Development

```bash
pip install -e ".[dev]"
pytest -q          # 22 hardware-free tests
```

The protocol layer (`buwizz.protocol`) has **no Bluetooth dependency**, so it
imports and tests cleanly in CI without a brick or `bleak`.

## Suggested next updates

See [`docs/python-lego-sensors.md`](docs/python-lego-sensors.md) for the full
roadmap. Highlights: a per-device LWP3 sensor-mode library, a `run_to_angle`
servo helper, auto-detection of attached devices, a `python -m buwizz` CLI, and
BuWizz 2.0 support.

## License

Original code and docs: **MIT** (see `LICENSE`). Imported third-party code keeps
its own license; provenance is documented in `NOTICE.md`.
