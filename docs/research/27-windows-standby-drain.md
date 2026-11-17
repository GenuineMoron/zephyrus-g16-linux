# Windows Modern Standby drain on this laptop (Zephyrus G16 GU605MI)

Research note, read-only. Source: `Microsoft-Windows-Kernel-Power` 506/507 pairs in a copy of `System.evtx` (local working copy, not in the repo). Date range in the log: 2026-02-26 to 2026-06-21 (UTC). Parsed with python-evtx; the full pair table is a CSV (local working copy, not in the repo).

## Bottom line

- Windows on-battery DRIPS standby sessions of at least 1 h (n=16, DRIPS >= 50%): median **863 mW**, range 755-2520 mW. Linux s2idle on the night of 2026-11-14/15 was 0.80-0.89 W, so the two are close.
- Windows DRIPS sessions of 10 min or more (n=62): median **1677 mW**, range 755-11720 mW.
- Three on-battery sessions of 60-65 min never entered DRIPS (0%). They drained about 3.0-3.1 W (median 3061 mW, n=3). This is the sleep failure mode, not normal standby.
- Other NO-DRIPS sessions in March show 3.5-13.5 W over 4-38 min. They are most likely active use inside a session, not standby (INFERRED from zero DRIPS and the audio/active fields). Treat them as excluded from standby numbers.
- Monthly split matters. DRIPS-class sessions of 10 min+ run about 0.9-1.0 W in March and June, but about 3.8-4.2 W in April and May, even at 90%+ DRIPS. DRIPS residency alone did not keep those months low. The logs do not name the cause; I did not verify a guess (for example the dGPU) because the logs do not show it.
- Event 507 carries no per-component attribution for these sessions. The top-offender section explains what is and is not available.

## Units and method (read this first)

- Battery energy = `BatteryRemainingCapacityOnEnter` (506) minus `BatteryRemainingCapacityOnExit` (507), both in the same session. Units: **INFERRED mWh** (magnitude matches `Kernel-Power 105 RemainingCapacity` and the ~79 Wh full capacity; the event fields do not state units).
- Average mW = drain / `DurationInUs` (507). % battery = drain / `BatteryFullChargeCapacityOnEnter`.
- Windows reports full charge capacity as 78.4-79.4 Wh (79443 mWh in March, 79252 mWh in June). The 76.9 Wh estimate from mAh is about 3% lower. The percentages here use Windows' number.
- Capacity is an integer mWh gauge reading. For sessions under about 20 min a 1-mWh step is a visible error, so stats use sessions of at least 10 min.
- AC sessions (`PowerStateAc` = True, 1067 of 1241) show no capacity drop and are not battery drain. They are kept in the CSV only.

## (a) Modern Standby sessions on battery (PowerStateAc = False), all 174

`DRIPS %` = `DripsResidencyInUs` / `DurationInUs`. `HW DRIPS %` = `HwDripsResidencyInUs` / `DurationInUs`. `SW DRIPS %` = DRIPS % minus HW DRIPS % (INFERRED). The `Class` label is mine: `DRIPS` = at least 50% DRIPS, `NO-DRIPS` = below 50%.

The per-session table (duration, drain, DRIPS split, raw `Reason` codes, `DisconnectedStandby`, `AudioPlaying`) stays in the local CSV. Monthly aggregate of the 174 battery sessions:

| Month | Sessions | Total hours | Sessions >= 10 min (drain > 0) | Median avg mW (>= 10 min) | p90 avg mW (>= 10 min) | DRIPS share (time-weighted) | DRIPS-class median mW (>= 10 min) |
|---|---|---|---|---|---|---|---|
| 2026-03 | 101 | 55.5 | 42 | 1559 | 3775 | 82.1% | 1005 (n=30) |
| 2026-04 | 22 | 5.6 | 8 | 3847 | 4905 | 91.7% | 3847 (n=8) |
| 2026-05 | 38 | 10.1 | 17 | 4204 | 6318 | 92.0% | 4204 (n=17) |
| 2026-06 | 13 | 10.9 | 7 | 912 | 1275 | 98.2% | 912 (n=7) |

p90 is nearest-rank. DRIPS share = summed `DripsResidencyInUs` / summed `DurationInUs` over all battery sessions in the month.

From the per-session rows:

- HW DRIPS makes up almost all DRIPS residency (SW DRIPS 0.0-0.1% in 172 of 174 sessions). The exceptions are two 2026-05 sessions (19.2 and 31.4 min) with 0% HW DRIPS and 75.8-79.9% SW DRIPS, at 11720 and 4833 mW.
- All 12 NO-DRIPS sessions of 10 min or more fall in 2026-03 (2910-13500 mW).
- Sessions under 10 min (100 of 174) are mostly NO-DRIPS and too short for the 1-mWh gauge step; they are excluded from the stats.

## (b) Summary statistics

- Note: the DRIPS-class 10 min+ max (11720 mW) is a short session where a 1-mWh step matters; the 1 h+ subset is the cleaner comparison.
- All DC sessions of at least 10 min with drain > 0: n=74. Median avg mW = 2620, range 755-13500 mW.
  - of which DRIPS-class (>= 50% DRIPS): n=62, median 1677 mW, range 755-11720 mW.
  - of which NO-DRIPS-class: n=12, median 3633 mW, range 2910-13500 mW.
- Sessions of at least 1 h (n=19), reported separately:
  - DRIPS-class n=16: median 863 mW, range 755-2520 mW.
  - NO-DRIPS-class n=3: median 3061 mW, range 2910-3147 mW.
