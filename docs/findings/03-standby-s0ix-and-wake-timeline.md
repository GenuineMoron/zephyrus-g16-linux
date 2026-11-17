# 03: Standby depth (S0ix) and the wake timeline

**Status:** measured. A full night on battery (2026-11-14/15) averaged **0.86 W, with ~100% of the time in S0i2.1**. The one bad night (~5 W) is still unexplained. Its "8% deep sleep" figure came from a kernel counting bug (below), so it does not show that the SoC stayed awake.

## How deep standby goes

Meteor Lake has three S0ix substates: S0i2.0, S0i2.1 and S0i2.2 (deepest). The `intel_pmc_core` debugfs files show which one the SoC reached:
- `substate_residencies`: time spent in each substate;
- `substate_requirements`: what each substate needs;
- `lpm_latch_mode`: when the status registers are captured.

**A real 60 s standby on AC:** 55.4 s in S0i2.1 (pmc0 and pmc1), 0.4 s in S0i2.0, 0 in S0i2.2.

- **What blocks S0i2.2:** with the status latched at S0i2.0 entry, the unmet S0i2.2-only requirements are clocks and rails. These are `AON5_OFF`, `XTAL_LVM_OFF`, `XTAL_AGGR_OFF`, `FILTER_PLL_OFF`, `SOC_PLL_OFF`, `IMG_PLL_OFF` and `IOE_COND_MET_S02I2_2` on pmc0, plus `AON2_OFF`, `XTAL_AGGR_OFF` and `SOC_PLL_OFF` on pmc1 (the IOE die). Those look like consequences rather than causes.
- **Others see the same:** a Framework 13 (155H) owner on Linux reports the same pattern (S0i2.2 = 0).
- **Expected gain is small:** the deepest substate is probably worth tens of mW at most. We are not chasing it.

## Standby power

| Case | S0ix residency | Average power |
|---|---|---|
| Short standbys on battery, 2 min each | 97% | ~1.8 W, including entry/exit overhead |
| A good night (2026-11-11) | n/a | 1.21 W |
| One bad night (2026-11-11/12) | unknown: the logged 8% is the counter bug below; the real value is 8% + k × 9.94% | ~5 W (80% → 1% in 12 h). **Cause unknown** |
| Night on battery (2026-11-14/15), 8.6 h in 9 stretches | S0i2.1 99.8–100% | **0.80–0.89 W** (96% → 87%); EC `VIUF`=0 throughout, so the BIOS cut the dGPU rail |

**Windows on the same laptop** (Kernel-Power 506/507 events, Feb–Jun 2026, [research/27](../research/27-windows-standby-drain.md)): battery standby sessions of 1 h or more with ~99% DRIPS (Windows' deep-sleep measure) drew **755–917 mW**. Some sessions failed: three at 0% DRIPS drew ~3 W for an hour, and others drew 1.6–2.5 W. **Linux's 0.86 W equals Windows' best case, so the standby floor is set by the hardware, not the OS.** Overnight loss can only shrink by spending less time in standby (hibernate policy), not by sleeping deeper.

About 6 s per hour is spent awake for systemd's battery check (`SuspendEstimationSec=1h`), around 4% of the night's energy.

## A kernel bug in the deep-sleep counter

`/sys/power/suspend_stats/last_hw_sleep` and `total_hw_sleep` lose whole multiples of 71.6 minutes. `drivers/platform/x86/intel/pmc/core.c` (`pmc_core_is_s0ix_failed`, Linux 6.4 to at least 7.3 and current master) does:

```c
pm_report_hw_sleep_time((u32)(s0ix_counter - pmcdev->s0ix_counter));
```

Both values are already scaled to microseconds, so the cast truncates the difference modulo 2³² µs = 4294.97 s. The same driver sets `max_hw_sleep` to the real counter range, 523986 s (~145 h).

| | Value |
|---|---|
| Stretch length | 9331 s |
| S0i2.1 residency (PMC substate counter) | 9322.6 s |
| `last_hw_sleep` | 732.66 s = 9322.6 − 2 × 4294.97 |

Anything that divides `last_hw_sleep` by the sleep time sees a healthy 2.6 h standby as "8% deep sleep". This repo's logger did, and the old bad night was logged the same way.

- **Introduced by:** ddd66d634735 ("Report duration of time in HW sleep state", 2023).
- **Fix:** [upstream/0001-intel-pmc-hw-sleep-u32-truncation.patch](../../upstream/0001-intel-pmc-hw-sleep-u32-truncation.patch). It builds cleanly with `W=1` against 7.3; it has not yet been run on hardware.
- **Logger workaround:** it now reads the PMC's 64-bit `slp_s0_residency_usec` from debugfs, with wrap handling.

[configs/usr/lib/systemd/system-sleep/40-sleep-stats](../../configs/usr/lib/systemd/system-sleep/40-sleep-stats) now logs every stretch:
- S0i2.x seconds;
- the GPU state before and after;
- the wake IRQ;
- the EC's dGPU power flags (`VIUF`, `VGAT`, `GC6S`; see [research/02](../research/02-ec-asus-wmi.md));
- RAPL energy for the SoC package and the whole platform (`psys`), to split standby power between the SoC and the rest of the laptop. Awake, `psys` read ~17% above the battery's own V×I.

Any stretch with less than 80% deep sleep (and at least 60 s long) gets a detail file, holding:
- the unmet requirements;
- LTR values;
- power-gating status;
- the PCI and USB devices that were awake;
- the kernel log for that stretch.

systemd also wakes once an hour (`SuspendEstimationSec=1h`) to re-measure the battery and hibernate early if it is draining fast.

## Wake timeline (kernel, one standby on AC)

| Phase | ms | Biggest contributor |
|---|---|---|
| resume_noirq | 548 | `pcieport 0000:00:01.0` 542 ms: powering the NVIDIA slot back on, see [02](02-standby-nvidia-wakes-idle-gpu.md) |
| resume_early | 28 | |
| resume | 1145 | `snd_hda_codec_alc269` 645 ms; `i915` 486 ms; USB devices ~95 ms each (keyboard x2, webcam) |
| complete | 5 | |

**Two contributors depend on setup:**
- **The 645 ms codec resume happens on AC only.** CachyOS sets `snd_hda_intel power_save=0` while on AC to avoid audio crackle (`cachyos-settings`: `/usr/lib/udev/audio-pm-ctl` and `20-audio-pm.rules`), so the codec can never sleep. On battery the kernel default (10 s) applies, and an idle codec stays asleep through standby.
- **`i915` (486 ms) includes the eDP panel power-up sequence.** Treat it as the floor.

**Measured wake time** on battery (Hybrid mode): ~1.1 s of kernel time. Resuming NVIDIA's slot is the biggest part. Wake is by lid open or the power button (the keyboard can't wake standby on Linux, plan B23).

## Going to sleep

`suspend_enter` takes 2.9 s, almost all of it NVIDIA ([02](02-standby-nvidia-wakes-idle-gpu.md)). i915 suspend takes 392 ms.
