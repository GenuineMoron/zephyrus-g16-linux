# 22 - EC RAM map, hotkey event codes, ambient light sensor (GU605MI, BIOS 329)

Wave-2 deep dive on note 02. Read-only: /dev/mem (256 bytes at 0xFE108300, ERAM only), DSDT/SSDT text,
sysfs, kernel log, the kernel source copy from wave 1 (local working copy, not in the repo), /usr/lib/udev/hwdb.d and
the mounted Windows partition (read-only, INF/registry strings only). No writes, no GPU-touching tools.
Tool: [`../../tools/ec-map.py`](../../tools/ec-map.py) (usage at the top of the file).

Label scheme as in note 02: **[proven]** = read from a table, sysfs or the live EC; **[inferred]** = reasoning.

## 1. ec-map.py

- Parses every `OperationRegion (..., SystemMemory, ...)` and its `Field` blocks from dsdt.dsl and the
  SSDTs next to it. Handles `Offset()`, unnamed padding fields, `AccessAs`/`Connection`, and multi-bit
  fields (the 120-bit MBDN is read as one integer). Bit order is ACPI LSB-first.
- Reads 256 bytes with `os.pread` on /dev/mem; `--parse-only` never touches /dev/mem.
- `--refs` lists the DSDT/SSDT method each field is used in; `-n N -i S` takes N samples and flags
  fields that changed with `*`; `--json` writes the last snapshot.
- Run: `sudo python3 -I ec-map.py -n 4 -i 10 --refs`.
- Check: ERAM map gives VIUF = 08.1, VGAT = 59.2, GC6S = C0.1, as in wave 1. Field count 206 named,
  231 entries, max bit 2048 (256 bytes, fills the window exactly).

## 2. Live EC values (ERAM), 2026-11-14 20:25-20:30, AC on, dGPU off

