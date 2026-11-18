# Hardware assumptions

The board and parts are ordered but not delivered. The firmware is written against the parts below ([ADR 0003](../architecture/adr/0003-hardware-abstraction.md)); **every line is to confirm against the actual order**. A different part means one new driver behind the same `umi_hal` interface, not a change to the core.

Status legend for the drivers in `firmware/lib/umi_drivers/src/esp32`: **devkit-proven** runs on a DevKitC today; **unverified** is written from the datasheet and compiles, but has never seen the part; **skeleton** is a placeholder that needs work beyond wiring.

## Parts

| Function | Assumed part | Why this part | Interface | Driver |
| --- | --- | --- | --- | --- |
| SoC | ESP32-S3-WROOM-1-**N16R8** (16 MB quad flash, 8 MB octal PSRAM) | BLE 5 for the phone; the PSRAM is what an on-device keyword model needs (without it, voice keywords need a new board revision, not an update); 16 MB fit two 3 MB OTA slots and ~10 MB of sessions (~90 h of riding). No ECDSA peripheral: signing is software (mbedTLS/PSA), keys protected by flash encryption and the eFuse HMAC ([ADR 0005](../architecture/adr/0005-device-identity.md)). | — | — |
| IMU | ST LSM6DSO32 | ±32 g range: pothole shocks on a rigid frame exceed the ±16 g of most 6-axis parts; FIFO with batching, so the core reads 10 ms at a time; ~0.6 mA at 104 Hz. | I2C 0x6A (SPI possible) | unverified |
| GNSS | u-blox M10 module (e.g. MAX-M10S) | Low power (~25 mW tracking), four constellations for Barcelona's street canyons, NMEA `RMC`/`GGA` at 1 Hz out of the box, PPS for timing. | UART 9600 baud (factory) | unverified (NMEA path proven in SIL) |
| PM2.5 | Plantower PMSA003 | Smallest common laser counter with a documented 32-byte frame; the same frame as the PMS5003/7003 family, so a swap is free. | UART 9600 baud, SET pin for sleep | unverified (frame path proven in SIL) |
| Microphone | TDK InvenSense ICS-43434 | Digital I2S (no analog front end to calibrate), −26 dBFS at 94 dB SPL, 65 dBA SNR, 120 dB SPL overload, bottom port that can sit behind a membrane. | I2S, 16 kHz, 24 bits in 32-bit slots, left channel | unverified |
| Temperature, humidity | Sensirion SHT40 | ±0.2 °C / ±1.8 %RH, 1.5 mm part; humidity feeds the PM2.5 correction. | I2C 0x44 | unverified |
| Fuel gauge | Maxim MAX17048 | ModelGauge needs no sense resistor; state of charge and charge rate over I2C at 23 µA. | I2C 0x36 | unverified |
| Flag button | Sealed tactile switch (IP67) | One button, used blind with gloves. | GPIO, active low, internal pull-up | devkit-proven path (BOOT button) |
| Buzzer | Piezo transducer, resonance in 2-4 kHz | Chirps at 2.0 and 3.2 kHz ([feedback]) carry above wind noise; no earphones allowed (RD 518/2026). | LEDC PWM through an NPN transistor | devkit-proven path |
| LED | WS2812-class RGB LED | One data pin, any colour (orange = `#FF5B1F`). The DevKitC-1 has one on board. | RMT | devkit-proven path |
| Battery | 1-cell LiPo, 600-1000 mAh | "A week of commutes" with the power budget below; to size with the enclosure (38 g target). | — | — |
| Keyword recogniser | ESP-SR / TFLite Micro model (Catalan, Spanish, English) | On-device only: audio never leaves the Clip. | PSRAM, mic | skeleton (no model yet) |

## Pin map (draft)

The Clip column is a proposal for the schematic; it avoids the strapping pins (0, 3, 45, 46), USB (19, 20) and GPIO 33-37, which the N16R8's octal PSRAM uses.

