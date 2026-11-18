# End-to-end tests

Unit tests prove each component on its own; these prove they agree. They run the real firmware logic, the simulator, the reference codec and the backend together, in-process, on a migrated and seeded SQLite database (no server, no network).

| File | What it proves |
| --- | --- |
| `test_e2e_firmware_sil.py` | A simulated ride's raw sensor streams (`umi-sim scenario`) go through the firmware SIL program: the Clip writes a complete session, signs every flag, records an EVENT where the rider braked hard or hit a pothole and nowhere else, a FLAG for every press and hold (with the recognised keyword) and a FLAG_UNDO for every double press. The phone then trims and uploads it and the ride shows in the rider's feed. |
| `test_e2e_fleet.py` | A simulated fleet uploads once (re-runs are deduplicated) and every rider sees their own rides; an untrimmed session is refused and never stored; five distinct riders flagging one corner move its hazard from pending to verified (on everyone's map, 3 riders) then to sent to the city (City Insights, 5 riders). |
| `../../simulator/tests/test_sim_firmware_sil.py` | The simulator and the firmware record the same session from the same ride (header, timing, samples, air, flags, events). |
| `conftest.py`, `demo.py` | The seeded API with its clock fixed at the demo's "now", the simulated city, keys and phone, the SIL program. |

They are marked `e2e` and excluded from the default CI suite, which has no PlatformIO.

```bash
(cd firmware && pio run -e sil)     # build the SIL program the firmware tests need
uv run pytest -m e2e                # every e2e test
```

Tests that need the SIL program skip themselves when it is missing; `UMI_SIL_PROGRAM` points them at another build. CI (`.github/workflows/e2e.yml`) builds it first and fails if it is missing, so they never pass by skipping.
