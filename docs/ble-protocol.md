# BuWizz 3.0 BLE protocol reference

A condensed reference for the BuWizz 3.0 application-mode protocol, as
implemented in [`src/buwizz/protocol.py`](../src/buwizz/protocol.py). Source of
truth: the official BuWizz 3.0 API document (download from
<https://buwizz.com/>). Where this repo and the document disagree, the document
wins — please open an issue.

## GATT service & characteristics

**Service UUID:** `50050000-74fb-4481-88b3-9919b1676e93`

All characteristics share the base `5005XXXX-74fb-4481-88b3-9919b1676e93`:

| Characteristic | Short UUID | Type | Purpose |
|----------------|-----------|------|---------|
| Application | `0x2901` | Write + Notify | Main command/telemetry channel |
| Bootloader | `0x8000` | Write + Notify | OTA firmware update |
| UART ch. 1-4 | `0x3901`-`0x3904` | Write + Notify | Transparent UART to LEGO device on motor ports 1-4 |

Enable notifications (write `1` to the CCCD) on a characteristic to receive
data. The status report streams at ~20 Hz once the Application CCCD is enabled.

## Application commands (write to the Application characteristic)

| Op-code | Name | Payload summary |
|---------|------|-----------------|
| `0x01` | Device status report | *Notification only* — see below |
| `0x20` | Set device name | 12 bytes, NUL-padded |
| `0x21` | Enable/disable motion wake-up | enable + idle/shallow-sleep timeouts |
| `0x22` / `0x23` | Set / read accel calibration | 6× float32 |
| `0x30` | **Set motor data** | 6× int8 (-127..127) + brake flags + LUT flags |
| `0x31` | Set motor data (extended/PU) | 4× int32 refs (ports 1-4) + 2× int8 (ports 5-6) + flags |
| `0x32` | Set status report period | 1 byte, 20-255 ms |
| `0x33` | Set ramp up/down rates | 6× up + 6× down (%/128 ms) |
| `0x34` | Set motor timeout | 0 = brake, 1 = coast, 2-254 = coast after N-1 s |
| `0x35` | Activate connection watchdog | timeout seconds (0 = off) |
| `0x36` | Set LED status | 4× RGB (+ optional blink config); empty = default |
| `0x37` | Set accel low-pass filter | 1 byte sampling setting |
| `0x38` | Set current limits | 6× steps of 30 mA |
| `0x40` | UART baud-rate setup | channel + baud (uint32) |
| `0x50` | **Set PU port function** | 4 bytes, one per port (see below) |
| `0x51` | Enable PID state reporting | port index 1-4 (0 = off) |
| `0x52` | Set servo reference | 4× int32 |
| `0x53` | Set servo PID parameters | port index + filter/gain block |
| `0xA1` | Activate shelf mode | — |
| `0xAC` | Check charger settings | — |

### PU port functions (command `0x50`)

| Value | Function |
|-------|----------|
| `0x00` | Generic PWM output (**enables raw UART on that port**) |
| `0x10` | PU simple PWM (default) |
| `0x14` | PU speed servo |
| `0x15` | PU position servo |
| `0x16` | PU absolute-position servo |

### Device status report (command `0x01`)

| Byte(s) | Field |
|---------|-------|
| 0 | `0x01` (command) |
| 1 | Status flags (USB, charging, battery level, long-range PHY, motion wake-up, error) |
| 2 | Battery voltage = `9 V + value × 0.05 V` |
| 3-8 | Motor currents, `value × 0.015 A` per output |
| 9 | MCU temperature (°C) |
| 10-15 | Accelerometer X/Y/Z (left-aligned 12-bit signed, 0.488 mg/digit) |
| 16-20 | Bootloader response (command, code, 3 data bytes) |
| 21 | Battery charge current (mA) |
| 22-53 | 4× Powered Up motor data: type (u8), velocity (i8), absolute position (u16), position (u32) |
| 54-67 | *Optional* PID controller state |

`buwizz.protocol.decode_status_report()` turns this into a typed
`StatusReport` dataclass.

## Quick mapping to this library

| You want to... | Call |
|----------------|------|
| Drive motors | `protocol.set_motor_data([...])` / `BuWizz.set_motors(...)` |
| Run a closed-loop servo | `set_pu_port_function([...])` + `set_servo_reference([...])` |
| Read battery / accel / temp | `decode_status_report(...)` / `BuWizz.wait_for_status()` |
| Read a motor encoder | `sensors.read_encoders(report)` |
| Talk to a raw LWP3 sensor | `sensors.UartSensorPort` |
