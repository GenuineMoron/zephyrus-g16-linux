# 02 - Embedded Controller and ASUS WMI: firmware vs Linux

Machine: ASUS ROG Zephyrus G16 GU605MI, BIOS GU605MI.329 (06/06/2025), CachyOS kernel 7.3.3-1.
Date of research: 2026-11-14. Read-only investigation; no system state was changed.

## 0. Sources and caveats

- ACPI: `~/.local/src/acpi-tables/dsdt.dsl` (81,845 lines). The DSDT header in
  `dmesg` (`ACPI: DSDT ... 06A364 ... INTL 20210930`) matches `dsdt.dat` size 435,044 bytes, so the
  decompiled tables are the ones this firmware boots with. SSDTs are in `ssdt*.dsl`.
- Linux driver source: fetched from `torvalds/linux` **master** (not the 7.3.3 tag). Files read
  (local working copy, not in the repo):
  `asus-wmi.c`, `asus-wmi.h`, `asus-nb-wmi.c`, `asus-armoury.c`, `asus-armoury.h`, and
  `hid/hid-asus.c`, `hid-ids.h`. Line numbers for driver code refer to those files and
  may differ slightly from 7.3.3.
- Not touched: `msdm.dat/dsl`, `lspci`, `nvidia-smi`, `vulkaninfo`, `/sys/class/drm/*/status`,
  `/sys/kernel/debug/ec` (permission denied anyway). EC RAM was **not** read raw; EC bit offsets are
  taken from the ACPI field declarations only.
- Labels: **[proven]** = read directly from the table, sysfs or log; **[inferred]** = my reasoning
  from code, not confirmed on hardware.

---

## 1. Embedded Controller `\_SB.PC00.LPCB.EC0` (PNP0C09)

Declaration: `dsdt.dsl:75579` (`Device (EC0)`).

- `_CRS` (75582): legacy EC ports `0x62` (data) and `0x66` (command/status). Kernel log confirms
  `ACPI: EC: EC_CMD/EC_SC=0x66, EC_DATA=0x62`, and `ec_event_clearing=query`. **[proven]**
- `_GPE` returns **0x6E** (75612). **[proven]**
- `_REG` (75624): sets `ECOK`/`OKEC` on region-space 3 (EC) availability. `_PS3` (around 76370) clears
  `ECOK`. Most battery/LID methods bail out if `ECOK == 0`. **[proven]**
- `_STA` (75602) returns 0x0F and sets `^^^GFX0.CLID = 1`. **[proven]**

### 1.1 EC RAM map (memory-mapped, not port I/O)

The ACPI-visible EC RAM is a SystemMemory region, not the port-I/O space:

| Region | Base | Length | Line |
|---|---|---|---|
| `ERAM` | `0xFE108300` | 0x100 | 75633 |
| `ERM2` | `0xFE108B00` | 0x100 | 75915 |
| `ERM3` | `0xFE108500` | 0x100 | 76158 |
| `ECDL` (SystemIO) | `0x62`, len 6 (ECDP/ECCP) | | 76290 |
| `IOWT` (SystemIO) | `0xED` | 1 | 76298 |

**[proven]** Selected `ERAM` fields (offset in parentheses where declared):

- Lid/AC/battery: `LIDS` (0x52 area), `ACIN` (~75708), `NOAC` (75757), `BATM`, `QCHK`, `BTPL/BTPH`,
  `MBCT` (16 b, battery current, 75724), `RCAP` (16 b, remaining capacity, 75725), `MBVT`, `DBAT`
  (battery id bitmask, 75765), `RSOC` (8 b, 75799), `MBDV`, `MDCP`, `MBCP` (design/full capacity),
  `CTMP` (75736, EC temperature), `RSOC`.
- dGPU / sleep: `VIUF` (75651), `VGAT` (75739), `GC6S` (75858), `UFON`/`UMAF` (75862 region),
  `TRSC`, `S3LW` (75742), `WOLN` (75715), `RTCF` (75709), `SHBS` (75658), `WLRY` (75642).
- Keyboard backlight: `KBLC` (75542), `KBLM` (75961), `KBS1..3`, `KBSP`, `KBBS`, `KBLO/KBHI` (75750).
- Battery extras: `CYCL` (75890, 16 b cycle count), `BASN`, `NMON`, `ECMJ/ECMN`, `BHCH` (battery
  charge handshake), `DNCT`, `MBDN`.
