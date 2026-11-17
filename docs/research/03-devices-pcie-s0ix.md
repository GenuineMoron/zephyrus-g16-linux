# 03 - Device-level ACPI power objects, PCIe/VMD/NVMe, TCSS, and S0ix blockers

Scope: read-only. No writes to /sys, /proc, or pmc_core. Sources: decompiled tables in
~/.local/src/acpi-tables/ (dsdt.dsl, ssdt1-24.dsl), live sysfs and debugfs reads,
kernel-side VMD source at /usr/src/vmd-mtl016-7.3.1/vmd.c, S0ixSelftestTool script.

Tags: [proven] = read from a file or live value during this pass. [inferred] = reasoning from code,
not measured. [unverified] = needs a source or a measurement not yet done.

## 1. Root ports and dGPU (RP12 -> PXSX)

- RP12 device: dsdt.dsl:5992 (`_ADR 0x00010000`, `_PRT` only; no power methods here). [proven]
- RP12 scope with power logic: ssdt15.dsl:2020 `Scope (\_SB.PC00.RP12)`.
  - `_S0W` ssdt15.dsl:2113-2127: returns 4 if `RD3C == 2`, 3 if `RD3C == 1`, else 0. This is the deepest
    D-state allowed while the system is in S0. [proven, logic]
  - `RD3C` value for RP12: not resolved in these tables (only `External` at dsdt.dsl:677-ish and
    ssdt15.dsl:177). Root ports in dsdt use `Name (RD3C, 0x02)` pattern at dsdt.dsl:20739 etc. for other
    slots, so RP12 likely 2 (D3cold). [inferred]
  - `_DSW` ssdt15.dsl:2130-2152 sets `WKEN`.
  - `_PR0`/`_PR3` ssdt15.dsl:2494 and 2502: both return `Package { PXP }`. Same power resource for D0 and D3hot. [proven]
- Power resource `PXP`: ssdt15.dsl:2154.
  - `_STA` 2156-2168: checks VDID, `GPRS(2)`, `PSTA()` (reset-pin state).
  - `_ON` ~2170-2231: branch for NVIDIA (`VEND == 0x10DE`) with `HGMD == 2`. Non-GC6 path calls `PON()`,
    `L23D()`, `CMDR |= 7`, then polls `PXSX.VEID == 0x10DE` with `Sleep(1)` (ssdt15.dsl:2207-2210).
    Sets `RP12.LREN` from `PXSX.LTRE`, `CEDR=1`, `PXSX.NVID = HYSS`. GC6 path (TDGC==1) calls `PXSX.GC6O()`.
  - `_OFF` ~2241-2300: NVIDIA path calls `DL23()`, then `POFF()` only if `Local0 == 0`; GC6 path calls `GC6I()`.
- `PON()` / `POFF()` (ssdt15.dsl ~2340-2505, RP12 scope):
  - PON: optional wait `PDOD - elapsed` (`Sleep`), `PIN.ON(PWRG)`, then `Sleep(P0DL)` if NVIDIA/AMD+HGMD==2, else `Sleep(PEP0)`, then `PIN.OFF(RSTG)` (reset deassert), then `Sleep(0x64)` = 100 ms. [proven]
  - POFF: `Sleep(LNRD/1000)` (LNRD from `UPRD`, set by ssdt15 `UPRD` method), `PIN.ON(RSTG)` (reset assert), `PIN.OFF(PWRG)` if `GPPR()`.
  - Timing values `P0DL`, `PEP0`, `PDOD` are `External` only (ssdt15.dsl:618, 632, 165). Their values are not in these tables. [unverified]
- `_PRW` RP12: dsdt.dsl:73549 `Scope (_SB.PC00.RP12)`. Uses `GPRW(GGPE(P3WG|P4WG|P7WG), 4)` if the wake
  pin config matches, else `GPRW(0xC7, 4)`. [proven]
- Live (sysfs, read-only): 0000:00:01.0 (RP12) `pcieport`, `power/control=auto`, runtime suspended,
  `d3cold_allowed=1`, wakeup disabled. 0000:01:00.0 (dGPU) runtime suspended, `d3cold_allowed=1`. [proven]
  I did not read the dGPU config space, since that can wake it.

