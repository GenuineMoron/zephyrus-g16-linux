# 26 - App workflow acceleration (browser/Electron video, calls, Resolve, OBS, fonts, colour)

Date: 2026-11-14. Read-only research. No config, package or device state changed.
Scope rules followed: browser profiles read only for media/gfx/widget keys; no history, cookies, sessions; no /dev/video* opened; no lspci, nvidia-smi, vulkaninfo; no /sys/class/drm status reads.

Scope deviations (disclosed): one `v4l2-ctl --list-devices` call, which would open video nodes, was attempted but did not run. One `cat /sys/class/drm/card*/device/vendor` read was made (PCI vendor IDs only, 0x10de and 0x8086). Neither changed anything.

## 1. Hardware video decode

### Intel iGPU VA-API (proven)
- `/etc/environment` sets `LIBVA_DRIVER_NAME=iHD`. The desktop session reports iHD.
- `vainfo` (Wayland display) reports libva 2.24.0, Intel iHD 26.3.5.
- Decode (VLD) profiles present: H.264 High, HEVC Main/Main10/Main12/4:2:2/4:4:4 (through 12-bit), VP8, VP9 Profile 0-3, AV1 Profile 0.
- Encode (EncSlice) profiles present: H.264, HEVC (Main, Main10, 4:4:4), VP9, AV1.
- ffmpeg: `h264_qsv`, `hevc_qsv`, `vp9_qsv`, `av1_qsv` and `*_vaapi` encoders/decoders are built. `hwaccels` lists qsv and vaapi.
- GStreamer `va` plugin exposes vah264dec, vah265dec, vaav1dec, vavp9 paths and the matching encoders on the Intel Gen Graphics driver.
- `libva-nvidia-driver` is installed (`nvidia_drv_video.so`). Browsers would only pick it if LIBVA_DRIVER_NAME were unset or set to nvidia. It is set to iHD, so Zen and Electron should stay on the iGPU. Do not install nvidia-vaapi-driver.

### Zen (Firefox-based, 1.24.1b)
- Active profile per `profiles.ini` (`Install` section Default): `<profile>.Default (release)`. Its prefs.js contains no `media.ffmpeg.*`, `media.hardware-video-decoding*`, `gfx.webrender.*`, `gfx.color_management.*` or `widget.*` overrides. Only `gfx.blacklist.video-overlay.failureid` appears. So everything is at Firefox defaults.
- Caveat: `profiles.ini` also marks `<profile>.Default Profile` as `Default=1`. That profile's user.js sets `gfx.webrender.compositor=false`, and the dmabuf line is commented out. Confirm which profile Zen actually opens. If it is the `<profile>` one, the compositor override is a leftover that is probably worth removing (inferred, not measured).
- Verify without changing anything: open `about:support` in Zen and check the Graphics section (Compositing, WebRender, "Hardware Video Decoding" status), and the Media section (H.264/VP9/AV1 hardware decoding entries). If a codec shows "Software" or a blocklist failure, that is the thing to fix.
- Web research (secondary, dated sources): the Mozilla VA-API bugs and forum threads show Linux VA-API decode is on by default for Intel on Wayland in recent Firefox, but there are blocklist failures on other GPUs. AV1 decoding on GPU can be affected by the FFVPX path (`media.ffvpx.enabled`). Only change those prefs if about:support shows a real software fallback.
- Battery impact: software AV1/VP9 decode of 1080p+ video costs noticeably more package power than iGPU decode. I have not measured it on this machine. Measure before claiming a figure (powertop or the battery discharge rate during a 10-minute YouTube playback, hardware vs software).