- Power limits in EC: `PL01` (0x9B), `PL02` (0x9D), `PL04` (0x9F, with `MMDF/MAMD/MBCM` bits).
- Thermal / fan / mux: `THRP`, `OSUT`, `PRAL/PRAH`, `CORL/CORH`, `CSKS`, `TTT1/TTT2`.
- Keyboard lock etc.: `LCKY`, `LALT`, `LPSK`, `BUKU` (0xFC).

**[proven] Declared but never referenced by any ACPI table** (grep count = 1, i.e. the declaration
only): `GC6S`, `S3LW`, `SHBS`, `WLRY`, `RTCF`, `WOLN`, `LIDE`, `S4UM`, `CBFG`, `DPFL`, `WSVP`,
`WANS`, `LRFN`, `LS4F`, `ECOB`, `KBLO`, `KBHI`, `CCDS`, `RFBN`, `ASDW`, `ASDO`, `CYCL`, `BASN`,
`NMON`. These are read/written by EC firmware or SMM only **[inferred]**, so ACPI will not show their
state. `CYCL` in particular is the reason `cycle_count` in sysfs reads 0 (see §2).

### 1.2 Query (`_Qxx`) methods

All in `dsdt.dsl`. Event codes sent to ATKD go through `IANE` (ATKD device, 77211). "Keymap" = Linux
`asus-nb-wmi.c` keymap (`asus-nb-wmi.c:610-691`).

| _Qxx | Line | What it does | Linux consequence |
|---|---|---|---|
| `_Q2F` | 79794 | `Notify(LID0, 0x80)` - lid change | `LID0` `_LID` reads `LIDS` (74896). Works. |
| `_Q3E` | 76382 | debug `P80B` only | none |
| `_Q3F` | 76390 | **AC/battery change**: `SELE()`/`CHBP()`, notify `ACAD 0x80`, `BAT1 0x80/0x81`. If ATKP: `IANE(0x58)+IANE(0xCF)` on AC, `IANE(0x57)+IANE(0xCF)` on battery | 0x57/0x58/0xCF/0x7B are `KE_IGNORE` (asus-nb-wmi.c:630-631, 687, 649) |
| `_Q40`,`_Q41` | 76487,76493 | `Notify(\_TZ.THRM, 0x80)` - thermal | ACPI thermal zone re-read |
| `_Q79` | 76499 | USB-C (`UBTC`) status notify if `USTC` | not in Linux keymap path |
| `_QCE` | 76508 | `Notify(PWRB, 0x80)` - power button | ACPI power-button |
| `_Q84`,`_QBA`,`_QB9` | 76514-76545 | `IANE(0x6E)` | 0x6E is `KE_IGNORE` ("Low Battery") |
| `_QB6` | 76532 | if RSOC > 50: `SPAB(1)` else `NDF9=0`, `SPAB(0)` - toggles NVIDIA dynamic-boost "DBAC/DBDC" flags and notifies `NPCF` | Battery-level dependent GPU power policy **[proven code]** |
| `_Q85`,`_Q8C` | 76554-76564 | notify `BAT1` 0x81 / 0x80 | battery info refresh |
| `_QAE`,`_QB4`,`_QDB` | 76567, 80825, 76682 | `IANE(0xE5)` | **0xE5 is not in the Linux keymap** (unknown code) |
| `_Q2E`,`_QA6` | 76573,76582 | `IANE(0x4F)` | **0x4F not in Linux keymap** (unknown code) |
| `_QE6` | 76591 | `Notify(GFX0, 0x02)` device wake, then `0x81` info change (500 ms sleeps) | dGPU wake path **[inferred]** |
| `_QD4` | 76600 | NVIDIA `NPCF.WM2M` / `NTWF` toggles, notify `NPCF 0xC1` | NVIDIA-side notification |
| `_QD7` | 76644 | `IANE(0xCF)` (AC-related) | ignored |
| `_QCF` | 76653 | `Notify(HIDD, 0xCF)` if `HIDD.BTLD` | HID dock |
| `_Q21` | 76663 | `IANE(0x7C)` | **0x7C -> KEY_MICMUTE** (mapped) |
| `_QD8` | 76672 | `PDAC=0`, sleep 200 ms, `IANE(0x7B)` | 0x7B ignored (charger connect) |
| `_QDC` | 76692 | `IANE(0x68)` | **0x68 not in Linux keymap** |
| `_QE0`,`_QE1` | 76701,76705 | empty | none |
| `_Q76` | 79803 | if `KBLC&0x80`: `IANE(0xC5)` (kbd brightness down) | **0xC5 -> KEY_KBDILLUMDOWN** (mapped) |
| `_Q77` | 79816 | if `KBLC&0x80`: `IANE(0xC4)` (kbd brightness up) | **0xC4 -> KEY_KBDILLUMUP** (mapped) |
| `_QD6` | 79829 | not dissected | open |
| `_QB5`,`_Q18`,`_Q17`,`_Q22`,`_Q31`,`_QAF`,`_Q8A`,`_QB8`,`_QDA` | 79838-79890 | not dissected | open |
| `_Q7A` | 81139 | if `VIUF==1`: `Notify(RP12.PXSX, 0x81)` (dGPU info change) | GPU hotplug/info **[proven code]** |
| `_QA8` | 81148 | toggles `NPCF.DBAC/DBDC` by `DB2F`, notify `NPCF 0xC0` | NVIDIA dynamic boost |
| `_QA9` | 81166 | `FGA9=0`, sleep 6 s, `Notify(RP12.PXSX, 0)` bus check | dGPU bus re-scan |
| `_QBC` | 81174 | `DNOT(NVDX)` if `UMFG != 1` | dGPU notify |

