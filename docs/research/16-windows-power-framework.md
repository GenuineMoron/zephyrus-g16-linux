# 16 - How Windows manages power on the GU605MI, and Linux replications

Scope: read-only audit of the offline Windows install (SYSTEM hive, DriverStore, decompiled ACPI DSL, Power Efficiency Diagnostics XML). No privileged writes. Decoded helper scripts (decode.py, opts2.py, ppm_values.txt) are a local working copy, not in the repo.
Labels: [proven] = read directly from the files; [inferred] = reasoning or a mapping not confirmed by Windows docs; [unverified] = needs a live test.
Privacy: user names, computer name, battery serial/ID and app paths were deliberately left out.

## 1. Windows power policy (SYSTEM hive, ControlSet001\Control\Power)

Active scheme: `User\PowerSchemes\ActivePowerScheme` = 381b4222-f694-41f0-9685-ff5bb260df2e = **Balanced**. [proven]
Other schemes present: 8c5e7fda = High performance, a1841308 = Power saver, e9a42b02 = Ultimate Performance, plus OEM GUIDs (961cc777, ded574b5, 3af9b8d9) [names of OEM ones unverified].

Effective values for the Balanced scheme (override if the scheme has one, otherwise the default), AC / DC: [proven, names from PowerSettings FriendlyName resources in powrprof.dll]
- Sleep after: 10800 s (3 h) / 180 s (3 min) [override]
- Hibernate after (9d7815a6): 0 / 0 (never)
- Allow hybrid sleep: 1 / 1; Allow wake timers: 1 / 0; Allow standby states: 1 / 1; System unattended sleep timeout: 120 / 120
- Turn off display after: 300 / 180 s; Dim after: 585 / 285 s; Display brightness 100 / 100
- Lid close action: 1 (Sleep) / 1; Power button: 3 (Shut down) / 3; Critical battery action: 2 (Hibernate)
- Link State Power Management (PCIe ASPM, ee12f906): **0 (off) on AC / 2 (max savings) on DC** [override, proven]
- Processor performance boost mode (be337238): 3 / 3 [override; value 3 = "efficient enabled" by the usual enum, inferred]
- Processor EPP (36687f9e-...c863, default): **33 AC / 50 DC** (per-class copies c864/c865 same)
- Minimum processor state (893dee8e): 5 / 5 %; Maximum processor state (bc5038f7): 100 / 100 %
- Core parking min cores (0cc5b647): **100 % AC / 10 % DC**; max cores 100 / 100
- Processor performance boost policy (45bcc044): 60 / 40; increase threshold 60 / 90; decrease threshold 20 / 30
- Heterogeneous policy in effect (7f2f5cfa): 4 / 4; Heterogeneous thread scheduling policy (93b8b6dc): 5 / 5; short-running variant (bae08b81): 5 / 5; hetero containment policy (60fbe21b): 1 / 1 [raw values; meanings [unverified]]
- System cooling policy (94d3a615): **1 (active) AC / 0 (passive) DC**
- Presence-aware / Standby budget (8619b916 group): Standby budget percent 5 % DC; standby reserve time 1200 s DC; standby budget grace 900 s DC; reserve grace 300 s DC; reset percentage 75 % DC; no AC budget [proven]
- Connectivity in standby (f15576e8): options Disable(0) / Enable(1) / Managed by Windows(2); no override in Balanced, so the default applies. [default unknown; "Managed by Windows" likely, inferred]
- Disconnected standby (68afb2d9): options Normal(0) / Aggressive(1); no override in Balanced [inferred default Normal]
- Energy saver: Charge level threshold 30 % DC; Energy saver policy 1 DC.
- Root values: HiberbootEnabled = 0 (**Fast Startup off**) [proven, Session Manager\Power]; HibernateEnabledDefault = 1; ModernSleep\EnabledActions = 7; EnergyEstimationEnabled = 1.
- CsEnabled is not present in this hive copy, so Modern Standby cannot be confirmed from the hive alone. The energy reports (below) say Connected Standby is supported and S4 is the only supported sleep state (S1/S2/S3 false). [proven from reports]

