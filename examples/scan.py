"""Scan for nearby BuWizz devices and print them.

Run:  python examples/scan.py
"""

import asyncio

from buwizz import BuWizz


async def main() -> None:
    print("Scanning for BuWizz devices (8s)...")
    devices = await BuWizz.discover(timeout=8.0)
    if not devices:
        print("No BuWizz devices found. Is the brick powered on?")
        return
    for d in devices:
        print(f"  {d.name or '<unnamed>'}  [{d.address}]")


if __name__ == "__main__":
    asyncio.run(main())