Also in `dsdt.dsl`: `_Q3F` sets `ATKP`-gated `IANE` calls only if `ATKP` is 1; `ATKP` is set by WMNB
`INIT` (`ATKD.INIT`, 77239-77241), which Linux `asus-wmi` calls at probe. **[proven]**

### 1.3 Sleep / dGPU power path (`VGAT`, `VIUF`)

- `dsdt`/`ssdt15.dsl` (dGPU `_ON` path): `VGAT = 1` set on init (`ssdt15.dsl:2245`) and cleared at the
  end of `_OFF` (`ssdt15.dsl:2314`). **[proven]**
- dGPU `_OFF` (`ssdt15.dsl` around 2255-2312): reads EC `VIUF` into `Local0` (line 2261). For NVIDIA
  (`VEND==0x10DE`) with `HGMD==2` and dGPU not in `TDGC` GC6 mode, it calls `POFF()` **only if
  `Local0 == 0`**; if `VIUF==1` the rail is left powered. **[proven code]**
- Meaning of `VIUF` (EC-set "VGA in use" flag) is **[inferred]**: when the EC reports the dGPU is in
  use, ACPI skips the power-off. A stuck `VIUF=1` during suspend would be a plausible cause of the
  overnight drain (see ../findings/03-standby-s0ix-and-wake-timeline.md). This is a lead to verify, not a finding.
- `GC6S` (EC bit, 75858) is never read by ACPI; the GC6 decision is in SSDT code via `TDGC/TGPC`
  instead **[inferred]**.

---

## 2. Battery `BAT1` and AC adapter

- `Device (BAT1)` at `dsdt.dsl:74602`. Legacy ACPI 1.0 battery: `_BIF`, `_BST`, `_BTP` only. **No
  `_BIX`** (no extended cycle/health info in ACPI). **[proven]**
- `_STA` returns 0x1F when `BP` (battery present flag set by `CHBP`, 74864) is 1, else 0x0F.
  **[proven]**
- `UPBI()` (74725ish) fills `PBIF` from EC fields `MDCP`, `MBCP`, `MBDV`; **model name is hard-coded
  to `"A32-K55"`, chemistry `"LiON"`, manufacturer `"ASUS "`**. **[proven]**
- `UPBS()` fills `PBST` from `MBCT` (current, signed), `MBVT` (voltage), `RCAP` (remaining). **[proven]**
- `_BTP` writes `BTPL/BTPH` in EC (74681-74700). **[proven]**
- Cycle count: `CYCL` (EC RAM, 16 b) exists but is **not read by any ACPI method**, so the standard
  path never reports it. Sysfs `cycle_count = 0` is therefore a placeholder, not a measurement.
  **[proven]**
- AC adapter `ACAD`: `_PSR` path via `ACIN`/`NOAC` (EC). Sysfs `online=1`. **[proven]**

### 2.1 Charge-limit mechanism

- ACPI does not implement a charge limit. The Linux `charge_control_end_threshold` path is
  `asus-wmi` DEVID `ASUS_WMI_DEVID_RSOC = 0x00120057` (`asus-wmi.h:123`); the setter is
  `asus-wmi.c:1600-1670` (`asus_wmi_set_devstate(RSOC, value)`), and the probe
  `asus_wmi_battery_init()` (`asus-wmi.c:1698-1704`) registers a battery hook only if RSOC is present.
  **[proven]**