Session Manager\Power AcPolicy / DcPolicy / *ProcessorPolicy are SYSTEM_POWER_POLICY / PROCESSOR_POWER_POLICY binary blobs. Not fully decoded. The processor part duplicates the scheme values above.

## 2. Intel DTT / DPTF / IPF on Windows

Services (ControlSet001\Services, Start value) [proven]:
- intelpep (Intel Power Engine Plug-in) Start=0 (boot). Binds ACPI\INT33A1, INT33A5, INT3396, INT33A4 (intelpep.inf). Matches DSDT PEPD (INT33A1).
- ipf_acpi (IPF ACPI, binds ACPI\INTC1042 = IETM manager, INTC1041, 1046, 1048, 1049, 1060, 1061, plus INTC1062-1067 and INTC10A0-10A5) Start=3 (demand).
- ipf_cpu / ipf_lf: Start=3; binds PCI\VEN_8086 DEV_7D03 (MTL) and others (dtt_ext/ipf_cpu INF).
- ipfsvc (Intel Innovation Platform Framework user service, ipfsvc.exe) Start=2 (auto).
- dptftcs Start=2 (auto).
- intelppm (Processor Power Management driver) Start=3; intelpmax, ThermalFilter Start=3.
- MPTFThermalPolicy binds ACPI\MSFT000E (Windows thermal policy); no service entry in this hive export.

Driver packages in DriverStore\FileRepository [proven]:
- dtt_sw: Dptf.dll, dptftcs.dll, DptfPolicy*.dll (PowerBoss, PowerShare, Passive/Passive2, Critical, Active/Active2, AdaptivePerformance, ApplicationOptimizer, EnergyPerformanceOptimizer, IntelligentThermalManagement, Pid, Rfim, SystemConfiguration, ThirdPartyGraphics, VirtualSensor). Device IDs SWC\VID8086_DTT_1.0 and DTTCFG.
- dtt_ext: "Intel(R) Dynamic Tuning Technology Extension" for PCI 8086:7D03 (MTL) and 7D03/AD03 variants.
- configuration\*.config (apo, dtt, epo, itm, rfim, systemconfiguration, vs2) are **encrypted** (no readable policy, high entropy). [proven] Thresholds cannot be read offline.
- ipf_cpu\ppm.dv (241 KB) and dsp.dv (504 KB) are DataVault containers with plaintext keys. ppm.dv holds the PPM tables used below. [proven]
- ACPI GDDV (ssdt11.dsl, PLDT.GDDV): a 0x654-byte "OEM Exported DataVault" blob. Header readable, body entropy 7.8 bits/byte, so it is **encrypted**. [proven]

### 2a. ACPI side (ssdt10 = "DptfTb", ssdt11 = PLDT, dsdt = PEPD/TCPU) [proven]
- Device \_SB.IETM, HID from PLDT.GHID("IETM") = INTC1042. Has _TRT, _ART, PSVT, GDDV (returns PLDT.GDDV), _DSM.
- _TRT (ssdt11, TRT0): TCPU -> SEN2 influence 0x28 (40), CHRG -> SEN4 influence 0x14 (20).
- _ART (ART0/ART1): active cooling table, TFN1 fan cools TCPU, steps 0x64/0x50/0x3C/0x28/0x1E/0x14.
- PSVT: CHRG cooled by SEN3, passive limit entry with "MAX".
- FPS0: fan performance states (0x64 ... with 0x2EE0 / 0x01F4 / 0x1388 fields). Field meaning [inferred: percent, power/noise, speed].
- TCPU NPCC (_PPCC, revision 2) entry index 0 (PL1): 0x88B8 = 35000 mW, 0xAFC8 = 45000 mW, 0x6D60 = 28000 mW, 0x7D00 = 32000 mW, 0x03E8 = 1000 ms [field order inferred]. Entry index 1 (PL2): 0xDBBA = 56250 mW. These do not match the ASUS armoury PL ranges (PL1 28..90 W, PL2 28..135 W) and are presumably Intel defaults. [inferred]