- By month, DRIPS-class 10 min+ (median mW): 2026-03: 1005 (n=30), 2026-04: 3847 (n=8), 2026-05: 4204 (n=17), 2026-06: 912 (n=7).
- Per-session battery use for 1 h+ DRIPS sessions: 1.4-5.0% of full capacity.

Long DRIPS-class sessions (>= 1 h), by month:

| Month | Sessions | Total hours | Median avg mW | Range mW | % batt per session |
|---|---|---|---|---|---|
| 2026-03 | 11 | 35.2 | 850 | 755-2520 | 3.17-5.01 |
| 2026-04 | 1 | 1.2 | 1555 | 1555 | 2.29 |
| 2026-05 | 0 | - | - | - | - |
| 2026-06 | 4 | 9.3 | 870.5 | 825-912 | 1.44-4.00 |

## (c) Top offenders and components

- **Not recorded for these sessions.** The 507 event has no per-device attribution. `Kernel-Power 172` and `Kernel-Power 187` events exist but carry no drain or device breakdown (172 is a State/Reason pair; 187 is a system-action call with `ApiCallerName` for `winlogon.exe`).
- Blockers visible in the 507 fields (PROVEN as named, meaning not decoded): `NonDripsTimeActivatedInUs`, `ActiveResidencyInUs`, `NonActivatedCpuInUs`, `NonAttributedCpuInUs`, `AudioPlaybackInUs`, `FirstDripsEntryInUs`, `DwmSyncFlushTime`, `GdiOnTime`, `MonitorPowerOnTime`.
- The three NO-DRIPS sessions had `FirstDripsEntryInUs` = 0 and `ActiveResidencyInUs` equal to the whole session. Something kept the CPU out of DRIPS for the whole time. Which component caused it is not in these logs. The next step would be the SleepStudy ETL or a live `powercfg /sleepstudy` run on the Windows side, which is out of scope here.
- Hibernate events (`Power-Troubleshooter 1`, `Kernel-Power 42/107` with TargetState 5) are a separate path, not Modern Standby. They are not counted above.

## (d) Field provenance

| Field | Event / provider | Used for | Label |
|---|---|---|---|
| Session start/end, 506/507 pairing by time order | Kernel-Power 506/507 | session boundaries | PROVEN (pairing check: `ScenarioInstanceIdV2` matched in 1241 of 1241 pairs) |
| `DurationInUs` | 507 | duration | PROVEN as named; the time unit is microseconds per the name |
| `BatteryRemainingCapacityOnEnter` / `OnExit` | 506 / 507 | drain (mWh) | PROVEN as named; unit mWh INFERRED |
| `BatteryFullChargeCapacityOnEnter` | 506 | % battery | PROVEN as named; unit INFERRED |
| `DripsResidencyInUs`, `HwDripsResidencyInUs` | 507 | DRIPS %, HW DRIPS % | PROVEN as named |
| `SleepSwDripsResidencyInUs`, `SleepDurationInUs` | 507 | cross-check of SW DRIPS | PROVEN as named (not used in table) |
| `SW DRIPS %` column = DRIPS - HW DRIPS | derived | SW DRIPS % | INFERRED |
| `PowerStateAc`, `DisconnectedStandby`, `AudioPlaying`, `Reason`, `LidOpenState` | 506/507 | filters and labels | PROVEN as named; reason meanings NOT decoded |
| `ActiveResidencyInUs`, `FirstDripsEntryInUs`, `NonActivatedCpuInUs` | 507 | NO-DRIPS interpretation | PROVEN as named; meaning INFERRED |
| `Kernel-Power 105` `RemainingCapacity` / `FullChargeCapacity` | 105 | unit cross-check | PROVEN as named |
| `Power-Troubleshooter 1` (hibernate fields) | Power-Troubleshooter | excluded | PROVEN as named; hibernate meaning INFERRED from `HiberWriteDuration` etc. |

## (e) What could not be decoded, and what was skipped

- **`EnergyDrain` (507)** is unusable. 158 of 1241 sessions have a non-zero value, and many short sessions show values in the tens of thousands or more. One session (2026-03) shows 1284 against an 813 mWh capacity drop, so its unit or meaning is unknown. Not used.
- **`Reason` codes** (506/507) are raw numbers. Not decoded. Labels above are only the raw values.
- **`NonResiliencyTimeInUs`** holds values near 2^64 (e.g., 18446744053264294810), which is an unsigned underflow. Not used.
- **`ScenarioInstanceId` (non-V2)** does not match between 506 and 507 in general; only V2 pairs. Pairing uses time order plus V2 check.
- **SleepStudy ETL traces** (`SleepStudy/*.etl`, `ScreenOn/`) were not parsed. The event log already had drain and DRIPS numbers, so step 2 was not needed. Those traces would show component-level DRIPS blockers, which the event log does not contain.
- **Operational logs**: only `Microsoft-Windows-Kernel-Power%4Thermal-Operational.evtx` exists in that folder. It has no standby drain data and was not used.
- Battery capacity is an integer mWh gauge. Short sessions are noisy.
- Windows `Kernel-Power 506` count (1243) and `507` count (1241) differ by 2. Two 506 events have no 507 before the next 506 (no orphan 507). Those two are dropped, so 1241 sessions are analysed.

## Privacy

No computer name, user name, SID or email is in this note. Session data is aggregated by month; per-session times are not published.
