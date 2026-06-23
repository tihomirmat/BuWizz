# BuWizz Remote Control — iOS 26 BLE Latency: Software (App) Action Plan

**Audience:** developer of the BuWizz remote-control app (Flutter)
**Scope:** what we can fix in the app, without firmware changes
**Related:** a companion firmware document covers the changes that must be made
on the BuWizz device itself.

---

## 1. Problem statement

On **iPhone 16 Pro Max running iOS 26.6**, the remote control exhibits
noticeable **BLE lag** between user input and motor response. The lag is most
visible during rapid/continuous control (e.g. dragging a joystick), which points
at command queueing and bandwidth contention rather than a dropped link.

## 2. Root cause (app side)

Two app-level behaviours dominate the latency:

1. **Command backlog.** If motor commands are written faster than the BLE
   connection can deliver them — especially with *write-with-response* or with a
   plugin that doesn't honour iOS flow control — packets pile up. The motor then
   "plays back" a queue of stale commands, so it lags behind the stick and keeps
   moving after release.
2. **Telemetry contention.** BuWizz streams a status report at ~20 Hz (every
   50 ms). Those notifications share each BLE connection event with our control
   writes; under iOS 26's tighter scheduling they crowd out control packets.

> There is also a firmware/PHY contributor (BuWizz auto-requests long-range
> Coded PHY, which lowers throughput and interacts badly with iOS 26's PHY
> negotiation). That is **not** fixable in the app and is covered in the
> firmware document.

## 3. Action items (in priority order)

### 3.1 Use a plugin that honours iOS write flow control — **`flutter_blue_plus`**

`flutter_blue_plus`'s `write(..., withoutResponse: true)` waits for CoreBluetooth's
"ready to send" state and only completes its `Future` when iOS can accept the
next packet. `flutter_reactive_ble`'s `writeCharacteristicWithoutResponse()` is
fire-and-forget on iOS and will overflow the buffer, producing exactly this lag.

**Action:** if currently on `flutter_reactive_ble` (or `quick_blue`) for the
control path, migrate the motor-write path to `flutter_blue_plus`, or verify the
current plugin awaits the iOS ready callback.

### 3.2 Write motor commands **without response**

BuWizz motor commands (`0x30` / `0x31`) generate **no response** by design, so
write-with-response only adds wasted round-trips.

**Action:** all motor writes use `withoutResponse: true`.

### 3.3 Coalesce — keep only the latest command, never a queue

Store the *desired* motor state and push the newest value once the radio is
ready. Drop superseded commands.

```dart
class BuWizzControl {
  final BluetoothCharacteristic appChar; // 0x2901 application characteristic
  BuWizzControl(this.appChar);

  List<int> _latest = const [0x30, 0, 0, 0, 0, 0, 0, 0, 0];
  bool _dirty = false;
  bool _pumping = false;

  /// speeds: -1.0..1.0 per motor port (up to 6 ports)
  void setMotors(List<double> speeds) {
    _latest = _motorPacket(speeds);
    _dirty = true;
    _pump(); // fire-and-forget; the loop coalesces
  }

  Future<void> _pump() async {
    if (_pumping) return;
    _pumping = true;
    try {
      while (_dirty) {
        _dirty = false;                       // take latest, drop stale
        await appChar.write(_latest, withoutResponse: true); // backpressure
      }
    } finally {
      _pumping = false;
    }
  }

  static List<int> _motorPacket(List<double> speeds) {
    final p = List<int>.filled(9, 0);
    p[0] = 0x30;                              // Set motor data
    for (var i = 0; i < speeds.length && i < 6; i++) {
      p[1 + i] = (speeds[i] * 127).round().clamp(-127, 127) & 0xFF; // int8
    }
    // p[7] = brake flags, p[8] = LUT-disable flags
    return p;
  }
}
```

Because the loop re-reads `_latest` after each awaited write, a fast-moving stick
yields **one packet per connection event carrying the newest value** — never a
backlog.

### 3.4 Throttle (or pause) telemetry while driving

```dart
// Slow status report to ~150 ms (≈6.7 Hz) instead of the 50 ms default:
await appChar.write([0x32, 150], withoutResponse: true);

// Or stop status entirely while actively driving: don't enable notifications
// (skip setNotifyValue(true)), and re-enable only when telemetry is needed.
```

### 3.5 Platform tuning

```dart
import 'dart:io' show Platform;

// Android only (no-op/throws on iOS — guard it). Big Android win:
if (Platform.isAndroid) {
  await device.requestConnectionPriority(
      connectionPriorityRequest: ConnectionPriority.high);
  await device.requestMtu(185);
}
```

On **iOS** the app cannot set connection priority or PHY — those come from the
firmware (see firmware document).

### 3.6 Hygiene that otherwise mimics lag

- `FlutterBluePlus.stopScan()` before connecting and stay stopped while
  connected — scanning during a connection disrupts iOS timing.
- Keep the screen awake during control (`wakelock_plus`); iOS 26 dorms BLE when
  the screen locks or the app backgrounds.
- Keep BLE writes off the build/`setState` path; never `await` a write inside a
  widget build.
- Tune BuWizz motor timeout/watchdog (`0x34` / `0x35`) so a brief iOS stall
  doesn't trip a disconnect that reads as worse lag.

## 4. How to verify the fix

- **Input-to-motion latency:** with the coalescing writer, releasing the stick
  should stop the motor effectively immediately (no "coast through a queue").
- **Sustained drag test:** hold a continuous stick sweep for 10 s; motor should
  track the stick, not trail it by a growing margin.
- **Instrumentation:** log the time between `setMotors()` calls and the
  completion of each `write` future. If write-future completion lags the call
  rate, the coalescing loop is doing its job (dropping stale commands); if it
  grows unbounded, flow control isn't being honoured (revisit 3.1).
- Compare with telemetry at 50 ms vs 150 ms vs disabled (3.4) to quantify the
  contention contribution.

## 5. Expected residual

Even with all of the above, some iOS 26 latency originates in the **PHY / connection
parameters negotiated by the firmware**. If lag remains after 3.1–3.4, the
firmware changes in the companion document are required to fully resolve it.

## References

- Apple Accessory Design Guidelines (connection parameters):
  https://developer.apple.com/accessories/Accessory-Design-Guidelines.pdf
- iOS Core Bluetooth flow control (`canSendWriteWithoutResponse`):
  https://developer.apple.com/documentation/corebluetooth
- flutter_blue_plus: https://pub.dev/packages/flutter_blue_plus
- BuWizz 3.0 API (commands 0x30/0x31 motor data, 0x32 data period, 0x34/0x35
  timeout & watchdog): https://buwizz.com/
