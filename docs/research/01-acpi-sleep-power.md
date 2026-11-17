# 01 - ACPI / BIOS sleep and power-state logic (ROG Zephyrus G16 GU605MI, BIOS 329)

Scope: decompiled tables in ~/.local/src/acpi-tables/ (dsdt.dsl, ssdt1..24.dsl), Linux sources fetched from torvalds/linux master (drivers/acpi/osl.c, drivers/acpi/x86/s2idle.c, drivers/acpi/acpica/exoparg1.c, kernel/time/tick-sched.c, tick-common.c, timekeeping.c). Runtime evidence from read-only dmesg/journal, /sys/power/mem_sleep, /proc/acpi/wakeup, /proc/cmdline, /proc/config.gz.

Caveats: Linux sources were fetched from `master`, not the exact 7.3 tag. The kernel in use is CachyOS 7.3.x. Line numbers in the DSL are from `grep -n`/`sed -n` on the files as they exist now. Items marked **[inferred]** are reasoning, not measurement.

---

## 1. _PTS, _WAK, _Sx packages

**Sx packages** (dsdt.dsl 6008-6034): `_S0`=0,0,0,0; `_S3`=0x05; `_S4`=0x06; `_S5`=0x07. There is no `_S1`/`_S2`.

**_PTS(Arg0)** (dsdt.dsl 6036-6046) calls, in order, if Arg0 != 0:
- `XPTS` (dsdt.dsl 81780): empty.
- `\_SB.PC00.LPCB.LPTS` (dsdt.dsl 5793-5801): sets `SLPX=1`, `SLPE=1` (ACPI PM1 control via SystemIO SLPR), and if `PWBT` then `PBEN=1`.
- `\_SB.TPM.TPTS`: TPM pre-sleep (not analysed further).
- `\_SB.PC00.MC.NPTS` (dsdt.dsl 6723-6740): copies the MC PM0..PM6 power-management shadow registers into PA* shadows, then PACP/PAAC.
- `RPTS` (dsdt.dsl 28720-28783): the main entry method.
  - `D8XH(0, Arg0)`, `D8XH(1, 0)`: writes to POST port 0x80 (debug only).
  - For Arg0 == 4 (S4 hibernate) or 5 (S5 poweroff): `EC0.PLEA = 0`.
  - For Arg0 == 4 or 5 **and** `PG3S == 1` and `H_EC` present: `PGWD(ACWA, DCWA, ACET, DCET)` then `PGCL()` (EC-based PG3 power-gating writes). This is the only S4/S5-specific branch seen; it is state dependent (PG3S, PCHS) and was not analysed further.
  - `\_SB.TPM.PTS` (if present), then `SPTS(Arg0)` (ssdt22.dsl 1142-1156): Thunderbolt TCON/TG0N/TG1N when TRTD/ITRT.
  - PFLV==2/ECON==1 prints only (no action).
- No `Sleep()` or `Stall()` on the _PTS path.

**_WAK(Arg0)** (dsdt.dsl 6048-6054): `RWAK` (dsdt.dsl 28886), `MC.NWAK` (6742), `LPCB.LWAK` (dsdt.dsl 5803-5811: `SLPE=0`; if PBEN then `PWBT=1`, `PBEN=0`), `XWAK` (81784, empty), returns AM00.
- `RWAK`: `D8XH(1,0xAB)`; `RPWM` = 0 or 0x180 from DSTS; `SWAK(Arg0, RPWM)` (ssdt22.dsl 1159: NHPG/NPME if NEXP; Bus-check notifies for RP01 etc. on Arg0 3/4); `ACCF(ACTT)` on S3; GFX0 IUEH notifies if GBSX bits; `LPCB.SWUB`.
- No time-dependent delays on the _WAK path were found.

