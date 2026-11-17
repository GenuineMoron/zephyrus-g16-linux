# Roadmap: what is still being worked out

The guide is written only from verified understanding. This is the investigation
plan. Each area means deep-reading the relevant firmware (decompiled ACPI), driver
and kernel source, plus community and upstream research, then measuring on the
laptop. Results become findings, and findings become guide sections.

| # | Area | What we're reading and measuring | State |
|---|---|---|---|
| 1 | Firmware: sleep and power | `_PTS`/`_WAK`, Modern Standby `_DSM` (PEPD) vs what Linux calls, lid/power button/wake sources, the 171 ms `PDOD` wait on resume | Read (notes) |
| 2 | Firmware: EC and ASUS WMI | EC events, battery/charger, every ASUS WMI feature vs `asus-wmi`/`asus-armoury` support | Read (notes) |
| 3 | Firmware: devices and S0ix | Per-device power resources and `_DSD` (StorageD3Enable, TBT), NVMe behind VMD, what blocks S0i2.2 | Read (notes) |
| 4 | NVIDIA driver power | RTD3/GC6/S0ix internals, options to avoid waking an idle GPU, ACPI `_DSM` errors, Dynamic Boost | Read (notes) |
| 5 | Intel graphics and display power | i915 suspend/resume cost, PSR/Panel Replay, DC states, i915 vs xe, `intel_lpmd` errors | Read (notes) |
| 6 | Audio | CS35L56 lifecycle and upstream fix, codec resume time, crackle workaround, speaker tuning, mics | Read (notes) |
| 7 | Power stack and community | asusd/supergfxd/power-profiles/cachyos-settings conflicts, EPP/PPT per profile, charge limit, known model issues | Read (notes) |
| 8 | Observability | kdump, PMT crashlog, bpftrace, RAPL, ACPI method tracing, S0ixSelftestTool; the always-on vs on-demand stack | Read (notes) |
| 9 | Kernel, boot, hibernate | Every cmdline parameter, boot-time breakdown, LZ4/threads/image size, swap/zram, OOM handling | Read (notes) |
| 10 | Desktop experience | niri/noctalia config, input, portals, theming, fonts on OLED, UX papercuts in the logs | Read (notes) |
| 11 | Display and colour | Panel identity (EDID), P3 colour management, HDR status, 240 Hz vs VRR vs battery, OLED care | Read (notes) |
| 12 | Performance | Scheduler and hybrid cores, thermals/fans/power limits, PRIME vs MUX for games, VMD/NVMe, btrfs, memory | Read (notes) |
| 13 | Hardware features | Camera (IR?), mics, Bluetooth, Wi-Fi, USB-C/TB/HDMI per GPU, card reader, keyboard, sensors, firmware updates | Read (notes) |
| 14 | Health, logs, security | Every recurring warning explained or fixed, Secure Boot/TPM/firewall, update and rollback hygiene | Read (notes) |

First pass done: see the [research notes](research/) and the [action plan](plan.md).

## Measurements still needed

- **A night on battery** with the per-stretch standby logger, to catch the ~5 W night.
- **Idle power on battery** with the screen on: a baseline, then a measurement after each change.
- **Hibernate save/resume time** with LZ4 and a smaller image.
- **Real-world wake time:** lid open to a usable desktop.
