# Standard Library
import logging
from collections import namedtuple
from dataclasses import KW_ONLY, dataclass

# Third Party
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

logger = logging.getLogger(__name__)
AccelerometerReading = namedtuple("AccelerometerReading", ["x", "y", "z"])
StatusFlags = namedtuple(
    "StatusFlags",
    ["usb_connected", "battery_charging", "battery_level", "ble_long_phy", "motion_wakeup_enabled", "error"],
)
PoweredUpMotorData = namedtuple("PoweredUpMotorData", ["motor_type", "velocity", "absolute_position", "position"])

# Discovering BuWizz3 device
#
# When active, BuWizz3 device advertises main advertisement data and optional scan response data
# (shown in Figure 1). Main advertisement data contains device name (‘BuWizz3’ by default, but can be
# customized) and short manufacturer information (sequence of 8 bytes - 05:4E:’B’:’W’:’B’:’L’:00:00 in
# bootloader and 05:4E:’B’:’W’:’x’:’y’:<serialLSB>:<serialMSB> in the application, where x and y are
# replaced with firmware version and serial number contains lower 16 bits of device’s serial number).
# Scan response data contains the 128-bit UUID of the device’s main (BuWizz application) service.
#
# Service UUID
# BuWizz 93:6E:67:B1:19:99:B3:88:81:44:FB:74:D1:92:05:50
# The below is the same as above but read in reverse order.
BUWIZZ_SERVICE_UUID = "500592d1-74fb-4481-88b3-9919b1676e93"
#
# There are 6 characteristics in this service, shown in the table below. These have a data exchange
# characteristic with a data exchange descriptor and a Client Characteristic Configuration Descriptor
# (CCCD) controlling the characteristic behavior.
# Characteristic UUID Type
# Application 0x2901 Write + Notify
BUWIZZ_CHAR_UUID_APPLICATION = "50052901-74fb-4481-88b3-9919b1676e93"
# Bootloader 0x8000 Write + Notify
BUWIZZ_CHAR_UUID_BOOTLOADER = "50058000-74fb-4481-88b3-9919b1676e93"
#
# UART ch. 1 0x3901 Write + Notify
# UART ch. 2 0x3902 Write + Notify
# UART ch. 3 0x3903 Write + Notify
# UART ch. 4 0x3904 Write + Notify
BUWIZZ_CHAR_UUID_UART_CH1 = "50053901-74fb-4481-88b3-9919b1676e93"
BUWIZZ_CHAR_UUID_UART_CH2 = "50053902-74fb-4481-88b3-9919b1676e93"
BUWIZZ_CHAR_UUID_UART_CH3 = "50053903-74fb-4481-88b3-9919b1676e93"
BUWIZZ_CHAR_UUID_UART_CH4 = "50053904-74fb-4481-88b3-9919b1676e93"


# https://buwizz.com/BuWizz_3.0_API_3.6_web.pdf

BUWIZZ_CMD_DISPLAY_STATUS_REPORT = 0x01


@dataclass
class BuwizzDeviceStatusReport:
    # Device status report
    # Once  enabled  by  writing  1  to  data  CCCD,  the  BuWizz3  device  will  periodically  send  device  status
    # report with the approximate frequency of 20 Hz
    # Byte Array Byte numbers and values:
    # 0 (command) 0x01
    # 1 Status flags - bit mapped to the following functions:
    #   Bit Function
    #       7 unused
    #       6 USB connection status (1 - cable connected)
    #       5 Battery  charging  status  (1  -  battery  is  charging, 0 - battery is full or not charging)
    #       3-4 Battery  level  status  (0  -  empty,  motors  disabled;  1  -  low;  2  -  medium;  3  - full)
    #       2 BLE long range PHY enabled
    #       1 unused
    #       0 error (overcurrent, overtemperature...)
    #
    # 2 Battery voltage (9 V + value * 0,05 V) - range 9,00 V – 15,35 V
    # 3-8 Motor currents, 8-bit value for each motor output (value * 0,015 A) - range 0 - 3,8 A
    # 9 Microcontroller temperature (value in °C)
    # 10-11 Accelerometer x-axis value (left-aligned 12-bit signed value, 0.488 mg/digit)
    # 12-13 Accelerometer y-axis value (left-aligned 12-bit signed value, 0.488 mg/digit)
    # 14-15 Accelerometer z-axis value (left-aligned 12-bit signed value, 0.488 mg/digit)
    # 16 Bootloader response command
    # 17 Bootloader response code
    # 18-20 Bootloader response data (3 bytes)
    # 21 Battery-charge current (mA)
    # 22-53 PoweredUp motor data structure (4x)
    # - Motor type (unsigned 8-bit)
    # - Velocity (signed 8-bit)
    # - Absolute position (unsigned 16-bit)
    # - Position (unsigned 32-bit)
    # 54-67 Optional: PID controller state
    # - Process value (single precision float)
    # - Error (float)
    # - PID output (float)
    # - Integrator state (signed 8-bit int)
    # - Motor output (signed 8-bit int)
    _: KW_ONLY

    command: bytearray
    status_flags: bytearray
    battery_voltage: float
    motor_currents: bytearray
    microcontroller_temperature: bytearray
    accelerometer: tuple[bytearray]
    bootloader: bytearray
    battery_charge_current: bytearray
    poweredup_motor_data_a: bytearray
    poweredup_motor_data_b: bytearray
    poweredup_motor_data_c: bytearray
    poweredup_motor_data_d: bytearray


