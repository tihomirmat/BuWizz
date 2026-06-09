"""Connect to a BuWizz and ramp port 1 forward, then backward, then stop.

Run:  python examples/drive_motors.py
"""

import asyncio

from buwizz import BuWizz


async def main() -> None:
    async with BuWizz() as bw:
        print("Connected. Driving port 1...")
        # Faster status updates so last_status stays fresh.
        await bw.set_data_period(50)

        for speed in (0.25, 0.5, 0.75, 1.0):
            await bw.set_motors([speed, 0, 0, 0])
            await asyncio.sleep(0.5)

        await bw.set_motors([-0.5, 0, 0, 0])
        await asyncio.sleep(1.0)

        await bw.stop()
        print("Stopped.")


if __name__ == "__main__":
    asyncio.run(main())