**SMI port 0xB2 (APMC)**: `OperationRegion (WSMI, SystemIO, 0xB2, 2)` at dsdt.dsl ~79503-79508 (WSCP/WSSP). `WISM` writes WSCP under MMTX. `ASMI` (dsdt.dsl 79517-79522) sets ALPR and writes `WSCP = EXSI (0xAB)` -> SMI. Callers are `MWGF` (dsdt 80165-80186) and ANVI (dsdt ~77330). **None are on the S0ix or _PTS/_WAK path.** QSMI=0xB8 (ssdt24.dsl 357) is set by `MXDM` (Type-C/display mux, not sleep). **[inferred]** EC commands 0x97/0x98 used by the LPS0 DSM (below) may cause EC-side firmware work, but no SMI is directly triggered from the sleep path in the AML.

**Sleep()/Stall() on suspend-related AML**: none in _PTS/_WAK/PEPD. The large delays found are elsewhere (see section 5).

---

## 2. Low Power S0 / Modern Standby: \_SB.PEPD (INT33A1)

- `Device (PEPD)` at dsdt.dsl 50516. `_HID "INT33A1"`, `_CID PNP0D80`, `_STA` = 0x0F only when `S0ID==1`.
- `_DSM` at dsdt.dsl ~52899-53110 (the `_DSM` within PEPD).

### Function-0 masks (what the BIOS advertises)

| UUID | Function 0 buffer | Mask | Functions advertised |
|---|---|---|---|
| Microsoft 11e00d56-... (dsdt 52902-52910) | `0x81, 0x01` | 0x181 | 0, 7, 8 |
| Intel c4eb40a0-... (dsdt 52953-52960) | `0x7F` | 0x7F | 0-6 |

Confirmed in dmesg: `ACPI: \_SB_.PEPD: Duplicate LPS0 _DSM functions (mask: 0x1)` (only bit 0 overlaps; harmless warning).

### Function semantics on this BIOS

**Microsoft UUID**
- Fn 7 (MS entry, dsdt ~52915-52931): if PFLV==2 && ECON==1 && PPOE==1 -> `LPCB.NRTS(0)` (NRTS not analysed).
- Fn 8 (MS exit): same guard -> `LPCB.NRTS(1)`.
- Fn 0 is the only other valid call. Fns 3/4/5/6/9 are not advertised by this UUID.

**Intel UUID** (dsdt.dsl ~52953-53110)
- Fn 1 (device constraints): returns DEVY, after `UPDV()` once (IPDI guard). Only if S0ID==1.
- Fn 2 (BCCD): returns BCCD (empty package).
- Fn 3 = **screen off** (~52995-53010): `IMNG(3)` (if present), D8XH, `MSDF = 0`, **`EC0.ECMD(0x97)`**.
- Fn 4 = **screen on** (~53011-53020): `IMNG(4)`, D8XH, `MSDF = 1`, `EC0.GOSS = 0` if GPP8==0 && GPP9==1.
- Fn 5 = **deep standby entry** (ASUS log text "[PEP] deep standby entry", ~53021-53058): `GUAM(1)` if S0ID, `FMAE` -> `MNMS=1`, `D9FG=1`, **`EC0.ECMD(0x98)`**, sets `PC00.DPOF=1` if TDM0/TDM1 monitors off (Thunderbolt/USB4 DPOF), **`GPRV(0x03, 0)` "allow PS_ON"**.
- Fn 6 = **deep standby exit** (~53059-53075): `GUAM(0)`, `PC00.DPOF=0`, **`GPRV(0x03, 1)` "veto PS_ON"**.
- Returns Buffer(1){0}.

Line numbers for Fn 3/4 are approximate (±10) because I read them from a window of the dsdt; the grep hits for GUAM/GPRV are exact (53031, 53076, 53086, 53097).

### What Linux calls (drivers/acpi/x86/s2idle.c)