| Field | Value | Meaning and evidence |
|---|---|---|
| CTMP 58.0 | 42-47 C | main thermal zone (`_TZ.THRM`, `_TMP` at dsdt:74952). **[proven]** matches acpitz/coretemp 44-45 C |
| CLOT 01.0 | 39 | thermal zone `_TMP` at dsdt:76757. Sensor identity unknown |
| VLTT C6.0 | 37 | `_TMP` at dsdt:76884. Sensor identity unknown |
| VRTT C5.0 | 0 | read by NVIDIA NPCF (ssdt24:2153). **[inferred]** dGPU/VR temp; 0 while dGPU is off |
| FRMS 66.0 | 1185-1231 | CPU fan tach. WMNB 0x110013 / GCFR compute `RPM/100 = 2140890 / value / 100` (dsdt:77813) **[proven code]** |
| FRS2 68.0 | 1140-1231 | GPU fan tach (WMNB 0x110014, dsdt:77831) **[proven code]** |
| FRS3 60.0 | 557-585 | mid fan tach (WMNB 0x110031, dsdt:78097) **[proven code]** |
| MBVT 4A.0 | 16981-16984 mV | battery voltage (UPBS). **[proven]** |
| MBCT 46.0 | 0 mA | signed battery current (UPBS). 0 = not charging, as sysfs |
| RCAP 48.0 | 4654 mWh | remaining capacity; sysfs `charge_now` 4654000 uWh **[proven]** |
| MBCP 6C.0 | 4825 mWh | full-charge capacity; sysfs `charge_full` **[proven]** |
| MDCP 6A.0 | 5650 mWh | design capacity; sysfs `charge_full_design` **[proven]** |
| MBDV 75.0 | 15930 mV | design voltage (UPBI). **[proven]** that UPBI reads it |
| RSOC 77.0 | 96 % | state of charge; `_QB6` uses it to set NVIDIA dynamic boost (RSOC > 50) **[proven]** |
| BHCH E7.0 | 0x50 = 80 | charge limit. `_QDB` writes 0x50, UPBS tests `== 0x50`. Matches sysfs threshold 80 **[proven]** |
| BTMP 78.0 | ~2999-3000 | battery temperature, probably 0.1 K (~26.7 C). No ACPI reader **[inferred]** |
| CYCL E2.0 | **87** | battery cycle count. sysfs `cycle_count` reads **0**. The ACPI battery has no `_BIX` and no method reads CYCL, so 0 is a placeholder **[proven]** |
| PL01 9B.0 | 90 W | PL1, written by WMNB 0x1200A3; matches `ppt_pl1_spl` 90 **[proven]** |
| PL02 9D.0 | 104 W | PL2, written by WMNB 0x1200A0. sysfs `ppt_pl2_sppt` says 135. **Mismatch: check which value is applied** |
| PL04 9F.0 | 217 | not read by ACPI **[unknown]** |
| ACIN 44.0 | 1 | AC present; `_PSR` returns it **[proven]** |
| NOAC 5E.0 | 0 | inverse of ACIN **[proven]** |
| LIDS 52.5 | 0 | 1 = lid CLOSED (`_LID` returns the inverse) **[proven]** |
| VGAT 59.2 | 0 | dGPU power flag: 1 while NVIDIA is on (set in `_ON`, cleared in `_OFF`, ssdt15). **[proven]** |
| VIUF 08.1 | 0 | dGPU "VGA in use", read by `_OFF` (ssdt15:2261) and `_Q7A` **[proven]** |
| TTT1 FE.0 / TTT2 FF.0 | 120 / 80 | thresholds read by SFMN (fan mode). **[inferred]** |
| NDF9 0C.0 / DB2F 0E.4 / FGA9 0D.1 | 0 / 1 / 0 | NVIDIA dynamic-boost and bus-check flags (`_QB6`, `_QA8`, `_QA9`) |
| MBDN D0.0 | "GU60558" | battery model string, ASCII **[proven]** |
| ECMJ E4.0 / ECMN E5.0 | 3 / 39 | EC firmware version, from the field names **[inferred]** |
| DVMJ EE.0 / DVMN EF.0 | 17 / 0 | version fields, meaning unknown |
| CHKR 12.0 | 0xAA55 | EC signature **[inferred]** |

Changed over the 60 s window (`*` in the tool): CTMP (47 -> 42), MBVT (+/- 3 mV), FRMS/FRS2/FRS3 (fan
tachs), BTMP (2998-3000). The rest held steady.

**Fan decoding check:** hwmon `asus` (hwmon6) fan1/fan2/fan3 read 1700-1800 / 1800-1900 / 3600-3800 RPM
over the same period. Using `RPM ~= 2140890 / field`, FRMS/FRS2/FRS3 give 1700-1800 / 1700-1900 /
3700-3800, within about 100 RPM (WMNB floors to 100 RPM). FRMS and fan1 (CPU) move in opposite directions
in the samples, so the mapping is right. **[inferred from correlation plus proven WMNB divisor]**

### Corrections to note 02

- **KBLC is not in the EC.** It sits in the `EXBU` field at `0x45C36018` (length 0x15E), the BIOS
  ASL mailbox, not `ERAM`. The same applies to `AACI`, `ALSP`, `ALSE`, `ALAE`, `LBTN`, `BRTL`.
  This region was outside the read-only scope of this pass, so it was not read.
- **CYCL is real:** 87 cycles, not a placeholder. Linux reports 0.
- Note 02 said `_Q2E`/`_QA6` send 0x4F. Confirmed; the methods are only ATKP-gated.

## 3. Hotkey event codes (EC query -> ATKD.IANE -> Linux)

### 3.1 Full EC-query-to-IANE table (from the DSDT, not guessed)

Direct `_Qxx` methods (`IANE` called in the method body):

