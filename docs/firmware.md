# BuWizz 3.0 firmware & over-the-air (OTA) updates

This page summarises how the BuWizz 3.0 brick's firmware is structured and how
it is updated, based on the **public** BuWizz 3.0 API document. The firmware
itself is proprietary (closed source) and is distributed only as signed images
through the official BuWizz mobile apps — there is no public source tree to
build. What *is* public is the BLE protocol used to deliver an update, which is
what this document and the `bootloader` GATT characteristic cover.

> ⚠️ **Safety:** Flashing firmware over BLE can brick a device if interrupted or
> if an image for the wrong target is sent. Do not attempt a real OTA flash
> against the documented bootloader unless you have an official, correctly
> signed image and you understand the recovery path. The code in this repo does
> **not** ship firmware images and does not implement a flash routine.

## Hardware / firmware architecture

BuWizz 3.0 runs **two** microcontrollers, each with its own firmware:

| MCU | Role | Power domain | Updatable |
|-----|------|--------------|-----------|
| **Nordic nRF52833** ("Nordic") | Main MCU: BLE stack, application logic, status reporting, servo/PID control | Always-on (until battery cut-off) | Yes, via BLE bootloader |
| **"Tajnik" co-processor** | Generates PWM for all 6 motor outputs, measures motor current & temperature, drives the 4 RGB LEDs, handles UART on motor ports 1-4 | Motor/LED power domain | Yes, via Nordic in bootloader mode |

The Nordic supports **BLE 5 long-range / coded PHY**, which the device requests
automatically after connecting to extend range.

## Operation modes

- **Application mode** — normal operation; the API commands in
  [`ble-protocol.md`](./ble-protocol.md) are available.
- **Bootloader mode** — used to transfer new firmware. The device enters it if
  memory verification fails at boot, or when the application requests it. The
  bootloader has a **2-minute inactivity timeout** and then restarts.
- **Application sleep / off** — low-power states; wake on button or motion.

LED patterns indicate the mode (e.g. *red/green alternating slow* = Nordic in
bootloader, *chasing red counter-clockwise* = Tajnik in bootloader). The full
table is in the API document.

## The OTA / bootloader channel

Firmware data is exchanged over a dedicated GATT characteristic in the BuWizz
service:

| Characteristic | Short UUID | Full UUID | Use |
|----------------|-----------|-----------|-----|
| Bootloader | `0x8000` | `50058000-74fb-4481-88b3-9919b1676e93` | OTA / firmware update |

Notes from the public API relevant to OTA:

- In **bootloader mode** the BLE MTU can be negotiated larger and packets may be
  up to **244 bytes** (vs. up to 129 in application mode) for faster transfer.
- The periodic status report (command `0x01`) carries **bootloader response
  fields** (bytes 16-20: response command, response code, 3 response data
  bytes), so update progress/acknowledgements can be observed on the normal
  notification channel.
- The Tajnik co-processor is updated indirectly: the Nordic, while in
  application/bootloader mode, relays dedicated commands to flash Tajnik.

## How updates reach end users today

In practice, end users update firmware through the official **BuWizz app**
(iOS/Android), which bundles the latest signed images and walks the brick
through the bootloader handshake. The recommended "upgrade" path for a normal
user is therefore:

1. Open the official BuWizz app and connect to the brick.
2. Accept the firmware-update prompt if one is offered.
3. Keep the brick close and charged until the app reports success.

See the official user guide and downloads at <https://buwizz.com/>.

## What this repository adds

This repo does **not** replace the official updater. It documents the firmware
architecture, exposes the bootloader characteristic UUID in
`buwizz.protocol` for tooling/diagnostics, and focuses its effort on the
**application-mode** control protocol and Python sensor access (see
[`python-lego-sensors.md`](./python-lego-sensors.md)).