Other root ports (RP01-RP11) have `_PRW` at dsdt.dsl:73382-73530. RP01 uses `P1WG`/`P1RN`; RP02-RP11 use GPE 0xC0 with S4.
RP04 (0000:00:1c.0) hosts the RTS5250 SD reader at 0000:2c:00.0 (`RP04.PXSX`), `rtsx_pci`, runtime suspended. [proven]

## 2. NVMe, VMD, and StorageD3

- VMD0: dsdt.dsl:69796, `_ADR 0x000E0000`.
  - `StorageD3Enable` (`_DSD` UUID 5025030f-...) is only added when `VDSD == 1` (dsdt.dsl:69806-69815).
    `VDSD` value not resolved here. [unverified]
  - `_PS0` / `_PS3` (dsdt.dsl ~69818-69845): toggle `ISAT` (LTR-ignore bit for SATA) when `VMS0 != 0`. [proven]
- Child root ports under VMD0: SP01-SP12, dsdt.dsl:69869-71706. The NVMe slot is SP11 (dsdt.dsl:71539).
  - SP11 has its own `VPON`, `VPOF`, `RL23`, `RLA` methods (`Sleep(0x0A)`, `Sleep(0x64)`, `Sleep(0x10)`).
  - SP11 has no `_PRW`, `_S0W`, `_PR0`, `_PR3`, or `StorageD3Enable` inside its block (checked by grep over 71539-71706). [proven]
  - So no ACPI power resource is attached to the SSD path. This means D3cold for the SSD would be handled by
    the PCI core and VMD, not by ACPI `_PR3`.
- NVMe device: 10000:e1:00.0, WD PC SN5000S (`nvme0`, fw 34230100), `power/control=on`,
  `runtime_status=active`, `d3cold_allowed=1`, `power_state=D0`, `firmware_node` empty (no ACPI companion). [proven]
  - `power/control=on` means runtime PM is off for the SSD. [proven]
  - `nvme_core default_ps_max_latency_us=100000` (100 ms APST cap). [proven]
- VMD root port 10000:e0:06.2 (SP11): `power/control=auto`, `autosuspend_delay_ms=100`, runtime active. [proven]
- VMD controller 0000:00:0e.0 (`vmd`): `power/control=on`, runtime active, `d3cold_allowed=1`, not wake-capable. [proven]

### VMD driver (kernel side)
- Loaded module: /lib/modules/7.3.3-1-cachyos/updates/dkms/vmd.ko.zst, so the patched out-of-tree VMD is active. [proven]
- The patch (vmd-mtl016-dkms, commit 7307899e381c) adds the MTL016 MSI flush: `readw(vmdirq->flush_addr)`
  before demuxing (vmd.c ~796-804). [proven]
- `vmd_suspend` (vmd.c:1250) only frees IRQs. `vmd_resume` (vmd.c:1262) only re-enables MSI remap and
  re-requests IRQs. Neither touches D-states, LTR, or ACPI. Ops are `SIMPLE_DEV_PM_OPS` (vmd.c:1281). [proven]
- Device table: `0x7d0b` uses `VMD_FEATS_CLIENT | VMD_FEAT_INTERRUPT_QUIRK` (vmd.c:1300-1301). [proven]
- LTR default quirk (vmd.c ~912-944): only applies if BIOS left max-snoop LTR at zero, and sets
  `VMD_BIOS_PM_QUIRK_LTR` = 0x1003 = 3,145,728 ns (~3.1 ms). [proven, code]

### Linux NVMe suspend path (not verified against source)
- Source of `drivers/nvme/host/pci.c` is not in /usr/src. Fetching upstream v7.3 returned HTTP 429. [unverified]
- Expected from upstream: `nvme_suspend`/`nvme_resume` run `nvme_dev_disable`/reset; `NVME_QUIRK_SIMPLE_SUSPEND`
  and `pm_suspend_via_firmware()` decide whether the controller is fully shut down before s2idle; `acpi_storage_d3()`
  looks at the `StorageD3Enable` `_DSD` on the device's ACPI companion. [inferred]
- Because the SSD has no ACPI companion (`firmware_node` empty), `acpi_storage_d3()` should not find `StorageD3Enable`
  on the SSD itself. Whether it walks up to VMD0 is unverified. [inferred]
- `power/control=on` on the NVMe suggests the driver forbids runtime PM. That keeps the SSD in D0 while the
  system is awake. [inferred]
