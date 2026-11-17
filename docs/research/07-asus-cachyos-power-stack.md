# 07 - ASUS / CachyOS power and performance stack (GU605MI, read-only audit)

Date: 2026-11-14. Kernel 7.3.3-1-cachyos. All checks were read-only (pacman -Q, systemctl status/is-active, sysfs reads, asusctl/supergfxctl/powerprofilesctl GET commands, config reads, journalctl).

## 1. Inventory

| Component | State | Notes |
|---|---|---|
| asusd 6.5.0 (asusctl, rog-control-center 6.5.0) | active (asusd.service static, udev-triggered) | Config /etc/asusd/asusd.ron, fan_curves.ron |
| supergfxd 5.2.7 | enabled, running | mode Hybrid; `supergfxctl --status` = suspended (dGPU idle) |
| power-profiles-daemon 0.30-3 | installed, **masked** | Deliberate; see conflicts |
| intel_lpmd | enabled, running | Loaded /etc/intel_lpmd/intel_lpmd_config_F6_M170.xml (correct for Meteor Lake 185H) |
| ananicy-cpp 1.2.0 | enabled? (unit file enabled, active) | rules in /etc/ananicy.d (cachyos set) |
| cachyos-settings 1.4.4 | installed | sysctl 70-cachyos-settings.conf, udev 60-ioschedulers, 61-writeback-limits, 99-cpu-dma-latency, zram, THP |
| gamemode 1.8.2 | installed | custom ~/.config/gamemode.ini calls asusctl profile set |
| scx-scheds 1.1.4 | installed | scx_loader NOT installed/active, sched_ext disabled |
| tuned, tlp, auto-cpufreq, thermald, irqbalance, cpupower | not installed / inactive | No conflict from these |
| asus-shutdown.service | disabled | udev 99-asusd.rules pulls asusd + asus-shutdown in on asus-nb-wmi bind (asus-linux guide says do not enable manually; consistent) |

## 2. CPU power

- intel_pstate, active, HWP; governor powersave on all policies; no_turbo=0; hwp_dynamic_boost=0; min_perf_pct=8, max_perf_pct=100.
- EPP = balance_power on all 22 policies. Matches asusd.ron mapping for Balanced (profile_balanced_epp = BalancePower).
- platform_profile = balanced (choices quiet/balanced/performance); throttle_thermal_policy = 0 (balanced). Consistent.
- asusd.ron mapping: Quiet -> EPP Power; Balanced -> BalancePower; Performance -> Performance. AC profile = Balanced, battery profile = Quiet (`asusctl profile get`). Fan curves: quiet curve enabled on CPU; balanced/performance curves disabled (firmware default).
- Core layout (lscpu, cpufreq): P-cores 0-11 (6 cores, SMT, max 4.8-5.1 GHz), E-cores 12-19 (max 3.8 GHz), LP-E cores 20-21 (max 2.5 GHz). cpu_atom cpus = 12-21 (E and LP-E both reported as atom).
- LP-E use: intel_lpmd lp_mode_cpus is empty and all three profile defaults (PerformanceDef/BalancedDef/PowersaverDef) are -1 (force off), so lpmd does NOT force LP-mode. Whether LP-E cores (20,21) are actually used well is UNKNOWN. Recommendation: measure per-CPU load under a light workload (`mpstat -P ALL` style via /proc/stat) before tuning.
- Kernel cmdline (GRUB_CMDLINE_LINUX_DEFAULT) contains `pcie_aspm=force pcie_aspm.policy=powersupersave`. Forced ASPM on all links can cause wake/link problems on some devices; it is a candidate to A/B test if sleep or Wi-Fi/NVMe issues recur. Also present: `nvidia.NVreg_DynamicPowerManagement=0x02 nvidia.NVreg_EnableS0ixPowerManagement=1 nvidia.NVreg_PreserveVideoMemoryAllocations=0`.
- vm.swappiness reads 150 (cachyos file says 100; something else overrides, likely zram drop-in). Not a power issue; noted.

