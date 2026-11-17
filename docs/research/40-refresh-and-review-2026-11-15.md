# 40: System refresh, software review and idle audit (2026-11-15)

Goal: bring everything important up to date, review the installed software against what is currently best, and reach the cleanest, most efficient setup. This note records what changed, the measurements behind each decision, and what is still open.

## Updates

- **Repo upgrade:** 160 packages (pre/post snapper snapshots), including:
  - `linux-cachyos` 7.3.3 → 7.3.4 and `nvidia-open` modules;
  - Noctalia 5.4.1 → 5.5.0;
  - Zen 1.24.2b, bluez 5.88, Qt 6.12.0-5, dbus 1.16.4, openssh 10.6p2.
- **Kept local packages:** `libdisplay-info` 0.3.0-1.3 (the HDR patch; the repo has 1.1). Umbriel, wlroots and libdisplay-info had no updates, so the HDR setup and the Umbriel test build were unaffected.
- **AUR:**
  - `noctalia-greeter-git` r324: 16 commits, including first-configure sizing, output repositioning and an auth cancel fix.
  - Also other user apps, and `bitwarden-bin` 2026.10.3 (staged, see open items).
  - Every PKGBUILD change was reviewed first; sources point at upstream releases with pinned checksums.
- **Bluetooth:** `/etc/bluetooth/main.conf.pacnew` merged, keeping the three LE connection settings (MinConnectionInterval 7, MaxConnectionInterval 9, ConnectionLatency 0).
- **Firmware:**
  - fwupd offers only the UEFI dbx (Secure Boot revocation list), which does nothing while Secure Boot is off, so it was skipped.
  - BIOS GU605MI.329 is still the newest (ASUS support API, every region).
  - Microcode 0x2b is the newest for Meteor Lake.
- **Noctalia 5.5:** running since 23:12 via the upstream `Type=notify` service layout (below).
- **Umbriel test build:** rebuilt on main `2572005a` plus #818 and #819 (all 157 tests pass). It is installed at `/usr/local/libexec/umbriel-test` and takes effect at the next login.

## The VMD fix is upstream

`linux-cachyos` 7.3.4 contains 7307899e381c ("PCI: vmd: Flush DMA writes before handling MSI on Meteor Lake").
- **Evidence:**
  - The stock 7.3.4 `vmd.ko` `vmd_irq` calls `_raw_spin_lock`/`_raw_spin_unlock`, exactly like our patched build.
  - It is listed in kernel.org's ChangeLog-7.3.4.
- **Done:** `vmd-mtl016-dkms` removed and the initramfs rebuilt; it now holds the stock `kernel/drivers/pci/controller/vmd.ko.zst`. Sources are kept in `~/.local/src/vmd-mtl016-dkms`.
- **LTS fallback:** the 6.18 LTS kernel still lacks the fix (not in 6.18.63 or its stable queue).

## Software review: decisions

Three reviews: desktop and core tools, applications, and platform/power. Decisions:

| Area | Before | Now | Why |
|---|---|---|---|
| Terminal | Alacritty | **Ghostty 1.4** | Native GTK tabs and splits; Noctalia recolours it live. Measured: same idle cost (below) |
| Images | Gwenview | **Loupe** | libadwaita; opens HEIC/AVIF/JXL (glycin loaders) |
| PDF | Zen | **Papers** | GNOME's document viewer since 49 |
| Disk usage | Filelight | **Baobab** | libadwaita |
| Archives | Ark | Nautilus (built in) | Already the default for zip/7z/tar |
| Calculator | KCalc | Noctalia launcher `/calc` | |
| Partitions | KDE Partition Manager | (GNOME Disks or GParted on demand) | Rarely used; pulled in kpmcore |
| Monitors | glances + btop | btop | Duplicate |
| Video | mpv + VLC | **mpv** | mpv has the HDR path |
| Browser | Zen + Firefox | **Zen** | Firefox only served as the mailto handler (now Thunderbird) |
| Office | LibreOffice | (Google Docs) | Preference |
| Polkit | mate-polkit | **Noctalia's agent** (`[shell] polkit_agent = true`) | Themed prompts |
| Unused helpers | bluedevil, swayidle, xsettingsd | removed | None were running |
| Themes | WhiteSur GTK/icons, Kora, char-white | removed | GTK/KDE/GTK2 configs repointed first (below) |
| Gaming | Lutris, ProtonUp-Qt, Goverlay | **Faugus, ProtonPlus** | See the next paragraph |
| Profile sync | profile-sync-daemon | removed | It only synced Firefox profiles (not Zen) |
| Also removed | OBS, glaxnimate, GIMP, Inkscape, Krita, Scribus, CUDA toolkit (5.3 GB), asusctltray, rog-control-center, supergfxctl, and other user apps | | Unused; CUDA was unused because Blender ships an sm_89 cubin |