### 2b. Intel PEP device constraints (DSDT PEPD DEVY, UPDV, UPDE) [proven]
- The DEVY table has 120 slots. At boot all 120 are "Reserved.Reserved.Reserved.Reserved" with constraint 0xFF,0,0x81.
- UPDV() fills DEVY at runtime through UPDE(path, name, enable, constraint). Constraint index: 0 = D0 (PCP0), 1 = D0F1 (PCP1), 2 = D2 (PCP2), 3 = D3 (PCP3). Enable is gated by bits of the variable PEPC.
- Devices gated by PEPC (enable only when bit set): SAT0, GFX0 (0x8000), UA00-UA02, I2C0-I2C7, SPI0-SPI2, XHCI (0x4000), PEMC, PSDC, IPU0 (0x20000), HECI (0x40000), THC0/THC1, GNA0 (0x800000), VMD0 (0x1000000), HEC3, PUF0/PUF1, VPU0.
- Always listed with constraint 3 (D3) regardless of enable: GLAN, CNVW, TXHC/TXDC, TRP0-3 and TDM0/1 (Thunderbolt/USB4 root ports, enable bits TRE*/DME*), HDAS (GUCP bits), and the USB HID 0AC9 MI* entry.
- [inferred] A device with enable=1 and constraint 3 is one PEP may hold in D3 when the platform idles; enable=0 removes that requirement. Exact PEP semantics not confirmed from Microsoft docs.
- Linux (wave-1 note 01 and drivers/acpi/x86/s2idle.c): calls LPS0 Intel fn 3/5/6/4 and MS fn 7/8. It does NOT call Intel fn 1 (constraints) directly; constraints go through the LPI path. So Linux does not replicate the per-device D-state constraint list, and it cannot be easily reproduced without the UPDV logic and the PEPC value.

### 2c. Windows idle-state view (energy report, Processor Power Management Capabilities) [proven]
- 22 logical processors in 3 classes by nominal frequency: 2300 MHz (indices 0,1,10-19), 1800 MHz (indices 2-9, probably the E-cores), 2500 MHz (indices 20,21, probably LP-E). Class-to-Linux-CPU mapping is [inferred].
- 11 idle states per processor, idle state type "Micro Power Engine Plugin" (PEP), performance control "ACPI Collaborative Processor Performance Control" (CPPC).

### 2d. Intel PPM gears and per-P-state EPP (ipf_cpu\ppm.dv, MTL Mobile) [proven, decoded]
Binary records: path string + type(3=DWORD) + size + value. Parsed all /MTL/Platform/Mobile/PPMSettings values (ppm_values.txt; local working copy, not in the repo).

PPMSettings P1..P11 (P1 = highest performance). EPP is 0-100 percent [inferred scale; Windows EPP percent maps to HWP 0-255]:
| P-state | AC EPP core / atom | DC EPP | AC CPMin atom | DC CPMin atom | AC SoftPark |
|---|---|---|---|---|---|
| P1 | 25 | 25 | 4 | 100 | 1000 |
| P2 | 33 | 33 | 4 | 4 | 1000 |
| P3 | 40 | 40 | 4 | 4 | 1000 |
| P4 | 45 | 45 | 4 | 4 | 1000 |
| P5 | 50 | 50 | 4 | 4 | 0 |
| P6 | 55 | 55 | 4 | 4 | 0 |
| P7 | 60 | 60 | 4 | 4 | 0 |
| P8 | 70 | 70 | 4 | 4 | 0 |
| P9 | 80 | 80 | 4 | 4 | 0 |
| P10 | 85 | 85 | 4 | 4 | 0 |
| P11 | 90 | 90 | 4 | 4 | 0 |

