# 08 - Observability tools and a transparency stack for the G16 (GU605MI)

Scope: read-only research on kernel 7.3.3-1-cachyos (Intel Core Ultra 9 185H, RTX 4070, niri, systemd 262).
No state changed. No lspci, nvidia-smi, vulkaninfo, or /sys/class/drm/*/status reads. Nothing installed.
Sources: kernel config (`zcat /proc/config.gz`), /proc, /sys, `pacman -Si/-Ss` (repo metadata), and the
existing clone at ~/.local/src/S0ixSelftestTool. Kernel documentation references were not
re-checked online.

## 0. Findings that change priorities (verified on this boot)

1. **Lockup detectors are off.** Cmdline has `nowatchdog`. `/proc/sys/kernel/watchdog=0`, `nmi_watchdog=0`,
   `softlockup_panic=0`, `hardlockup_panic=0`, `hung_task_panic=0`. CONFIG_SOFTLOCKUP_DETECTOR and
   CONFIG_HARDLOCKUP_DETECTOR are both `=y`, so enabling them is a cmdline/sysctl change, not a rebuild.
   Consequence: a kernel deadlock with IRQs alive produces no panic, so pstore and kdump never fire. This is
   the most important gap. Recommend removing `nowatchdog`, then `kernel.softlockup_panic=1` first and
   `hardlockup_panic=1` only after measuring false positives from ASUS SMM stalls.
2. **No hardware watchdog.** `/sys/class/watchdog` is empty. iTCO is locked by the BIOS (per existing notes).
3. **Kdump is built but not armed.** CONFIG_KEXEC, CONFIG_KEXEC_CORE, CONFIG_CRASH_DUMP are `=y`.
   `/sys/kernel/kexec_crash_size=0` and there is no `crashkernel=` on the cmdline, so no memory is reserved.
4. **Ramoops is not configured.** CONFIG_PSTORE_RAM=m, but no `ramoops.*` on the cmdline and no reservation.
5. **EFI pstore works end to end.** `efi_pstore.pstore_disable=0` and `pstore.kmsg_bytes=32768` are set.
   `/var/lib/systemd/pstore/<id>/001/` holds about 20 `dmesg-efi_pstore-*` chunks of about 1.1-1.7 KB
   each, all archived 2026-11-14. `/sys/fs/pstore` itself is root-only (0750), so read archives via
   systemd-pstore output or as root.
6. **PMT crashlog is not active.** CONFIG_INTEL_PMT_CRASHLOG=m, but `intel_pmt_crashlog` is not loaded and
   `/sys/class/intel_pmt/` has only `telem1..telem13`. The aux devices are `intel_vsec.telemetry.0..2`, with no
   crashlog device. Open question (section 1d).
7. **ACPI method tracing is compiled in.** CONFIG_ACPI_DEBUG=y. `acpi.trace_method_name=(null)` and
   `acpi.trace_state=disable` are both exposed as module parameters, so the feature is ready to use.
8. **RAPL and battery.** RAPL domains: `intel-rapl:0` (package-0, with core and uncore subdomains),
   `intel-rapl:1` (psys), and `intel-rapl-mmio:0`. `energy_uj` is mode 0400 root-only. BAT1 exposes
   `voltage_now` (about 16.98 V) and `current_now`, but no `power_now`. Power must be computed as V*I.
9. **dGPU state without waking it.** PCI 0000:01:00.0 and 0000:01:00.1 (NVIDIA function and HDA audio)
   both show `runtime_status=suspended`, `control=auto`, and cumulative `runtime_suspended_time`. Reading
   `power/runtime_status` and the time counters does not resume the device. Locating these required only
   reading the cached `vendor` attribute, not config space.
10. **BTF is present.** /sys/kernel/btf/vmlinux is 6.6 MB, so CO-RE bpftrace/bpftool tools work.

## 1. Crash and hang capture

### 1a. Kdump / kexec
- Support: CONFIG_KEXEC=y, CONFIG_KEXEC_CORE=y, CONFIG_CRASH_DUMP=y. Kdump needs no extra kernel config.
- Packages (verified with `pacman -Si`): `kexec-tools` 2.0.32-1 (extra); `makedumpfile` 1.7.9-1 (extra, dump
  filtering); `crash` 9.0.3-1 (extra, offline analysis); `cachyos-kdump-tools` 1.1.1-1 (cachyos repo, wrapper).
  All are installed-nothing-yet. Not checked: whether `cachyos-kdump-tools` is compatible with the cachyos
  kernel's initramfs (mkinitcpio), which should be verified before arming.
- Arming: add `crashkernel=512M` (or a size measured on this machine), reboot, then load the crash kernel with
  `kexec -p`. Dump target: local btrfs (/var/crash) or ssh. Netdump over Wi-Fi is not viable (see 1d).
- Hibernate: kdump captures a panic that happens while the kernel runs, including in the freeze phase before
  the image write, since RAM is intact. It cannot capture a firmware hang after power-off, or a hang in resume
  where the crash kernel itself cannot run. Kdump is weakest in the NVMe VMD path (MTL016 stalls, see that note):
  the crash kernel's NVMe reset could stall and fail to write. Mitigate with `module_blacklist=nvidia,nvidia_drm,nvidia_modeset,nvidia_uvm`
  and `nvme` timeouts in the crash kernel cmdline.
- Overhead: about 512 MB of RAM reserved, zero runtime cost.
- Would it have helped: yes for the kernel-deadlock class (btrfs freeze, cs35l56 firmware reload). A vmcore
  shows blocked tasks and locks, far better than pstore text. It only helps once lockup detection can fire (0).

### 1b. Ramoops / pstore backends
- CONFIG_PSTORE_RAM=m, not used. Needs a reserved region on the cmdline (`ramoops.mem_address`,
  `ramoops.mem_size`, `ramoops.record_size`). Survives only a warm reboot, not a power cycle or a power-off
  hang. The EFI backend (already on) survives power cycles because it writes to NVRAM. Ramoops adds little
  unless the EFI backend fails. Keep as a fallback only.
- EFI pstore limit: EFI varstore space is small and shared with BIOS data. efivarfs reports 156 entries and
  free space that is not directly readable as bytes from stat. The current 20-chunk, about 30 KB archive
  shows it works, but check free space before raising `pstore.kmsg_bytes`.
- Caveat: pstore only writes on a panic/oops path. A hang with no panic writes nothing. Pair with
  section 0.1.

### 1c. Netconsole
- CONFIG_NETCONSOLE=m; module at /lib/modules/7.3.3-1-cachyos/kernel/drivers/net/netconsole.ko.zst.
- Interfaces: `wlo1` (Wi-Fi), `tailscale0`, `lo`. No wired NIC (USB-C Ethernet dongle would be the option).
- Wi-Fi is powered down before suspend, and USB controllers are suspended during the hibernate freeze. So
  netconsole can only stream kernel runtime output and cannot capture hibernate-path hangs. Useful for
  runtime hang debugging, not for the S4 problem. Cost: negligible.

### 1d. Intel PMT crashlog
- CONFIG_INTEL_PMT_CRASHLOG=m (module not loaded). PMT telemetry is loaded (`pmt_telemetry`, `pmt_discovery`,
  `pmt_class`, `intel_pmc_ssram_telemetry`, `intel_pmc_pwrm_telemetry`). Telemetry GUIDs and their 13 telem
  nodes are present, but no `crashlog` node.
- Interpretation: either the platform firmware does not expose a crashlog VSEC feature on this machine, or
  the driver did not bind. Check root-only: `journalctl -k -b | grep -iE 'pmt|crashlog|vsec'` and
  `lsmod`/`/sys/module` for `intel_pmt_crashlog`. Do not modprobe (state change).
- Would it help: this is the only source of PMC/firmware state from a hang that the kernel cannot log, so
  it's the most valuable option if the platform supports it. Unknown until the check above.

### 1e. Hardware watchdog alternatives
- None present. iTCO is BIOS-locked. The custom hrtimer watchdog module is the only hang-to-panic mechanism.
- Software option: enable lockup detectors (section 0.1) with `kernel.softlockup_all_cpu_backtrace=1` and
  `kernel.hardlockup_all_cpu_backtrace=1` so the first panic log includes all CPUs.
- Use `sysrq` (`kernel.sysrq` bitmask) for manual dumps during a controlled test: `w` (blocked tasks),
  `l` (backtrace on all CPUs), `c` (crash, which triggers kdump if armed).

## 2. Tracing and perf

| Tool | Package (repo) | Status here | Overhead | Notes |
|---|---|---|---|---|
| bpftrace | `bpftrace` 0.27.1-1 (extra / cachyos-extra-v3) | not installed | low for kprobe/fentry; risky on suspend path | BTF present; prefer fentry/tracepoints over kprobes |
| bpftool | installed | /usr/bin/bpftool | none | inspect loaded progs |
| bcc | `bcc` 0.37.0-2 (extra) | not installed | low | heavier install, use bpftrace first |
| perf | `perf` 7.3.1-1 (extra) | not installed | on-demand only | `perf sched`, `perf trace -e power:*` |
| trace-cmd | installed | /usr/bin/trace-cmd | low (events) | `/sys/kernel/tracing` root-only (0750), so must run as root |
| libpfm | 4.14.1 (extra) | not installed | none | only for perf events by name |
| systemd-analyze | systemd 262 | installed | none | boot chain; does not cover resume time |

- **ACPI method tracing**: `acpi.trace_method_name=<path>` and `acpi.trace_state=enable|method|option`.
  Parameters exist at /sys/module/acpi/parameters/. Writable at runtime was not verified (check perms first).
  Output is very verbose; use only for one method (e.g. a GPIO/EC/PEP method identified from the decompiled
  DSDT in ~/.local/src/acpi-tables). Also set `acpi.debug_level` if needed.
- **acpi_listen**: not installed (acpid package). ACPI notify events are better watched via udevadm monitor or
  the input layer (`evtest` on the lid/power input devices).
- **ftrace boot-time tracing**: CONFIG_BOOTTIME_TRACING=y and CONFIG_FUNCTION_TRACER=y. Boot-time config via
  bootconfig needs CONFIG_BOOT_CONFIG, not checked. Useful for early-boot hangs only.
- **Risks**: kprobes on suspend-path functions can add latency that changes the failure. Measure before and
  after. A kretprobe in the freeze path has already been seen to misbehave (module notes). Prefer tracepoints.

## 3. Power measurement

- **RAPL** (`/sys/class/powercap/`): `intel-rapl:0` package-0 (core and uncore subdomains), `intel-rapl:1`
  psys (platform, closest to whole-SoC-plus), `intel-rapl-mmio:0` (MMIO mirror). `energy_uj` is 0400 root
  (Platypus mitigation), so a logger needs root or a udev rule that grants group read. Overhead: negligible at
  1 Hz. Caveat: psys does not include the dGPU, panel, or NVMe fully. RAPL energy counter wraps (use
  `max_energy_range_uj`).
- **Battery**: BAT1 gives `voltage_now` (about 16.98 V) and `current_now`. There is no `power_now`. Compute
  P = V*I in discharge only; on AC the reading is 0 by design. Update rate and accuracy not measured; compare
  against a wall meter before trusting numbers for the overnight drain (about 5 W, open).
- **turbostat**: system `/usr/bin/turbostat` 7.3.1; the S0ix tool ships its own binary (2026.09.28, 161 KB).
  Needs root (MSR). Reports package C-states (C10 residency visible: idle state 4 total time about 4.4 Ms),
  PkgWatt, SLP_S0 (if available on MTL). Overhead: negligible at 1-5 s intervals.
- **powertop**: 2.16.1 installed. `powertop --auto-tune` writes runtime PM settings system-wide, so it is a
  state change. Use `--csv` only for reading, and not during a suspend test.
- **upower**: history of percentage and rate from the battery daemon; low overhead; coarse time resolution.
- **PMT telemetry**: 13 telem nodes with GUIDs. Mapping GUIDs to per-IP power needs Intel's `pmt` tool or
  libpmt (not in Arch repos checked). Open question.

## 4. Platform introspection

- **S0ixSelftestTool** (`~/.local/src/S0ixSelftestTool`, HEAD 2707d34): a bash script run as
  root. `-s` performs a real S2idle cycle via `echo freeze > /sys/power/state` (about 3 min), reads package
  C-states and SLP_S0 with turbostat, and uses acpidump+iasl to check the FADT. `-r on|off` samples runtime
  PC10. It also runs `powertop --auto-tune` (state change) and bundles its own turbostat binary.
  Recommendation: on-demand only, never during a hibernate or standby test. Use the system turbostat and audit
  the bundled one (or just don't run it).
- **intel_pmc_core** (loaded, 167936 bytes): `/sys/kernel/debug/pmc_core` root-only. Provides LTR, slp_s0 and
  substate residency, and IP block PM status. The best source for "which block blocks S0ix". Use root debugfs,
  on-demand.
- **chipsec**: not in Arch repos (python-chipsec not found). Use only read-only subcommands; its kernel
  module loads a driver (state change). Low priority given the goals here.
- **fwupd**: installed (2.1.9-1.1). `fwupdmgr get-devices` and `fwupdmgr security` are read-only. Avoid
  `fwupdmgr refresh`, which performs network I/O. ASUS LVFS coverage not checked.
- **dmidecode**: 3.7-1 installed; `/sys/firmware/dmi/tables` root-only. Run once, on-demand.
- **acpi tables**: acpica 20251212 (iasl) installed; `acpidump` needs root. The decompiled tables are already
  in ~/.local/src/acpi-tables.
- **EC**: `ec_sys` is not enabled in the kernel config checked. ACPI_EC_DEBUGFS=m exists, but debugfs is root-only
  and EC writes are unsafe. Read-only EC dump only, and only as root, on-demand.

## 5. GPU

- **intel_gpu_top**: `intel-gpu-tools` 2.6-1 (extra). Reads the i915/xe PMU; Intel GPU only. Overhead low.
  Does not touch the dGPU.
- **nvtop**: 3.4.0 (extra). Uses NVML, which wakes the dGPU. Do not run it during RTD3 or standby tests. Avoid.
- **NVIDIA state without waking**: use PCI attributes only: `power/runtime_status`, `runtime_suspended_time`,
  `runtime_active_time`, `control`. Do not read `/sys/class/drm/*/status`, `config`, or NVML. This is what the
  existing kprobe logger already relies on. Current values: 01:00.0 suspended, 01:00.1 suspended.
- **drm_info**: not in Arch repos (AUR). It opens DRM nodes and can resume the NVIDIA device. Avoid for
  the dGPU; Intel-only if used at all.
- **wayland-info**: `wayland-utils` 1.3.0 (extra) provides `wayland-info`. Compositor-side only; does not
  touch the GPU. Safe.

## 6. Recommended stack

### Always-on (low overhead, no state change needed beyond cmdline)
1. Remove `nowatchdog`. Enable lockup detectors with `softlockup_panic=1` now; add
   `hardlockup_panic=1` after a measured false-positive test. Overhead: negligible.
2. Keep EFI pstore (already on) and journal persistence (`/var/log/journal` exists; Storage=auto).
3. 1 Hz logger for RAPL psys + BAT1 V*I + turbostat package C-state residency, as a root systemd unit writing
   CSV to a local log directory. Overhead: well under 0.1% CPU. Gives the overnight drain data.
4. Kdump armed (`crashkernel=512M`, `kexec -p` at boot, `makedumpfile -l -d 31` to /var/crash). Cost: 512 MB
   RAM. Benefit: vmcore for every panic, including lockup panics from item 1.

### On-demand (run only during a test, as root, after saving state)
- trace-cmd standby events (existing), bpftrace probes (fentry/tracepoints), perf sched during resume,
  ACPI method trace on one method, pmc_core debugfs snapshot before and after a suspend, S0ix selftest (`-s`)
  with the system turbostat, sleepgraph (pm-graph) in its test mode, intel_gpu_top during a GPU-busy test,
  wayland-info for compositor state.
- Never during a test: nvtop, drm_info, powertop --auto-tune, any NVIDIA NVML query.

### Wiring into a repo of reproducible scripts
Suggested layout for a local script directory (not created here):
- `probe/capabilities.sh`: read-only check of cmdline, sysctls, module presence, pstore, PMT, RAPL perms, BTF,
  package presence. Prints a table so the stack can be verified after each kernel or cmdline change.
- `install/packages.txt` plus an install script that runs `pacman -S --needed` (run manually; the script does
  not install itself): `bpftrace perf kexec-tools makedumpfile crash cachyos-kdump-tools intel-gpu-tools wayland-utils`.
- `logger/` systemd unit for the 1 Hz RAPL + battery logger, with paths and rotation.
- `tests/` one script per scenario that snapshots pmc_core, turbostat, trace-cmd, and pstore before and after.
- `cmdline/` a file recording the exact cmdline changes (remove nowatchdog; add crashkernel, ramoops only if
  needed) so each change is reviewable and reversible.

## 7. Open questions (need root, or a decision)
1. Does the PMT crashlog exist on this firmware? Check `journalctl -k -b | grep -iE 'pmt|crashlog|vsec'` as root.
2. Is `acpi.trace_method_name` writable at runtime (perm bits of /sys/module/acpi/parameters/)? Only a stat is
   needed, not a write.
3. Does kdump's crash kernel survive the NVMe VMD (MTL016) reset path? Needs a controlled test.
4. Will the hardlockup detector false-positive on ASUS SMM stalls? Measure with softlockup first.
5. EFI varstore free space in bytes; decides how far `pstore.kmsg_bytes` can go.
6. Accuracy and update rate of the BAT1 current/voltage readings vs a wall meter.
7. Is the bundled turbostat in S0ixSelftestTool identical to upstream 2026.09.28? Audit before running it.
8. Web sources (kernel docs for kdump, pmt, ramoops, lockup detectors; Intel pmt/libpmt; CachyOS kdump
   tools) were not checked. Verify before acting.