def match_buwizz_uuid(device: BLEDevice, adv: AdvertisementData) -> bool:
    # This assumes that the device includes the UART service UUID in the
    # advertising data. This test may need to be adjusted depending on the
    # actual advertising data supplied by the device.
    logger.info(f"match_uuid {adv}")
    if BUWIZZ_SERVICE_UUID.lower() in adv.service_uuids:
        return True

    return False


def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray) -> None:
    """Simple notification handler which prints the data received."""
    command_code = data[0]
    if command_code == BUWIZZ_CMD_DISPLAY_STATUS_REPORT:
        logger.info(handle_notify_device_status_report(data))
    else:
        logger.info("%s: %r, %s", characteristic.uuid, data, command_code)


def decode_accelerometer_bytes(data: bytearray) -> str:
    """Decode byte encoded version of accelerometer readings."""
    # (left-aligned 12-bit signed value, 0.488 mg/digit)
    raw = f"{ord(data):>016b}"
    reversed_raw = "{:>016b}".format(int(f"{ord(data):016b}"[::-1], 2))[4:]
    val = int(reversed_raw, 2)
    # TODO: figure out how the the signedness works. Maybe just email BuWizz team?
    # TODO: Maybe make use of python stdlib function struct.unpack just like PyBricks does???
    # https://docs.python.org/3/library/struct.html#struct-alignment
    # TODO: Reverse engineering values from looking at raw value in App and then back on this console logs
    return (round((val * 0.488 / 1000) - 1, 3), raw, reversed_raw, f"{val:>012b}")


def decode_battery_voltage(data: bytearray) -> float:
    """Decode byte value into real battery voltage.

    Battery voltage (9 V + value * 0,05 V) - range 9,00 V – 15,35 V
    """
    return 9.0 + int(data) * 0.05


def decode_status_flags(data: bytearray) -> StatusFlags:
    """Decode byte encoded version of status flags.

    bit description
    7 unused
    6 USB connection status (1 - cable connected)
    5 Battery  charging  status  (1  -  battery  is  charging, 0 - battery is full or not charging)
    3-4 Battery  level  status  (0  -  empty,  motors  disabled;  1  -  low;  2  -  medium;  3  - full)
    2 BLE long range PHY enabled
    1 motion_wakeup_enabled
    0 error (overcurrent, overtemperature...).
    """
    return StatusFlags(
        usb_connected=bool(data >> 6 & 0x1),
        battery_charging=bool(data >> 5 & 0x1),
        battery_level=int(data >> 3 & 0x3),
        ble_long_phy=bool(data >> 2 & 0x1),
        motion_wakeup_enabled=bool(data >> 1 & 0x1),
        error=bool(data & 0x1),
    )


def decode_poweredup_motor_data(data: bytearray) -> PoweredUpMotorData:
    """Decode Powered Up Motor spec data.

    # PoweredUp motor data structure (4x)
    # - Motor type (unsigned 8-bit)
    # - Velocity (signed 8-bit)
    # - Absolute position (unsigned 16-bit)
    # - Position (unsigned 32-bit)
    """
    return PoweredUpMotorData(
        motor_type=data[0],
        velocity=data[1],
        absolute_position=data[2:3],
        position=data[4:7],
    )


def handle_notify_device_status_report(data: bytearray) -> AccelerometerReading:
    """Decode byte array data into Device Status Report."""
    # TODO: Decode bytes into usable values.
    return BuwizzDeviceStatusReport(
        command=data[0],
        status_flags=decode_status_flags(data[1]),
        battery_voltage=decode_battery_voltage(data[2]),
        motor_currents=[b * 0.015 for b in data[3:9]],
        microcontroller_temperature=data[9],
        accelerometer=AccelerometerReading(
            x=decode_accelerometer_bytes(data[10:11]),
            y=decode_accelerometer_bytes(data[12:13]),
            z=decode_accelerometer_bytes(data[14:15]),
        ),
        bootloader=data[16:20],  # TODO
        battery_charge_current=data[21],
        poweredup_motor_data_a=decode_poweredup_motor_data(data[22:29]),
        poweredup_motor_data_b=decode_poweredup_motor_data(data[30:37]),
        poweredup_motor_data_c=decode_poweredup_motor_data(data[38:45]),
        poweredup_motor_data_d=decode_poweredup_motor_data(data[46:53]),
    )