- Could the SSD block S0ix? The SSD sits on VMD, which is on the PCH side (PMC0). PMC0 `SATA_PGD0`/`VMD` entries
  in `substate_requirements` are `Required` for S0i2.2 and show `Yes` live. The SSD itself is not a named blocker
  in pmc_core. [inferred] The live data does not show the SSD as the blocker. The S0i2.2 blockers are PLL, XTAL,
  and IOE items (below).

## 3. Thunderbolt / USB4 / TCSS / IOE

- TXHC (TCSS xHCI, 0000:00:0d.0): ssdt14.dsl:814. `_PRW` ssdt14.dsl:87673. `usb4-host-interface` port
  properties SS01-SS04 at ssdt14.dsl:87797-88007. [proven]
- TDM0 (Thunderbolt, 0000:00:0d.2 `thunderbolt`): ssdt14.dsl:1638 (`_ADR 0x000D0002`), `_PS0` 1684, `_PS3` 1716,
  `_S0W` 1732, `_PR0` 1747. `_PRW` at ssdt14.dsl:88595. [proven]
- TCSS D3cold power resource `D3C` with `STAT` (default 1) at ssdt14.dsl ~780-800. Logs "TCSS D3C STAT". [proven]
- UBTC (USB Type-C connector) at ssdt19.dsl:88. [proven]
- Live: 0000:00:0d.2 TBT is runtime suspended with a 15 s autosuspend, not wake-capable. 0000:00:0d.0 TCSS xHCI is
  runtime suspended, `d3cold_allowed=1`. [proven]
- PMC1 (IOE die) status: `TCSS`, `IOE_D2D_*`, `TBTLSX_PGD0`, `TAM_PGD0` are on (PCH IP list).
  `IOE_D2D_PGD1_PG_STS` is Live=Yes. [proven]
- `IOE_COND_MET_S02I2_2_REQ_STS` (pmc0): S0i2.2 Required, Live blank (not met in the current state). [proven]
  Its meaning and what sets it are not in these tables. [unverified] Likely tied to TCSS/UBTC/IOE idle.

## 4. Wi-Fi, Bluetooth, audio, ISH, touchpad, camera

- Wi-Fi CNVW (0000:00:14.3, iwlwifi): dsdt.dsl:12447. `_PRW` = `GPRW(0x85,4)` if GP1E else `GPRW(0x6D,4)`. [proven]
  Live: `power/control=on`, runtime active, wake disabled.
- Bluetooth BTH0: dsdt.dsl:54714. Not checked further.
- Audio HDAS (0000:00:1f.3): dsdt.dsl:10294. `_PRW` `GPRW(0x8A,4)` if GP1E else `GPRW(0x6D,4)` (dsdt.dsl:10317).
  Live: `power/control=auto`, runtime active. [proven]
  CS35L56 amp `_DSD` (`cirrus,dev-index`, `cirrus,boost-type`) at dsdt.dsl:80941; the owning device was not confirmed
  (it is near ASUP at 80813). [unverified]
- ISH: device ISHD at dsdt.dsl:11175, `_HID` PNP0C02 (resources, not a real ISH device object). [proven]
  No live ISH device in sysfs.
- Touchpad: ASUP at dsdt.dsl:80813, `_HID` ASUS2018. [proven]
- Camera: IPU0 at dsdt.dsl:6650. Its `_HID` is ACPI000E (Time and Alarm), so this is not the camera. [proven]
  The camera sensor object was not located.
- LPS0 (`PEPD`, INT33A1 / PNP0D80): dsdt.dsl ~50512-50530. `_DSM` UUID c4eb40a0-6cd2-11e2-bcfd-0800200c9a66
  at dsdt.dsl:52953. Function 0 returns 0x7F. Function 3 (enter) calls IMNG, D8XH, and `EC ECMD(0x97)`. [proven]
- Wake sources: /proc/acpi/wakeup has only `LID0 S4 enabled`. `LID0` `_PRW` at dsdt.dsl:74891. [proven]
  XHCI, TBT, Wi-Fi, and iGPU are all wake-disabled.

## 5. pmc_core interpretation