| _Qxx | IANE code | Linux asus-nb-wmi.c keymap | Likely key / meaning |
|---|---|---|---|
| _Q21 | 0x7C | KEY_MICMUTE | mic mute (mapped) |
| _Q76 / _Q77 | 0xC5 / 0xC4 | KEY_KBDILLUMDOWN / UP | keyboard backlight (mapped) |
| _QD5 | 0x38 | KEY_PROG3 | Armoury Crate / ROG key (mapped) |
| _QD6 | 0xB3 | KEY_PROG4 | Aura key (mapped) |
| _Q3F | 0x57/0x58/0xCF | IGNORE | AC/battery change |
| _QD8 | 0x7B | IGNORE | charger connect |
| _Q84, _QBA, _QB9 | 0x6E | IGNORE | low battery |
| _QD7, _QDA(via QLIB 0xCF) | 0xCF | IGNORE | AC mode |
| **_Q2E, _QA6** | **0x4F** | **none** | unknown; see 3.3 |
| **_QAE, _QB4, _QDB** | **0xE5** | **none** | battery charge-limit state (see 3.3) |
| **_QDC** | **0x68** | **none** | unknown; see 3.3 |

Via `QLIB(arg)` (switch at dsdt:79527). Callers in the DSDT are the only way these reach IANE:

| _Qxx | QLIB arg | IANE / action | Linux | Likely key |
|---|---|---|---|---|
| _QB5 | 0x25 | 0xAE | KEY_FN_F5 | Fn+F5 fan mode (mapped) |
| _Q22 | 0x2A | 0x6B | KEY_TOUCHPAD_TOGGLE | touchpad toggle (also sets TPFG) |
| _QAF | 0x2B | 0x88 | KEY_RFKILL | airplane / radio |
| _Q8A | 0x2C | 0x8A | KEY_PROG1 | color/Splendid mode |
| _QB8 | 0x2E | 0xB5 | KEY_CALC | **a calculator mapping is probably wrong for this key** |
| _Q18 | 0x26 | BRTN(0x87) | ACPI, i915 | brightness; up/down direction **[inferred]** from SKEY pairing (0x10 -> BRTN 0x87, 0x20 -> BRTN 0x86) |
| _Q17 | 0x27 | BRTN(0x86) | ACPI, i915 | brightness, the other direction **[inferred]** |
| _Q31 | 0x22 | Notify(SLPB,0x80) | ACPI sleep button | sleep |

Not called from any `_Q` method on this firmware, so unreachable from the EC (see section 3.4): QLIB cases
0x15, 0x24, 0x09, 0x0A, 0x0B, 0x0C, 0x16, 0x17 (keyboard via QLIB), 0x19, 0x1A, 0x2D (-> 0x82 camera),
0x30 (-> 0x9E), 0x33 (-> 0x7A ALS toggle), 0x34, 0x35, 0x36, 0x37 (-> 0x86 MyASUS).

`SKEY` (dsdt:80548) is a second dispatcher, reached from WMNB 0x00100021 (the OS asks ACPI to inject a
key). Its cases are 0x86 MyASUS, 0xC4/0xC5, 0xB3, 0xAE, 0x6B, 0x8A, 0x9E, 0x7C, 0x38, 0xB5, 0x35, plus
brightness and sleep. So the Windows software sees key IDs that match the EC table above.

### 3.2 Codes with no keymap entry

Only three codes are both emitted directly by the DSDT and missing from asus-nb-wmi.c (`keymap`
at lines 610-691 in the wave-1 source): **0x4F, 0xE5, 0x68**. Two more are reached only through SKEY or
unreachable QLIB cases: **0x9E** (SKEY case 0x9E, which WMNB 0x00100021 can call; also QLIB 0x30 with no caller) and **0x0A/0x1A** (only from unreachable QLIB cases).

Linux logs these at **info** level, `Unknown key code 0x..` (asus-wmi.c:4694). The retained journal (4 boots,
back to 2026-11-14 12:32) has **no** such lines, so none of the three fired in that time. Absence is
proof of "not pressed", not of "not emitted", but a press will show up.

