# 05 - Intel graphics / display power (ROG G16 GU605MI, MTL-H 185H, kernel 7.3.3-1-cachyos)

Read-only research. Data taken 2026-11-14 ~19:15. Boot 0 started 17:59:36; prior boots -1..-3 used for history. No NVIDIA-side reads (no nvidia-smi, lspci, status files). debugfs read only on DRI minor 1 (i915, 0000:00:02.0). Minor 0/129 (nvidia-drm) untouched.

## 1. Suspend/resume cost inside i915 (measured)

Journal, boot 0 (s2idle cycle at 18:17:46):
- `pci_pm_suspend` i915: 392,393 us. `_late`: 18,856 us. `_noirq`: 12,151 us.
- `pci_pm_resume_noirq`: 15,266 us. `_early`: 21,273 us. `pci_pm_resume`: 478,897 us.
- Resume log shows GT0 and GT1 GuC re-init (submission, SLPC, RC) and HuC re-auth (clear media, then all workloads) and the GSC proxy rebind. DMC is NOT reloaded on resume (the DMC load message appears only at boot).
- Interpretation (inferred from ordering, not from kernel source): the bulk of the ~479 ms is GuC/HuC reload and re-auth plus display re-init. The suspend side is GuC/HuC/GT teardown plus display disable.
- Other devices in the same window are ~0-40 ms, so i915 is the single largest device cost.
- Not verified: the exact split between GuC, HuC, GSC and display. Upstream source was not fetched in this pass (the raw.githubusercontent xe path returned 404, and i915 source was not pulled). Doing that is still open.

## 2. Panel: ATNA60DL01-0 (Samsung 16in 2.5K OLED, 240 Hz)

- Mode in use: pipe A 2560x1600 @ 240 Hz (pixel clock 1125275 kHz, htotal 2640, vtotal 1776, so 240.0 Hz). The compositor is driving the panel at 240 Hz.
- PSR: `i915_edp_psr_status` reports sink PSR = yes (DPCD 0x01, PSR1 only), Panel Replay = no. Source runs PSR1 (`PSR mode: PSR1 enabled`). PSR2 is not used because the sink is PSR1-only; the `enable_psr2_sel_fetch=yes` module param is irrelevant here.
- Panel Replay: not supported by this panel's sink, so there is nothing to enable. `enable_panel_replay` is -1 (auto) and correctly does nothing.
- Sink status at snapshot: SRDENT (in self-refresh). PSR is active.
- FBC enabled (`i915_fbc_status`: enabled, not compressing at snapshot).
- SAGV enabled, IPS enabled, LPSP enabled, runtime PM enabled, `intel_display_caps` has_psr yes, has_dmc yes, has_dsc yes.
- DC states (`i915_dmc_info`, counts since boot): DC3->DC5 = 17,048, DC5->DC6 allowed = 17,048. Display reaches deep DC states. `enable_dc` is -1 (auto), which is working.
- VRR / adaptive sync: not checked (no debugfs field read for it). Open.
- DPCD backlight: `i915.enable_dpcd_backlight=3` is on the cmdline; intel_backlight is the eDP-1 backlight device.

## 3. eDP power sequencing (T1-T12)

- `i915_panel_timings` and `i915_drrs_status` do not exist on this kernel. The programmed PP_ON/OFF delay registers are not exposed via debugfs.
- VBT parsed from `i915_vbt` dump (saved as `vbt.bin`; local working copy, not in the repo). BDB block 27 (BDB_EDP) entry for panel 0 decodes to T1+T3=2000 ms, T8=2000, T9=2000, T10=1700, T11+T12=5000 ms.
- These values look like placeholders, not real panel timings (real eDP values are typically tens to a few hundred ms). Treat as UNVERIFIED.
- Evidence they are not on the resume critical path: total i915 resume is 479 ms, far short of a 2 s+ panel-on delay. Not proven.
- Conclusion: the panel's T-values are not a meaningful lever from userspace. Nothing to change here.

## 4. xe vs i915

- `lsmod`: xe loaded (refcount 0 for xe itself, pulled in by the PCI alias autoload; `xe` has aliases for 7D45/7D55/7DD5).
- 0000:00:02.0 is bound to i915 (`/sys/bus/pci/devices/0000:00:02.0/driver` -> i915). xe has no bound device; its driver dir has only bind/unbind/new_id/module etc.
- No xe probe messages in the journal in any boot checked.
- Upstream xe_pci.c: MTL sets `require_force_probe = true`. Without `xe.force_probe=7d55` xe refuses the device with -ENODEV. This matches the observed state. The 7D55 ID is confirmed by the i915 log ("device ID 7d55").
- i915 says MTL is `require_force_probe: no` (i915 is the default driver for MTL).
- Recommendation: stay on i915 for MTL. xe is not needed. It is harmless but idle. It could be prevented from loading with a modprobe `install xe /bin/false` drop-in (not applied; read-only task). Expected gain is nil for power; it is cosmetic.
- Note: `/etc/mkinitcpio.conf` has `MODULES=(vmd i915)` and no xe. Good.
- Note: the lpmd/PMC work in other notes (NPK, S0i2.1) is unaffected by xe.

## 5. intel_lpmd

