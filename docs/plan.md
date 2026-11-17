# Action plan (from the 2026-11-14 deep read)

This plan merges the [research notes](research/). Each item is changed one at a
time and checked as stated; the result becomes a finding or a guide section.

## A. Clear wins, low risk (apply, then verify)

| # | Change | Why (source) | Verify |
|---|---|---|---|
| A1 ✅ | gamemode end hook restores the profile that was active before the game, instead of always "Balanced" | On battery, a game left the laptop in Balanced rather than Quiet (07) | Start/stop a game on battery; `asusctl profile -p` |
| A2 ✅ (revised) | **Keep** `intel_lpmd`, restart it after hibernation (`system-sleep/60-intel-lpmd-after-hibernate`) | Its LP mode is off, but WLT hints are on: it retunes EPP/EPB per workload type (idle 255, battery-life 178, sustained 64), which is not "nothing" as note 05 claimed. Its perf counters break across hibernation → ~19 errors/min (05, 14). Whether it helps battery is measured in B-list | Journal quiet after the next hibernate |
| A3 | `ufw logging off` (or low) | ~190 warning lines per session, mostly IGMP broadcasts (14) | Journal warning count |
| A4 ✅ | Network-mount health check every 10 min instead of 2 | Probed the network mounts every 2 min (14) | Timer list; mounts still heal |
| A5 (niri, retired) | niri `screenshot-path` → `~/Pictures/Screenshots` | Screenshots only go to the clipboard now (10) | Take a screenshot |
| A6 ✅ | Alt+Tab window switcher: noctalia-git (5.3.0+git, Oct) replaced by stable **noctalia 5.4.1** from the repos; `shell.window_switcher.mru = true`; niri `Alt+Tab { spawn "noctalia" "msg" "window-switcher"; }` | No switcher before (10) | Use it |
| A7 | Fix the GTK theme errors (WhiteSur `gtk.css` parse error on every GTK app start); make GTK3/GTK4 consistent | (10) | No CSS errors in the journal; visual check |
| A8 | Hibernate: `hibernate_compression_threads` 3 → 8–12, compressor LZ4 | Only 3 of 22 threads compress; LZ4 decompresses ~1.5× faster (09) | Timed hibernate cycles (capped filler) |
| A9 | Enable systemd-oomd for the user slice | Apps now run in their own units, so oomd can stop just the runaway one before swap thrash (09) | Synthetic memory hog in a capped scope |
| A10 | Byte-based dirty limits (`vm.dirty_bytes` / `dirty_background_bytes`) | 10%/3% of 32 GB lets ~3 GB of dirty pages build up → write stalls (12) | Input latency during a large write |
| A11 | Find what sets `vm.swappiness=150` (sysctl.d says 100) and settle it deliberately | Unknown writer (09, 12) | `sysctl vm.swappiness` after boot |

## B. Measure first, then decide

| # | Question | Plan |
|---|---|---|
| B1 | **The 5 W standby night.** Is the dGPU actually powered while Linux thinks it is off? The BIOS `_OFF` skips `POFF()` when EC `VIUF`=1 (02) | Log the EC `VIUF` byte (via `ec_sys`, read-only) and RAPL/battery power per standby stretch; a night on battery |
| B2 ✅ idle | 60 Hz vs 240 Hz: **no difference on a static screen** with PSR1 on ([31](research/31-screen-on-idle-ab.md)); moving content (scroll/video) still to measure |
| B3 | NVMe runtime PM is off (`power/control=on`) | Idle power with `auto` vs `on`; watch for VMD stalls (03) |
| B4 | The 171 ms resume wait: Linux's ACPI `Timer` is jiffies-based and excludes suspend time, so the BIOS `PDOD` guard waits needlessly (01) | Confirm with monotonic vs boottime across s2idle; check the 7.3 source; prepare an upstream report/patch |
| B5 | `UseKernelSuspendNotifiers=0` | ~20 suspend cycles for reliability and timing (04); risky, do last |
| B6 | S0i2.2: IOE LTR 5.64 ms and the USB-C/TB die (03) | Unplug all USB-C; one `ltr_ignore` test; latched requirements |
| B7 | Fan 3 at ~3700 rpm at idle; PL2 104 W (RAPL) vs 135 W (asus-armoury) (12) | Identify the fan; sustained-load turbostat run |
| B8 | NVMe I/O scheduler kyber vs none (12) | fio p99 latency |
| B9 | MUX (dGPU direct) vs Hybrid for games (12) | MangoHud frame-time runs; needs a reboot |
| B10 | Codec power-save on AC (CachyOS turns it off to avoid crackles) (06) | Listen for crackles with power_save=10 on AC |
| B11 | kdump (crashkernel=512M) and dropping `nowatchdog` (08) | Cost/benefit; detectors with panic only during debugging |

