"""Stream the BuWizz status report: battery, temperature, accelerometer.

Run:  python examples/read_status.py
"""

import asyncio

from buwizz import BuWizz


async def main() -> None:
    async with BuWizz() as bw:
        await bw.set_data_period(100)  # 10 Hz
        print("Streaming status (Ctrl-C to stop)...")
        for _ in range(50):
            s = await bw.wait_for_status(timeout=2.0)
            ax, ay, az = s.accelerometer
            print(
                f"battery={s.battery_voltage:.2f}V "
                f"({s.status.battery_level.name})  "
                f"temp={s.temperature}C  "
                f"accel=({ax:+.2f}, {ay:+.2f}, {az:+.2f})g  "
                f"usb={'Y' if s.status.usb_connected else 'N'}"
            )


if __name__ == "__main__":
    asyncio.run(main())