### Residency (live)
- pmc0 S0i2.0 4,191,462; S0i2.1 65,783,620; S0i2.2 0.
- pmc1 S0i2.0 4,186,430; S0i2.1 65,783,803; S0i2.2 0.
- Package C-states (cumulative): C2 622M, C6 880M, C8 778M, C10 72.9M, C3 3.6M, C7 0, C9 0. [proven]

### S0i2.2-only requirements not met (Live blank; S0i2.1 `-`)
- pmc0: `AON5_OFF_STS`, `XTAL_LVM_OFF_STS`, `XTAL_AGGR_OFF_STS`, `FILTER_PLL_OFF_STS`, `SOC_PLL_OFF_STS`,
  `IMG_PLL_OFF_STS`, `IOE_COND_MET_S02I2_2_REQ_STS`.
- pmc1: `AON2_OFF_STS`, `XTAL_AGGR_OFF_STS`, `SOC_PLL_OFF_STS`.
- Met for S0i2.2 (Live Yes): pmc0 `UXD_CONNECTED_REQ_STS`, `PRE_WAKE2_EN_REQ_STS`, `AON2_OFF_STS`; pmc1 `AON5_OFF_STS`.
- These are the deepest-only gates (PLL/XTAL shutdown and IOE conditions). They are the likely S0i2.2 blockers. [inferred]

### Caveat on the Live column
- These readings were taken while awake. The S0ix tool (s0ix-selftest-tool.sh:180-245) uses `$(NF-1)` on the
  Live Status column after an S0ix cycle, so the Live column is what it reads. Blanks here mean "not in S0ix
  right now", not necessarily "blocking". The valid check needs a latched S0ix capture. [inferred]
- `lpm_latch_mode` currently reads `[S0i2.0]`; `substate_status_registers` latched value
  `PMC0:LPM_STATUS_0: 0x110031c1`. [proven]

### LTR (ltr_show)
- PMC0 IOE_PMC raw 0x8cac8cac: valid, scale 3 (32,768 ns), value 172 -> 5.64 ms (matches "5636096"). [proven decode]
  This is the largest valid LTR. It is a plausible S0i2.2 blocker, since IOE exit latency must fit under it. [inferred]
- PMC0 XHCI snoop raw 0x8bd0: ~1.0 ms (999,424 ns). [proven decode]
- PMC1 SOUTHPORT_E raw 0x10031003: 3.1 ms, not valid-bit-flagged in the display. [proven decode, owner unknown]
- PMC0 SOUTHPORT_A raw 0x0841: ~66.6 µs. The display showed 0 because the valid bit is clear. [proven decode]
- PMC1 AGGREGATED_SYSTEM 0x7ffffff: no requirement (max value). [proven decode]
- No LTR_IGNORE bits are set anywhere. The VMD `ISAT` toggle sets one for SATA only when `VMS0 != 0`. [proven]

## 6. Recommended experiments (safe first)

1. Read-only: capture `substate_requirements` Status and Live columns after a single s2idle cycle, using the
   S0ix tool's own latching procedure. Run it manually. This separates real blockers from awake-state noise.
2. Read-only: `nvme id-ctrl` and `nvme get-feature -f 0x0c` (APST table) to see the NVMe deepest PS and
   latency values. Do not run `nvme set-feature`.
3. Read-only: keep `dsdt.dsl` / `ssdt15.dsl` checks; resolve `P0DL`, `PEP0`, `PDOD`, `VDSD`, `RD3C`
   (RP12) by grepping the remaining tables (ssdt24 and ssdt19 were not fully searched).
4. Write experiment (manual, not run here): `ltr_ignore` for IOE_PMC (ltr_show index 25) to see whether
   the 5.6 ms LTR is what blocks S0i2.2. Revert after.
5. Write experiment (manual): unplug all Type-C and Thunderbolt devices before the S0ix test. This isolates the
   TCSS/IOE condition (`IOE_COND_MET_S02I2_2`).

## 7. Open questions

- What sets `IOE_COND_MET_S02I2_2_REQ_STS`, and is it tied to TCSS D3cold or UBTC?
- Values of `P0DL`, `PEP0`, `PDOD`, and whether RP12 `RD3C` is 2.
- Whether `acpi_storage_d3()` walks up from the SSD to VMD0 (NVMe upstream source needed).
- The LPIT residency counter addresses (lpit.dat, 204 bytes, 3 native LPI states; not decoded).
- Whether the camera sensor is under a different device than IPU0.
