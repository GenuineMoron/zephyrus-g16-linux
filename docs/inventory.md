# Inventory: everything this project changed on the laptop (2026-11-15)

Built from a scan of every file in the relevant system directories that no package owns, plus the package config files pacman reports as modified, masked units, user-level files and the kernel command line. "Repo" means the copy under [configs/](../configs/) or [tools/](../tools/).

## Short answers

- **Firmware or BIOS:** nothing was modified. The BIOS image, EC RAM, ACPI tables, CPU MSRs and Intel telemetry were all read only. BIOS settings were inspected from photos and left as they were (Fast Boot was already on).
- **Drivers:** no new drivers were written. Upstream fixes backported and installed:
  - the `hid-asus` keyboard driver (DKMS package, our patch: backlight writes reach an autosuspended keyboard);
  - the `asusd` daemon (asusctl pull request #404);
  - `libdisplay-info` (HDR from DisplayID 2.0) and an Umbriel test build with our two output fixes.
  The `vmd` NVMe fix was a DKMS package until kernel 7.3.4 shipped it.

  One kernel fix was written and build-tested but **not** installed (`intel_pmc_core`, hardware-sleep counter). One diagnostic kernel module was built for the hibernate investigation and is not installed (`tools/hibtrace`).
- **Plugins:** one, our Noctalia plugin ROG Control ([own repo](https://github.com/GenuineMoron/noctalia-rog-control)). Umbriel and the rest of Noctalia are only configured.
- **Our own software:** small shell and Python programs: sleep hooks, loggers, a health check, measurement tools. No compiled programs of our own are running.
- **Everything else** is configuration: kernel parameters, systemd/udev/logind/sleep settings, app launchers, environment variables.

## 1. Our own programs (running or triggered)

| What | Path | Purpose | Repo |
|---|---|---|---|
| Speaker-amp hibernate fix | `/usr/lib/systemd/system-sleep/30-cs35l56-hibernate` | Unbinds the CS35L56 amps around hibernate (fixes the hang, [finding 01](findings/01-hibernate-hang-cs35l56.md)) | yes |
| Keyboard USB sleep guard | `/usr/lib/systemd/system-sleep/10-asus-kbd-autosuspend` | Wakes the ASUS keyboard/Slash chips before system sleep, autosuspend after ([06](findings/06-keyboard-usb-blocks-deepest-idle.md)) | yes |
| Standby logger | `/usr/lib/systemd/system-sleep/40-sleep-stats` | Per-stretch S0ix, watts, EC flags, RAPL, details on bad stretches | yes |
| Lock before hibernate | `/usr/lib/systemd/system-sleep/50-lock-before-hibernate` | Short sleeps need no password; hibernate always comes back locked | yes |
| Profile re-send after wake | `/usr/lib/systemd/system-sleep/20-asus-profile-resend` | Writes the thermal mode back after resume (G-Helper's `SleepReset` for GU605MI: the EC can lose it) | yes |
| Lid-open guard | `/usr/lib/systemd/system-sleep/70-lid-open-ends-s2h` | Stops systemd re-suspending when the lid was opened around a battery check | yes |
| Standby window + night mode | `/usr/local/bin/sleep-window-update` + `systemd-suspend-then-hibernate.service.d/10-battery-window.conf` | Sizes the instant-wake window from measured drain; on battery hibernates at 01:00–07:00 | yes |
| Wake policy | `/usr/local/bin/wakeup-policy.sh` + `wakeup-policy.service` | Disables unneeded ACPI wake sources (stray-wake guard) | yes |
| GPU wake logger | `/usr/local/sbin/gpu-wake-log` + service | Logs every NVIDIA wake with the call path and the apps holding it | yes |
| PSR watcher | `/usr/local/sbin/psr-watch` + service | Logs Panel Self Refresh changes and the code path that disabled it | yes |
| Health check | `/usr/local/bin/g16-doctor` + `g16-doctor.service`/`.timer` + pacman hook `99-g16-doctor.hook`; optional `/etc/default/g16-doctor` | Checks after updates and 5 min after boot that every fix is still in place: the SSD fix (by disassembling `vmd_irq`, so stock kernels with the fix pass), boot options, hibernate offset, amp hook, stale key-remap hwdb, timers that will never fire, failed units, GPU asleep, backups. Silent when healthy | yes |
| Restart into Windows | `/usr/local/bin/reboot-to-windows` + `sudoers.d/50-reboot-to-windows` | Sets UEFI BootNext; used by the Noctalia power menu | yes |
| Keyboard light timeout | `~/.local/bin/kbd-light-idle` + Noctalia idle behavior `keyboard-light` | Light off after 60 s idle, back on input (Armoury parity, ~0.5 W) | yes |
| Power button → power menu | `~/.config/systemd/user/power-key-menu.service` + Umbriel `XF86PowerOff` binding | Holds logind's `handle-power-key` lock while Noctalia runs, so a press opens the session menu; logind's default applies at the greeter ([42](research/42-audit-2026-11-16.md)) | yes |
| Sleep on battery when idle | `~/.local/bin/idle-sleep` + Noctalia idle behavior `sleep-on-battery` (900 s) | Suspend-then-hibernate after 15 idle minutes on battery, unless audio plays or a sleep block is held ([42](research/42-audit-2026-11-16.md)) | yes |
| Shell auto-relock | `~/.local/bin/noctalia-relock-if-locked` + `~/.config/systemd/user/noctalia.service` | Noctalia as a restartable service that re-locks if the session was locked ([04](findings/04-shell-killed-by-oom.md)) | yes |
| Game power | `/usr/local/sbin/game-governor` + `game-governor.service` (always on; detects Proton games by their presents) + `~/.config/game-env/*.env` + `~/.config/environment.d/57-proton-game-defaults.conf` + `tools/game-capture` | Frame target per game, efficient start, Performance only while it measurably helps; no launch wrappers ([44](research/44-game-power-governor.md)) | yes |

## 2. Patched upstream software (installed)

| Component | How installed | Fix | Until |
|---|---|---|---|
| ~~`vmd` kernel module~~ | ~~`vmd-mtl016-dkms`~~ **removed 2026-11-15** | 7307899e381c is in linux-cachyos 7.3.4 (stock `vmd_irq` takes the lock; ChangeLog-7.3.4) | Done ([40](research/40-refresh-and-review-2026-11-15.md)) |
| `umbriel` | `/usr/local/libexec/umbriel-test` via `~/.config/systemd/user/umbriel.service.d/90-test-build.conf` (self-removes on failure) | umbriel #818 (VRR retry storm) + #819 (frame retry backoff), on main `2572005a` | Both PRs merged and packaged |
| `libdisplay-info` | local package 0.3.0-1.3 | DisplayID 2.0 HDR metadata, so HDR works on the ATNA60DL01 ([37](research/37-umbriel-hdr.md)) | Upstream MR 210 released |
| `asusd` | `/usr/local/libexec/asusd-pr404` via `/etc/systemd/system/asusd.service.d/50-pr404.conf` | asusctl PR #404: hidraw opened per write so the keyboard chips can sleep ([06](findings/06-keyboard-usb-blocks-deepest-idle.md)) | Arch ships asusctl with PR #404 (the health check warns on any asusctl update) |
| `hid-asus` | `hid-asus-wake-dkms` (local package, `BUILD_EXCLUSIVE_KERNEL` 7.3.4-1; source `packaging/hid-asus-wake-dkms`) | Takes a runtime-PM reference around the worker's backlight/Fn-lock writes, so they reach an autosuspended keyboard (stock: `-108`) | Upstream patch tested, awaiting a Signed-off-by |

Not installed, ready for upstream: `upstream/0001-intel-pmc-hw-sleep-u32-truncation.patch`; draft CS35L56 thaw patch in research/25.

## 3. Configuration changes

**Kernel command line** (`/etc/default/grub`, modified):
- `quiet splash loglevel=3 rd.udev.log_level=3 vt.global_cursor_default=0`: silent boot.
- `nowatchdog`.
- `nvidia-drm.modeset=1 nvidia-drm.fbdev=1`.
- `i915.enable_dpcd_backlight=3`: OLED brightness over DPCD.
- `nvidia.NVreg_PreserveVideoMemoryAllocations=0 nvidia.NVreg_DynamicPowerManagement=0x02 nvidia.NVreg_EnableS0ixPowerManagement=1`.
- `resume=UUID=… resume_offset=…`: hibernate to the btrfs swapfile.
- `pcie_aspm=force pcie_aspm.policy=powersupersave`.
- `efi_pstore.pstore_disable=0 pstore.kmsg_bytes=32768`: crash logs survive a hang.

**Boot:**
- `/etc/mkinitcpio.conf.d/99-hybrid-slim.conf`: initramfs 238 → 26 MB, with `vmd i915` early.
- GRUB hidden menu, 1 s.
- Plymouth `bgrt` theme.

**Sleep and power:**

| File | Setting |
|---|---|
| `/etc/systemd/logind.conf.d/10-lid.conf` | Lid → suspend-then-hibernate; docked → ignore |
| `/etc/systemd/sleep.conf.d/10-hibernate-delay.conf` | `SuspendEstimationSec=1h`, fallback delay |
| `/etc/modprobe.d/blacklist-intel-th.conf` | Intel Trace Hub off (it blocked S0i2.1) |
| `/etc/modprobe.d/asus-fnlock.conf` | Fn-lock default off |
| `/etc/udev/rules.d/71-asus-kbd-autosuspend.rules` | Keyboard/Slash chips autosuspend |
| `/etc/udev/rules.d/80-nvidia-pm.rules` | NVIDIA runtime PM `auto` |
| `/etc/udev/rules.d/61-intel-igpu-symlink.rules` | `/dev/dri/intel-igpu` for the greeter |
| Masked units | `nvidia-suspend/resume/hibernate/suspend-then-hibernate.service` (caused `chvt 63` console flashes), `power-profiles-daemon.service` (asusd owns profiles) |
| `/etc/asusd/*.ron` | AC Balanced, battery Quiet, 80% charge limit, Aura static amber, Slash off |
| `/etc/systemd/system/nvidia-powerd.service.d/10-ac-only.conf` + `/etc/udev/rules.d/81-nvidia-powerd-ac-only.rules` | NVIDIA Dynamic Boost daemon only on the charger (it ran on battery all day, 13 wake-ups/s) |

**Desktop:**
- `~/.config/environment.d/50-gtk-gl-renderer.conf`: `GSK_RENDERER=gl` (GTK stops waking the dGPU, [05](findings/05-apps-wake-nvidia-gpu.md)).
- `~/.config/environment.d/60-session-apps.conf`: Wayland env for Electron/Qt, cursor.
- Noctalia `settings.toml`:
  - apps run as systemd services;
  - `ui_scale`;
  - MRU window switcher;
  - idle `keyboard-light`.
- `~/.local/share/applications/zen.desktop` override: Zen sees only Mesa EGL and the Intel DRM device. Its media process had been opening the RTX 4070.
- **Editors (2026-11-17):** Quiet.md (Markdown and notes; AppImage v0.1.13 in `~/.local/share/quiet-md`, checksum and minisign signature verified, self-updating; its launcher sets `VK_DRIVER_FILES` to Intel's Vulkan driver so the RTX 4070 stays asleep) and GNOME Text Editor (text and code; Geist Mono 11, line numbers, 4-space indents). `~/.config/environment.d/52-webkit-vblank-timer.conf` keeps any WebKitGTK view from waking the RTX 4070 ([05](findings/05-apps-wake-nvidia-gpu.md)).
- **Umbriel** (the only session since 2026-11-15; niri, used before, is retired):
  - `~/.config/umbriel/config.toml`: Intel-only (the NVIDIA card stays asleep; HDMI and the NVIDIA USB-C port can't drive a monitor), 240 Hz, HDR auto, VRR off (umbriel#809), factory ICC, no blur, keybinds, Num Lock left off;
  - `~/.config/systemd/user/umbriel.service.d/10-intel-only-egl.conf`: the compositor itself uses Mesa EGL only;
  - the factory ICC copied to `~/.local/share/icc/`.

**Other:**
- A network-mount health-check timer: the interval was raised from 2 to 10 min. Lesson (2026-11-16): an empty `OnUnitActiveSec=` in a drop-in resets every trigger, `OnBootSec` included, so the timer never ran; `g16-doctor` now flags timers that will never fire. Its script no longer mounts idle shares, which had defeated `x-systemd.idle-timeout`.
- `coredump.conf.d/10-limit.conf`.
- `resolved.conf.d/10-no-mdns-llmnr.conf`.

## 4. Temporary items still in place (remove when done)

| Item | Why it's there |
|---|---|
| `/etc/tmpfiles.d/zz-pm-debug.conf` | `pm_debug_messages=1` (logs every wake) |
| `/etc/modprobe.d/zz-pmc-s0ix-diagnosis.conf` | `warn_on_s0ix_failures=1` |
| `/etc/tmpfiles.d/zz-pmc-latch.conf` | PMC latch mode for diagnosis |
| `/var/backups/retired-2026-11-16/` (root only) | The old `*.bak-*` copies from /etc and /usr/local and the host-named health check, moved there 2026-11-16. Delete when nothing is missed |
| `~/.local/share/archive/desktop-leftovers-2026-11-15/` | Everything removed on 2026-11-15 (KDE/Plasma configs, old themes, Alacritty, Firefox profile, psd, supergfxd.conf, old VMD sources, the August drain script). Delete once nothing is missed |
| `rust` package | Build dependency for asusd (can stay or go) |
| `~/sleeplab/` | Raw research, downloads, traces (sanitised copies live in this repo) |

## 5. Duplicates and overlaps

- **Resolved 2026-11-16:** the health check is installed as `g16-doctor`, the same file as in this repo (machine-neutral; the backup stamp path lives in `/etc/default/g16-doctor`).
- **Resolved 2026-11-15:** VLC (mpv), Firefox (Zen), Alacritty (Ghostty), Gwenview (Loupe), Ark (Nautilus), Filelight (Baobab), KCalc (launcher `/calc`), glances (btop), mate-polkit and bluedevil (Noctalia), supergfxd (asusd), Lutris/ProtonUp-Qt/Goverlay (Faugus/ProtonPlus), the old standby script ([40](research/40-refresh-and-review-2026-11-15.md)).
- **Three loggers with the same pattern** (`gpu-wake-log`, `psr-watch`, the sleep logger): a private ftrace instance, a kprobe and a journal tag. They could become one `g16-telemetry` service. They are small and independent, so this is optional.
- **Resolved 2026-11-15:** the Switch 2 controller driver starts only when the controller is plugged in (`53-procon2-driver-on-demand.rules`), instead of running permanently at 53 wake-ups/s.
- **Wake-source policy in two styles:** a shell script writing `/proc/acpi/wakeup`, and udev rules for USB. → Express it all as udev rules plus one tmpfiles line.
- **GPU isolation configured three times:** Umbriel `[drm]`, the Umbriel EGL drop-in, and the Zen launcher override. Each is needed (compositor and app level), but they should be documented together. A single GPU-policy section of the guide is to write.
- **Research notes in two places:** `~/sleeplab/research` (raw, may contain personal paths) and `docs/research` (sanitised copies). The repo copy is canonical for others.

## 6. Packaging this up

Proposed shape, for Arch/CachyOS first:

1. **`zephyrus-g16-tuning`** (one PKGBUILD in `packaging/`). It installs only to package-owned `/usr` locations, so pacman tracks and removes everything cleanly:
   - sleep hooks → `/usr/lib/systemd/system-sleep/`;
   - services and drop-ins → `/usr/lib/systemd/system/`;
   - udev rules → `/usr/lib/udev/rules.d/`;
   - modprobe → `/usr/lib/modprobe.d/`;
   - tmpfiles → `/usr/lib/tmpfiles.d/`;
   - `environment.d` defaults → `/usr/lib/environment.d/`;
   - user units → `/usr/lib/systemd/user/`;
   - scripts → `/usr/bin` and `/usr/lib/zephyrus-g16/`;
   - `g16-doctor` plus its pacman hook.

   Every hook first checks the DMI product name (`GU605MI`, later siblings), so the package is harmless on other machines. Kernel parameters can't be set by a package: a `g16-doctor --fix-cmdline` helper (or post-install message) shows the exact GRUB line.
2. **Separate packages for patched upstream code**, each removed when upstream ships the fix:
   - `vmd-mtl016-dkms` (retired: kernel 7.3.4 has the fix), `hid-asus-wake-dkms` (exists);
   - `asusctl-pr404` (or a `asusd` override package);
   - optionally `intel-pmc-hwsleep-dkms`.
3. **User-level defaults** as an opt-in `g16-user-setup` script (Noctalia idle keyboard light, Zen override, Umbriel config), not forced by the package.
4. **Non-Arch:** the same files with a `Makefile` (`make install` / `make uninstall`) using the same paths.

## 7. Upstream contributions (help others too)

| Where | What | State |
|---|---|---|
| linux (platform-driver-x86) | `intel_pmc_core` hardware-sleep time truncated to 32 bits | Patch ready; needs one >72 min standby on the patched module |
| asusctl #404 | "Tested on GU605MI": PC10 0.4% → 65%, our autosuspend guard for #690 | Test report posted 2026-11-15; follow-up posted 2026-11-16 (backlight `-108` with the kernel A/B; lit Num Lock blocks autosuspend) |
| asusctl #744 (GitLab, another owner's report) | Same model's idle-power report: root cause is the keyboard chips held awake | Comment to post; needs a GitLab account |
| Cirrus / linux-sound | CS35L56 firmware reload deadlocks hibernate under memory pressure | Draft in research/25 |
| NVIDIA open-gpu-kernel-modules | Every system suspend resumes an idle RTD3 GPU (+2.7 s); NPCF/ACPI notifies wake it | To write ([research/33](research/33-nvidia-wake-paths.md)) |
| systemd | suspend-then-hibernate re-suspends after a battery-check wake without checking the lid | To write |
| Zen / Firefox | The media process initialises NVIDIA EGL and opens `/dev/nvidia0` on hybrid laptops | To write, after verifying the override |
| Umbriel | The nested compositor opens NVIDIA EGL despite rendering on the iGPU | To verify in a real session first |
| Umbriel #818, #819 | VRR retry storm; frame retry backoff | Open, checks green |
| Noctalia [#5395](https://github.com/noctalia-dev/noctalia/pull/5395) | Plugin stream workers wake 10×/s (100 ms poll); pidfd wait + cancel hang fix | PR opened 2026-11-16 (rebased on c1a7283, tests re-run), checks green |
| Noctalia [#5397](https://github.com/noctalia-dev/noctalia/issues/5397) | Lock-keys OSD polls LED sysfs every 200 ms: main thread 10.5 → 5.8 wake-ups/s with it off | Bug filed 2026-11-16 with the A/B and two fixes (pause while input-idle; compositor IPC) |
| noctalia-dev/community-plugins #1453 | ROG Control ([own repo](https://github.com/GenuineMoron/noctalia-rog-control)) | **Merged 2026-11-16** after the 1.3.0 review fixes. The maintainer set the store version to 1.0.0 (new plugins aren't bumped in review), so the store's 1.0.0 is our 1.3.0 code. The next store update should be 1.4.0, above both |
| asusctl [#478](https://github.com/OpenGamingCollective/asusctl/issues/478) | Single-colour keyboards look like RGB (same board name as RGB SKUs) | Filed 2026-11-16: detect via the 0x5d capability report |
| asusctl [#477](https://github.com/OpenGamingCollective/asusctl/issues/477) | Platform profile not re-sent after resume (G-Helper SleepReset for GU605MI/MV/CR) | Filed 2026-11-16; local `system-sleep/20-asus-profile-resend` meanwhile |
| linux-input (hid-asus) | Backlight/Fn-lock writes fail with `-108` on an autosuspended keyboard | Patch `upstream/drafts/0001-HID-asus-wake-the-keyboard-for-feature-reports.patch`: A/B tested (stock 4× `-108`, patched 0), applies to hid.git for-next. Needs a Signed-off-by, then `git send-email` |