- `0x00120057` has **no explicit dispatch in the DSDT WMNB** (grep count 0 in the DSTS/DEVS blocks),
  so it falls through `WCHK()` (`dsdt.dsl:78370` for DSTS, `78935` for DEVS) into the SMI path
  (`W15H` / `WSCP=0xAA`, `dsdt.dsl:78958`, ASMI at 79517). Therefore the limit is implemented in
  **SMM firmware**, not ACPI. **[proven fallthrough, inferred SMM implementation]**
- Live: `BAT1/charge_control_end_threshold = 80`; `asusd.ron` also has
  `charge_control_end_threshold: 80` (`/etc/asusd/asusd.ron`). `charge_full = 4,825,000 uWh`,
  `charge_full_design = 5,650,000 uWh` -> **85.4 % of design capacity**. `capacity = 96`, `status =
  Not charging`, `current_now = 0`: the battery is being held at the threshold, which matches the
  limit. **[proven]**

---

## 3. ASUS ATK WMI device (`ATKD`, PNP0C14 `_UID "ATK"`)

- `Device (ATKD)` at `dsdt.dsl:77142`. Two WDG GUIDs (`_WDG` at 77218 and 78973 for the second
  device `UAT2`). The ASUS management GUID is `97845ED0-4E6D-11DE-8A39-0800200C9A66` (first bytes
  `D0 5E 84 97`). **[proven]**
- `WMNB` (77346-78952): methods dispatched by method ID (`INIT`, `BSTS`, `SFUN`, `SCDG`, `VERS`,
  `MWGF`, `GLCD`, `WDOG`, `OSVR`, `ANVI`, `DSTS`, `DEVS`). `DSTS` branch at 77406, `DEVS` branch at
  78386. **[proven]**
- `ATKQ` event queue, `IANQ`/`GANQ`/`IANE` (77195-77215); `IANE` notifies `ATKD 0xFF` (Hardware-
  Specific) and Linux `asus-wmi` reads the queue with `GANQ` via `_WED(0xFF)` (77204-ish). **[proven]**

### 3.1 DSTS (device status) IDs implemented in ACPI

The DSTS branch dispatches on these IDs (raw list; `WCHK` fallthrough handles any others):

```
0x00010031 0x00030022 0x00040017 0x00040019 0x0004001A 0x00050001 0x00050013 0x0005001A
0x0005001C 0x0005001D 0x0005001E 0x0005001F 0x00050024 0x00050025 0x00050026 0x0005002E
0x00050031 0x00050032 0x00050033 0x00050035 0x00050036 0x0005003A 0x0005003B 0x00050043
0x00050051 0x00060023 0x00060024 0x00060025 0x00060026 0x00060059 0x0006005B 0x0006005C
0x0006005D 0x00060061 0x00060064 0x0006006A 0x0006006B 0x00060077 0x00060091 0x00060093
0x00060095 0x000600B1 0x000600B2 0x000600C1 0x000600C2 0x000600C3 0x00080041
0x00080042 0x00080043 0x00090014 0x00090016 0x00090017 0x00090018 0x00090019 0x0009001A
0x0009001C 0x0009001D 0x00090020 0x00090021 0x00090029 0x00090030 0x00090040 0x00090041
0x00100021 0x00100043 0x00100046 0x00100051 0x00100052 0x00100053 0x00100054 0x0010005A
0x0010005B 0x0010005C 0x00100066 0x00110011 0x00110013 0x00110014 0x00110015 0x00110016
0x00110018 0x0011001B 0x0011001C 0x0011001D 0x0011001E 0x00110021 0x00110024 0x00110025
0x00110026 0x00110027 0x00110028 0x00110029 0x00110031 0x00110032 0x00110033 0x00120000
0x00120058 0x0012005A 0x0012005B 0x00120063 0x00120065 0x00120067 0x0012006C 0x00120070
0x00120072 0x00120076 0x00120077 0x00120079 0x0012007B 0x00120081 0x00120082 0x00120083
0x00120087 0x00120088 0x00120089 0x00120090 0x00120091 0x00120092 0x00120093 0x00120094
0x00120095 0x00120096 0x00120097 0x00120098 0x00120099 0x001200A0 0x001200A1 0x001200A2
0x001200A3 0x001200B0 0x001200B1 0x001200C0 0x001200C1 0x001200C2 0x001200C3 0x001200D1
0x001200D2 0x001200D3 0x001200D4 0x001200E1 0x001200E2 0x00130014 0x00130021 0x00130022
0x00130023 0x00130025 0x00130026 0x00130031 0x00130041 0xA0000001 0xC0400000 0xC0400001
```