### 3.3 Meaning of 0x4F, 0xE5, 0x68

- **0xE5 is not a physical key [inferred, fairly strong].** `_QDB` (EC 0xDB) sets `BHCH = 0x50` (80 %
  charge limit) and then sends 0xE5. `_QAE` and `_QB4` send 0xE5 too, with no state change. This looks
  like a "battery charge-limit state changed" notification that makes Armoury Crate refresh its toggle.
  Map it to KE_IGNORE, not to a key.
- **0x4F (EC 0x2E and 0xA6) and 0x68 (EC 0xDC): unknown [unverified].** The EC query numbers do not
  follow a clear rule (for example 0xD5 and 0xD6 are Armoury and Aura), so the physical keys are not guessed here. Not in SKEY, so the OS never injects them; they are EC-side events.

### 3.4 Physical-key identification test (manual, no state change)

```
journalctl -k -f | grep --line-buffered 'Unknown key code'
```
Press each unidentified Fn key (candidates: any Fn key not in the mapped list above, e.g. the MyASUS key,
camera key, and whichever Fn+letter chords exist on this keyboard). Each press logs its code. Pair the
code with the key. This is the one step that settles 0x4F and 0x68 without touching the EC.

Things the DSDT shows **cannot** happen on this firmware, so do not expect them: ALS toggle 0x7A (its QLIB
case has no caller), camera 0x82 (QLIB 0x2D has no caller), MyASUS 0x86 (only from SKEY, i.e. Windows
software). If the camera or MyASUS key works in Windows, the path is in the Windows driver, not this table.

### 3.5 Proposed keymap / hwdb (not applied; needs a kernel rebuild or hwdb)

- **hwdb cannot add these codes.** asus-wmi drops unknown codes before input. hwdb only remaps codes
  the kernel already reports, through the `Asus WMI hotkeys` device with `KEYBOARD_KEY_<hex>`, as the
  M1607KA entry does (60-keyboard.hwdb:302-303, `KEYBOARD_KEY_7e=prog2`). So an hwdb entry works for
  remapping, e.g. KEY_CALC on 0xB5, but not for 0x4F/0x68/0xE5.
- **Kernel keymap (asus-nb-wmi.c, asus_nb_wmi_keymap), after the test in 3.4:**
  ```
  { KE_IGNORE, 0xE5, },  /* battery charge-limit state change (EC 0xAE/0xB4/0xDB), not a key */
  ```
  0x4F and 0x68: add `KE_KEY` with the matching KEY_* once identified, or KE_IGNORE if they are only
  state notifications. Do not add either blind.
- **Possible hwdb remap, not verified:** `evdev:name:Asus WMI hotkeys:...:pnGU605MI*:` with
  `KEYBOARD_KEY_b5=reserved` if the key behind 0xB5 (QB8) is not a calculator. Test first.
- Upstream: a keymap PR for GU605MI would be the durable fix. No GU605 entry appeared in the wave-1 quirk list.

## 4. Ambient light sensor

- **ACPI device `ASUS9001` is not an ALS.** It is `_SB.ARLS`, `_HID "ASUS9001"`, with only `_STA`
  (0x0F when `AACI==1`, else 0). No `_ALI`, `_ALR`, `_ALC`, `_CRS`, no EC field. **[proven]**
- **Windows binds ASUS9001 to Armoury Crate.** `/mnt/win/os/Windows/INF/oem99.inf` and `oem238.inf`
  (`ArmouryCrateControlInterface`, service `ACDS`) use `ACPI\ASUS9001`. The registry also holds a
  `SensorGroup` compatible-ID string near it, which is a generic Windows tag. **[proven]** for the INF; the
  registry link is weaker.
- **Linux:** `/sys/bus/acpi/devices/ASUS9001:00` has no driver link (`driver` entry absent). **[proven]**
  `ASUS2018` (`_SB.ASUP`) is the other ASUS device; Windows binds it to `ATKWMIACPI` (oem189.inf).