- Constants: ACPI_LPS0_SCREEN_OFF=3, SCREEN_ON=4, ENTRY=5, EXIT=6, MS_ENTRY=7, MS_EXIT=8, MS_TURN_ON_DISPLAY=9 (lines 134-141).
- `acpi_sleep_run_lps0_dsm()` (line 466) only runs a function if its bit is set in the relevant mask.
- prepare_late (lines 627-665): Intel 3 (screen off) -> MS 7 (MS entry) -> Intel 5 (entry). MS 3 and MS 5 skipped (bits absent).
- restore_early (lines 686-720): Intel 6 (exit) -> MS 6 (absent, skipped) -> MS 8 (MS exit) -> MS 9 (absent, skipped) -> Intel 4 (screen on).
- Linux never calls Intel fn 1 directly here (constraints go through the LPI path, lpi_device_get_constraints), and never calls Intel fn 2 (BCCD).

**Observed dmesg (journal, boot 2026-11-14, 18:17:46 and 18:26:20)** matches the code exactly:
`screen off` -> `lps0 ms entry` -> `lps0 entry` -> [suspended] -> `ACPI fixed event wakeup` -> `lps0 exit` -> `lps0 ms exit` -> `screen on`. All transitions reported as successful.

### Windows vs Linux differences

- Linux covers every function this BIOS advertises except Intel fn 1 (constraints, via LPI) and fn 2 (BCCD). **[inferred]** Windows' PEP driver most likely queries fn 1/2 (constraints/BCCD) and may issue them more often; the AML for fn 2 is only a static return, so there is no behavioural effect for Linux to miss.
- MS fn 9 ("turn on display") is **not advertised** by this BIOS (mask bit 9 clear), so Windows should not call it either; this is not a gap.
- Fn 7/8 are called by both. What NRTS does (LPCB.NRTS, not yet read) is the one piece of Windows-vs-Linux behaviour I have not confirmed.

---

## 3. Lid, power button, sleep button, wake GPEs

- **LID0** (`Device (LID0)`, dsdt.dsl 74888-~74915): `_HID PNP0C0D`. `_LID` returns !LIDS from EC0 (MUT0 locked). `_PRW = GPRW(0x00, 0x20)`.
- **EC query _Q2F** (dsdt.dsl 79794-79797): `Notify (LID0, 0x80)`. This is the lid-change path from EC. DUMY lid logic (dsdt 28262-28292, 28564-28583) also notifies LID0 on resume.
- **PWRB** (`Device (PWRB)` dsdt.dsl 80837, `PNP0C0C`): no `_PRW`, so the power button is a fixed-feature event (FADT).
- **SLPB** (dsdt.dsl 29576, `PNP0C0E`): no `_PRW`, fixed-feature.
- **GPRW** (dsdt.dsl 29288-29306) picks the deepest S-state from SS1..SS4 (dsdt.dsl 3838-3841: SS1=0, SS2=0, SS3=1, SS4=1). Result: all wake-capable devices get S4 as their deepest wake state. LID0 (arg 0x20) also resolves to S4 via FindSetLeftBit.
- **EC GPE = 0x6E** (dmesg: `ACPI: EC: GPE=0x6e`).

**Runtime (/proc/acpi/wakeup)**: every device is `*disabled` except **LID0 (`*enabled`)**. The dGPU PXSX/RP12 is disabled. So the only ACPI-level wake source currently armed is the lid. Power button and RTC (alarmtimer) are separate, not in this list.

**Other GPE handlers of note**: `_E50`/`_E51` (dsdt.dsl 80849-80867) notify RP12.PXSX (0x81) and call `ATKD.IANE(0xC0)`. The _PRW GPEs for PXSX are 0xC0/0xC1/0xC2/0xC7 plus 0x69 (dsdt.dsl 20992-26857).

**[inferred]** s2idle wake on this machine: "ACPI fixed event wakeup" is the reason logged at both resumes in the journal, so the wake came through the fixed-event path (power button or RTC-based); the lid was not the trigger in those two tests.

---

## 4. ASUS quirks: UMFG, HGMD, PDOD, WOFF, and the RP12 PXP power resource

