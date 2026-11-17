# 12 - Performance and responsiveness (GU605MI, CachyOS 7.3.3)

Scope: read-only audit. No state changes, no GPU-loading tests, no web research performed in this pass (external claims are marked "unverified / background knowledge").
Snapshot taken 2026-11-14 ~19:15, uptime 1h18m, load avg 0.44, PSI near zero.

## 1. CPU scheduling

Verified:
- Kernel `7.3.3-1-cachyos`. `CONFIG_SCHED_CLASS_EXT=y`, but `/sys/kernel/sched_ext/state` = `disabled`; `scx_loader.service` inactive. scx-scheds 1.1.4, scx-manager 1.16.0 and scx-tools are installed.
- No BORE in config (grep for SCHED_BORE/BMQ empty). Default scheduler is EEVDF. `CONFIG_SCHED_AUTOGROUP=y`, `sched_autogroup_enabled=1`.
- Preempt model full (`PREEMPT_DYNAMIC`), `HZ=1000`.
- Driver `intel_pstate` active (passive not used); EPP = `balance_power` on all 22 CPUs; `hwp_dynamic_boost=0`.
- Topology (`/sys/devices/cpu_core/cpus` = 0-11, `/sys/devices/cpu_atom/cpus` = 12-21). LP-E cores 20-21 have max 2.5 GHz vs 3.8 GHz for E 12-19 and 4.8 GHz for P.
- ananicy-cpp active, 15,812 rules loaded, detects "22 CPUs, 2 LLCs, SMT=on, big.LITTLE=yes", P = 0-11, E = 12-21 (LP-E lumped with E). It logs **"Cgroups are not available on this platform (or are not enabled)"**, so `cgroup` rules are inert; nice/ioclass/sched rules still apply. `/etc/ananicy.d/00-types.types` maps Game (nice -5), Chat (-3), Heavy_CPU (+9), BG_CPU (idle sched, nice 14), Launcher (nice 16, idle IO).
- Idle: cpu0 cpuidle residency is dominated by C10 (~4535 s of ~4680 s uptime). Package sleeps well.
- `thermald` inactive (appropriate: ASUS uses `asus-nb-wmi` throttle policy; thermald would fight RAPL).
- No `hfi`/ITMT lines in the current boot's kernel log (grep empty). Whether Thread Director feedback is active is **unverified**; intel_pstate HWP on MTL normally uses it, so treat as "probably active".

Assessment: scheduling is reasonable. The only real gap is that ananicy's cgroup layer is dead, and LP-E cores are not distinguished from E cores. Neither is a measurable responsiveness problem at present (PSI cpu some avg300 = 0.00).

## 2. Thermals, fans, power limits

Verified (idle-ish, 1h uptime):
- coretemp: 38-44 C package/core; acpitz 44 C; NVMe 29-30 C; iwlwifi 39 C.
- ASUS fans: fan1 1800 rpm, fan2 1800 rpm, **fan3 3800 rpm** (unexpected at ~40 C; see open questions).
- `core_throttle_count` = 0 on all 22 CPUs since boot.
- `asus_custom_fan_curve` (hwmon6) is present and in auto mode (`pwm*_enable=2`). Curves are 8 points; at 62 C the first point is 17/12/20 PWM, and at 80 C they reach 130/104/198 PWM.
- platform_profile = `balanced` (choices quiet/balanced/performance).
- RAPL (`intel-rapl:0`): constraint_0 (PL1, long_term) = **90 W**; constraint_1 (PL2, short_term) = **104 W**; constraint_2 = 217 W. Equivalent MMIO domain identical.
- asus-armoury: `ppt_pl1_spl` = 90 (range 28-90, default 90, at max), `ppt_pl2_sppt` = 135 (range 28-135, at max). **Mismatch:** ASUS reports PL2 135 W but RAPL shows 104 W. Possibly the EC value vs what the kernel programmed; unresolved.
- `nv_dynamic_boost` = 20 W (range 5-20, at max), `nv_temp_target` = 87 C (range 75-87, at max).
- `gpu_mux_mode` = 1 (choices 0;1). Assumed to be Hybrid, matching supergfxctl "Hybrid" (inferred: 0 = dGPU/MUX, 1 = hybrid).
- dGPU 0000:01:00.0 runtime_status = **suspended**, driver nvidia, control auto. RTD3 is working on this kernel.
- `asusctl profile -p` returned nothing (not verified why).

