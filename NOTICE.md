# Provenance & third-party material

This repository collects publicly available BuWizz firmware/software references
and adds an original, well-tested Python control library on top. Provenance and
licensing of everything imported is recorded here.

## Imported, redistributable

| Path | Source | License | Notes |
|------|--------|---------|-------|
| `third_party/buwizz-pro3-bluetooth-python/` | [neozenith/buwizz-pro3-bluetooth-python](https://github.com/neozenith/buwizz-pro3-bluetooth-python) | MIT (© 2023 Josh Peak) | Community BuWizz Pro 3 BLE library based on `bleak`. Imported as a reference; the upstream `LICENSE` is preserved. The bundled BuWizz API PDF and the large `poetry.lock` were intentionally **not** copied (see below). |
| `src/buwizz/lwp3.py` (derived data) | [pybricks/pybricksdev](https://github.com/pybricks/pybricksdev) — `pybricksdev/ble/lwp3/bytecodes.py` | MIT (© 2018-2025 The Pybricks Authors) | The LEGO device-type IDs (`LegoDeviceType`) and LWP3 message-kind values (`MessageKind`) are derived from Pybricks' `IODeviceKind` / `MessageKind`. Re-expressed as standalone enums; no Pybricks source files are copied verbatim. |

## Original work in this repository

The `src/buwizz/` package, the `examples/`, the `tests/`, and the documents in
`docs/` are original work authored for this repository and released under the
MIT `LICENSE` at the repo root. The protocol implementation is a clean-room
implementation based on the **publicly published** BuWizz 3.0 API document.

## Referenced but deliberately NOT copied

- **Official BuWizz 3.0 / 2.0 API PDFs** — © BuWizz d.o.o. These are freely
  downloadable from <https://buwizz.com/> but are copyrighted documents, so we
  link to them rather than redistribute them.
- **[BuWizz/BuWizz-Android-Demo](https://github.com/BuWizz/BuWizz-Android-Demo)**
  — the official Android demo app. It is public on GitHub but ships **without a
  license file**, which under GitHub's terms means "all rights reserved". We
  therefore reference it and use only the publicly documented protocol facts; we
  do **not** vendor its source.
- **BuWizz device firmware** — the firmware that runs on the brick's Nordic
  nRF52833 and the "Tajnik" co-processor is **proprietary and closed-source**.
  It is distributed only as signed OTA images through the official BuWizz apps.
  There is no public firmware source to import; `docs/firmware.md` documents the
  architecture and update mechanism from the public API instead.

If you are a rights holder and would like any reference changed, please open an
issue.