### RP12 scope and PXP power resource (ssdt15.dsl)
- `Scope (\_SB.PC00.RP12)` at ssdt15.dsl 2020. Names: `WAKG` (2107 area), `WOFF` (2111), `LNRD` (2112), `SCLK`=6, `PWRG`, `RSTG`.
- `PowerResource (PXP)` at 2154. `_STA` 2157-2168. `_ON` at 2171, `_OFF` at 2250.
- `_ON` (2171-2245): guard `If (\UMFG != One)` (2173). If `HGMD==2` and VEND==10DE (NVIDIA): `If (PXP._STA() != 0)` ... `PON()`, `L23D()`, `CMDR |= 7`, `D0ST=0`, then **`While (PXSX.VEID != 0x10DE) { Sleep(1) }`** (no timeout) ~2191-2195, then LREN/CEDR/NVID.
- `_OFF` (2250-~2300): NVIDIA path does `DL23()` then `POFF()` (when not TDGC) plus GC6I.

### PON / POFF (ssdt15.dsl 2395-2480)
`PON` (2395):
1. `CEMP(1)` if present; `SHPO(WAKG,1)`/`CAGS` if WAKG.
2. `PSD0(SLOT)` if PRTP==2.
3. Inside `If (PWRG)`:
   - **WOFF residual sleep (2418-2426):** `Local0 = (Timer - WOFF)/0x2710` (ms). `If (Local0 < PDOD) Sleep(PDOD - Local0)`; then `WOFF = 0`.
   - `PIN.ON(PWRG)`.
   - **`If (HGMD==2 && VEND in {10DE,1002}) Sleep(P0DL)`** (2433-2435) else `Sleep(PEP0)`.
4. `SPCO(SCLK,1)` if SCLK present.
5. `PIN.OFF(RSTG)`, then **`Sleep(0x64)` = 100 ms, unconditional** (end of PON, ~2448).

`POFF` (2452-2480):
- `Local1 = LNRD/1000; Sleep(Local1)` (LNRD = latency, set by `UPRD()` at ssdt15.dsl 2506-2512, bounded to 0x2710 us; callers are the _DSM methods at dsdt.dsl 20862 etc.).
- `PIN.ON(RSTG)`, PSD3 for PRTP==2, `SPCO(SCLK,0)`, `PIN.OFF(PWRG)` if GPPR==1.
- **`WOFF = Timer` (2476)**.

### Where the values come from
- **PDOD** is `PDOD,16` in the GNVS field (dsdt.dsl 3045, inside the field starting at 1419). It is never written in the AML (only External declarations), so the value is set by firmware in the ACPI NVS page at boot.
  - I computed the layout from the field list: **PDOD = GNVS + 0xB6F (16-bit LE)**; PEP0 = GNVS + 0x70; PFLV = +0x5C; S0ID = +0x73; RTD3 = +0x6F; ECON = +0x40; PPOE = +0x858. GNVS total computed = 0xDA6, matching OperationRegion(GNVS, SystemMemory, 0x45BFD000, 0x0DA7). The computation is therefore self-consistent.
  - Physical address: **0x45BFDB6F** (PDOD), 0x45BFD070 (PEP0). Reading it requires root (/dev/mem is root:kmem 0640; /sys/firmware/acpi/tables is root-only). I did NOT read it.
- **P0DL** is in the TPNV region (dsdt.dsl 3822, base `TPNB` at 3799), not GNVS. Its runtime address was not determined.
- **WOFF** is set only in POFF (2476) and cleared in PON. Its effect is limited to the first PON after a POFF.
- **UMFG** is an EC field (dsdt.dsl 75571, `EXBU` field 75528). Set to 1 on dGPU-unplug (76442, 81176), cleared at 78920. Should be 0 on this machine (dGPU present); not read.