## C. Features to add

| # | Feature | Notes |
|---|---|---|
| C1 | Face login with the **IR camera** (howdy + linux-enable-ir-emitter) | Present on /dev/video2; AUR; PAM lockout risk, keep password fallback (13) |
| C2 | Unmapped ASUS hotkeys (EC codes 0x4F, 0xE5, 0x68) | Identify with evtest; map in hwdb or report to asus-wmi (02, 13) |
| C3 | Colour accuracy for design work | niri has no colour management; Resolve colour management now; colorimeter + ICC; evaluate a KDE session for colour/HDR (11) |
| C4 | Thunderbolt docks | Install `bolt` (security level is "user") (13) |

## D. Upstream reports

| # | Report | To |
|---|---|---|
| D1 | CS35L56 HDA hibernate deadlock (draft in research/06) | Cirrus Logic / linux-sound |
| D2 | NVIDIA wakes an RTD3-suspended GPU on every system suspend | NVIDIA/open-gpu-kernel-modules |
| D3 | ACPI `Timer` excludes suspended time (BIOS power-sequencing guards misfire) | linux-acpi, after B4 |
| D4 | Unmapped hotkeys (0x4F, 0x68; 0xE5 is a charge-limit notice to ignore) | asus-linux / platform-driver-x86 |
| D5 | `intel/pmc`: hardware sleep time truncated to 32 bits of µs ([patch](../upstream/0001-intel-pmc-hw-sleep-u32-truncation.patch), W=1 clean) | platform-driver-x86, after one long standby on the patched module |

## E. At the end

- Remove the temporary diagnostics (pm_debug_messages, warn_on_s0ix_failures, pmc latch).
- Write the guide sections from the findings.

## Wave 2 additions (Windows install, BIOS image, telemetry, harness)

