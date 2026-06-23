# BuWizz 3.0 — iOS 26 BLE Latency: Firmware Action Plan

**Audience:** BuWizz device firmware team (Nordic nRF52833 "Nordic" MCU)
**Scope:** changes on the BuWizz device that the iOS/Flutter app **cannot** make
**Related:** a companion software document covers the app-side mitigations.

---

## 1. Problem statement

On **iPhone 16 Pro Max / iOS 26.6**, customers report **BLE control lag** with
the remote-control app. App-side coalescing and write-without-response reduce it,
but a residual latency remains that originates in the **link-layer parameters and
PHY** negotiated by the BuWizz firmware — which an app on iOS cannot influence.

## 2. Background: what iOS 26 changed

Recent iOS releases (26.x) have documented BLE regressions relevant here:

- The iOS controller initiates **PHY upgrades (1M → 2M)**; if the peripheral
  **rejects** the PHY update, iOS 26 tends to **drop the connection** instead of
  staying on the previous PHY as older iOS did.
- Reports of **packet loss / scheduling sensitivity** on iOS 26 even at strong
  RSSI, which is aggravated by low-throughput PHYs and sub-optimal connection
  parameters.

BuWizz 3.0, by design, **auto-requests BLE 5 long-range Coded PHY** shortly after
connecting. Coded PHY trades throughput for range (≈125/500 kbps vs 1 Mbps),
which **adds control latency** and interacts poorly with the iOS 26 PHY behaviour
above. For a real-time remote-control use case, this is the dominant firmware-side
cause.

## 3. Requested firmware changes (priority order)

### 3.1 Make Coded PHY opt-in, not automatic — **highest impact**

- **Today:** firmware automatically requests `PHY_CODED` (long range) after
  connection.
- **Request:** default new connections to **1M PHY (low latency)** and expose a
  **mode/command to opt into long-range** only when the user/app wants range over
  latency.
- **Suggested mechanism:** a new application command (e.g. an unused op-code) or
  a flag in an existing setup command that selects `LOW_LATENCY (1M)` vs
  `LONG_RANGE (Coded)`. The app would select low-latency for normal driving.
- **Rationale:** removes the throughput penalty for the common RC case and avoids
  the iOS 26 Coded-PHY edge cases.

### 3.2 Accept iOS-initiated PHY updates without disconnecting

- **Request:** when the central (iOS) initiates an `LL_PHY_REQ` (e.g. 1M ↔ 2M),
  the firmware must **accept and continue** on the agreed PHY rather than
  rejecting (which causes iOS 26 to drop the link).
- **Note:** nRF52833 supports 2M PHY. Allowing 2M on the data connection (when
  not in long-range mode) would also **increase throughput and reduce latency**
  for iOS clients that request it.

### 3.3 Request Apple-compliant low-latency connection parameters

Have the peripheral request a connection-parameter update that follows Apple's
Accessory Design Guidelines and favours responsiveness:

| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| Connection Interval Min | **15 ms** | Multiple of 15 ms; per Apple guidelines |
| Connection Interval Max | **30 ms** | Must be ≥ Min + 15 ms; avoid Min==Max==15 (iOS scales to 30) |
| Peripheral (Slave) Latency | **0** | Critical for snappy control; do not use non-zero latency on the control link |
| Supervision Timeout | **4–6 s** | Must satisfy `Timeout ≥ (1 + Latency) × IntervalMax × 2`; gives margin against iOS 26 stalls without long stale-state windows |

- **Why slave latency 0:** any non-zero peripheral latency lets the device skip
  connection events, which directly delays motor commands.
- Issue the parameter-update request a short, fixed time after connection (and
  after any PHY settlement), not repeatedly, to avoid renegotiation churn.

### 3.4 Avoid renegotiation loops / parameter churn

- iOS 26 has shown deadlock-like behaviour when system services and the peripheral
  **compete to set connection parameters** (one requests fast params, the other
  reverts, repeat). Ensure the firmware:
  - requests its preferred parameters **once** and then **honours iOS-driven
    updates** instead of immediately re-requesting its own;
  - does not tie Coded-PHY entry to the same trigger as parameter updates, so the
    two don't oscillate.

### 3.5 (Optional) Larger MTU on the data connection

- Supporting an MTU exchange up to ~185–247 bytes on the **application**
  connection (not just bootloader) lets the app batch more per event if needed.
  Lower priority than 3.1–3.3 for the lag issue, but a cheap throughput win.

## 4. Interplay with the app

- App-side fixes (coalescing writes, write-without-response, throttling the 20 Hz
  status report via command `0x32`) reduce queue-induced lag.
- Firmware fixes (3.1–3.3) reduce **link-induced** lag and the iOS 26
  PHY/parameter instability.
- Both are needed for a fully responsive iOS 26 experience; neither alone closes
  the gap.

## 5. Validation / acceptance

Test on **iPhone 16 Pro Max, iOS 26.6** (and ideally an iPhone 17 unit, where the
iOS 26 PHY regressions were most reported):

1. **PHY:** confirm the data connection runs on **1M (or 2M)** for normal mode,
   and that an iOS-initiated 1M↔2M PHY change **does not disconnect**.
2. **Connection params:** verify negotiated interval ≤ 30 ms and **peripheral
   latency 0** via a sniffer or nRF connection logs.
3. **Latency:** measure input-to-motor-response with the app's instrumentation
   before/after; target sub-perceptible lag (well under ~100 ms end-to-end).
4. **Stability:** sustained 10-minute drive with screen on; no spontaneous
   disconnects attributable to PHY rejection or parameter churn.
5. **Range regression check:** confirm the opt-in long-range mode (3.1) still
   reaches previous Coded-PHY range when explicitly selected.

## References

- Apple Accessory Design Guidelines (§ Connection Parameters):
  https://developer.apple.com/accessories/Accessory-Design-Guidelines.pdf
- Apple QA1931 — advertising & connection parameters for a stable connection:
  https://developer.apple.com/library/archive/qa/qa1931/_index.html
- Selecting suitable connection parameters for Apple devices (Silicon Labs):
  https://docs.silabs.com/bluetooth/9.1.1/mobile-apps-suitable-connection-parameters/
- BuWizz 3.0 API (Coded-PHY / long-range behaviour, connection model):
  https://buwizz.com/