Gear groups (MTL Mobile): AC/Balanced (default gear 1, enabled), AC/Collaboration (default gear 1, disabled), DC/BetterPerf (default gear 3, enabled), DC/EnduranceGaming (default gear 0, enabled). Gear entries map workload classes to a P-state: Bli = bursty light, Bur = burst, Sus = sustained, FgGt1/FgLte1 = foreground graphics condition. Examples:
- AC/Balanced gear 1: Bli -> P5 (EPP 50), Bur -> P2 (EPP 33), Sus -> P5 (EPP 50).
- AC/Balanced gear 5: Bli -> P8 (70), Bur -> P5 (50), Sus -> P8 (70).
- DC/BetterPerf gear 1: Bli -> P7 (60), Bur -> P3 (40), Sus -> P7 (60). DC/BetterPerf gear 3: Sus -> P8 (70).
Mapping of gears to the ASUS Quiet/Balanced/Performance modes is [unverified]. Probably the Armoury/Windows profile selects a gear group, and DTT picks the gear dynamically.

Linux comparison [proven current state, from wave-1 note 07]: AC EPP = balance_power on all policies. Linux balance_power is roughly 75 % on the 0-100 scale (0xC0 = 192/255), far less performance-leaning than Windows AC Balanced (33-50). Linux Quiet profile sets EPP = power (100 %) on battery, while Windows DC BetterPerf uses 60-70.

## 3. Energy reports (Windows Power Efficiency Diagnostics) [proven]
Location: ProgramData\Microsoft\Windows\Power Efficiency Diagnostics\energy-report-2026-06-01..06-20.xml plus energy-report-latest.xml (21 reports). Aggregated across reports:
- Power plan Balanced; plan personality 2 on AC and on battery; video quality bias on battery 1, plugged in 0.
- **PCI Express ASPM disabled (plugged in), Error severity, all 21 reports.** Matches the AC=0 override.
- 802.11 radio power policy: maximum performance (plugged in).
- Platform timer resolution: current 15.6 ms; many 1 ms (10000 x 100 ns) requests from browsers, a game-streaming app, Steam and an AI desktop client. Outstanding 1 ms requests recorded in 53 log entries. [proven]
- System Availability Requests: Steam "System Required" request 89 times between 06-03 and 06-14 (blocks sleep). Also one Windows Update preview process execution request. [proven]
- Sleep timeout long (plugged in) warning: 10800 s.
- Supported sleep states: S4 only among S1-S4; Connected Standby supported; ASPM disabled.
- CPU utilization: average 1.3-2.5 % on quiet days; "high" (17 %) on at least one day.
- Battery: design capacity 90005 mWh, last full charge 79252 mWh = 88 %. Linux sysfs (wave-1 note 07) reads 85.4 % (charge_full 4825000 / design 5650000 uWh). The two methods disagree; both come from the same EC. [proven values; disagreement noted]
- Device driver error: an Android ADB interface with a problem code (cosmetic, ignore).
- Latest report (06-20 onward) has analysis errors for CPU/USB/Power capabilities: the analysis stopped working after 06-14 (Analysis Failure/Error entries).

Not parsed: SleepStudy ETL traces (C:\Windows\System32\SleepStudy\*.etl, including an abnormal-shutdown trace dated 2026-06-21). These need an ETL parser (tracerpt on Windows, or a Linux ETL reader). Not attempted here.

## 4. thermald (research only, not installed)
Source checked: github.com/intel/thermal_daemon (README/release notes, fetched online). [proven from fetched page]
- Default since 2.3: "tries --adaptive and fallback to old style". --adaptive requires kernel 5.8+.
- Release notes say adaptive mode is "not expected to be on par with Windows DPTF".
- The page does not state which ACPI tables it reads (DPTF/_PSV/_TRT/PPCC), and does not describe a built-in thermal-conf.xml. It does not mention conflicts with intel_lpmd, asusd or PPD.
- It can disable active power limits with --disable-active-power, so it can be turned into a passive-only daemon.

Assessment [inferred]: Windows DTT policy values are encrypted (configuration\*.config, GDDV). Only the plaintext PPCC/TRT/ART/PSVT tables are readable, and thermald adaptive would not reproduce the PPM gear logic. The ASUS platform profile already drives PL and fan curves, so a second PL writer would conflict with asusd. Do not install thermald. If thermal throttling becomes a problem, measure first (turbostat/ intel_pmt or thermal_zone trip points).