| Signal | DevKitC-1 (`UMI_HW_SIM=1`) | Clip (`UMI_HW_SIM=0`) |
| --- | --- | --- |
| Flag button | GPIO 0 (BOOT, on board) | GPIO 1 |
| Buzzer (PWM) | GPIO 4 (external piezo) | GPIO 2 |
| LED (WS2812 data) | GPIO 48 (on board; 38 on board v1.1) | GPIO 38 |
| I2C SDA / SCL (IMU, SHT40, MAX17048) | — | GPIO 8 / 9, 400 kHz, external 4.7 kΩ pull-ups |
| GNSS TX→RX / RX←TX | — | GPIO 17 / 18 (UART1) |
| GNSS PPS | — | GPIO 16 (not used yet) |
| PM TX / RX | — | GPIO 10 / 11 (UART2) |
| PM SET (sleep) | — | GPIO 12 (not used yet) |
| Mic BCLK / WS / SD | — | GPIO 5 / 6 / 7 (I2S0) |
| Fuel gauge ALRT | — | GPIO 13 (not used yet) |
| Charger STAT | — | GPIO 14 (not used yet) |

## Power budget (estimates to measure)

| Consumer | While riding | Idle (no session) |
| --- | --- | --- |
| ESP32-S3, core task every 10 ms, BLE connected or advertising | 30-45 mA | < 1 mA with light sleep and slow advertising (not implemented yet) |
| GNSS tracking | 8-10 mA | off, or hot-start backup ~30 µA |
| PMSA003 fan and laser | 60-100 mA when running | off (SET low), 30 s warm-up after wake |
| IMU, mic, SHT40, gauge | ~2 mA | IMU wake-on-motion ~10 µA |
| **Total** | **~100-150 mA** | **target < 1 mA** |

The PM sensor dominates. Its 30 s warm-up rules out sleeping between 10 s `AIR` records, so the realistic options are to run it continuously while riding (a 1000 mAh cell gives ~7-9 h of riding, about a week of 2 × 30 min commutes) or to sample it in bursts (e.g. 30 s on every 2 min) and accept gaps in `AIR`. Measure before deciding.

## Bring-up checklist (the day the order arrives)

1. **Module**: read the marking and run `esptool.py flash_id`: 16 MB flash; boot log shows 8 MB octal PSRAM. If it is an N8 or R2 part, voice keywords are off the table for this revision.
2. **Flash and partitions**: `pio run -e clip -t upload`, check `partitions.csv` fits, the `sessions` FAT mounts and survives a power cut mid-write (read the file back with `python -m umi_protocol inspect`).
3. **I2C scan**: 0x6A (IMU), 0x44 (SHT40), 0x36 (MAX17048) answer; IMU `WHO_AM_I` = 0x6C.
4. **IMU orientation**: with the Clip mounted, rest reads `az ≈ +9.8`; braking reads negative `ax`. Fix the axis mapping in the driver (`imu.c`) if not, and decide the mount (handlebar vs frame: the handlebar turns with steering). Note the part runs at 104 Hz, not 100 Hz: the core's 100-sample "1 s" windows then cover 0.96 s (see follow-ups).
5. **GNSS**: antenna placement and ground plane, time to first fix outdoors, fix quality in Eixample street canyons; then configure the receiver (UBX-CFG: RMC and GGA only, 1 Hz, 38400 baud, a dynamic model suited to bikes) and measure the delay between the epoch and the NMEA output (it skews `TIME_SYNC`).
6. **Microphone**: port position and acoustic path in the housing (membrane, foam, wind); calibrate against a class-1 meter with a 94 dB / 1 kHz calibrator and set the per-unit offset (`umi_spl_init`'s `offset_db`); check the A-weighting at 16 kHz against the meter on traffic noise.
7. **Buzzer**: resonance and loudness at 2.0 and 3.2 kHz at 25 km/h in wind; if the part's resonance differs, change `[feedback] chirp_*_hz` in `protocol/constants.toml`.
8. **LED and button**: LED type and data pin; button polarity, bounce length (debounce is 30 ms) and feel with gloves.
9. **PM sensor**: frames arrive at 1 Hz, fan current, warm-up time, SET-pin sleep; compare PM2.5 with a reference station to calibrate the humidity correction (κ).
10. **SHT40 placement**: self-heating from the ESP32 and the battery; compare with a reference thermometer.
11. **Fuel gauge**: battery model (ModelGauge config for the chosen cell), charge detection, low-battery threshold.
12. **Power**: measure each line of the budget above; decide the PM duty cycle and the idle sleep strategy.
13. **Provisioning**: burn `device_id`, generate the flag key on the device, enable flash encryption, NVS encryption and secure boot v2 (ADR 0005), register the public key with the backend.
14. **BLE**: range in a pocket and on the handlebar, pairing and bonding with iOS and Android.