(The list is the union of `IIA0 == 0x...` comparisons between the DSTS and DEVS markers; a few
entries such as `0x00060097` appear only in the DEVS block. Treat exact membership as approximate
to +/-1 ID; the table below covers everything Linux cares about.)

### 3.2 DEVS (device set) IDs implemented in ACPI

```
0x00010031 0x00030022 0x00040017 0x00040019 0x00050001 0x00050011 0x00050013 0x0005001A
0x0005001C 0x0005001D 0x0005001E 0x00050024 0x00050025 0x00050026 0x0005002E 0x00050031
0x00050032 0x00050035 0x00050036 0x00060023 0x00060026 0x00060064 0x00060091 0x00060095
0x00060097 0x000600C1 0x000600C2 0x000600C3 0x00090014 0x00090019 0x0009001A 0x0009001D
0x00090020 0x00090029 0x00090040 0x00090041 0x00100021 0x00100052 0x00100054 0x00100066
0x00110013 0x00110014 0x00110015 0x00110016 0x00110018 0x0011001C 0x0011001E 0x00110021
0x00110024 0x00110025 0x00110028 0x00110031 0x00110032 0x00120000 0x00120058 0x0012005B
0x00120070 0x00120072 0x00120073 0x00120074 0x00120076 0x0012007B 0x00120089 0x00120092
0x00120095 0x00120098 0x001200A0 0x001200A1 0x001200A2 0x001200A3 0x001200B0 0x001200B1
0x001200C0 0x001200C1 0x001200C2 0x001200E1 0x001200E2 0x00130014 0x00130022 0x00130025
0xC0400000 0xC0400001
```

### 3.3 Feature-by-feature comparison with Linux

Legend: "DSDT" = what the ACPI code does for that DEVID. "Fallthrough" = not dispatched in ACPI, so
the call reaches SMM via `WCHK` (`dsdt.dsl:78370/78935`). Live values from sysfs.

