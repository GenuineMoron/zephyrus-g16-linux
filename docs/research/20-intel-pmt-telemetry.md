# 20 - Intel PMT telemetry and RAPL on the G16 (Meteor Lake-H, kernel 7.3.3-1-cachyos)

Scope: read-only. Nothing written to /sys, /proc, /dev, MSRs or EFI. Reads used sudo cat/python for
the root-only telemetry and RAPL files. No installs, suspends or reboots. No lspci, nvidia-smi,
vulkaninfo, or drm status reads.

Deliverables:
- Notes: this file.
- Decoder: [../../tools/pmt/pmt_read.py](../../tools/pmt/pmt_read.py) (read-only, XML-driven).
- XML source (public): the `xml/` directory of github.com/intel/Intel-PMT (master archive, downloaded
  2026-11-14; local working copy, not in the repo).
- Raw region dumps, boot-time (t0): `telemN_t0.bin` (local working copy, not in the repo).
- 10 s delta capture: `pmt-delta-2026-11-14.txt` (local working copy, not in the repo).

---

## 1. Enumeration

### 1a. /sys/class/intel_pmt (13 nodes, all root-only 0440 for `telem`, guid/size/offset world-readable)

| node | guid | size (B) | offset | parent (aux) | public XML | status |
|---|---|---|---|---|---|---|
| telem1 | 0x130670b2 | 3352 | 744 | intel_vsec.telemetry.0 (00:0a.0) | MTL/0 "Normal telemetry in Punit" (xml size 3336) | decoded |
| telem2 | 0x1a067002 | 1216 | 200 | intel_vsec.telemetry.0 (00:0a.0) | MTL/2 "Normal telemetry in DMU" | decoded |
| telem3 | 0x130671b2 | 596 | 0 | intel_vsec.telemetry.0 (00:0a.0) | MTL/1 "Fixed telemetry in Punit" (xml size 704) | decoded |
| telem4 | 0x1a067102 | 132 | 0 | intel_vsec.telemetry.0 (00:0a.0) | MTL/3 "Fixed telemetry in DMU" (xml size 200) | decoded |
| telem5 | 0x02625030 | 1180 | 3200 | intel_vsec.telemetry.1 (00:14.2) | none | raw only |
| telem6 | 0x02781795 | 196 | 288 | intel_vsec.telemetry.1 (00:14.2) | none | raw only |
| telem7 | 0x02880208 | 188 | 3584 | intel_vsec.telemetry.1 (00:14.2) | none | raw only |
| telem8 | 0x03224788 | 932 | 1024 | intel_vsec.telemetry.1 (00:14.2) | none | raw only |
| telem9 | 0x05077612 | 844 | 3344 | intel_vsec.telemetry.2 (00:14.2) | none | raw only |
| telem10 | 0x05317874 | 48 | 104 | intel_vsec.telemetry.2 (00:14.2) | none | raw only |
| telem11 | 0x05709395 | 80 | 512 | intel_vsec.telemetry.2 (00:14.2) | none | raw only |
| telem12 | 0x05850976 | 608 | 512 | intel_vsec.telemetry.2 (00:14.2) | none | raw only |
| telem13 | 0x04772882 | 292 | 1024 | intel_vsec.telemetry.2 (00:14.2) | none | raw only |

- All 13 are bound to `pmt_telemetry` (aux driver intel_vsec.telemetry.{0,1,2}). Bus paths:
  `0000:00:0a.0` (Punit/ DMU VSEC block, the first aux) and `0000:00:14.2` (PMC SSRAM, two aux).
- Module chain (from `/lib/modules/.../pmt/`, `/lib/modules/.../pmc/`): `pmt_class`, `pmt_discovery`,
  `pmt_telemetry`, `intel_pmc_ssram_telemetry`, `intel_pmc_pwrm_telemetry`, `intel_pmc_core`,
  `intel_vsec`. The `intel_pmt_crashlog` module is not present on this kernel
  (`modinfo` returns nothing), so no crashlog node exists (see open questions).
- The kernel log confirms: `intel_vsec 0000:00:0a.0: enabling device`,
  `intel_pmc_ssram_telemetry 0000:00:14.2: enabling device`, `intel_pmc_core INT33A1:00: initialized`,
  and RAPL: `hw unit of domain package 2^-14 Joules` (and pp0-core, pp1-gpu, psys all 2^-14 J).

### 1b. GUID to definition mapping

- `pmt.xml` (Intel repo) has 15 mappings. Four of the 13 GUIDs on this machine match the public MTL
  definitions (telem1-4). The other nine (telem5-13) are not in the public repo.