## 3. PPT / thermal (ASUS armoury)

- firmware-attributes asus-armoury: ppt_pl1_spl current 90 (range 28..90, default 90); ppt_pl2_sppt current 135 (28..135, default 135); nv_dynamic_boost 20 (5..20); nv_temp_target 87 (75..87); gpu_mux_mode 1 (hybrid / dGPU-linked off); charge_mode 1 (choices 0;1;2, meaning not verified); panel_overdrive 1.
- Conflict to verify: legacy sysfs /sys/devices/platform/asus-nb-wmi/ppt_pl1_spl reads 5, while the firmware-attributes value reads 90. Either the legacy node is a different scale or a stale/write-only read. `asusctl armoury list` also printed "Multiple asusd interfaces devices found" (warn). Check which interface asusd actually writes before trusting either number.
- Balanced/Quiet/Performance PPT differences were NOT read; only the current stored values. Recommended: record ppt values under each profile (asusctl profile set + sysfs read) before any tuning.

## 4. Battery health and charging

- BAT1: charge_control_end_threshold = 80 (asusd.ron charge_control_end_threshold: 80; `asusctl battery info` = 80%; asusd journal shows reload to 80). Compliant with the 80% recommendation for a mostly-plugged-in laptop.
- Health: charge_full 4825000 uWh vs charge_full_design 5650000 -> 85.4% of design. cycle_count reads 0 (likely not reported by EC; do not trust).
- WARNING (verify): capacity = 96%, status = "Not charging", AC online = 1. With an 80% end threshold, the capacity should be at or near 80%, not 96%. Either the EC stops charge at a different reference than the kernel capacity, or the threshold is not being enforced. Test: unplug and let it discharge, then plug in and watch whether charging resumes below 80%. If it does not stop at 80%, the threshold is not enforced (check asusd logs for write errors).
- charge_mode choices 0;1;2 (current 1). Unknown meaning on this model; leave as is unless documented.

## 5. Conflicts and misconfigurations

1. **PPD masked while asus-linux guide says asusctl works "primarily with power-profiles-daemon".** Here asusd drives platform_profile + EPP directly (platform_profile_linked_epp=true). Functionally consistent, but any shell/GUI widget that calls org.freedesktop.UPower.PowerProfiles fails (`powerprofilesctl get` -> "unit is masked"). Action: confirm noctalia's power-profile widget and rog-control-center use asusd (not PPD); otherwise either accept the widget error or unmask PPD and let it own the profile (then set asusd `platform_profile_linked_epp` consistently).
2. **intel_lpmd WLT proxy hints (WLTProxyEnable=1, WLTHintEnable=1) vs asusd EPP.** Two daemons can write EPP/EPB. Currently EPP matches asusd (balance_power), so no visible fight. Test: change profile and read EPP back after 10 s; if it snaps to a different value, lpmd is overriding.
3. **gamemode end hook returns to Balanced, not to the previous profile.** gamemode.ini: start = `asusctl profile set Performance`, end = `asusctl profile set Balanced`. On battery, asusd wants Quiet, so exiting a game unplugged leaves the machine on Balanced. Fix: record the prior profile in the start hook (e.g. `asusctl profile get` to a temp file) and restore it in end, or use a script that restores the AC/battery default.
4. **Two ASUS armoury/PPT readings disagree** (see section 3).
5. **pcie_aspm=force** on kernel cmdline: a candidate cause of wake/link issues; A/B test only.
6. **No scheduler conflict:** scx_loader not running, sched_ext disabled; scx-scheds installed but unused. Fine; leave it.
7. **ananicy-cpp + gamemode:** no duplicate CPU-priority conflict found (ananicy handles niceness/cgroups, gamemode handles governor/profile). Fine.

## 6. Community knowledge (sources checked)

