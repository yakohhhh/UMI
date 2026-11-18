# SIL scenario format v1

Raw sensor streams that drive the firmware's simulated drivers (`firmware/lib/umi_sim`), on the host (`pio run -e sil`) or on a devkit. The simulator writes them (`umi-sim scenario`), so a virtual ride can run through the real firmware logic: detectors, button state machine, flag signing and the session log writer.

It is the layer *below* `.umis`: a scenario is what the sensors would output, a `.umis` is what the firmware made of it.

## File

UTF-8 text, one reading per line, `\n` line endings, lines in non-decreasing `t_ms` order. Lines starting with `#` are comments. The first line is the header:

```
# umi-sil-scenario v1
```

Every other line is `t_ms,kind,fields…` where `t_ms` is milliseconds since power-on (integer).

| Kind | Fields | Rate | Notes |
| --- | --- | --- | --- |
| `imu` | `ax,ay,az,gx,gy,gz` | 100 Hz | m/s² and rad/s, as the accelerometer reports them (gravity included: `az ≈ +9.81` at rest). Body frame: x forward, y left, z up. |
| `gnss` | one NMEA 0183 sentence | 1 Hz (`$GNRMC` then `$GNGGA`) | Everything after the second comma is the sentence, checksum included (it contains commas). |
| `pm` | 64 hex chars | 1 Hz | One 32-byte Plantower frame (`42 4D 00 1C …` + checksum), as read on the UART. |
| `spl` | `dba` | 10 Hz | Sound level of the next 100 ms in dB(A). The simulated mic synthesises PCM at that level so the real SPL code path runs. |
| `env` | `temp_c,rh_pct` | 0.1 Hz | |
| `button` | `down` or `up` | on change | Raw contact state before debouncing; bounces may be included to test the debouncer. |
| `battery` | `mv,pct` | 0.1 Hz | |
| `keyword` | `kind,confidence,lang` | once | Result the keyword recogniser returns for the current hold window (`kind` and `lang` as names from `constants.toml`, e.g. `roadworks,92,ca`). Without it a hold window times out with no keyword. |

Unknown kinds are skipped with a warning, so the format can grow without breaking older firmware builds.

## Example

```
# umi-sil-scenario v1
# rider=sim-0001 route=gracia-22@ seed=42
0,battery,3980,82
0,env,19.5,61.0
0,imu,0.02,-0.01,9.81,0.000,0.001,0.000
10,imu,0.03,0.00,9.79,0.000,0.000,0.001
1000,gnss,$GNRMC,075200.00,A,4124.0000,N,00209.6000,E,10.80,92.5,181126,,,A*6C
1000,gnss,$GNGGA,075200.00,4124.0000,N,00209.6000,E,1,12,0.8,42.0,M,49.5,M,,*5B
1000,pm,424d001c00090011001500080010001400000000000000000000000000000000011b
1000,spl,64.2
125000,button,down
125412,button,up
```

(The checksums above are illustrative; the simulator writes valid ones and the firmware rejects bad ones.)