### Timer semantics (the key question)
- `Timer` opcode -> `acpi_ex_opcode_0A_0T_1R` case `AML_TIMER_OP` (drivers/acpi/acpica/exoparg1.c lines 63-69) -> `acpi_os_get_timer()`.
- **drivers/acpi/osl.c 661-665 (master):**
  ```c
  u64 acpi_os_get_timer(void)
  {
      return (get_jiffies_64() - INITIAL_JIFFIES) *
          (ACPI_100NSEC_PER_SEC / HZ);
  }
  ```
  So the AML Timer is **jiffies-based**, not ktime/boottime. With CONFIG_HZ=1000 (confirmed in /proc/config.gz), each tick is 10000 units = 1 ms, so `/0x2710` yields ms at 1 ms granularity.
- **Jiffies and suspend (kernel/time/tick-sched.c:57-100, tick_do_update_jiffies64(now))**: jiffies advances from `now` supplied by the tick code, which is `ktime_get()` (CLOCK_MONOTONIC) (tick-sched.c 308, 1219, 1409, 1472; 757 tick_nohz_update_jiffies; 1034 tick_nohz_restart_sched_tick).
- **CLOCK_MONOTONIC excludes suspend (kernel/time/timekeeping.c ~2113-2126)**: `__timekeeping_inject_sleeptime()` does `tk_xtime_add(delta)` and `tk_set_wall_to_mono(wall_to_monotonic - delta)`, so monotonic is unchanged; the sleep is added to `offs_boot` (tk_update_sleep_time) -> CLOCK_BOOTTIME only.
- `tick_freeze()` (tick-common.c 519+) suspends the tick and timekeeping during s2idle.

**Conclusion (code-level, not measured):** on Linux s2idle, `Timer` does not advance during the suspended interval. `Timer - WOFF` counts only active time since the GPU was powered off, so the WOFF residual `Sleep(PDOD - Local0)` is computed as if almost no time passed, even when the GPU was off for minutes. This matches the observed "171 ms every resume" if PDOD is large relative to pre-suspend active time.

**Is it a Linux bug?** Not proven. The ACPI spec wording on whether Timer() counts during sleep states was not verified (search returned only the 2013 patch "ACPI: implement acpi_os_get_timer() according the spec" by Mika Westerberg, which used ktime_get(); current master uses jiffies, so the implementation has changed since). The firmware's intent ("time since rail was turned off") clearly assumes the suspended interval counts, so there is a semantic mismatch. Whether that's a Linux bug or a firmware assumption depends on the spec and on what Windows' Timer does; neither was confirmed.

### Alternative explanation for the 171 ms (important)
The NVIDIA path **always** runs `Sleep(P0DL)` (2433-2435) regardless of WOFF, and PON always adds `Sleep(0x64)` (100 ms) at the end. A constant 171 ms per resume is at least as consistent with `P0DL` (+100 ms tail) as with the WOFF residual, which only varies with pre-suspend active time. **Do not attribute the 171 ms to WOFF until it is separated from P0DL.**

---

## 5. Other sleep-path delays, busy waits, and wake sources

- **Unbounded poll** in PXP `_ON` (ssdt15.dsl ~2195): `While (PXSX.VEID != 0x10DE) Sleep(1)`. Can hang if the GPU never answers config reads after power-on.
- **PON fixed tail** `Sleep(0x64)` (100 ms, ~2448) on every PON.
- **EC query _QA9** (dsdt.dsl ~81150-81160): `FGA9 = 0; Sleep(0x1770)` (6000 ms) then `Notify (RP12.PXSX, Bus Check)`. Blocks the EC query handler for 6 s. Triggered by EC query 0xA9 (dGPU-related, FGA9 set in the unplug path). Not yet correlated with resume.
- **EC query _QBC** (dsdt.dsl ~81170): `If (UMFG != 1) DNOT(NVDX)`.
- **ASRT** (dsdt.dsl 6980-7001): assert handler, infinite loop with 60 s Sleep. Only if called; no evidence it is hit.
- **RPTS PG3 path** (dsdt.dsl ~28731-28752): EC PGWD/PGCL for S4/S5 when PG3S==1. Potential S4/S5 delay; not timed.
- **Wake GPEs**: LID0 (GPE 0x00, S4 max), XHCI 0x6D/0x89/0x6B, HDAS 0x8A/0x6B, GLAN 0x86/0x6B, CNVW 0x85/0x6B, I3C0 0x8E/0x6B, AWAC 0x72, PXSX 0xC0-0xC7/0x69, RP01-RP07 various (dsdt 73386-73470). /proc/acpi/wakeup shows all of these disabled except LID0.
- **Thunderbolt** (SPTS/SWAK, TDM0/TDM1 DPOF) is set by LPS0 fn 5 and cleared by fn 6.