- **No IIO devices:** `/sys/bus/iio/devices` does not exist. No ACPI0008 or INT33D5 (ISH) in the
  DSDT/SSDTs. No 00:12.0 Intel ISH PCI function in sysfs. **[proven]**
- The Windows SYSTEM hive lists "Intel(R) Integrated Sensor Hub - 43FC", which suggests an ISH existed in
  Windows. Linux shows no ISH device. Treat the sensor as absent or not wired. **[inferred]**
- **Kernel:** the keymap has `0x7A -> KEY_ALS_TOGGLE` and `0xC6` as ALS notification (ignored). The
  ASUS ALS enable (DEVID 0x050001, `asus_wmi_set_als`) is only forced by a DMI quirk for some models.
  DSTS 0x050001 returns 0xFFFFFFFE here, and there is no `als_enable` node. **[proven]**
- **Userspace reader via EC: not possible.** No ERAM field carries light data. The ALS-related fields
  (ALSP, ALSE, ALAE) are in EXBU (BIOS mailbox), outside the read scope of this pass.
- **Recommendation:** no ALS driver. This unit probably has no ambient light sensor, or it is not
  reachable from ACPI. Check only if auto-brightness is wanted: a Windows "auto brightness" toggle
  in Settings > Display, and the Windows Device Manager "Sensors" category.

## 5. Other EC features Linux does not use

- **Battery cycle count CYCL (E2.0):** 87. Linux reports 0. A battery driver or asusd could read it.
  Reading EC RAM for this needs root and a read-only ec debugfs or the ACPI path, not done here.
- **Charge limit BHCH (E7.0):** EC copy of the 80 % limit, which asusd sets through SMM via DEVID 0x120057.
  Linux reads the value back from sysfs; BHCH could be a cross-check.
- **Battery capacity and voltage:** RCAP, MBCP, MDCP, MBVT, MBCT, RSOC are all used by ACPI and match
  sysfs. The 16-bit MBCT is signed (mA), which sysfs reports as `current_now` 0.
- **Fan tachs FRMS/FRS2/FRS3:** used by WMNB, already exposed as hwmon `asus` fan1-3, so no gap here.
- **PL01/PL02/PL04:** written by WMNB. PL02 = 104 vs sysfs 135 is the one discrepancy to resolve
  (dsdt:78792 writes it, so check what the EC applies).
- **dGPU / power-path flags:** VGAT, VIUF, GC6S, NVPS, UFON, TRSC, UMAF, PODF, CAMF. Only VGAT/VIUF
  are read by ACPI. GC6S is declared but unused, which fits note 02.
- **Charger / USB-C path flags:** PDAI, UPDI, U45N, UPEN, UPNN, PONL (WMNB PDSS, dsdt:78148-78163)
  are the charge-port state behind `charge_mode`. Not read from Linux.
- **Lid:** LIDS is the EC lid-closed bit (inverted). Linux gets the lid from the ACPI button.
- **SMBus mailbox (SMAD, SMCD, SMD0, SMST, SMAA, SMAR, SAD0):** an EC-side SMBus interface (possibly the
  battery/charger). No ACPI reader; not explored.
- **Thermal extras:** CLOT, VLTT, VRTT, TTT1/TTT2. Only the zone that uses them is known.
- **EC version:** ECMJ.ECMN = 3.39 and DVMJ.DVMN = 17.0 (inferred from names). Useful in bug reports.
- **Keyboard/Fn-lock bits:** LCKY, LALT, LPSK, BUKU (FC.x). Names suggest lock keys; not verified.

## 6. Open items

1. Identify 0x4F and 0x68 (section 3.4). Print the key press map.
2. Confirm which PL2 is applied (EC 104 vs sysfs 135).
3. Read EXBU (`0x45C36018`) for KBLC and the ALS flags, but only as a deliberate step, since it is
   outside the read scope.
4. Decide on the CYCL exposure (battery driver patch or asusd).
