# 0003 · Hardware abstraction layer and simulated drivers

**Status** Accepted · November 2026

## Context

The board and parts are ordered but not here. The detection logic (hard brakes, potholes, button gestures, dB(A)) is the riskiest part of the firmware and should not wait for them. Parts may also change between board revisions.

## Decision

- The firmware is layered: `umi_hal` (interfaces only), `umi_core` (pure C logic, no ESP-IDF include), `umi_protocol` (codec), `umi_drivers` (real parts) and `umi_sim` (simulated parts). `src/` only wires tasks.
- Everything in `umi_core`, `umi_protocol` and the frame parsers of `umi_drivers` compiles on the host and is unit-tested there (`pio test -e native`).
- `umi_sim` implements the HAL from a scenario file (raw 100 Hz IMU, NMEA, PM frames, sound levels, button edges). It runs on the host (`pio run -e sil`) and on a bare ESP32-S3 DevKitC (`-e devkit`), so the RTOS, flash, BLE and button paths are exercised before the board exists.
- The parts we design for are listed in `docs/hardware/assumptions.md`; each real driver is a ticket blocked on the hardware.

## Consequences

- Detector thresholds are tuned on recorded and synthetic scenarios, and the same scenarios become regression tests once real recordings exist.
- Swapping a part means writing one driver against an existing interface.
- The simulator (`simulator/`) can export scenarios, so a virtual ride can drive the real firmware logic end to end.