| Function (Linux name) | DEVID | BIOS (DSDT) behaviour | Linux exposure on this unit | Live value |
|---|---|---|---|---|
| Fan curve CPU/GPU/mid | 0x110024 / 0x110025 / 0x110032 (+0x110026/27/33 levels) | Implemented: `CFCV`/`GFCV`/`SFCV`/`CFLB`/`GFLB`/`SFLB` in EC (78032-78092) | `asus_custom_fan_curve` hwmon (hwmon6) | curves read below |
| Fan control CPU/GPU | 0x110013 / 0x110014 | returns `Local0`/`Zero` | hwmon `asus` pwm1/2 | `pwm1_enable=2` (cached), `pwm2_enable=0`, `pwm3_enable=0` |
| Mid fan | 0x110031 | implemented (`Local0`) | hwmon `asus` fan3 | `fan3_input=3700` |
| Fan boost mode | 0x110018 | 0xFFFFFFFE (unsupported) | none | - |
| Throttle thermal policy (platform_profile) | 0x120075 | **not dispatched** -> fallthrough | `throttle_thermal_policy` + `platform_profile` | 0 = balanced; profile `balanced` (choices quiet/balanced/performance) |
| PPT PL1 SPL | 0x1200A3 | present (`0x10000`) | `firmware-attributes/ppt_pl1_spl`, legacy `asus-nb-wmi/ppt_pl1_spl` | **90 W** (min 28, max 90) |
| PPT PL2 SPPT | 0x1200A0 | present | `ppt_pl2_sppt` | **135 W** (min 28, max 135) |
| PPT PL3 FPPT | 0x1200C1 | present (`0x10000`) | legacy `ppt_fppt` only (no firmware-attributes node) | legacy shows 5 (cached, see caveat) |
| PPT APU SPPT | 0x1200B0 | 0xFFFFFFFE | absent | - |
| PPT platform SPPT | 0x1200B1 | 0xFFFFFFFE | absent | - |
| NVIDIA dynamic boost | 0x1200C0 | present | `nv_dynamic_boost` | **20 W** (min 5, max 20, default 20) |
| NVIDIA temp target | 0x1200C2 | present | `nv_temp_target` | **87 C** (min 75, max 87, default 87) |
| NVIDIA TGP (additional) | 0x120098 | from `NPCF.ACBT` | not exposed (no `nv_tgp` node) | - |
| NVIDIA base TGP | 0x120099 | from `NPCF` | not exposed | - |
| dGPU power state (D0/D3) | 0x120097 | 0xFFFFFFFE | absent | - |
| dGPU disable | 0x090020 | returns `0x00010001` (`CUMA`) | `dgpu_disable` | **0** (enabled) |
| GPU MUX (hybrid/dGPU) | 0x090016 | returns `DGPM` | `gpu_mux_mode` | **1** = Optimus/hybrid (armoury: 1 = optimus) |
| eGPU | 0x090018 / 0x090019 | 0xFFFFFFFE | absent | - |
| Mini-LED | 0x05001E / 0x05002E | returns 0 (not present) | absent | - |
| Panel overdrive | 0x050019 | **not dispatched** -> fallthrough (SMM) | `panel_overdrive` | **1** |
| Panel HD/FHD mode | 0x05001C | 0xFFFFFFFE | absent | - |
| Screen auto brightness | 0x05002A | not dispatched | absent | - |
| ALS (ambient light) | 0x050001 | 0xFFFFFFFE | absent | - |
| LightBar / ScreenPad | 0x050025 / 0x050031-2 | 0xFFFFFFFE | absent | - |
| Boot POST sound | 0x130022 | present (`W15H`) | `boot_sound` | **0** (off) |
| Charge mode (barrel/USB) | 0x12006C | `PDSS` (`dsdt.dsl:78147`) | `charge_mode` (read-only) | **1** (labelled "Barrel" in driver comment) |
| Charge limit (RSOC) | 0x120057 | **not dispatched** -> SMM fallthrough | `charge_control_end_threshold` | **80** |
| MCU powersave | 0x1200E2 | returns 0 (not present) | absent | - (Ally-only quirk in driver anyway) |
| Keyboard backlight | 0x050021 | **not dispatched** -> SMM fallthrough; KBLS (`0x10005B`) returns EC buffer | LED `asus::kbd_backlight` (asus-wmi `kbd_led`, `asus-wmi.c:2163`) | **3 / max 3** |
| Keyboard RGB/aura (TUF/ROG mode) | 0x10005A | 0xFFFFFFFE | absent (only TUF RGB path in driver) | - |
| Lid flip (ROG) | 0x060077 | 0xFFFFFFFE | absent | - |
| Mic mute LED | 0x040017 | 0xFFFFFFFE | not exposed | - |

Firmware attributes present on this unit (`/sys/class/firmware-attributes/asus-armoury/attributes`):
`boot_sound, charge_mode, dgpu_disable, gpu_mux_mode, nv_dynamic_boost, nv_temp_target,
panel_overdrive, pending_reboot, ppt_pl1_spl, ppt_pl2_sppt`. Notably **absent**: `mcu_powersave`,
`egpu_enable`, `dgpu_power_state`, `mini_led_mode`, `panel_hd_mode`, `screen_auto_brightness`,
`nv_tgp`, `nv_base_tgp`, `ppt_pl3_fppt`, `ppt_apu_sppt`, `ppt_platform_sppt`. Each absence matches a
DSDT return of 0 / 0xFFFFFFFE, except `ppt_pl3_fppt` (DSDT says present) and `nv_tgp`/`nv_base_tgp`
(cause not determined). **[proven]** for the sysfs state; the mapping to DSDT returns is **[proven]**
where stated above.

**Caveat on legacy `asus-nb-wmi` nodes.** `/sys/devices/platform/asus-nb-wmi/ppt_pl1_spl`,
`ppt_pl2_sppt`, `nv_dynamic_boost`, `ppt_fppt` return the driver's cached `asus->...` values
(`asus-wmi.c:1268-1277`, `1448-1456`) and they are marked deprecated (`asus_wmi_show_deprecated`).
They read **5** while the armoury nodes read 90/135/20. Use the `firmware-attributes` values; treat
the legacy ones as unreliable. **[proven]**

### 3.4 Live fan / thermal snapshot

- `hwmon5 (asus)`: `cpu_fan=1700 RPM`, `gpu_fan=1700 RPM`, `mid_fan=3700 RPM`.
- `hwmon6 (asus_custom_fan_curve)` curves (temp C / pwm), point 1..8, mostly points 6-8 duplicated:
  - CPU (pwm1): 62/17, 67/30, 72/40, 74/71, 76/81, 80/130, 80/130, 80/130
  - GPU (pwm2): 58/12, 62/12, 67/25, 69/30, 72/81, 78/104, 78/104, 78/104
  - Mid (pwm3): 62/20, 67/48, 72/48, 74/86, 76/142, 80/198, 80/198, 80/198