| # | Item | Source | Next |
|---|---|---|---|
| A12 ✅ | `GSK_RENDERER=gl` (GTK renamed `ngl`; the old name logged a deprecation on every launch) | 23 | Verified: dGPU stays asleep |
| B12 ✅ cause | **PC10 blocked at screen-on idle** → cause proven: asusd keeps hidraw open, so the chips can't suspend ([finding 06](findings/06-keyboard-usb-blocks-deepest-idle.md)); fixed locally 2026-11-15 with asusctl PR #404 + autosuspend (PC10 0.4% → 65% screen off); a lit Num Lock LED also blocks it (fixed 2026-11-16) (#690 risk). Earlier note:: OS requests PC10 81% of the time, achieved 0.2%; PCH LTR 51 µs from xHCI snoop LTR (< 325 µs C10 threshold). The always-on ASUS ITE keyboard USB devices are the prime suspect | 20, 03 | PMT before/after keyboard autosuspend and xHCI runtime PM; package W and PC10% |
| B13 | psys 19 W vs package 4.8 W on AC at idle (screen on) | 20 | Measure on battery: PMT + battery V×I at 60 vs 240 Hz |
| B14 | Windows turns PCIe ASPM **off on AC**, max saving on DC; Linux forces powersupersave on both | 16 | A/B on AC: idle W and latency |
| B15 | Windows Balanced EPP ≈ 50% on AC; Linux balance_power ≈ 75% | 16 | A/B responsiveness (harness) and W |
| B16 | PL2: EC holds 104 W (matches RAPL); asus-armoury says 135 W | 22, 12 | 60 s load + turbostat |
| B17 | Boot 16.7 s: GRUB 3.0 s (1 s timeout), i915 early load 1.5 s, firmware 6.2 s | 19 | GRUB_TIMEOUT=0 now; then systemd-boot/UKI; i915 late-load test; BIOS Fast Boot / CSM / network-boot off |
| B18 | Battery cycle count: EC `CYCL`=87, Linux reports 0 | 22 | Small reader in the health check |
| B19 | Finish the BIOS setup-option decode (AMI PFAT; LZMA section) with BIOSUtilities | 18 | Analysis only |
| C5 | **Factory colour profile** for this panel from Windows (`GU605MI_..._CMDEF.icm`, factory ΔE 0.34 sRGB / 0.35 P3) | 17 | Install for colour-managed apps (colord) |
| C6 | Windows Dolby "game" speaker profile (20-band optimizer curve, leveler, virtualizer) | 17 | Resolve DAX3 units, then PipeWire filter-chain; listen A/B |
| C7 | OLED care like Armoury (pixel shift; refresh pass after 30 min idle) | 15 | Small idle-triggered service |
| C8 ✅ (timeout) | Keyboard backlight off after 60 s idle (noctalia custom idle behavior + `kbd-light-idle`); measured ~0.5 W at level 2 ([31](research/31-screen-on-idle-ab.md)). Dim on low battery still to do | 15, 31 | Live use |
| C9 | Mic noise suppression (Windows Studio "voice focus" equivalent): DeepFilterNet in EasyEffects | 24 | Install and A/B |
| C10 | Intel NPU stack (intel-npu-driver, OpenVINO) | 24 | Optional; small models only today |


| B20 ✅ | **Night mode** (`sleep-window-update`): on battery, hibernate once asleep ≥ 1 h and the time is 01:00–07:00. No wake-up afterwards | — | Hibernated drain is logged per stretch |
| B21 (watching) | **PSR (Panel Self Refresh) found off** after a night of use, although the panel supports PSR1 and the VBT allows it. Stays on through: fresh boot, screen blank (off while blank, back on after), 25 s standby, lid close/open, 50 s timer wakes with the lid shut, night light 4000 K on/off. [`psr-watch`](../configs/usr/local/sbin/psr-watch) logs every change | — | Find the trigger (lid close?) from the log; then a controlled idle-power A/B — 2026-11-16: not seen this boot; PSR went off only with the screen off and came back each time ([42](research/42-audit-2026-11-16.md)) |
| B22 | BIOS: animated POST logo; ErP for hibernated drain | 28 | Photos of the submenus; A/B FPDT firmware time; hibernated drain with ErP off vs on |

| B23 | **Keyboard/touchpad can't wake standby on Linux; they can on Windows.** Windows' log shows 11 keyboard and 6 touchpad exits from ≥90% hardware-DRIPS standby (lid open). On Linux, with the whole USB wake chain armed (`usb 3-6: usb suspend, wakeup 1`, root hub wakeup 1, xHCI `wakeup: 1` → D3hot, ACPI `XHCI` GPE enabled), a key press produced no wake; it slept to the RTC backstop twice. The touchpad is sent I2C-HID SET_POWER SLEEP at suspend. `wakeup-policy.sh` keeps XHCI wake off (stray-wake guard, restored) | 27, test 2026-11-15 | Read the XHCI/keyboard-port ACPI (`_S0W`, `_PRW`, `_DSW`, USB port `_DSD`), try xHCI D3cold, check the touchpad wake IRQ path; bpftrace on PME/GPE during a key press |
| B24 ✅ | **A lid-open can be lost in suspend-then-hibernate.** (a) Opening within ~2 s of sleep entry is missed (seen 2026-11-11). (b) After a timer wake systemd's s2h loop re-suspends without checking the lid, so a lid opened just before or during that wake is ignored. Today with 50 s checks (test only) it needed the power button. With hourly checks the window is ~3 s per hour | systemd `custom_timer_suspend` | Fix with B23 (a key press would then recover), or a post hook that ends the loop when the lid is open after a timer wake — Fixed 2026-11-15: `70-lid-open-ends-s2h` holds two wake alarms when the lid opened around a battery-check wake (fired correctly that day). (a) still depends on B23 |