- asus-linux Arch guide: https://asus-linux.org/guides/arch-guide/ - says asusctl works primarily with power-profiles-daemon; other power tools conflict; do not enable asusd manually (udev does it); nvidia-suspend/hibernate/resume services and nvidia-powerd are recommended on NVIDIA setups; S0ix "important for sleep and idle power consumption".
- asusctl manual: https://asus-linux.org/manual/asusctl-manual/ and https://github.com/flukejones/asusctl/blob/main/MANUAL.md (charge limit 20-100, profile commands). Search snippets said CLI changed in 6.x to subcommands (`profile set`, `battery limit`); this machine's `asusctl profile get/list` and `asusctl battery info` work.
- Arch Wiki Asusctl: https://wiki.archlinux.org/title/Asusctl . Arch Wiki ASUS: https://wiki.archlinux.org/title/ASUS . No dedicated Arch Wiki page for the 2024 G16 with power details found.
- KDE bug 456537 (charge limit does not persist when set via KDE; asusctl CLI does persist): https://bugs.kde.org/show_bug.cgi?id=456537
- CachyOS forum, GU605MY (i9/RTX 4090, kernel 7.0.10) sleep thread: https://discuss.cachyos.org/t/sleep-is-broken-again-even-worse-this-time-asus-laptop/30664 . Screen off, fans on, machine not asleep; wake triggers (PCI devices, LID0, Bluetooth) disabled via udev; NVreg_UseKernelSuspendNotifiers=1 with S0ix and NVIDIA suspend services disabled reportedly fixed it for ~2 weeks. Directly relevant to the overnight s2idle drain on this machine.
- Kernel patch context (2024): ASUS ROG M16 (GU604) defaulted to S3 via quirk because s2idle wakeups drained batteries: https://lkml.iu.edu/hypermail/linux/kernel/2409.1/03689.html
- Battery-life reports (anecdotal): Arch forum GU605MV Ultra 9 185H, ~2 h browsing, drains faster than Windows/Ubuntu: https://bbs.archlinux.org/viewtopic.php?id=300525 . r/ZephyrusG14 Jan 2025 (2024 Ultra 9 + RTX 4080, Pop!_OS): ~3 h max: https://redlib.hyperreal.coffee/r/ZephyrusG14/comments/1i1qqrm/poor_battery_life_on_linux_with_g16_2024 . r/ZephyrusG14 thread for 2024 AMD G16 iGPU-only: ~10 h Linux, hybrid ~6 h: https://redlib.hbubli.cc/r/ZephyrusG14/comments/1kt9ax1/the_2025_linux_on_g1416_thread/mtveh80/?context=3 . Rtings GU605 light use ~6 h (Windows): https://rtings.com/laptop/reviews/asus/rog-zephyrus-g16-2024-gu605
- No controlled Linux-vs-Windows battery benchmark for GU605MI found. No verified speaker, webcam, Wi-Fi BE200/AX211, or OLED PWM findings were gathered in this pass (out of scope for this audit).

## 7. Recommended actions (priority order)

1. Verify battery threshold enforcement (section 4 warning): unplug, discharge to ~70%, plug in, confirm it stops near 80%.
2. Fix gamemode restore: have the end hook restore the prior profile instead of hardcoding Balanced (conflict 3).
3. Confirm noctalia/rog-control-center do not depend on PPD; if they do, fix the widget path (conflict 1).
4. Read the actual PPT values per profile and resolve the 5 vs 90 discrepancy before tuning (section 3).
5. A/B test pcie_aspm=force against default only if wake/link problems recur (conflict 5).
6. Overnight drain (open): check /proc/acpi/wakeup and per-device wakeup; apply the CachyOS thread's approach (disable spurious wake sources, NVreg_UseKernelSuspendNotifiers=1) only after measuring.
7. Check LP-E core utilization under idle before deciding whether to pin background work to cpus 20-21.

## 8. Open questions

- Does the threshold actually stop at 80% on this EC? (section 4)
- Is the legacy ppt_pl1_spl (5) or firmware-attributes (90) the live value?
- What does charge_mode 0/1/2 do on this model?
- Does lpmd WLT proxy override EPP during real load?
- Does any noctalia widget query PPD and show an error?
