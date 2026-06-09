# Standard Library
import asyncio
import contextlib
import logging
import sys

# Third Party
from bleak import BleakClient, BleakScanner

# Our Libraries
from buwizz_pro3_bluetooth_python.buwizz import match_buwizz_uuid, notification_handler

logger = logging.getLogger(__name__)


async def main() -> None:
    device = await BleakScanner.find_device_by_filter(match_buwizz_uuid)

    if device is None:
        print("no matching device found, you may need to edit match_nus_uuid().")
        sys.exit(1)

    def handle_disconnect(_: BleakClient) -> None:
        print("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()

    async with BleakClient(device, disconnected_callback=handle_disconnect) as client:
        print("Connected...")
        print("Iterating Services...")
        for service in client.services:
            logger.info(service)
            for char in service.characteristics:
                print(f"Iterating Characteristics of Service {service}...")
                logger.info(char)
                logger.info(
                    "  [Characteristic] %s properties: %s",
                    char,
                    ",".join(char.properties),
                )
                if "notify" in char.properties:
                    await client.start_notify(char, notification_handler)

                for descriptor in char.descriptors:
                    print(f"Iterating Descriptors of Characteristic {char}...")
                    logger.info("    [Descriptor] %s", descriptor)
                    try:
                        value = await client.read_gatt_descriptor(descriptor.handle)
                        logger.info("    [Descriptor] %s, Value: %s", descriptor, value)
                    except Exception as e:
                        logger.error("    [Descriptor] %s, Error: %s", descriptor, e)

        await asyncio.sleep(6.0)

    logger.info(device)


if __name__ == "__main__":
    log_level = logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    with contextlib.suppress(asyncio.CancelledError):
        asyncio.run(main())