- Package: `intel-lpmd 0.1.1-2` (cachyos repo). Upgraded from 0.1.0-7 on 2026-10-26.
- Service: active since boot 0, enabled, preset disabled. Launches `/usr/bin/intel_lpmd --systemd --dbus-enable`.
- Config in use: `/etc/intel_lpmd/intel_lpmd_config_F6_M170.xml` (family 6, model 170 = MTL, which matches this CPU's `model : 170`).
  - Mode 1 (cgroup v2 isolate).
  - PerformanceDef = BalancedDef = PowersaverDef = -1 (force OFF, never enter Low Power Mode, for all power profiles).
  - So lpmd never isolates CPUs in this config. It only polls and sets WLT EPP hints (WLTHintEnable=1, WLTProxyEnable=1).
  - MinPollInterval 2000 ms.
- The "read_aperf_mperf_tsc_perf failed for cpu = N" errors:
  - Present in boot -3 (from 11:49), boot -2 and boot -1 (bursts from 12:39, roughly 19 per minute with some minutes at 38, i.e. about one line per online CPU per poll). Total 5,130 in all boots.
  - ABSENT in boot 0 (current boot, since 17:59). 0 matches in boot 0 for `aperf`.
  - So the error is not steady; it is boot-to-boot / state dependent. Cause not identified.
  - /dev/cpu/N/msr is root:root 0600 (no read issue for root); msr module is not loaded as a module but MSR device nodes exist.
  - Upstream search: WebSearch found no page containing the exact message. The only related code is the turbostat-style APERF/MPERF "read via perf API" helper in the kernel tree (Len Brown series, `tools/power/turbostat`). Inference: lpmd 0.1.1 reads APERF/MPERF through the perf API, and this message means a short read. Unconfirmed.
  - `/proc/sys/kernel/perf_event_paranoid` = 2 (normal). Not an obvious cause.
- Usefulness on MTL-H here: with every profile forced off, lpmd currently gives ~no power benefit and adds a 2 s poll plus CPU wakeups. It is effectively a monitor.
- Recommendation:
  - Option A (simplest, my preference for this laptop): `systemctl disable --now intel_lpmd`. Measure s2idle drain and active idle before/after.
  - Option B: keep it only if the WLT EPP hints are wanted. These are already served by power-profiles-daemon/ASUS profile; check for overlap before keeping.
  - Do not "fix" the error by editing config; the config is not the source of the error.
- Not applied. Read-only task.

## 6. Other Intel-side power knobs checked

- i915 params (`i915_params`/cmdline): enable_psr=-1 (auto, PSR1 active), enable_panel_replay=-1 (auto, unsupported by sink), enable_fbc=1 (FBC on), enable_dc=-1 (auto, DC5/DC6 used), enable_sagv=yes, enable_ips=yes, enable_dsb=yes, enable_dpt=yes, enable_dc_balance=no, enable_dmc_wl=0, enable_flipq=no, disable_power_well=1 (power wells active, the default), enable_dpcd_backlight=3 (set explicitly).
- GuC SLPC and RC are enabled on both GTs (boot log). Frequency: min/RPn 800 MHz, RP0 2350 MHz, actual 700-800 MHz idle. Power management of the GT is active.
- Media power gating: `i915_capabilities`: "has slice power gating: no", "has subslice power gating: no", "has EU power gating: no". MTL-H here cannot power-gate slices or subslices (platform property, not a setting). The GT can still RC6.
- Panel refresh: 240 Hz is the largest single display power cost on this OLED. Dropping to 60 Hz on battery (niri output mode) is the largest display lever. Not measured here.
- Display core: `i915_power_domain_info` shows PW_A in use (pipe A, TRANSCODER_A, DDI A/AUX_IO_A), other wells off. Display is minimal. Good.

## Recommended actions (in priority order)

1. Measure, don't guess: run a timed s2idle cycle with `intel_lpmd` enabled vs disabled (`systemctl stop intel_lpmd` for a test). Compare overnight drain (open question; see ../findings/03-standby-s0ix-and-wake-timeline.md).
2. Consider disabling intel_lpmd (config forces all profiles off, so no benefit; the errors are noise and poll wakeups).
3. Check VRR and battery refresh policy: confirm niri drops to 60 Hz on battery. Power impact of 240 vs 60 Hz is the largest i915-side lever left.
4. Leave i915 as the driver. xe is idle and unnecessary.
5. Leave PSR1, FBC, DC and SAGV on (already on).
6. For the suspend/resume 480 ms: pull the i915 source for `intel_gt_suspend`/`intel_uc_resume`/`intel_display_resume` (fetch from raw.githubusercontent.com/torvalds/linux/master/drivers/gpu/drm/i915/...) to confirm where the time goes. Not done.

## Proven vs inferred

Proven (directly observed):
- PSR1 active, Panel Replay unsupported by sink.
- DC5/DC6 reached (counts 17,048).
- Pipe at 240 Hz.
- i915 is bound to the iGPU; xe loaded but unbound.
- lpmd config F6_M170 forces all profiles off.
- i915 suspend 392 ms, resume 479 ms, GuC/HuC re-init on resume.
- lpmd aperf errors in boots -3..-1, none in boot 0.

Inferred (not fully proven):
- GuC/HuC reload is the bulk of the 479 ms resume (ordering evidence only).
- lpmd error comes from an APERF/MPERF read via perf API (no direct source confirmation).
- xe refuses MTL without force_probe (upstream xe_pci.c summary; matches observation).
- VBT block 27 values are placeholders (decode is sound; plausibility judgement only).

## Open questions

- Why lpmd aperf errors stop in boot 0 (what changed at 17:59?).
- Whether the eDP panel actually runs at 240 Hz when idle on battery, and what the power difference is.
- VRR state (not read).
- Real T1-T12 programmed values (not exposed by debugfs on 7.3).
- i915 resume breakdown (GuC vs HuC vs display) needs source-level tracing or ftrace (read-only, i915 only).
