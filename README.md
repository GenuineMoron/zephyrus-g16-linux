# Linux on the ASUS ROG Zephyrus G16 (2024, GU605MI)

A guide to running Linux on this laptop at least as well as Windows: battery, sleep, performance, display, audio, the desktop experience, and every hardware feature. It is written for anyone with this model. Most of it should also apply to its siblings (GU605MV/MY/MZ) and other Meteor Lake + NVIDIA laptops, but the measurements here come from a GU605MI.

> **Work in progress.** This is not a finished guide yet.
>
> - **Verified:** the [findings](docs/findings/) are measured, traced to the code or firmware that causes them, and fixed or explained.
> - **Not done yet:** most areas are still being read through (firmware, drivers, kernel, tools). The [roadmap](docs/roadmap.md) lists what is still open.
> - **Pending:** sections are written up only once they are understood and verified.

Every recommendation is backed by a measurement, and every root cause is traced to code, a firmware table or a kernel trace. Guesses are labelled as guesses. If a file in `configs/` has no finding or research note explaining it, that is a bug in this repo.

## Tested setup

| | |
|---|---|
| Laptop | ASUS ROG Zephyrus G16 GU605MI (2024), BIOS 329 |
| CPU / iGPU | Intel Core Ultra 9 185H (Meteor Lake-H), Intel Arc graphics (i915) |
| dGPU | NVIDIA GeForce RTX 4070 Laptop, open kernel modules 620.70.06 |
| Display | 2560x1600 240 Hz OLED on the Intel GPU; HDMI and one USB-C port are wired to NVIDIA |
| OS | CachyOS, kernel 7.3.x, Umbriel (Wayland) + Noctalia shell, btrfs, s2idle standby |

Full inventory: [docs/hardware.md](docs/hardware.md).

## Guide outline

| Section | State |
|---|---|
| Hardware overview: what works and what doesn't | Researching |
| Installing and the base system (CachyOS) | Not written yet |
| Sleep, wake and hibernate | Partly verified: [01](docs/findings/01-hibernate-hang-cs35l56.md), [02](docs/findings/02-standby-nvidia-wakes-idle-gpu.md), [03](docs/findings/03-standby-s0ix-and-wake-timeline.md) |
| Hybrid graphics (Intel + NVIDIA) | Partly verified: [02](docs/findings/02-standby-nvidia-wakes-idle-gpu.md), [05](docs/findings/05-apps-wake-nvidia-gpu.md) |
| Battery and power management | Researching |
| Performance: CPU, thermals, gaming, storage | Researching |
| Display: OLED, colour, refresh rate, brightness | Researching |
| Audio | Partly verified: [01](docs/findings/01-hibernate-hang-cs35l56.md) |
| Desktop experience (Umbriel + noctalia; niri until 2026-11-15) | Partly verified: [04](docs/findings/04-shell-killed-by-oom.md) |
| Hardware features: camera, Wi-Fi, Bluetooth, ports, keyboard | Researching |
| System health, updates, security | Researching |
| Debugging tools and method | [docs/methodology.md](docs/methodology.md), [docs/lessons.md](docs/lessons.md) |

## Verified so far