## 5. Ranked recommendations and experiments
1. EPP per power source (highest value, cheap to test). Measure Windows-like EPP on AC: try balance_performance (~50 %) instead of balance_power (~75 %), and compare responsiveness and sustained performance on a 5-minute build or benchmark. On battery, compare Quiet's power (100 %) with ~60-70 % (Windows DC BetterPerf). Caveat: the EPP percent mapping is inferred. Confirm with turbostat (Bzy_MHz, PkgWatt) before changing the default. Owner: asusd profile mapping (wave-1 note 07).
2. PCIe ASPM by power source. Windows disables ASPM on AC and uses max savings on DC. This laptop forces powersupersave on both (kernel cmdline in note 07). Test pcie_aspm.policy=default on AC: check NVMe/Wi-Fi errors in journal and idle package power on AC before and after. Do not change on battery until AC result is clear.
3. Standby / hibernate timing. Windows: sleep after 3 h on AC, 3 min on DC, hibernate never, and a 5 %/refresh standby budget on DC. Linux already has SuspendEstimationSec=1h and a 30-cs35l56 hibernate hook (wave-1 findings). Candidate: set systemd HibernateDelaySec on battery (about 30-60 min) to match the Windows budget idea, after the overnight drain is measured (open issue; see ../findings/03-standby-s0ix-and-wake-timeline.md).
4. Inhibitors. Windows shows Steam "System Required" blocking sleep 89 times. Check systemd inhibitors during a game session (systemd-inhibit --list) and make sure the Linux game launcher does not keep the system awake without need.
5. Timer resolution. Many 1 ms timer requests on Windows (browsers, streaming, Steam). On Linux, check timer-driven wakeups with powertop --time or perf sched; reduce only after measuring.
6. P/E scheduling hints. Windows AC core parking min cores = 100 % and atom min = 4 %; SoftPark latency 1000 at P1-P4 only. Linux: intel_lpmd lp_mode_cpus is empty (note 07). Test whether LP-E cores (20,21) are used under light load (mpstat per CPU). Heterogeneous policy values (4/5) need a Windows doc check before copying.
7. thermald: do not install. Re-evaluate only if measured throttling appears under asusd profiles.

## 6. Open questions / tools wanted
- Meaning of Windows heterogeneous policy (7f2f5cfa=4, 93b8b6dc=5) and boost mode (be337238=3): find the powrprof.dll resource tables for the option strings (needs a PE resource parser; pefile not installed) or the PowerSettings option subkeys (only partly present).
- Mapping between ASUS Armoury/Windows profiles and DTT gear groups (needs Armoury Crate config from ASUS app AppData; not read here).
- DPTF PL values actually applied (PPCC field order) and GDDV decryption (likely impossible offline).
- SleepStudy ETL parse for top standby drain offenders on Windows (needs tracerpt or an ETL reader on Linux). Would show whether Windows drained at all in standby on this hardware.
- Tools wanted: pefile (Python, PE resources), an ETL reader (etl-parser or tracerpt), turbostat (for EPP experiments), powertop --time for wakeup attribution.

## Sources
- /mnt/win/os/Windows/System32/config/SYSTEM (exported to cs1_power.reg, sm_power.reg, intelpep.reg, intelppm.reg; local working copy, not in the repo)
- /mnt/win/os/Windows/System32/powrprof.dll (setting names via FriendlyName resources)
- /mnt/win/os/Windows/System32/DriverStore/FileRepository/{dtt_sw,dtt_ext,ipf_acpi,ipf_cpu,ipf_ef_*,intelpep,mptfthermalpolicy}*
- /mnt/win/os/ProgramData/Microsoft/Windows/Power Efficiency Diagnostics/energy-report-*.xml
- Decompiled ACPI tables {dsdt.dsl, ssdt10.dsl, ssdt11.dsl} (local working copy, not in the repo)
- Wave-1 notes: 01, 03, 07 in this directory and ../findings/03-standby-s0ix-and-wake-timeline.md
- thermald: github.com/intel/thermal_daemon (fetched 2026-11-14)