| B25 | **Screen-on PC10 is blocked by timer wake-ups (TNTE_CDIE 94%), not the display** (PSR self-refresh 80–95%) ([36](research/36-screen-on-blockers-and-wakeups.md)). Biggest sources: browser tabs, procon2-driver 53/s, tailscaled 42/s, nvidia-powerd 13/s (fixed: AC only), ananicy-cpp 14/s, bpftune 10/s | 36 | Make procon2-driver on-demand; measure ananicy/bpftune value; re-measure — 2026-11-16: procon2 on demand ✅ (rule 53); remaining idle sources measured in [42](research/42-audit-2026-11-16.md): Noctalia 52/s (4 streams = D17, plus a 200 ms lock-keys LED poll), tailscaled 15, ananicy 14 |
| B26 ✅ | scx_lavd --autopower vs EEVDF at idle: lavd **+0.35 W** platform and it wakes the dGPU on start → stay on EEVDF | 34, 36 | Done (idle). Light load/gaming not run |
| B27 (cause found) | Periodic NVIDIA wakes = EC `_QB6` on every 1% battery change → `SPAB` → `Notify(NPCF,0xC0)` (unconditional) → `rm_acpi_nvpcf_notify` resumes the GPU for ~23 s (22.6 s measured); ~0.45 W on battery | 36, 42 | Fixed upstream in a future NVIDIA release (bug 4084236; PR #1299). Re-measure after each driver update; no local driver patch |
| C11 ✅ | Umbriel second session (HDR, system-wide factory ICC, VRR fullscreen): installed + configured + nested-tested; Intel-only EGL drop-in | 35 | Done: Umbriel is the only session since 2026-11-15 (D10) |

Confirmed not possible / not worth it: undervolting (CFG lock and OC lock set, 18); ambient-light auto-brightness (no sensor: ASUS9001 is the Armoury control device, 22); Secure Boot (lockdown blocks hibernation; unsigned vmd module, 19); thermald adaptive (DTT data vault encrypted, would fight asusd, 16); decrypting Armoury's per-mode tables (vendor-protected; measure on Windows with HWiNFO instead, 15).

## Session: Umbriel only (2026-11-15)
- **D10 ✅ niri removed.** Umbriel is the only session: HDR + colour management work ([research/37](research/37-umbriel-hdr.md)), idle power equals niri. Removed niri, xwayland-satellite, cachyos-niri-noctalia, xdg-desktop-portal-gnome (nautilus, wl-clipboard, cursor theme, Alacritty config, adw-gtk-theme marked explicit first, or `-Rs` would have taken them). Greeter defaults to `--session Umbriel`, tuigreet fallback runs `start-umbriel`. Retired: greetd-trial-guard (disabled), swayidle.service (disabled), ~/.config/niri (archived in ~/.local/share/zephyrus-retired/).
- **D11 Umbriel optimisation + upstream work:** EBUSY dropped frames (umbriel#810), VRR modeset/retry (#809), colour-mapping cost during video (direct scanout off with `sdr_gamut = "srgb"`), benchmark script (idle / windowed video / fullscreen video / scrolling / memory) to measure each change.
- **D12 ✅ Theme** ([research/38](research/38-theme-wallpapers-plugins.md)): left bar, screen corners, wallpaper-derived palette, daily Bing/Spotlight photo, keyboard RGB follows theme, plugins (umbriel-companion, pixel-shift, phone-connect, tailnet). Open: icon theme (accent folders), Bitwarden, Qt (qt6ct) theming.
- **D13 ✅ ROG plugin** published: [GenuineMoron/noctalia-rog-control](https://github.com/GenuineMoron/noctalia-rog-control) v1.1.0 (graphics switching through asusd + asus-shutdown; supergfxd retired), community-plugins PR #1453 ready for review.
- **D14 ✅ Umbriel PRs** #818/#819 open with checks green; the local test build runs both on current main.

## Session: refresh and review (2026-11-15 night)
- **D16 ✅** Full update (160 + AUR), VMD DKMS retired (fix in 7.3.4), software review applied (Ghostty, Loupe, Papers, Baobab, Faugus, ProtonPlus; about 300 packages removed), theme references fixed, Inter + Geist Mono, Noctalia 5.5 notify service + polkit agent, supergfxd retired, GTK `GDK_DISABLE=vulkan` (Loupe woke the dGPU). Details and measurements: [research/40](research/40-refresh-and-review-2026-11-15.md).
- **D17** Noctalia plugin streams cost 10 wake-ups/s each (100 ms poll): fix on branch `perf/event-driven-process-wait`, PR to open. Optional follow-up: eventfd-backed cancel for 0/s.
- **D18 ✅** Keyboard is white-only (GU605MI-QR081W "Single Light"; its capability report has no RGB wheel). Plugin 1.2.0 `rgb_keyboard = false` ([research/41](research/41-guides-g-helper-keys-2026-11-16.md)).

## Session: guides, G-Helper and keys (2026-11-16)
- **D19 ✅** G-Helper-style Fn-lock via hwdb (media keys by default, F-keys with Fn), ROG/Aura/fan/display/touchpad keys bound, sleep key = suspend-then-hibernate, GU605MI sleep-reset hook, Slash off on sleep/battery/lid-closed, SearXNG (socket-activated), cifs-utils restored, leftovers removed ([research/41](research/41-guides-g-helper-keys-2026-11-16.md)).
- **D20** Open: Dolby tuning run, Windows SSD/touchpad firmware tools, reddit guide text. Done 2026-11-16: power button opens the power menu; battery A/B run (60 Hz and turbo-off save nothing at idle/light load, [42](research/42-audit-2026-11-16.md)).
- **D21** Upstream drafts: asusctl re-send profile on resume, asusctl single-colour keyboard detection (`upstream/drafts/`).

## Session: audit (2026-11-16)
- **D22 ✅** The boot health check was raising a false alarm (it still expected the retired VMD DKMS module), and the network-mount timer had not run since 11-14 (an empty `OnUnitActiveSec=` also cleared `OnBootSec`). Both fixed. The health check is now `g16-doctor`, in the repo, and also catches dead timers and a stale key-remap database. Mount healing no longer mounts idle shares. Stray `.bak` files are archived ([42](research/42-audit-2026-11-16.md)).
- **D23 ✅** ROG Control 1.3.0: the maintainer's blocking review on #1453 is fixed, along with 11 issues from a fresh review: AMD low-power/k10temp/dGPU, re-enumeration, refused writes and launches, double profile writes, opt-in theme colour. Released, synced, replied to, and marked ready; **merged into the plugin store 2026-11-16** (store version 1.0.0 = our 1.3.0; next store update 1.4.0).
- **D24 ✅** Noctalia idle wake-ups: the pidfd PR (D17) is open as noctalia#5395; the lock-keys 200 ms LED poll is reported as noctalia#5397. Attribute the rest of the main loop's ~10/s with `NOCTALIA_IDLE_PROFILE=1` at the next shell restart.

## Session: unattended tests (2026-11-16/17, on battery)
- **D25 ✅** Power button → Noctalia power menu (logind power-key inhibitor bound to the shell). Sleep after 15 idle minutes on battery (`idle-sleep`), unless audio plays or sleep is blocked. Num Lock off (`numlock_toggle` lit the LED, and usbhid won't autosuspend a keyboard with a lit LED). hid-asus wake fix loaded and A/B-tested (stock 4× `-108`, patched 0). Posted: Noctalia PR #5395 and issue #5397, asusctl #477, #478 and the #404 follow-up ([42](research/42-audit-2026-11-16.md)).