| Area | State |
|---|---|
| Hibernate with lots of memory in use | **Fixed.** Speaker-amp firmware reload deadlocked with btrfs during hibernation: [01](docs/findings/01-hibernate-hang-cs35l56.md) |
| Lid close: standby, then hibernate | **Works.** Verified with ~21 GB in use |
| App launch speed | **Fixed.** GTK4 apps woke the RTX 4070 on every launch (+2.6 s). GTK now draws with OpenGL; games still find the GPU by themselves: [05](docs/findings/05-apps-wake-nvidia-gpu.md) |
| Standby → wake time | **Measured:** ~1.1 s (battery) / 1.7 s (AC) in the kernel. NVIDIA wakes an idle GPU on every standby: [02](docs/findings/02-standby-nvidia-wakes-idle-gpu.md) |
| Standby power | **0.86 W** over a full night on battery (~1%/h), S0i2.1 for ~100% of it. One earlier 5 W night is still unexplained; its "8% deep sleep" was a kernel counter bug: [03](docs/findings/03-standby-s0ix-and-wake-timeline.md) |
| Idle power | **Fixed locally:** asusd held the keyboard's USB chips awake, so the CPU reached its deepest idle state 0.4% of the time instead of ~65% (~0.8 W with the screen off). Patched asusd (upstream PR #404) + USB autosuspend; a lit Num Lock LED also blocks it: [06](docs/findings/06-keyboard-usb-blocks-deepest-idle.md) |
| Desktop shell robustness | **Fixed.** An out-of-memory kill no longer takes down the shell and lock screen: [04](docs/findings/04-shell-killed-by-oom.md) |
| Keyboard and hotkeys | **Done.** Fn row works like G-Helper (media keys by default, F1–F12 with Fn) through a udev hwdb remap; ROG/Aura/fan/display keys bound; the keyboard is white-only on the -QR081W, proven from its own capability report: [41](docs/research/41-guides-g-helper-keys-2026-11-16.md) |
| Keyboard backlight | **Fixed:** backlight changes failed (`-108`) while the keyboard was autosuspended; kernel patch tested (stock 4 failures, patched 0), packaged as DKMS: [42](docs/research/42-audit-2026-11-16.md) |
| Power button, idle sleep | **Done.** The power button opens the shell's power menu; on battery the laptop sleeps after 15 idle minutes (not while audio plays): [42](docs/research/42-audit-2026-11-16.md) |
| ASUS controls in the shell | **Done.** [ROG Control](https://github.com/GenuineMoron/noctalia-rog-control), a Noctalia plugin (in the Noctalia plugin store): performance modes, charge limit, graphics mode, overdrive, lighting, fans |
| NVIDIA GPU on battery | **Known issue:** the firmware notifies the NVIDIA driver on every 1% of battery, and the driver wakes the GPU for ~23 s each time (~0.45 W). NVIDIA has a fix queued for a future driver: [42](docs/research/42-audit-2026-11-16.md) |

Everything this project installed, patched or changed, and how it could be packaged: [docs/inventory.md](docs/inventory.md). All issues and their state: [docs/status.md](docs/status.md). Prioritised next steps: [docs/plan.md](docs/plan.md). Raw research notes (unverified): [docs/research/](docs/research/).

## Layout

```
configs/          files as installed, at their real paths (home/ = your $HOME)
docs/             findings (one per proven issue), roadmap, status, plan, methodology, lessons, hardware, research notes
tools/            inventory, standby tracer + analyser, EC map, Intel PMT decoder, latency harness, hibernate diagnostic module
packaging/        PKGBUILDs for patched packages (hid-asus DKMS, libdisplay-info)
upstream/         patches and reports sent (or ready to send) upstream
noctalia-plugins/ pointers to the shell plugins written for this laptop
```

## Before you copy anything

- These files were made for one GU605MI. Read the finding behind a file before installing it, and check paths, device IDs and kernel versions against your machine.
- Some changes need root, kernel parameters or out-of-tree kernel modules; the DKMS packages here are pinned to one kernel version on purpose.
- Nothing here comes with a warranty. Firmware settings (BIOS, MUX, EC) can leave a laptop needing a reset; the docs say so where it applies.

## License

Code, scripts and configuration files: [MIT](LICENSE). Documentation (`docs/`, READMEs): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Exceptions: `tools/hibtrace/` and the kernel patches in `upstream/` and `packaging/` are GPL-2.0, like the kernel code they build on; the two icons in `configs/home/.local/share/theme-accent-sync/apps/` are from WhiteSur-icon-theme (GPL-3.0, see `LICENSE.icons` there).