- `acpitz temp1 = 44.0 C`.
- `pwm*_enable` values are the cached driver mode (`asus-wmi.c:3129-3146`: "Just read back the
  cached pwm mode"), so `pwm1_enable=2` is not a firmware readback. **[proven]**

---

## 4. Keyboard backlight and hotkeys

### 4.1 USB devices (`0b05:*`) and drivers

| USB ID | sysfs product | HID bind | Linux quirk | Notes |
|---|---|---|---|---|
| `0b05:19b6` (3-6) | "ITE Device(8910)" | `0003:0B05:19B6.0001` -> **`asus`** (hid-asus) | `USB_DEVICE_ID_ASUSTEK_ROG_NKEY_KEYBOARD2` with `QUIRK_USE_KBD_BACKLIGHT \| QUIRK_ROG_NKEY_KEYBOARD \| QUIRK_HID_FN_LOCK` (`hid-asus.c:1821-1822`, `hid-ids.h:230`) | Main keyboard; hid-asus provides Fn-lock and backlight quirk. **[proven]** |
| `0b05:193b` (3-8) | "ITE Device(8910)" | `0003:0B05:193B.0002` -> **`hid-generic`** | none (ID not in `hid-ids.h`) | Second USB interface, most likely the Aura/lighting controller; no Linux driver. **[inferred]** |

- `/etc/modprobe.d/...`: `options asus_wmi fnlock_default=N`. **[proven]**
- The keyboard-backlight LED `asus::kbd_backlight` is registered by **asus-wmi** (under
  `asus-nb-wmi`, `asus-wmi.c:2163`), using DEVID `0x00050021` via DSTS/DEVS. Since 0x50021 is not
  dispatched in the DSDT, the value comes from SMM through `WCHK`. **[proven fallthrough; inferred SMM]**

### 4.2 Hotkey path (EC -> ATKD -> Linux keymap)

1. EC query method (e.g. `_Q77`, `_Q21`) runs `ATKD.IANE(code)` (ATKD `IANE` at 77211) when `ATKP`.
2. `IANE` pushes the code to `ATKQ` and notifies `ATKD 0xFF`; Linux reads it with `GANQ`.
3. `asus-wmi` looks it up in `asus-nb-wmi.c` keymap (`610-691`).

Mapping of codes actually sent by the EC on this board:

| Code | Source query | Keymap | Effect in Linux |
|---|---|---|---|
| 0x7C | `_Q21` | `KEY_MICMUTE` (650) | mic-mute key works |
| 0xC4 | `_Q77` | `KEY_KBDILLUMUP` (682) | keyboard brightness up |
| 0xC5 | `_Q76` | `KEY_KBDILLUMDOWN` (683) | keyboard brightness down |
| 0x6E | `_Q84`,`_QBA`,`_QB9` | `KE_IGNORE` (645) | - |
| 0x57,0x58,0xCF,0x7B | `_Q3F`,`_QD7`,`_QD8` | `KE_IGNORE` (630,631,687,649) | - |
| **0x4F** | `_Q2E`,`_QA6` | **no entry** | ignored (unknown code) |
| **0xE5** | `_QAE`,`_QB4`,`_QDB` | **no entry** | ignored (unknown code) |
| **0x68** | `_QDC` | **no entry** | ignored (unknown code) |

Open question: what Fn/hotkey the EC means by 0x4F, 0xE5 and 0x68. They are not in the keymap, so
Linux drops them silently. No "unknown key" messages appear in this boot's kernel log (filtered
journal), but the kernel logs unknown codes only at debug level, so absence is not proof.

---

## 5. Standby, wake and power-related EC/WMI items

- Sleep: `/sys/power/mem_sleep = [s2idle] deep`. The machine is on s2idle. **[proven]**
- EC module parameters (`/sys/module/acpi/parameters`): `ec_no_wakeup=N`, `ec_freeze_events=N`,
  `ec_busy_polling=N`, `ec_event_clearing=query`, `ec_delay=500`, `ec_polling_guard=550`,
  `ec_storm_threshold=8`, `ec_max_queries=16`. Defaults; nothing non-standard. **[proven]**