- The kernel's PMC SSRAM/PWRM drivers take their GUIDs from ACPI `_DSD` (strings `pmc_parse_telem_dsd`,
  `pmc_find_telem_guid`), so the nine unknown GUIDs are probably the PMC-side SSRAM blocks on 00:14.2.
  Their definitions are Intel-internal to this repo. Open question.
- Size mismatches vs public XML: telem3 (sysfs 596 vs XML 704) and telem4 (132 vs 200). The XML
  describes more than the region the firmware exposes. Samples past the end read as "outside region"
  (for example `LLC_FLUSHED_RESIDENCY` and `FIXED_BLOCK_SPARE*` in telem4).

### 1c. Kernel/driver confirmation of counter meaning
- `/sys/kernel/debug/pmc_core` (root, read-only files used): `slp_s0_residency_usec`, `die_c6_us_show`,
  `package_cstate_show`, `ltr_show`, `pch_ip_power_gating_status`, `substate_live_status_registers`,
  `substate_requirements`. These are the authoritative values the PMT numbers should match.
- Cross-check results (section 4) agree with them: PC10 residency 1.08 s in both sources,
  DIE DC6 about 248 s vs PMT 236-286 s over the same window.

---

## 2. Decoding model (verified against the Intel tool code and against this hardware)

Source of the rules: `tools/collectd-agent/pmt.py` in the Intel repo, plus the XSD.

- Sample storage: a `SampleGroup` with `sampleID = N` lives at byte offset `8*N`. A sample is bits
  `[lsb..msb]` of that little-endian qword.
- Transform: the `<transform>` expression in `*_aggregator_interface.xml` is applied to the raw value(s).
  Inputs come from `TransFormInput` (`sampleGroupIDREF`, `sampleIDREF`).

### 2a. Scale corrections that the decoder applies (checked, see table)

| transform | XML expression | what it really is | evidence |
|---|---|---|---|
| `xtal_time` (datatype `txtal_time`, label "s") | `raw / 38.4 * 1e6` | the expression yields **picoseconds**. Correct seconds = `raw / 38.4e6`. | XTAL counter advanced by 384,008,291 ticks in 10.0004 s = 38.399 MHz (ratio 0.99998). The decoder now shows XTAL = 1.001 s/s. |
| `energy_J` (datatype `tenergy_J`, "J") | `raw / 1048576` (2^-20 J) | the counter runs in the RAPL unit **2^-14 J** (ESU=14). | Kernel log: "hw unit of domain package 2^-14 Joules". PMT PACKAGE_ENERGY raw delta 745,446 in 10.0 s = 74,545 counts/s. At 2^-14 J that is 4.55 W, RAPL package 4.76 W on the same window (about 4% apart). At 2^-20 J it is 0.071 W, which is clearly wrong. |
| `vr_energy` (datatype `tvr_energy`, label "10nJ") | `raw / 16384` | the value is **J** (2^-14 J). The "10nJ" label is wrong. | VCCIA raw 23,399 counts/s gives 1.43 W, RAPL pp0-core 1.65 W. VCCGT 896 counts/s gives 0.055 W, RAPL uncore 0.046 W. |
| `PACKAGE_CSTATE_*_REFCNT`, `DIE_CSTATE_*_REFCNT` constants | not defined in the XML | constants are taken from a same-named sample (or the DIE_/PACKAGE_ twin) in the same region. | telem4 block-cause `DIE_CSTATE_BLOCK_CAUSE_CORE` = 95.4 % of `DIE_CSTATE_BLOCK_REFCNT`. |

