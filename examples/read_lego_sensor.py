"""Read LEGO motor encoders/sensors attached to BuWizz PU ports 1-4.

This uses the fully-supported path: the brick's status report already carries
per-port device type, velocity and position. Plug a Powered Up / Technic motor
or a rotation sensor into a port and turn it to see values change.

Run:  python examples/read_lego_sensor.py
"""

import asyncio

from buwizz import BuWizz
from buwizz.sensors import read_encoders


async def main() -> None:
    async with BuWizz() as bw:
        await bw.set_data_period(50)  # 20 Hz
        print("Reading attached LEGO devices (Ctrl-C to stop)...")
        for _ in range(100):
            s = await bw.wait_for_status(timeout=2.0)
            readings = read_encoders(s)
            if not readings:
                print("  (no devices detected on ports 1-4)")
            else:
                for r in readings:
                    print(
                        f"  port {r.port}: {r.device}  "
                        f"vel={r.velocity:+4d}  "
                        f"abs_pos={r.absolute_position:3d}  "
                        f"pos={r.position}"
                    )
            await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())
