# 36: What keeps the CPU out of PC10 with the screen on, software wake-ups, and scx_lavd (2026-11-15)

Hands-off run, on battery, screen on, an empty workspace shown, Noctalia idle actions paused. Everything was restored afterwards. Raw logs are a local working copy, not in the repo.

## Display is not the blocker

| Check | Result |
|---|---|
| PSR state samples (every 2 s) | Self-refresh (`SRDENT`) in 80–95% of samples |
| Display C-states (DMC) | DC5→DC6 entered ~500 times per 40 s window (normal with PSR1) |
| PMT block cause "display" | 0.6% |

## The blocker is timer wake-ups

Intel PMT, 30 s delta, screen on, idle (telem1–4; decoder [tools/pmt/pmt_read.py](../../tools/pmt/pmt_read.py)):

| Package C-state block cause | Share |
|---|---|
| PUNIT | 35.1% |
| CDIE (CPU die) | 25.0% |
| SOC_CORE | 23.5% |
| DTS (thermal sensor) | 8.5% |
| UNKNOWN | 6.2% |
| PCH | 1.0% |
| DISPLAY | 0.6% |

Wake reasons: **`TNTE_CDIE` 93.8%**, meaning the time to the next timer event on the CPU cores was too short for a deep state. LTR-related wakes were ≤1.2% (PCH) now that the keyboard USB chips can suspend ([finding 06](../findings/06-keyboard-usb-blocks-deepest-idle.md)).

## Who wakes the CPU (30 s, `sched:sched_wakeup` per woken task, screen on, idle)

| Task | Wake-ups/s | Notes |
|---|---|---|
| Zen browser threads (`Timer`, `Isolated Web Co`, `HeapHelper`, `IPC I/O Parent`, `IPDL Background`) | ~150 | Depends on open tabs |
| `procon2-driver` | 53 | Switch 2 Pro Controller userspace driver; polls even with no controller. Candidate: start it on controller plug (udev `SYSTEMD_WANTS`) |
| `claude` | 51 | The AI assistant process used for the measurement; absent in normal use |
| `tailscaled` | 42 | VPN daemon |
| `kworker`s | ~43 | |
| `noctalia`, `niri`, `dbus-broker`, `alacritty` | 12–15 each | Normal desktop |
| `ananicy-cpp` | 14 | CachyOS process-priority daemon |
| `nvidia-powerd` | 13 | **Was running on battery** (asusd only stops it on plug/unplug). Fixed: `ConditionACPower=true` + udev start/stop |
| `bpftune` | 10 | CachyOS auto-tuning daemon |

Interrupts: local timer 660/s across 22 CPUs; i915 21/s; vmd 6/s; Wi-Fi ~8/s.

## scx_lavd --autopower vs EEVDF (idle, screen on, 40 s windows, alternated)

| Scheduler | PC2 | PC6 | PC8 | PC10 | Package W | Platform W |
|---|---|---|---|---|---|---|
| EEVDF | 15.4 | 28.7 | 25.1 | 0.06 | 2.22 | 5.02 |
| lavd autopower | 15.6 | 34.1 | 13.8 | 0.15 | 2.38 | 5.42 |
| EEVDF | 14.6 | 27.8 | 26.0 | 0.34 | 2.22 | 4.98 |
| lavd autopower | 16.5 | 36.3 | 12.7 | 0.08 | 2.36 | 5.29 |

**scx_lavd uses ~0.15 W more package power and ~0.35 W more platform power at idle.** It shifts residency from PC8 to PC6. Starting it also woke the NVIDIA GPU (`resume ran in scx_lavd … RmIoctl`). → Stay on EEVDF. Light-load and gaming comparisons were not run.

## NVIDIA wake causes, now with call paths ([gpu-wake-log](../../configs/usr/local/sbin/gpu-wake-log))

| Cause | Call path (abridged) |
|---|---|
| Periodic, nobody using the laptop | `acpi_os_execute_deferred < acpi_ev_notify_dispatch < rm_acpi_nvpcf_notify < … < nv_indicate_not_idle < __pm_runtime_resume`. Firmware `Notify(NPCF, 0xC0)` reaches the driver's NVPCF handler, which resumes the GPU. This contradicts [research/33](33-nvidia-wake-paths.md)'s guess that this handler never fires |
| Any app opening the GPU (vulkaninfo, scx_lavd, Umbriel's EGL, Zen's media process) | `RmIoctl < rmapiAlloc… < os_ref_dynamic_power < nv_indicate_not_idle` |
| nvidia-powerd exiting | `rmapiFree… < os_ref_dynamic_power` |

Open: which EC event sends the periodic `Notify(NPCF, 0xC0)`. EC query debug logging (`dynamic_debug: file drivers/acpi/ec.c +p`) is on for this boot, to correlate with the next wakes. Also check whether the wakes stop now that nvidia-powerd is off on battery.