---

## Proven vs inferred

**Proven (code/log):**
- LPS0 call sequence on Linux matches the BIOS mask (dmesg + s2idle.c + PEPD _DSM).
- Timer = jiffies-based (osl.c 661-665). Monotonic clock excludes suspend (timekeeping.c). So Timer does not count the s2idle interval (code proof; not measured).
- WOFF set in POFF (2476), read in PON (2418-2426), and reset in PON.
- PON always runs Sleep(P0DL or PEP0) and Sleep(100 ms).
- PDOD is at GNVS+0xB6F (layout computed; value not read).
- Only LID0 is armed as an ACPI wake device (/proc/acpi/wakeup).

**Inferred:**
- The 171 ms is P0DL (+ the 100 ms tail) rather than the WOFF residual, or a mix.
- Windows queries LPS0 fn 1/2 more often than Linux (not confirmed).
- The jiffies/Timer behaviour is a Linux-vs-firmware semantic mismatch, not a clear Linux bug.

## Recommended actions / experiments (all read-only or run manually)

1. **Read PDOD and PEP0 (root, read-only):** `sudo dd if=/dev/mem bs=1 skip=$((0x45BFDB6F)) count=2 2>/dev/null | xxd` (PDOD), and `skip=$((0x45BFD070)) count=1` (PEP0). Run this manually as root.
2. **Split the 171 ms:** ftrace/bpftrace on `acpi_*` is a write to tracing state, so it has to be run manually. Alternatively compare resume latency when the GPU is powered off immediately before suspend vs after 5-10 s of active time. If the delay tracks the active time, it is the WOFF residual; if it stays constant, it is P0DL.
3. **Prove the clock semantics:** run a small read-only script before and after a short s2idle: print `time.clock_gettime(time.CLOCK_MONOTONIC)` and `time.clock_gettime(time.CLOCK_BOOTTIME)`. Expect monotonic to exclude the suspended interval and boottime to include it. This is the kernel behaviour Timer inherits via jiffies.
4. **Hardware reference:** the ACPI PM timer is at I/O port 0x1808 (dmesg: `ACPI: PM-Timer IO Port: 0x1808`). Reading it across a suspend (needs root) would show whether a hardware counter keeps running in S0ix. **[inferred]** it probably does, which would make the jiffies-based Timer the odd one out.
5. **Upstream check:** verify `acpi_os_get_timer()` in the exact 7.3 tag and search lore.kernel.org for "acpi_os_get_timer jiffies suspend" before filing anything. Do not file a bug until (2) and (4) are measured.
6. **Remove the P0DL/WOFF ambiguity in AML:** a DSDT/SSDT override changing `Timer` to a boottime-based value would be a firmware-level fix and needs its own review; out of scope here.

## Open questions

- Runtime value of PDOD, P0DL (TPNV base), and PEP0.
- What `LPCB.NRTS` does (MS fn 7/8 target) and whether it matters for S0ix residency.
- Whether the 6 s EC query _QA9 fires during resume on this machine.
- Whether the "ACPI fixed event wakeup" at resume is the power button, the RTC alarm, or a PCH GPE.
- ACPI spec definition of Timer() across sleep states.
- Whether the unbounded VEID poll in PXP `_ON` ever spins in practice.