### Electron/Chromium apps (Teams, Claude desktop, Spotify)
- `ELECTRON_OZONE_PLATFORM_HINT=auto` is set in environment.d and niri misc.kdl. Electron picks native Wayland when a Wayland session is present. Good.
- No Electron flags files exist (`~/.config/electron-flags.conf`, `chromium-flags.conf` absent). No custom Exec flags in the launchers.
- Teams is `teams-for-linux --gtk-version=3` (Electron, /opt/teams-for-linux). The Claude desktop launcher is an ELF binary and was not inspected for flags.
- Web research (anecdotal): recent Chromium (143+ reported) enables VA-API video decode on Wayland by default. For older builds, `VaapiVideoDecodeLinuxGL` is the flag most often cited. Do not add it blindly. Check `chrome://gpu` (or the app's devtools GPU info) first.
- Spotify (`spotify-launcher`) and Telegram (Qt, `QT_QPA_PLATFORM=wayland;xcb`) are not Chromium-decode-relevant for this decision. Telegram is Qt and uses its own media stack.

## 2. Video calls and screen sharing on niri

- niri documents PipeWire + xdg-desktop-portal-gnome for screencasting windows and monitors. Current config: `default=gnome;gtk`, Access/Notification to gtk, Secret to gnome-keyring. Portal and PipeWire user units are active.
- niri issue #2808 (secondary): Google Meet in Chromium fails format negotiation with the gnome portal. The wlr portal fixes format but breaks sharing after a browser restart. Teams and Zoom have no niri-specific report found. Treat browser screen share as untested until checked on this machine.
- Recommend: test Zen with Meet, Teams web and Zoom web, sharing (a) a single window, (b) a monitor. Use `pactl`/`wpctl` only (not device opening) to confirm a PipeWire screencast node appears while sharing.
- Native Teams (teams-for-linux, Electron) uses the same portal. Native Zoom is not installed; the browser client is the lower-risk path on niri.
- Camera: libcamera is not installed (`pacman -Q` error). v4l-utils is installed. Whether the Intel IPU/UVC camera appears through PipeWire was not checked, because checking requires opening video nodes, which was out of scope for this read-only pass. Check later with wireplumber's `wpctl status` (lists Video sources without opening devices).
- Background blur: server-side in Teams/Zoom/Meet web clients; no local Linux pipeline is set up. Not verified for each client on Linux.

## 3. DaVinci Resolve Studio 21.0.4 on Linux

- Installed: `davinci-resolve-studio 21.0.4-1`, launcher `DaVinciResolve.desktop` sets `__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia QT_QPA_PLATFORM=xcb`. Keep this offload setup; it routes Resolve to the dGPU.
- GPU decode: NVDEC (nvcuvid / CUDA) is the Linux path. A Linux Resolve 21.0.1 log (secondary, forum) shows NVDEC H.265 8/10/12-bit (4:2:0 and 4:4:4) and AV1 8/10-bit 4:2:0. H.264 is handled on NVDEC as well.
- Intel QSV decode in Resolve on Linux: no evidence found. The NixOS wiki (undated) says Intel GPU support is partial and the video timeline does not work. Treat Intel as not a Resolve decode/encode path on Linux. The iGPU's value here is in browser/OBS/calls, not Resolve.
- Encode: Resolve on Linux uses NVENC for H.264/H.265 and AV1 on RTX 40-series (third-party guide, secondary). The RTX 4070 Laptop qualifies, but that claim is not verified on this install.
- Fairlight: audio goes through the PipeWire ALSA/Pulse bridge. Not tested. No device opened. Recommend a 48 kHz project rate and a PipeWire quantum of 1024 for Fairlight playback. Check for xruns in `journalctl --user` when playing back.
- Cache/proxy (from config.user.xml): `AutoCacheDeleteMode=0`, `MaxCacheAgeInDays=30`, `FusionMemoryCacheMode=AUTO`, `PerfModeOptDecode=true`. Recommended for battery: Smart Cache / Optimised media at half resolution or H.264 proxies so the iGPU-less dGPU decode stays light. Set the scratch/cache on the NVMe, not on a sleep-prone path.
- Battery: Resolve on the dGPU keeps the RTX 4070 awake and drains quickly. Plug in for Resolve. This matches the gaming and dGPU notes elsewhere in the repo.

## 4. OBS 33.0.1 (installed)

- Plugins present: `obs-nvenc.so`, `obs-qsv11.so`, `linux-pipewire.so`.
- Recommendation: use QSV (AV1 or HEVC) for screen recording on battery, because the iGPU is already on for niri rendering and the dGPU stays asleep. Use NVENC only when plugged in and when quality on fast motion matters more than battery.
- QSV AV1 on Linux is supported per OBS 30.0 release notes. VA-API AV1 encode is listed in the 30.1 beta notes. Meteor Lake QSV on Linux has no confirmed report found; the VPL runtime (`vpl-gpu-rt`) should be the driver. Verify on the machine before relying on it.
- PipeWire capture: OBS 30.1 added the PipeWire screen and video source. Capture of windows under niri goes through the same portal path as the calls above.

## 5. Font rendering and scaling

- Proven: `font-antialiasing=grayscale`, `font-hinting=slight`, `text-scaling-factor=1.0`, `color-scheme=prefer-dark`. fontconfig: antialias true, hintstyle slight, rgba 5 (fontconfig default), lcdfilter 1. A user `conf.d` sets hintslight.
- Flag: `gtk-xft-dpi=122880` in gtk-3.0 and gtk-4.0 settings, and `Gdk/UnscaledDPI 122880` in xsettingsd. 122880/1024 = 120 DPI. At niri scale 1.5 the nominal DPI would be 144 (147456). 120 DPI is the 1.25-scale value. GTK text may therefore render smaller than the rest of the UI. This matches wave-1 item 10.10. Verify visually (compare a 10 pt label in Nautilus vs a 10 pt label in Zen) before changing it, because GTK4 applies the fractional scale separately.
- Electron/Chromium fractional scale: Electron on Wayland uses the fractional-scale protocol when available. Whether Teams text is blurry at 1.5 was not checked. Look at Teams text at 100% zoom; if blurry, check `chrome://gpu` and the app's scale flags. Do not add flags without testing.
- Flatpak access: the Craft apps (EffectCraft, PhotoCraft) have `devices=dri`, `wayland`, `xdg-pictures`, `xdg-documents`, and `VK_LOADER_DRIVERS_DISABLE=*nvidia*` (so Vulkan uses the Intel ICD, which is correct for this laptop). Host fonts are exported read-only by the runtime. User fonts under `~/.local/share/fonts` are exported as well. Do not add `--filesystem=home`.
- Installed fonts: Inter (UI), Noto (Sans/Serif/CJK/Emoji), Liberation, Carlito, Caladea, Fira Sans, Open Sans, DejaVu, Adwaita fonts, Cantarell. Enough for design-app coverage. No Adobe fonts or commercial licences checked.

## 6. Colour and workflow extras

- Panel (wave-1 note 11): Samsung ATNA60DL01-0, about DCI-P3 primaries with a slight green overshoot, 400 nit full field. No ICC or colord profile for this panel exists on the system.
- Zen: `gfx.color_management.mode` is not set (Firefox default). On Linux, Firefox colour-manages only when a colord profile is present. Without a profile there is no conversion; sRGB content is shown as-is, which is the correct default for web design work. No change recommended until a measured profile exists.
- Chromium/Electron: no colour-management flags are set. Same reasoning.
- Resolve colour: use its own colour management (DaVinci YRGB or ACES, as already set up in the ACES Transforms folder). Keep the monitor SDR.
- Screenshots/annotation: no grim/slurp/satty/swappy installed (pacman errors). Recommend installing grim+slurp+satty only after confirming niri's built-in screenshot path (wave-1 item 3 notes screenshot-path null; set it to `~/Pictures/Screenshots`). Not installed; optional.
- Image viewers: GIMP 3.2.6 and Krita 6.0.4 installed. gwenview and mpv configs exist. Not reviewed further.

## Ranked recommendations

1. Verify Zen's real GPU decode with `about:support` (Graphics + Media sections) on the profile it actually opens. Resolve the `profiles.ini` Default=1 conflict and drop the leftover `gfx.webrender.compositor=false` if it is still there. Highest impact for battery during browser video and web apps.
2. Verify GTK font size at scale 1.5. Consider changing `gtk-xft-dpi` from 120 to 144 (147456) after a visual check. Low effort, visible improvement across GTK apps.
3. Test browser screen share (Meet, Teams web, Zoom web) on niri: window and monitor, with the portal path. Do this before relying on it for a call.
4. For OBS on battery, use QSV (AV1 or HEVC) for recording/streaming; NVENC only when plugged in. Test QSV on Meteor Lake once before a real recording.
5. Resolve: plug in for Resolve work. Use NVDEC/NVENC. Use proxies or optimised media on battery. Keep 48 kHz and test Fairlight playback for xruns.
6. Keep sRGB for web and design work until a measured colord profile exists. Do not add colour-management prefs yet.
7. Measure, do not guess, the battery impact of software vs hardware decode (powertop during 10-minute playback).

## Open questions
- Which Zen profile is live, and is `about:support` showing hardware decode for H.264/VP9/AV1.
- Actual Teams/Meet/Zoom screen-share behaviour on niri with gnome portal (untested).
- Camera enumeration through PipeWire (needs `wpctl status`, not device opening).
- Whether Resolve 21.0.4 uses Intel QSV at all on Linux (no evidence found).
- Meteor Lake QSV AV1 in OBS on Linux (no confirmed report).
- Claude desktop and Spotify GPU/Ozone flags (binary launcher; not inspected).

## Sources consulted (web, secondary)
- DaVinci Resolve Linux NVDEC/Intel notes: https://wiki.archlinux.org/title/DaVinci_Resolve , https://wiki.nixos.org/wiki/DaVinci_Resolve , https://forum.blackmagicdesign.com/viewtopic.php?p=1024570
- Firefox VA-API: https://bugzilla.mozilla.org/show_bug.cgi?id=1683808 , https://bugzilla.mozilla.org/show_bug.cgi?id=1793507
- niri screencast: https://github.com/niri-wm/niri/issues/2808 , https://www.mintlify.com/niri-wm/niri/features/screencasting
- Chromium VA-API on Wayland: https://ubuntuhandbook.org/index.php/2024/01/chromium-va-api-wayland/
- OBS QSV/AV1 on Linux: https://Phoronix.com/news/OBS-Studio-30-Released , https://gamingonlinux.com/2024/03/obs-studio-30-1-out-now-with-av1-support-for-va-api-pipewire-video-capture