- Lid wake: `LID0._PRW` = `GPRW(0, 0x20)` (`dsdt.dsl:74891`). **[proven]**
- EC GPE `0x6E` is the EC's own GPE (`_GPE`, 75612), and it is also the code used for "low battery"
  (IANE 0x6E). **[proven]**
- **MCU powersave** (`mcu_powersave`, `ASUS_WMI_DEVID_MCU_POWERSAVE = 0x001200E2`): the DSDT returns 0
  for DSTS (`dsdt.dsl:78327`), so the BIOS does not advertise it on this unit, and the attribute is
  absent. The Linux driver only uses it for ASUS ROG Ally (`asus-wmi.c:1521-1530`). **Not applicable.**
  **[proven]**
- EC flags for standby that exist but are **not used by ACPI**: `S3LW`, `WOLN`, `RTCF`, `SHBS`,
  `WLRY`, `GC6S`, `S4UM`, `DPFL`. Any real use is in EC or SMM firmware. **[inferred]**
- Battery-level policy in EC: `_QB6` toggles NVIDIA dynamic-boost flags based on `RSOC > 50`
  (76532-76545; `SPAB`, 81675). **[proven]**
- `_QE6` (dGPU wake/info sequence with 500 ms sleeps, 76591) and `_QA9` (6 s bus-check delay,
  81166) are the EC-driven dGPU resume paths. **[proven code]**
- Overnight drain hypothesis (inferred, not measured): the dGPU `_OFF` path (ssdt15, `VIUF`) can leave
  the NVIDIA rail powered if EC `VIUF` is 1 at suspend. Confirm by reading EC `VIUF` in a controlled
  test (needs root debugfs `ec`, which was not available for this read-only pass).

---

## 6. Recommended settings (no changes made)

Battery and standby:

1. **Keep `charge_control_end_threshold = 80`** (already set via asusd). Health is 85.4 %; a limit of
   80 is the right trade-off for a daily-plugged machine.
2. **Keep `platform_profile = quiet` on battery** (asusd already does this:
   `platform_profile_on_battery: Quiet`, `change_platform_profile_on_battery: true`). Quiet also
   reduces fan curves' high end.
3. **Keep `gpu_mux_mode = 1` (hybrid)** on battery. dGPU mode (0) forces the NVIDIA GPU to stay
   active. `dgpu_disable` is already 0 (enabled, but the dGPU should be in D3cold when idle).
4. Lower `nv_dynamic_boost` on battery (20 W -> 5-10 W) if the dGPU is used on battery. Does nothing
   for standby power.
5. Do **not** try `mcu_powersave`: the firmware does not advertise it on this unit.

Performance (AC):

6. `ppt_pl1_spl=90`, `ppt_pl2_sppt=135` are firmware maximums, so they are already full power.
   `nv_temp_target` max is 87 C.
7. Fan curves are firmware-stored (EC `CFCV/GFCV/SFCV`); the custom curves above are what the driver
   wrote. Compare with Windows Armoury Crate curves before tuning.

Keyboard:

8. `fnlock_default=N` is set. The hid-asus `QUIRK_HID_FN_LOCK` is active; no action needed.
9. Consider mapping 0x4F / 0xE5 / 0x68 only after identifying them (see §4.2). Upstream would need a
   keymap entry in `asus-nb-wmi.c`.

## 7. Open questions

1. Live EC RAM values (`VIUF`, `VGAT`, `GC6S`, `CYCL`, `KBLC`, `LIDS`, `RSOC`) need root debugfs
   (`/sys/kernel/debug/ec/ec0/io`). Not read. Reading `CYCL` (ERAM offset ~0xE2) would give a real
   cycle count.
2. Meaning of EC events 0x4F, 0xE5 and 0x68 (Fn keys? thermal mode? Armoury?). Check Windows
   ASUS software events or a `WMI` event dump.
3. Why `ppt_pl3_fppt` (DSDT says present) and `nv_tgp`/`nv_base_tgp` are missing from
   firmware-attributes on this unit. Check the `asus-armoury` limit table for this DMI product.
4. `hid 0b05:193b` has no driver. Identify its function (lighting?) with `hid` descriptor dump.
5. `_Q76`, `_Q77`, `_QD6`, `_QB5`, `_Q18`, `_Q17`, `_Q22`, `_Q31`, `_QAF`, `_Q8A`, `_QB8`, `_QDA` and
   the `_QA8`/`_QBC` paths were not fully traced.
6. The kernel tag (7.3.3) may differ from the master source used here; re-check the asus-armoury
   attribute list against the running tree before editing anything.
