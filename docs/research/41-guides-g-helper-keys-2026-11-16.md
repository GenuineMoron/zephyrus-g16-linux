# 41: Similar guides, G-Helper deep-dive, ROG keys, and fixes (2026-11-16)

After the reboot onto 7.3.4, there were three goals:

- the keyboard and hotkeys set up properly for this laptop;
- every similar guide and project compared against ours;
- G-Helper studied for anything we're missing.

This note records what was found, what changed, and what is still open.

## Post-reboot check

- **Kernel and storage:** kernel 7.3.4 with the stock `vmd.ko` (DKMS retired). `completion polled` stalls this boot: 0.
- **Services:** the dGPU is runtime-suspended; asusd and asus-shutdown are active; Noctalia 5.5 is running; the Umbriel test build is live (`/usr/local/libexec/umbriel-test`).
- **Boot timing:** 6.8 s firmware + 2.4 s loader + 0.5 s kernel + 2.1 s initrd + 4.7 s userspace.
  - GRUB loads only the initramfs. The microcode is embedded, and only this CPU's 141 KB file (`06-aa-04`).
  - Its 1 s hidden timeout is the deliberate "hold Esc" window, so nothing was changed.

## Keyboard: white-only, confirmed

The unit is a **GU605MI-QR081W**. Five independent signals agree:

- **ASUS listing:** ASUS's regional store listing for this SKU shows "Backlit Chiclet Keyboard Single Light". Third-party spec sites say RGB, copied from the model family.
- **Earlier test:** every colour path tested on 2026-11-15 lit plain white (asusd D-Bus, asusctl, WMI `kbd_rgb_mode`). Rainbow, which the keyboard's own firmware generates, only pulses white.
- **The keyboard's own capability report:** queried the way G-Helper does it (`AuraProbe`: on report `0x5d` send `b9`, then `"ASUS Tech.Inc."`, then `05 20 31 00 20`, and read the feature report back):
  ```
  5d 05 20 31 00 20 01 00 00 00 23 04 01 00 56 03 0f 04 00 00
  type=0x00 year=0x23 layout=0x01 feat1=0x00 feat2=0x56 family=0x04 (Zephyrus)
  ```
  - **RGB wheel:** `feat2` bit `0x08` is clear, so no colour wheel.
  - **Single colour:** bit `0x10` ("one-zone red effect") is set.
  - **G-Helper misses it:** its own rule ignores that bit when type is `0x00`, so it would not auto-detect this keyboard. It relies on a model list plus a manual `no_rgb` switch.

**Plugin change:** ROG Control 1.2.0 gained `rgb_keyboard`, our `no_rgb`. It's set to false here, so:

- the panel offers Static, Breathe and Pulse (G-Helper's white list), with no colour row;
- the theme-colour writes stop.

Upstream: [drafts/asusctl-detect-single-colour-keyboard.md](../../upstream/drafts/asusctl-detect-single-colour-keyboard.md).

## ROG keys: G-Helper-style Fn-lock

**There is no hardware Fn-lock on this keyboard** (USB `0b05:19b6`). Three pieces of evidence:

- The top row always sends F1-F12, and Fn+key sends the printed function.
- Fn+Esc sends a plain Esc.
- **hid-asus quirk does nothing here:** since commit f631011e36b8 (ProArt P16), hid-asus sends `5a d0 4e 01` at every probe, because the quirk is keyed on the shared `0x19b6` ID. This keyboard ignores it, and writing `00` changed nothing (tested).
- **Old setting does nothing either:** the old `/etc/modprobe.d/asus-fnlock.conf` (`asus_wmi fnlock_default=N`, from June) couldn't help, because WMI `DSTS 0x00100023` returns "no such device". The file was removed.

G-Helper also treats every Zephyrus as software Fn-lock (`IsHardwareFnLock()` is Vivobook/Zenbook/ProArt only). Its software layout is:

- F1-F11 do the printed function;
- F12 stays F12;
- Fn+key keeps doing the function.

### What the keys send

Recorded with `evtest`, using a filter that drops typing keys and their scancodes.

| Key | No Fn (hardware) | With Fn (hardware) |
| --- | --- | --- |
| F1 | `7003a` F1 | `c00e2` Mute |
| F2 / F3 | `7003b` / `7003c` | `ff3100c5` / `ff3100c4`. hid-asus handles both in the kernel (keyboard light) |
| F4 Aura | `7003d` | `ff3100b3` PROG3 |
| F5 fan | `7003e` | `ff3100ae`. The kernel cycles the thermal mode itself (1489a34e97ef); on 7.3 the event also reaches userspace as PROG4 |
| F6 | `7003f` | Win+Shift+S (three keys from the keyboard) |
| F7 / F8 | `70040` / `70041` | `ff310010` / `ff310020` brightness |
| F9 | `70042` | Win+P |
| F10 | `70043` | `ff31006b` F21 (touchpad toggle) |
| F11 | `70044` | not pressed (hid-asus sleep usage is `0x6c`) |
| F12 | `70045` | **nothing at all**: no event on any input device, no kernel message, no vendor report |
| M1 / M2 / M3 / M4 | `c00ea` vol−, `c00e9` vol+, `ff31007c` mic mute, `ff310038` PROG1 (ROG) | n/a |
| Fn+Win | firmware Win-key lock, no event | |
| Fn+RCtrl / Fn+arrows | Menu / Home, End, PgUp, PgDn (plain codes) | |

G-Helper handles Fn+F12 as WMI event 136 (`0x88`) plus `DeviceSet(UniversalControl, Airplane)`. That event never arrives under Linux on this model, so airplane mode stays in the control centre. The `XF86RFKill` binding is kept in case a later kernel delivers it.

### What was set up

- **`/etc/udev/hwdb.d/90-asus-g16-fnkeys.hwdb`:** a kernel keymap swap, so the layout applies everywhere (greeter, TTY, games) at zero runtime cost.
  - No Fn: mute, keyboard light −/+, Aura, fan, Print, brightness −/+, display, touchpad, sleep, F12.
  - With Fn: F1-F4, F7, F8, F10, F11.
  - Fn+F5 (the kernel acts on it) is mapped to `reserved`, so it doesn't step the mode twice. Fn+F6 and Fn+F9 send key combinations, so they keep their functions.
  - The only keys lost from the laptop keyboard are F5, F6 and F9 (G-Helper loses all of F1-F11).
  - **Trap found:** plain `systemd-hwdb update` writes `/etc/udev/hwdb.bin`. That copy shadows the `/usr/lib/udev/hwdb.bin` which systemd package updates rebuild (`systemd-hwdb --usr update`), and the initramfs then carries it too (+2.4 MB). The file now says to use `--usr`; the stray `/etc` copy was removed and the initramfs rebuilt (back to 25.8 MB).
- **Umbriel bindings:**
  - `XF86Launch3` (Aura) → ROG Control `next-aura`.
  - `XF86Launch4` (fan) → `next-profile`.
  - `XF86Launch1` (M4/ROG) → the ROG Control panel.
  - `XF86Display` and `Mod+P` (Fn+F9) → control centre, monitor tab.
  - `XF86TouchpadToggle` → `touchpad-toggle`.
  - `XF86RFKill` → `airplane-toggle`.
  - `Print` and `Mod+Shift+S` (Fn+F6) → region screenshot. Noctalia settings moved to `Mod+I`; pin moved to `Mod+Shift+P`.
- **`touchpad-toggle`:** flips `enabled` in `~/.config/umbriel/touchpad.toml`, an optional include. The state survives restarts.
  - **Umbriel rule learned the hard way:** with a `[drm]` policy, Umbriel refuses to load while any include is missing ("cannot safely load DRM policy while an include is missing"). A missing file at login would even fall back to the default config. So the file must always exist.
  - The first attempt briefly made a reload fail; the previous config stayed active.
- **Sleep key:** `/etc/systemd/logind.conf.d/20-keys.conf` sets `HandleSuspendKey=suspend-then-hibernate`, the same as the lid. Tested: F11 slept and the next press woke it.
- **Verified by hand:**
  - every function with no Fn, and Fn+F1/F7 giving F1/F7;
  - Fn+Up giving PgUp after a sleep cycle;
  - OSD for Aura and fan modes.

## Keyboard backlight writes fail while the keyboard sleeps

Found in the final health check: `asus 0003:0B05:19B6.0001: Asus failed to set keyboard backlight: -108`, 15 times this boot. One of them was at 13:11:25, the moment the idle behaviour turned the light "off".

**Cause:**
- Since 2026-11-15 the keyboard's USB controller autosuspends 2 s after the last key (`71-asus-kbd-autosuspend.rules` with the asusd PR #404 build; 0.8 W at screen-off idle).
- hid-asus sends backlight and Fn-lock feature reports from its worker with no runtime-PM reference, so a write to the suspended device fails with `-ESHUTDOWN`.
- The LED class still reads the new value. The keyboard keeps the old one until the next key press resumes it; then `asus_resume()` re-sends the stored level.

**Effect:**
- The 60 s idle-off never turned the light off.
- Brightness changes made with the touchpad (Noctalia, plugin, asusd) are late.
- asusd's `Brightness` setter goes through the same kernel path, so it fails the same way.

**Verified:**
- The keyboard was `suspended`.
- A write through logind or asusd added a failure.
- Re-sending asusd's current `LedPower` resumed the keyboard (`runtime_status` active, `runtime_active_time` +411 ms). The pending level then applied with no failure, and the keyboard autosuspended again.

**Fixes:**
- **Now:** `kbd-light-idle` wakes the keyboard first by re-sending `LedPower`. That goes through asusd's hidraw write, whose open resumes the device.
  - Tested from suspended: restore 1 → 1, restore 3 → 3, off → 0 twice, with 0 new failures and asusd's saved config unchanged.
  - Re-sending `LedMode` was rejected: asusd then re-applies its own brightness and turns Off into Med.
- **Root cause:** the kernel patch `upstream/drafts/0001-HID-asus-wake-the-keyboard-for-feature-reports.patch` takes `hid_hw_power()` around the two worker writes only, because `reset_resume` must not resume itself.
  - The source was verified as CachyOS 7.3.4-1's own hid-asus.c: identical file, and the module differs only by one AutoFDO-inlined function.
  - It builds cleanly.
  - **Packaged, not installed:** `packaging/hid-asus-wake-dkms`. `BUILD_EXCLUSIVE_KERNEL` is 7.3.4-1 only, so a newer kernel falls back to stock.
  - It has not been loaded live yet. Install the package built from `packaging/hid-asus-wake-dkms` with `sudo pacman -U hid-asus-wake-dkms-7.3.4.1-1-any.pkg.tar.zst`, reboot, then check `journalctl -k | grep "failed to set keyboard backlight"` stays empty.
- **asusctl:** follow-up comment for PR #404 drafted (`upstream/drafts/asusctl-pr404-followup-backlight.md`).

## G-Helper: what it knows about the GU605

From seerge/g-helper `9d1b2a5` (2026-11-15) and its Linux port utajum/g-helper-linux (559★):

| G-Helper quirk | Applies to | What it does | Here |
| --- | --- | --- | --- |
| `IsSleepReset` | GU605MI, MV, CR | Re-sends the performance mode after every resume | **Adopted**: `system-sleep/20-asus-profile-resend` (below). The Linux port declares it but never calls it |
| `IsChargeLimit6080` | GU605 (and GA403, GU405…) | Only 60/65/70/75/80/100 % honoured | 80 % in use. Noctalia/UPower only offer it on/off at 80 |
| `IsStandardForceFix` | GU605 | Re-sets dGPU-enable when Windows misses the GPU in Standard | Windows driver issue; the dGPU enumerates normally here |
| `DynamicBoost20` | GU605 | Dynamic Boost slider max 20 W | Firmware defaults kept (tunings off) |
| `IsFanRequired` / `IsPowerRequired` | GU605 / GU605M | Custom PPT needs fan curves applied and vice versa | Only matters with custom limits; none are set |
| `IsSlash`, `IsOLED` | GU605 | Slash bar; OLED features | Slash configured (below); OLED notes below |
| Fan max RPM (port) | GU605 | 6200 / 6200 RPM CPU/GPU | Reference for fan displays |
| Hardware hotkeys | FX506 only | | Software Fn-lock as above |

### Sleep reset, measured

The firmware won't say which mode it is in:

- **WMI readback:** `DSTS 0x00120075` reads `0x10003` in Silent, Balanced and Turbo alike.
- **RAPL limits:** constant across modes (PL1 90 W / PL2 104 W; armoury `ppt_pl1_spl` 90, `ppt_pl2_sppt` 135). The EC enforces each mode internally.

So a lost mode can't be detected, which is why G-Helper re-sends it blindly.

**What asusd does on wake:** it re-sends the charge limit, but the profile only if the charger changed during sleep (`ctrl_platform.rs`).

**The hook:** writes the current `throttle_thermal_policy` back. asusd then re-syncs that mode's fan curve. Side effect: every mode write makes the EC send an NVPCF notify that wakes the dGPU for a few seconds (`gpu-wake` log: `rm_acpi_nvpcf_notify`), the same as pressing the fan key.

Upstream: [drafts/asusctl-resend-profile-on-resume.md](../../upstream/drafts/asusctl-resend-profile-on-resume.md).

### G-Helper features against this setup

| G-Helper / g-helper-linux | Here |
| --- | --- |
| Modes, per-power-source defaults, OSD | asusd + ROG Control (bar, panel, keys) |
| Charge limit, one-shot full charge | UPower/asusd 80 %; plugin "charge to 100 % once" |
| GPU Eco/Standard/Ultimate | asusd + asus-shutdown via the plugin. Optimized (auto-Eco on battery) isn't needed: the RTX 4070 runtime-suspends (D3cold) in Hybrid |
| Keyboard light, effects, sleep/boot lighting | asusd; `LedPower` keyboard: boot+awake on, sleep+shutdown off (already) |
| Keyboard light timeout | Noctalia idle behaviour `keyboard-light`, 60 s (seen working: off at 13:11) |
| Slash | Disabled. Now also `ShowOnSleep`, `ShowOnBattery`, `ShowOnLidClosed` = false, so enabling it can't drain the battery |
| Fn-lock, M-keys, ROG key | hwdb + Umbriel (above) |
| BIOS / driver update check | Same ASUS API checked by hand (below) |
| Auto refresh rate (60 Hz on battery) | **Open:** needs a battery-only A/B; Umbriel would switch modes via an include |
| CPU turbo off on battery | **Open:** needs a battery measurement (snappiness trade-off) |
| Flicker-free OLED dimming, visual modes | Windows-only (ASUS Splendid service). Gamut is handled by Umbriel (factory ICC, `sdr_gamut = "srgb"`). Dimming would need a compositor feature (see Hyprland discussion 14145) |
| Audio DSP (Dolby) | **Prepared, not run:** see Audio |
| Undervolt | Locked on Meteor Lake |

### ASUS updates for GU605MI

From the support API G-Helper uses (`rog.asus.com/support/webapi/product/GetPDBIOS` and `GetPDDrivers`; the query sends the model name only):

- **BIOS:** 329 (2025-06-30) is the newest. This unit has it.
- **Slash firmware:** V014. The bar reports `bcdDevice 0x000e` = 14, so current.
- **SSD firmware tool:** V1.0.0.05 (2025-04-30, WD PC SN5000S). The drive runs `34230100`. LVFS has nothing newer, and the tool doesn't name its target version, so run it once from Windows to be sure.
- **Touchpad firmware:** V1.0.0.1 (2024-05-21). Version can't be read from Linux.
- **fwupd:** only the UEFI dbx 20250902 → 20260707 is pending. Secure Boot is off, and Windows Update applies dbx itself, so it's left to Windows.

## Similar guides and projects

| Source | Machine | Worth taking? |
| --- | --- | --- |
| [OGC asusctl docs](https://opengamingcollective.github.io/asusctl/) (official, now on GitHub) | all | Don't run power-profiles-daemon/tuned with asusd: already masked. asusd is udev-started. Cardwire is the experimental supergfxctl successor, not needed with RTD3. rtkit probing NVIDIA HDMI audio can keep the dGPU awake |
| [asus-linux Arch guide](https://asus-linux.org/guides/arch-guide/) | all | Skip the OGC repo on CachyOS; nvidia-powerd; S0ix check. All in place |
| [Y0shm4st3r/cachyos-rog-zephyrus-g16-2024-setup](https://github.com/Y0shm4st3r/cachyos-rog-zephyrus-g16-2024-setup) | **GU605MI**, CachyOS | `i915.enable_dpcd_backlight`, ufw, mitigations check. Its NVIDIA-in-initramfs step is the opposite of our slim initramfs (dGPU loads on demand; nvidia-smi works) |
| [livepatrone/cachyos-asus-Instalation](https://github.com/livepatrone/cachyos-asus-Instalation) (= the r/ZephyrusG14 Reddit guide) | G14 GA403WW | Limine + sbctl (Secure Boot off here by choice), MT7925 Wi-Fi powersave (we have Intel Wi-Fi), MUX guard script (not needed: we stay Hybrid and asus-shutdown applies switches) |
| r/cachyos "Ultimate guide… 2025 G16" | GU605C (Arrow Lake, RTX 50) | Could not be fetched (reddit blocks automated fetches, and no archive copy was read). Needs a paste or reddit API credentials |
| [Kryptos-s/gu605-bios-hidden-options](https://github.com/Kryptos-s/gu605-bios-hidden-options) | **GU605** BIOS 307 | ReBAR, VT-d, power limits as hidden NVRAM options. VMX/VT-d are already visible and on in BIOS 329. Editing NVRAM is risky with little gain; not done |
| [sharpsteve/Zephyrus-Linux](https://github.com/sharpsteve/Zephyrus-Linux) | GA605WV (AMD) | 80 % charge limit, Slash off on battery/sleep (now set), `nvidia-powerd` masked on AMD only |
| [lihe07/linux-on-zephyrus](https://github.com/lihe07/linux-on-zephyrus) | G16 Air AMD | ASPM powersupersave, quiet + EPP power on battery, watchdog off (all in place); turbo off on battery (open) |
| [Boltthecat19/rog-g16-popos](https://github.com/Boltthecat19/rog-g16-popos) | GU605C, Pop!_OS | MEI GSC proxy in initramfs (17 s i915 stall): **not affected** (HuC/GSC load at 1 s). cs35l56 firmware symlinks: **not affected** (no "bin file required"). `noatime`: already |
| [omacom/omarchy#6232](https://github.com/omacom/omarchy/issues/6232) | GU605CM/MI | `i915.enable_dpcd_backlight=3` for OLED brightness: already on the cmdline |
| [CANVEXTER/Tetricks](https://github.com/CANVEXTER/Tetricks), deadbrainviv/ASUS-GU605C, ehmiiz GU605MI blog, ArchWiki Laptop/ASUS | various | Nothing new. The ArchWiki row for GU605MI says everything works; the charge limit resets after hibernation, which asusd re-applies on wake |
| [utajum/g-helper-linux](https://github.com/utajum/g-helper-linux) | many | eBPF dGPU block, refresh-rate auto, audio DSP; covered above |

## Fixes from auditing the 2026-11-15 cleanup

- **cifs-utils was removed** with the KDE/VLC dependencies (pacman.log 2026-11-15 22:24).
  - Without `mount.cifs`, the kernel must resolve the share host itself and fails: "CIFS: Unable to determine destination address".
  - A CIFS network-share automount had failed at boot.
  - Reinstalled `cifs-utils` and `smbclient` as explicit; the automount works again.
  - The other 305 removals were checked: the portal file picker (GTK) and screen capture (Umbriel) are intact; nothing uses curl-impersonate.
- **Leftovers removed:**
  - `intel-lpmd` (disabled since 2026-11-15) and its sleep hook.
  - Five `.bak` scripts in `/usr/local/bin`.
  - The no-op `asus-fnlock.conf`.
  - `supergfxd.conf`. Its only non-redundant line, `alias nouveau off`, moved to `nvidia-only.conf`.
  - All archived under `~/.local/share/archive/desktop-leftovers-2026-11-15/`.
- **Self-inflicted dGPU wake:** `cat /proc/asound/card*/codec#0` reads the NVIDIA HDMI codec (card1) and woke the dGPU (`gpu-wake`: `print_codec_info`). Read `card0` only.

## SearXNG (private search)

SearXNG is installed from upstream git (`2d500cb`) in `~/.local/share/searxng/venv`, served by granian with the official container's settings.

- **Address:** `http://127.0.0.1:8888`, this machine only.
- **Zero idle cost:**
  - `searxng.socket` listens, and the first request starts `searxng.service`.
  - That service runs `systemd-socket-proxyd --exit-idle-time=15min`, and it pulls in `searxng-app.service` (granian on 127.0.0.1:8889, `StopWhenUnneeded`).
  - With no traffic for 15 minutes both stop, so nothing runs while unused.
  - Cold start: 2.1 s including the first search. Warm: 0.8 s.
- **Settings:** limiter off; no Valkey; JSON output on; metrics off; GET.
  - Wikipedia, Wikidata and OSM are removed: they demand a contact address in every request, and no personal details are attached.
  - The Tor-only engines are removed too.
- **Startup fixes:**
  - Readiness waits on `/healthz`, because the socket file appears before granian listens.
  - TCP instead of a unix socket, so SearXNG sees a client address.
  - `trusted_proxies = []`.
  - Version frozen.
  - One "X-Forwarded-For nor X-Real-IP" line is still logged once per start; that's by upstream design.
- **Reddit:** posts show up as search results. Reading their contents through SearXNG would sidestep the block noted above, so it isn't used that way.
- **Configs:** `configs/home/.config/searxng/` (the secret key is not committed), plus the three user units.

## Audio: Dolby tuning, prepared

On Windows, the speakers run through ASUS's Dolby Atmos tuning; on Linux they play untuned.

**Tool:** [antoinecellerier/speaker-tuning-to-easyeffects](https://github.com/antoinecellerier/speaker-tuning-to-easyeffects) (202★, >50 laptops confirmed, GU605 not yet). It converts the tuning XML from the Windows driver into a PipeWire filter-chain, with no extra daemon.

**Prepared:**
- **Codec:** ALC285, subsystem `1043:1C63`.
- **Driver:** ASUS's `DriverOnly_Dolby_ROG_Realtek_B_V6.0.9715.1Sub1` (GU605MI, 2024-12-04). Downloaded; SHA-256 matches ASUS's published `4DD80619…E6C6`.
- **Packages installed:** `7zip` and `lsp-plugins-lv2`. Calf isn't needed on HDA.

**Location:** converter and verified driver are kept locally (local working copy, not in the repo).

**Plan:** install with `--target-sink ''` as a separate selectable output ("Dolby Balanced"), so the default stays untouched until the outputs are compared by ear.

**Not run:** the downloaded converter has not been run yet; that is a separate, deliberate step.

## Open

1. **Power button:** a short press currently powers off instantly (logind default), and the button sits right above Del. Suggested: `HandlePowerKey=suspend-then-hibernate`.
2. **Battery A/B:** 240 vs 60 Hz on battery, and turbo off on battery. Both need the laptop unplugged and idle for a few minutes each.
3. **Dolby tuning:** run the converter (above), then compare the outputs.
4. **Windows visit:**
   - run ASUS's SSD firmware tool (V1.0.0.05) and touchpad tool;
   - let Windows Update apply the dbx.
5. **Reddit guide** (2025 G16): read it by hand, or through reddit API access.
6. **Keyboard backlight kernel fix:** install the `hid-asus-wake-dkms` package (above) and reboot.
7. **Carried over:**
   - Bitwarden `bitwarden-bin` swap;
   - opening the Noctalia pidfd PR;
   - the DaVinci Resolve 21.1.1 download.