**Gaming:**
- CachyOS's own `cachyos-gaming-applications` bundle ships Lutris, Faugus and Heroic side by side, so CachyOS doesn't prefer one.
- The Lutris library was empty and ProtonUp-Qt had installed no tools.
- Faugus and ProtonPlus depend on gtk4 and libadwaita (verified from their packages).
- ProtonUp-Qt pulled in qt6-tools, the source of the Qt Designer/Linguist/Assistant launcher clutter.

**Kept:**
- KDE Connect, Blender, Resolve, and other user apps.
- pavucontrol (as a fallback).

## Theme and fonts

- **Stale references fixed:**
  - `~/.config/gtk-{3,4}.0/settings.ini` and `~/.gtkrc-2.0` still named WhiteSur-Dark and Kora.
  - `kdeglobals` had `Icons/Theme=Kora`, a WhiteSur look-and-feel package and a missing Kvantum style.
  - `kcminputrc` named the WhiteSur cursor.
  - All now point at adw-gtk3-dark, Adwaita-Accent and capitaine-cursors.
  - The KDE `colors.css` import was removed from `gtk.css`; Noctalia only manages its own `noctalia.css` import.
- **Icons: a lesson.**
  - Noctalia resolves app icons through the gsettings theme first, then the `settings.ini` themes. Kora in `settings.ini` was silently supplying the app icons Adwaita lacks.
  - Removing it left apps on their own detailed vendor icons; Files' own icon is a filing cabinet.
  - Adwaita-now, Kora, Papirus and WhiteSur were compared on the installed apps. Adwaita stays, with three picks:
    - a folder-style Files icon in the accent colour;
    - WhiteSur's Ghostty and DaVinci Resolve icons.
  - `theme-accent-sync` now copies `~/.local/share/theme-accent-sync/apps/*.svg` into `Adwaita-Accent/scalable/apps`. It also builds `org.gnome.Nautilus.svg` from the accent folder, and rebuilds when the accent or the picks change.