Counter width: some counters are 32-bit (for example telem2 `C0_RESIDENCY_CORE0`, bits 0-31). At 38.4 MHz
they wrap every 2^32 / 38.4e6 = **111.8 s**. Deltas must be taken modulo 2^width. The decoder now does
this (wrap-aware delta, width taken from the sample's bit range). Any logger sampling those counters
must sample at least once per 111 s. A 60 s logger is fine.

Note on telem1 `PSYS_ENERGY`: raw is small and wraps (386 then 329), so PMT PSYS is not a usable
counter on this region. Use RAPL psys (below) instead. Not resolved.

### 2b. Validation: an XTAL-based cross check
Two reads 10.0 s apart, timestamp at read time:
- XTAL: 384,008,291 ticks in 10.0004 s, ratio to 38.4 MHz = 0.99998.
- GT_RC6 (telem1), C6_RESIDENCY_CORE0 (telem1): per-second rates 0.996 and 0.997. Sum with C0 = 1.00.

---

## 3. RAPL (intel-rapl*) domains, limits and 10 s power

Domains (`/sys/class/powercap`), root-only `energy_uj` (mode 0400), `max_energy_range_uj` =
262,143,328,850 uJ (wraps about every 14.6 h at 5 W, about 50 min at 90 W):

| domain | name | limits (long/short/peak) | note |
|---|---|---|---|
| intel-rapl:0 | package-0 | PL1 90 W (window 56 s), PL2 104 W (2.4 ms), peak 217 W | enabled=1 |
| intel-rapl:0:0 | core | none (window 976 us) | enabled=0 flag, but energy counts |
| intel-rapl:0:1 | uncore | none (window 976 us) | enabled=0 flag, but energy counts |
| intel-rapl:1 | psys | PL1 190 W (28 s), PL2 260 W (976 us) | enabled=1 |
| intel-rapl-mmio:0 | package-0 (mmio) | same as package | mirror of package |

10 s average, measured at idle (screen on, on AC, battery 96 % "Not charging"), 10.148 s window:

| domain | delta uJ | avg W |
|---|---|---|
| package-0 | 48,259,398 | **4.755** |
| core | 16,772,784 | 1.653 |
| uncore | 471,679 | 0.046 |
| psys | 194,258,291 | **19.142** |
| mmio (package mirror) | 48,260,558 | 4.756 |

Sanity: package minus core minus uncore = 3.1 W (L3, ring, fabric and other package logic).
psys minus package = **14.4 W** of platform power outside the package in this window. Do not trust this
as a wall number until it is measured against a meter. Candidates: panel and backlight, the Wi-Fi/BT
module, the NVMe and the USB subsystem, the EC/charger path. The dGPU was runtime-suspended per wave 1 and
is not expected to draw much. This is the largest open question for overnight drain (section 6).

Battery for comparison: BAT1 gives `voltage_now` (16.98 V) and `current_now` (0 A while on AC and
"Not charging"). There is no `power_now`, so P = V x I applies only while discharging. Not measurable
right now. Use the 40-sleep-stats hook's `watts` column (`-1.00` on AC).

---

## 4. Sample readings (PMT, decoded, 2026-11-14, 20:29-20:33, uptime about 18 min)

Rates are per wall second, wrap-aware, from 10.0 s deltas (`pmt-delta-2026-11-14.txt`, last run).

Package and energy:
- PACKAGE_ENERGY (telem1): 1.975 W in the last window, 5.3 W in an earlier window (system busier).
  Cumulative since boot about 4.9 kJ.
- VCCIA_ENERGY (telem1): 0.39 W. VCCGT_ENERGY: about 0.02 W.

Package C-states (telem3, Punit fixed; all since boot, rates per second of wall time):

| counter | fraction of wall time (last window) |
|---|---|
| OS_REQUESTED_CSTATE_PC10 | **0.81** (OS asked for PC10 81 % of the time) |
| PACKAGE_CSTATE_BLOCKED_PC10 | **0.12** (PC10 asked but blocked 12 % of the time) |
| PACKAGE_CSTATE_C10 (achieved) | **0.002** |
| PACKAGE_CSTATE_C8 | 0.38 |
| PACKAGE_CSTATE_C6 | 0.26 |
| PACKAGE_CSTATE_C2 | (about 0.01 in an earlier window; sums with C6, C8 leave the rest) |
| DIE_CSTATE_RESIDENCY_DC6 (telem4) | 0.63 (earlier window: 0.14) |

So the package spends its requested-deep time in **PC8, not PC10**. PC10 is blocked about 12 % of the time
and the remainder is PC8 or PC6.

Block causes (telem3, percentages of block events since boot; cumulative, not per-second):
- Device block cause: CDIE 30.1 %, PUNIT 27.2 %, SOC_CORE 22.9 %, DTS 11.0 %, UNKNOWN 5.7 %,
  DISPLAY 1.8 %, PCH 1.3 %. The rest is 0.
- Block category: TIMER 38.1 %, IP_BUSY 27.9 %, LATENCY 22.9 %, HYSTERESIS 11.0 %, DEMOTION 0.02 %.
- DTS blocks 11 % of the time: thermal sensor activity keeps the package out of PC10. Worth checking
  thermal polling (`thermald`, the ASUS EC thermal loop, `intel_powerclamp`).
- TIMER 38 %: periodic timers keep waking the package. Consistent with `PACKAGE_CSTATE_COUNTS_C2` at
  97-123 wakes/s (telem2).

LTR (latency tolerance) and the C10 threshold:
- `PACKAGE_CSTATE_LTR_THRESHOLDS_C10` = 325 us. A package LTR below that blocks C10.
- `PACKAGE_CSTATE_LTR_VALUES_PCH` moved from **50 us** (earlier read) to **608 us** and then **160 us**
  in later reads. The 50 us reading is consistent with the XHCI (USB) snoop LTR:
  `pmc_core/ltr_show` reports `PMC0:XHCI ... Snoop(ns) 51200` (raw 0x8832). While XHCI is at 51 us,
  the package cannot enter PC10. Confirm which USB device (or the hub) asserts it.
- `PMC0:IOE_PMC` LTR = 5.6 ms (raw 0x8cac8cac). It does not constrain.
- Display LTR = 65.5 ms ("no constraint" value), not limiting.

PCH IP power gating (pmc_core `pch_ip_power_gating_status`, PMC0, at the time of reading) shows these
still powered: XHCI, DSP0, DSP1 (audio DSP), CNVI (Wi-Fi/BT), SPA/SPB/SPC are off, SBR0-SBR5 root ports
on, HDA4-6, PSF2/3/6, SPF, SPE, FUSE, plus several RSVD bits. `substate_requirements` lists which of
these block S0i2.x. Compare them to `substate_live_status_registers` (LPM_LIVE_STATUS_0 `0x110031c1`,
LPM_LIVE_STATUS_1 `0xfe07f9f6`) to see which requirements are currently unmet.

Platform residency (telem1, Punit normal, same window):
- GT_RC6 99.6 %, MEDIA_C6 about 92 % (earlier window), core0 C6 99.6 %, core0 C0 0.1 %.
- Display fabric: NOC_BW_DISP0/1 about 120-310 MB/s (units from XML are "MB", treat as relative).

Temperatures (Snapshot): PCH 38 C, DTS0 36-40 C, DRAM 40 C.

Caveat: the XML units for IO_TOTAL_WRITE_BANDWIDTH (about 25-57 "MB/s" at idle) and NOC_BW_* look too
high for an idle machine. Treat them as relative until calibrated.

Caveat on telem2 per-core residency: it is 32-bit for C0 (wraps every 111.8 s). Single-read values
are not meaningful. Use deltas (the decoder now does this).

### 4a. Cross-check against pmc_core debugfs (same boot, separate sources)
- `slp_s0_residency_usec` = 80,429,964 us = **80.4 s** of SLP_S0 residency since boot, at about 18 min
  uptime. That is about **7 %**, which matches the "8 % S0ix" the overnight report uses. (The PMT
  counter basis is not SLP_S0 itself, but the PMC block agrees.)
- `package_cstate_show` (us): C2 85.5 s, C3 0.7 s, C6 143.4 s, C8 104.6 s, C10 1.08 s.
  PMT telem3 C10 1.079 s and C6 about 132-143 s agree.
- `die_c6_us_show` = 248.5 s, PMT DIE DC6 236-286 s. Agree.

---

## 5. Which counters explain each symptom

(a) Overnight standby drain of about 5 W with 8 % S0ix:
1. Package energy during suspend. The PMT PACKAGE_ENERGY and RAPL package counters keep counting in
   S0ix. Take them before and after each suspend and divide by the time: this gives the watts the
   package draws in the suspended state (no battery needed, and not affected by AC). If package is
   about 0.5 W and the battery says 5 W, the other 4.5 W is outside the SoC (psys minus package), which
   points at panel, dGPU, Wi-Fi, USB or EC.
2. Deep-state denial. `OS_REQUESTED_CSTATE_PC10` minus `PACKAGE_CSTATE_C10` per segment is the
   requested-but-not-achieved PC10 time. `PACKAGE_CSTATE_BLOCKED_PC10` says it was blocked.
   The block causes (DEVICE_BLOCK_CAUSE_*, BLOCK_CATEGORY_*) say by what. Overnight, the top
   candidates are TIMER (periodic wakes), DTS (thermal sampling) and IP_BUSY.
3. LTR during suspend: `PACKAGE_CSTATE_LTR_VALUES_PCH` and the XHCI snoop LTR (51 us blocks C10).
4. PCH IP PG state and LPM live status (pmc_core) at the moment of suspend: any requirement that stays
   unmet keeps the S0i2 path closed. Log `substate_live_status_registers` before and after.
5. `slp_s0_residency_usec` delta per segment: the same counter the 40-sleep-stats hook already
   reports as `deep_pct`. Use it as the ground truth for the percentage.

(b) Idle with the screen on:
1. GT_RC6 % and MEDIA_C6 % (is the GPU idle), and NOC_BW_DISP0/1 (display fabric traffic).
2. Package C-state residency C8 vs C10, PC10 requested vs blocked, and the block causes (CDIE, PUNIT,
   DTS, TIMER). A large C8 share with PC10 blocked is the screen-on signature.
3. Package C2 wake rate (`PACKAGE_CSTATE_COUNTS_C2`): 97-123 wakes/s points at a tick or timer
   source. Check CONFIG_HZ and the timer-slack/ tick settings.
4. PCH IP PG: XHCI, DSP0/1, CNVI, SBR0-5 on. Each one that has LTR over 325 us is fine; each one with
   LTR under 325 us blocks C10.
5. RAPL package minus core minus uncore (about 3.1 W at idle) is the non-core package share.

---

## 6. Proposed low-overhead logger

Cost: one decoder run is about 0.65 s wall, mostly XML parse of four definitions (cache them or use
a `pickle` file to cut this to ~50 ms). Each read is a 3-10 KB sysfs read, so the steady-state cost is
negligible.

Awake (every 60 s):
- Run as a root systemd service (telem and RAPL files need root). Example command:
  `python3 -I <repo>/tools/pmt/pmt_read.py --dev telem1 telem2 telem3 telem4 --watch 60 --csv /var/lib/pmt-log/awake.csv --only 'OS_REQ|CSTATE_C|CSTATE_BLOCK|LTR_VALUES_PCH|ENERGY|GT_RC6|BLOCKED|XTAL$'`
  The script writes one CSV per device (`awake-telemN.csv`), with the raw counts for the matched
  samples. A row is about 150-200 bytes at this filter, which is about 1 MB/day/device. Note the
  32-bit counters (wrap 111.8 s): 60 s is safe.
- RAPL: a second column per row (package, core, uncore, psys `energy_uj`, read as root in the same
  process). The decoder does not do RAPL yet; add it or use a 5-line sibling script.
- Also log the pmc_core files `slp_s0_residency_usec`, `package_cstate_show`, `ltr_show` (cheap reads).

Standby (before/after each suspend):
- Extend the existing `/usr/lib/systemd/system-sleep/40-sleep-stats` `pre` and `post` branches to call
  the decoder with `--json --only ...` and write `/var/lib/sleep-stats/pmt-pre.json` and
  `pmt-post.json`. The hook already runs as root and reads the pmc_core files, so no new privilege is
  needed. Cost is about 0.7 s per call, which is fine inside systemd-sleep.
- In `post`, compute per-segment deltas (energy in J, counter deltas with wrap, and the mean watts
  over the segment time): `(pkg_energy_post - pkg_energy_pre) / (t_post - t_pre)`.
- Keep the segment's `OS_REQ_PC10`, `PC10`, `BLOCKED_PC10` and the top block causes in the same
  row so one line answers "why did it not reach deep sleep?".

Caveats:
- The hook's `pre` runs before the freeze; PMT reads are fast (<10 ms each) and do not touch device
  state, so they do not change the suspend path. Do not add an `--dump-dir` in the hook (it writes
  files, which is fine on disk, but keep the hook minimal).
- Measure before trusting: run the logger for one overnight cycle and compare the package-energy
  watts with the battery watts from the hook.

---

## 7. Open questions

1. PMT telemetry for the nine GUIDs on 00:14.2 (telem5-13). Probably PMC SSRAM and PWRM. Needs the
   Intel definitions (not public) or an ACPI `_DSD` dump (root) to map them.
2. Crashlog: `intel_pmt_crashlog` is not built as a module on this kernel, and there is no crashlog
   node. Confirm whether the firmware exposes a crashlog VSEC feature (check `pmt_discovery` feature
   list and the kernel `CONFIG_INTEL_PMT_CRASHLOG`, which the wave-1 notes say is `=m`).
3. PSYS: the PMT PSYS counter wraps and does not add up. RAPL psys (19 W at idle) is far above package
   (4.8 W) in the same window. Is psys a firmware estimate? Compare with a wall meter.
4. psys minus package = 14.4 W at idle. This is the single biggest question for drain and needs a wall
   meter. Candidate: the panel and backlight, the dGPU (D3cold not confirmed), the EC.
5. Energy-unit confirmation: ESU=14 from the kernel log, and PMT agrees to 4 %. Confirm by reading
   `MSR_RAPL_POWER_UNIT` with turbostat (read-only).
6. The XML energy transform (/2^20) disagrees with the hardware. Report upstream (Intel-PMT repo) if
   wanted.
7. Telem2 per-core C0 is 32-bit. Confirm the width from the XML group length (the decoder uses the bit
   range in the sample definition, which says 0..31).
8. The 40-sleep-stats `watts` column is -1 on AC. For drain measurement the logger needs package
   energy, which works on AC too.
9. IO_TOTAL_WRITE_BANDWIDTH and NOC_BW_* units from the XML are not calibrated.