Assessment: thermal headroom is large at idle. Sustained PL1 = 90 W is far above the 45 W base of the 185H; the fan curve is the real limiter under sustained load, so this needs a load test (see plan). PL2 mismatch needs checking before anyone tunes it.

Undervolting (background knowledge, unverified): Intel mailbox voltage offset (MSR 0x150) has been locked or ignored on recent mobile parts. Assume "not available" unless `intel-undervolt`/`ryzenadj`-style probing shows otherwise. Not tested here, and reads of MSRs were out of scope.

## 3. Gaming / GPU path

Verified:
- supergfx Hybrid; PRIME offload via env vars in Lutris (`__NV_PRIME_RENDER_OFFLOAD` not used; `__VK_LAYER_NV_optimus=NVIDIA_only`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`), gamemode enabled in Lutris.
- gamemode 1.8.2 installed, no `/etc/gamemode.ini` (stock defaults in use). MangoHud installed. gamescope absent. 6 Steam/Proton compatdata dirs.
- NVIDIA kernel params: `nvidia-drm.modeset=1 fbdev=1`, `NVreg_DynamicPowerManagement=0x02`, `NVreg_EnableS0ixPowerManagement=1`, `NVreg_PreserveVideoMemoryAllocations=0`.
- Kernel cmdline also has `pcie_aspm=force pcie_aspm.policy=powersupersave`.

Background knowledge (unverified): MUX (dGPU-direct) avoids the iGPU-to-dGPU copy and usually gains a few percent FPS and lower latency; requires reboot; battery cost; external HDMI on the dGPU avoids the copy in any mode only when the display is wired to it, which in Hybrid mode depends on the port.

## 4. Storage and I/O

Verified:
- NVMe: WD PC SN5000S 2 TB, fw 34230100, PCIe 16 GT/s x4 (`current_link_speed`/`width` on the NVMe). Behind Intel VMD domain 10000 (`0000:00:0e.0`, driver `vmd`, out-of-tree patched module). `vmd: module verification failed ... tainting kernel` in dmesg.
- `nvme0n1` scheduler = `kyber` (choices none/mq-deadline/kyber/adios/bfq); nr_requests 256; read_ahead 1024 KB; wbt 2000 us; queue_count 23.
- APST `default_ps_max_latency_us` = 100000 (kernel default). ASPM policy = powersupersave; link L1 ASPM enabled.
- btrfs `/` and `/home`: `rw,noatime,compress=zstd:1,ssd,discard=async,space_cache=v2`. `/swap` (swapfile subvol) mounted noatime. `fstrim.timer` active (weekly).
- Kernel log: no NVMe timeout/reset/"completion polled" messages this boot (grep count 0). The MTL016 erratum fix is installed as `vmd-mtl016-dkms`; upstream fix 7307899e381c is not in stock 7.3.3, so the patched module is needed.
- Journal: "block groups with swapfile extents will not be scrubbed or balanced" (expected btrfs behaviour, harmless).

Assessment: storage setup is sound. `kyber` on a multi-queue NVMe is unusual (`none` is the usual choice for NVMe) but the latency gain is unmeasured. The main responsiveness risk is the VMD erratum, which the patched module addresses.

VMD removal (unverified, background knowledge): disabling VMD in BIOS exposes the NVMe on native PCIe and removes the remapping layer and the out-of-tree module. On Windows the boot must have the native NVMe driver (stornvme) set to start at boot before the switch, or it will BSOD (INACCESSIBLE_BOOT_DEVICE). This is the fallback option. Benefit for performance is small; the benefit is removing the erratum class entirely.

## 5. Memory

Verified:
- 32 GB RAM. zram0: 30.8 GB, zstd, prio 100, DATA 1.8 MB (almost unused). Swapfile `/swap/swapfile` 32 GB, prio -1 (fallback).
- `vm.swappiness` = **150** at runtime. CachyOS ships 100 in `/usr/lib/sysctl.d/70-cachyos-settings.conf`; `/etc/sysctl.d/` is empty; no source found for the 150 override (set by an unknown script or runtime write).
- Other: `vfs_cache_pressure=50`, `page-cluster=0`, `watermark_scale_factor=10`, `min_free_kbytes=67584`, `dirty_ratio=10`, `dirty_background_ratio=3` (CachyOS values).
- THP `enabled=[always]`, `defrag=defer+madvise`. MGLRU enabled (0x0007). zswap runtime `N` (kernel default is on, but disabled here; not investigated).
- systemd-oomd inactive; no earlyoom/oomd process. PSI memory: some/full avg300 = 0.00.

Assessment: memory config is reasonable for zram. Two notes: swappiness 150 is an unusual value with no traceable source, and the dirty ratios (10%/3% of 32 GB = ~3.2 GB dirty ceiling) allow long write stalls on large copies. No userspace OOM daemon is running.

## 6. Ranked improvements (expected impact on responsiveness and FPS)

1. **Keep VMD patch / evaluate VMD off** (high for responsiveness; erratum class). Already mitigated. Verify each kernel update.
2. **Dirty writeback caps** (medium for UI stalls during big writes): set `vm.dirty_bytes` (e.g. 256 MB) and `vm.dirty_background_bytes` (e.g. 64 MB) instead of ratios. Measure: during `dd` of 16 GB, record max input-latency and `Dirty`/`Writeback` in /proc/meminfo; compare before/after.
3. **Sustained thermal test before touching power limits** (medium): run a CPU-only load (e.g. `stress-ng --cpu 22 -t 600`, run manually) while logging `turbostat --quiet -i 5` and the fan/temp hwmon values; record `thermal_throttle` counter deltas. Decide PL1 only from this data. Resolve PL2 90/135 vs 104 RAPL mismatch first.
4. **Fan curve tuning** (medium, noise/thermal trade-off): curves are already aggressive; check `fan3` (3800 rpm at idle) before changing anything.
5. **NVMe scheduler none vs kyber** (low-medium): `fio --rw=randread --bs=4k --iodepth=1 --runtime=60` on a test file under a background writer; compare p99 latency. Do not run on the root filesystem's swap file.
6. **EPP/platform profile for games** (medium, measurable): `performance` EPP vs `balance_power` with fixed-CPU workload; record `turbostat` package W and wall time.
7. **MUX mode for games** (medium, reboot-based): A/B with MangoHud `output_folder` logs on the same scene, 3 runs each. Only worth it if the Hybrid frame-time gap is measurable; the battery trade-off is covered in the power notes.
8. **ananicy cgroup layer** (low): investigate why cgroups are unavailable; fix only if rules matter for games.
9. **scx scheduler** (unknown; try last): scx_lavd or scx_bpfland via scxctl; measure with the same frame-time logs and a CPU-latency test (`cyclictest` short run). Disable if no win.
10. **swappiness 150 -> 100** (low): no traceable source; with zram at 30 GB and little use, impact is small. Measure with a controlled memory-pressure test.
11. **Enable a userspace OOM policy** (low-medium for tail latency): systemd-oomd or earlyoom. Measure with PSI memory `full` during a forced allocation test.
12. **PCIe ASPM powersupersave** (unknown; power/perf trade-off): test `pcie_aspm.policy=performance` for NVMe latency; weigh against the power notes.

## 7. Measurement plan (reproducible)

- Baseline snapshot: `turbostat --quiet -i 5 -n 2` (sudo, read-only), `sensors`, `/sys/devices/system/cpu/cpu*/thermal_throttle/*_throttle_count`, PSI, `/proc/meminfo` Dirty/Writeback.
- Each change: record kernel cmdline/sysctl/EPP state; run the same scenario 3x; compare medians.
- CPU: `stress-ng` fixed-duration runs with turbostat; `7z b` or `sysbench cpu` for scores (run manually).
- Storage: `fio` with fixed job files; p99/p99.9 latencies.
- Games: MangoHud `output_folder` + frame-time CSV, same in-game scene, 3 runs each.
- Interactivity: a scripted "input latency" proxy (e.g. `evtest` timestamps during a `dd` write) is crude; keep it as a sanity check, not a benchmark.

## 8. Open questions

- Which hwmon fan is which, and why fan3 runs at 3800 rpm at idle (dGPU fan? wrong label?).
- Why PL2 is 135 W in asus-armoury but 104 W in RAPL; which one is the EC actually enforcing.
- Source of `vm.swappiness=150` (not in any sysctl.d file).
- Whether Thread Director/HFI is active (no kernel message this boot).
- Whether stock 7.3.3 `vmd` has the 7307899e381c fix (believed not; verify with objdump on the stock module if desired).
- `asusctl profile -p` returned nothing; check the asusctl version/CLI syntax before trusting profile state.
- Undervolt availability on MTL (needs MSR probing; out of scope here).
- External web research on MTL performance tuning and VMD BIOS procedure was not performed in this pass.