- **Fonts:**
  - fontconfig `sans-serif` and `system-ui` → **Inter**; `monospace` and `ui-monospace` → **Geist Mono** 1.9.2 (AUR `otf-geist-mono`, Vercel's release zip).
  - gsettings monospace → "Geist Mono 10". Ghostty uses Geist Mono 12.
- **Wallpaper colours:** the community templates bat, fzf and micro were added (obsidian dropped). The fzf snippet appends to a universal variable on every source, so fish reads its `--color=` flags into a global instead.
- **Shell:** zoxide (`z`) and fzf key bindings (Ctrl-R, Ctrl-T, Alt-C).
- **Cursor:** capitaine stays.
- **Launcher:** 13 developer, test and setup entries hidden with `NoDisplay` overrides (`configs/home/.local/share/applications/README.md`).

## Keyboard colour: not reaching the LEDs

- **Symptom:** the keyboard stays white whatever the ROG panel or the theme sets.
- **Tests, watching the keyboard:**

| Test | asusd state | Keyboard |
|---|---|---|
| `busctl set-property … LedModeData` red | applied, then the theme re-applied green (expected) | white |
| `asusctl aura effect static -c 0000ff` | `LedModeData` blue | white |
| USB autosuspend off (`power/control=on`), magenta | magenta | white |
| asusd restarted (re-init), magenta | magenta | white |
| firmware path `kbd_rgb_mode` "1 0 255 0 255 0" | - | white |
| `rainbow-cycle` | `LedMode` 2 | pulsing **white** |
| Fn+F4 | nothing bound in Umbriel | no change |

- **What it shows:**
  - asusd writes three 64-byte HID reports per change (bpftrace on `hidraw_write`), so commands do reach the hardware.
  - Every effect runs, but only in white. That is how a white-backlit keyboard renders RGB effects.
  - ASUS's US spec lists every GU605 SKU as "1-Zone RGB", but other regional pages list a GU605M "Single Light" variant.
- **Open:** check in Windows Armoury Crate (colour wheel or brightness only?), or the full model code on the bottom sticker. If Windows can colour it, it is a Linux driver bug worth an asusctl issue with this table; if not, the plugin's colour controls are moot on this unit.

## supergfxd retired; graphics switching through asusd

- **Why:** upstream asusctl deprecated supergfxd; graphics mode is asusd's `dgpu_disable` and `gpu_mux_mode` attributes.
- **How asusd does it:**
  - asusd queues GPU writes (`QueuedGpuValue`, -1 when nothing is waiting); `CurrentValue` stays the running mode.
  - `asus-shutdown.service` applies the queue at shutdown, after `prepare_nvidia_for_gpu_firmware_writes`. It was **disabled** here and is now enabled. Idle cost: 0 wake-ups/s, 5 MB.
- **Removed:** supergfxctl (about 5 wake-ups/s), and `/etc/supergfxd.conf` archived. Our own `80-nvidia-pm.rules` duplicates its NVIDIA runtime-PM rule, and the dGPU still reaches `suspended`.
- **ROG Control 1.1.0:**
  - Without supergfxd, the panel offers Eco/Standard/Ultimate from asusd. A queued value shows as pending with Restart and Cancel; Cancel writes the running value back, and asusd clears the queue.
  - Tested by queuing Ultimate and cancelling: the state went to `pending = 5, action = reboot`, then back, and `QueuedGpuValue` returned to -1.
  - supergfxd is still used where it runs.

## ROG Control: its own public repository

- [GenuineMoron/noctalia-rog-control](https://github.com/GenuineMoron/noctalia-rog-control) (MIT, fresh history, topics set, release v1.1.0).
- The live plugin symlink now points at `~/Projects/noctalia-rog-control`.
- This repo keeps a pointer in `noctalia-plugins/README.md` instead of a copy.
- Store PR #1453 was updated to 1.1.0; both checks pass.

## GTK apps waking the RTX 4070 (fixed)

- **Finding:** the gpu-wake log blamed Loupe. A clean A/B on a fresh process (Loupe is single-instance, so an existing window must be closed first):
  - with the session environment (`GSK_RENDERER=gl`, Mesa-only EGL), Loupe opened **14 `/dev/nvidia*` handles and woke the dGPU**;
  - with `GDK_DISABLE=vulkan` it opened 0, and the dGPU stayed suspended.
- **Cause:** GTK 4.24 still creates a Vulkan instance in some apps despite the GL renderer.
- **Fix:** added to `~/.config/environment.d/50-gtk-gl-renderer.conf` and applied to the running manager with `systemctl --user set-environment`. It is GTK-only; games still see NVIDIA Vulkan.
- **Not affected:** Papers, Baobab, Nautilus and Ghostty did not open NVIDIA.
- **Left alone:** the ArtCraft launcher (Electron AppImage) also woke the dGPU twice that day. Its NVIDIA-only Craft apps inherit its environment, so forcing it to Intel could break them.

## Terminal A/B (Alacritty vs Ghostty)

- **Method:**
  - bpftrace counted scheduler switches of every thread in the process (accurate when threads exit), plus CPU from `/proc/<pid>/stat`.
  - 3 × 30 s per case, the panel off, one window with an idle fish.
  - A first attempt that matched processes by name was discarded: it caught another Alacritty window that was in use.

| Case | Wake-ups/s | CPU | RSS |
|---|---|---|---|
| Alacritty, 1 window | 0.00 | 0% | 85 MiB |
| Ghostty, 1 window | 0.03 (1.27 in the first run while settling) | 0% | 140 MiB |
| Ghostty resident, no window | 0.00–0.03 | 0% | 49 MiB |

- **Decision:** equal on power, +55 MiB per window. The rule was "switch only if no worse", so Ghostty it is.
- **Done:**
  - Umbriel `Mod+Return` → `spawn ghostty` (reloaded live).
  - Dock pin replaced.
  - The Noctalia alacritty template removed; Alacritty uninstalled, its config archived.
  - Noctalia's own terminal fallback order already prefers ghostty.
- **Not affected:** neither terminal woke the dGPU.

## Noctalia 5.5 service layout

- **The service:** `~/.config/systemd/user/noctalia.service` now follows upstream: `Type=notify`, `After=umbriel.service`, `Before=graphical-session.target`, `WantedBy=umbriel-session.target`. That way XDG autostart apps start only after the tray is listening.
- **Kept:** `Restart=always`, the relock `ExecStartPost`, `OOMPolicy=continue` and `Slice=session.slice`.
- **Live check:** restarted while locked at 23:12. The service went active with 0 restarts, the lock screen came back, the polkit agent registered and all four plugins loaded. Umbriel Companion auto-updated to 1.3.0.

## Idle audit: Noctalia's stream threads

Locked, panel off, 60 s, `sched_wakeup` by task:

| Process | Wake-ups/s | Note |
|---|---|---|
| noctalia | 52.5 | see below |
| claude | 49.4 | the AI assistant used for the audit |
| tailscaled | 15.7 | |
| ananicy-cpp | 14.6 | |
| nvidia-powerd | 13.5 | on AC by design |
| umbriel-test | 10.2 | |

- **Noctalia:** 4 threads at exactly 10.0/s, each in `poll(fds, 2, 100)`, plus the main loop at about 10/s. The 4 are the long-lived plugin streams:
  - Umbriel Companion's `umbriel subscribe`;
  - ROG Control's asusd and UPower `gdbus monitor`;
  - phone-connect's KDE Connect monitor.
- **Cause:** `src/system/process.cpp` waits `kProcessPollInterval` (100 ms) to `waitpid(WNOHANG)` and check the cancel flag. Our earlier "streams cost about 0" measurement looked only at the gdbus processes.
- **Fix written and tested** (branch `perf/event-driven-process-wait` on GenuineMoron/noctalia, commit 1a9b70a on main f04c320):
  - The child's pidfd joins the poll set, so the worker sleeps until output, exit or the deadline. Cancel is still the atomic flag, checked once a second while idle; there is no API change.
  - Measured on an idle cancellable stream: **59 → 6** scheduler switches in 6 s.
  - It also fixes a hang: a child that closed stdout and stderr but kept running made the loop fall back to a blocking `waitpid()` that ignored cancel. New test `cancelStopsChildThatClosedItsOutput` fails on the old code (`process_test.cpp:137`).
  - clang-format 23 and clang-tidy are clean; the process and plugin_process suites pass.
  - The PR is not opened yet; the description is in `upstream/noctalia-process-pidfd-pr.md`.

## Open items

1. **Reboot:** kernel 7.3.4, the new greeter, the Umbriel test build, and Noctalia 5.5 from login. After it, check:
   - the `vmd` module path;
   - `journalctl -k -b | grep -c 'completion polled'` (expect 0);
   - dGPU `suspended`;
   - `systemctl is-active asusd asus-shutdown`;
   - tray icons present.
2. **Bitwarden:** the Arch package is 7 months old (2026.3.1 against upstream 2026.10.4). The swap to `bitwarden-bin` is a manual step: `sudo pacman -Rs bitwarden && paru -S bitwarden-bin`. Settings in `~/.config/Bitwarden` are kept.
3. **DaVinci Resolve 21.1.1:** Blackmagic requires a manual download (`DaVinci_Resolve_Studio_21.1.1_Linux.zip`), then the AUR build.
4. **Keyboard colour:** the Windows / sticker check above.
5. **Noctalia PR:** open it from the pushed branch.
6. **NVIDIA bug #1549** (stale power budget, GPU stuck at base clock): watch MangoHud in the next gaming session; restarting nvidia-powerd works around it.
7. **The archive:** `~/.local/share/archive/desktop-leftovers-2026-11-15` (56 MB) holds every config and theme removed; delete it once nothing is missed. The Trash holds the app data of removed apps.
