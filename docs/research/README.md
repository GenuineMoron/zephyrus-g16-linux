# Research notes (raw, unverified)

These are raw working notes from the investigation, written with an AI assistant. They are kept close to how they were written, and they are unverified unless a finding in [../findings/](../findings/) says otherwise.

The first notes come from two waves of deep reading of this laptop on 2026-11-14 (notes 01–14, then 15–26 including the Windows install, the BIOS image and Intel telemetry), done read-only. They cover the decompiled firmware (ACPI), the driver and kernel source, the system configuration and logs, and community/upstream reports. Each file is one area of the [roadmap](../roadmap.md).

**Treat them as leads, not facts.** They can contain mistakes. A claim becomes part of the guide only after it is checked on the laptop and written up as a [finding](../findings/). Several claims have already been corrected by measurement. For example, note 01's guess that the 171 ms resume delay is `P0DL` is contradicted by the standby trace in finding 02: the 35 ms `P0DL` wait shows up on both entry and exit, and the 171 ms wait only on exit.

| Note | Area |
|---|---|
| [01](01-acpi-sleep-power.md) | Firmware: sleep, Modern Standby `_DSM`, lid/wake, ACPI Timer |
| [02](02-ec-asus-wmi.md) | Firmware: embedded controller, battery, ASUS WMI features vs Linux drivers |
| [03](03-devices-pcie-s0ix.md) | Firmware: device power objects, NVMe/VMD, S0ix blockers |
| [04](04-nvidia-power.md) | NVIDIA driver power management |
| [05](05-intel-graphics-display.md) | Intel graphics, panel power features, i915 vs xe, intel_lpmd |
| [06](06-audio-cs35l56.md) | Audio, CS35L56 amps, draft upstream bug report |
| [07](07-asus-cachyos-power-stack.md) | asusd/supergfxd/cachyos-settings, profiles, charge limit, community |
| [08](08-observability-tools.md) | Observability and debugging tools |
| [09](09-kernel-boot-hibernate.md) | Kernel cmdline, boot time, hibernate speed knobs, memory |
| [10](10-desktop-ux.md) | Desktop experience (niri + noctalia) |
| [11](11-display-color.md) | OLED panel, colour, HDR, refresh rate |
| [12](12-performance.md) | CPU scheduling, thermals, power limits, storage, memory |
| [13](13-hardware-features.md) | Every hardware feature: status and gaps |
| [14](14-health-logs-security.md) | Log audit, security posture, maintenance |
| [15](15-windows-armoury-crate.md) | Windows: Armoury Crate per-mode settings, OLED care, keyboard, battery |
| [16](16-windows-power-framework.md) | Windows: power plans, ASPM per source, Intel PPM/EPP tables, DTT, PEP constraints, energy reports |
| [17](17-windows-display-audio-camera.md) | Windows: factory ICC profile, Cirrus/Dolby speaker tuning, IR camera extension units |
| [18](18-bios-hidden-settings.md) | BIOS image: setup-option extraction (partial), NVRAM diffs, CPU lock MSRs |
| [19](19-boot-chain-fastboot.md) | Boot chain: FPDT timeline, Fast Boot, GRUB vs UKI, initramfs, Secure Boot |
| [20](20-intel-pmt-telemetry.md) | Intel PMT telemetry decoder, RAPL, PC10 blockers |
| [21](21-firmware-versions.md) | Firmware versions of every component vs latest |
| [22](22-ec-hotkeys-als.md) | EC live field map, hotkey codes, (no) ambient light sensor, battery cycles |
| [23](23-ux-latency-harness.md) | Measuring perceived latency: wake-to-first-frame, app launch, frame pacing, boot |
| [24](24-windows-feature-parity.md) | Every Windows/ASUS feature vs its best Linux equivalent, NPU |
| [25](25-kernel-patches.md) | Draft upstream patches: ACPI Timer, asus-wmi keys, CS35L56 thaw |
| [26](26-app-workflow-acceleration.md) | Creative workflow: browser decode, screen share, Resolve, OBS, fonts |
| [27](27-windows-standby-drain.md) | Windows Modern Standby drain on this laptop (1241 sessions from the event log) |
| [28](28-bios-settings.md) | BIOS settings as shipped (from photos of the setup screens) |
| [29](29-keyboard-touchpad-wake.md) | Why keyboard/touchpad can't wake standby on Linux (ACPI GPE, i2c-hid, Windows device settings) |
| [30](30-i915-psr-off.md) | i915 code paths that can leave PSR off without a reason |
| [31](31-screen-on-idle-ab.md) | Controlled screen-on idle A/B: keyboard light, 60 vs 240 Hz, keyboard chips; NPCF notifies that wake the dGPU |
| [32](32-ghelper-asus-wmi-map.md) | G-Helper's ASUS WMI map vs Linux: power limits on battery, missing controls |
| [33](33-nvidia-wake-paths.md) | NVIDIA open driver: why the GPU wakes on suspend, ACPI notifies, periodic |
| [34](34-scheduler-power.md) | sched_ext (scx_lavd/bpfland) and intel_lpmd for battery: research + A/B protocol |
| [35](35-umbriel.md) | Umbriel compositor as a second session: config, GPU isolation, known issues |
| [36](36-screen-on-blockers-and-wakeups.md) | Screen-on PC10 blockers (timer wakes, not display), per-process wake-ups, scx_lavd vs EEVDF, NVIDIA wake call paths |
| [37](37-umbriel-hdr.md) | HDR under Umbriel: root cause, fix, verification |
| [38](38-theme-wallpapers-plugins.md) | Theme, daily photo wallpapers, keyboard colour, Noctalia plugins |
| [39](39-rog-control-architecture.md) | ROG control on Noctalia: architecture |
| [40](40-refresh-and-review-2026-11-15.md) | System refresh, software review and idle audit |
| [41](41-guides-g-helper-keys-2026-11-16.md) | Similar guides and G-Helper reviewed; white keyboard confirmed by its capability report; G-Helper-style Fn-lock (hwdb); GU605MI sleep-reset hook; SearXNG; cifs-utils regression |
| [42](42-audit-2026-11-16.md) | Audit: health-check false alarm and dead mount timer fixed, `g16-doctor` in the repo, ROG Control 1.3.0 (maintainer review + 11 more fixes), idle wake-ups by source (Noctalia lock-keys 200 ms poll) |
| [43](43-elden-ring-umbriel.md) | Elden Ring under Umbriel: Xwayland white screen and Wayland swapchain crash, both from VK_EXT_present_timing (NVIDIA 620 + PRIME); per-game env via gamemode-external |
| [44](44-game-power-governor.md) | Game power: frame target per game (divisors of 240), efficient Balanced + balance_performance start, a governor that boosts to Performance only while it measurably helps; game-capture tool |
