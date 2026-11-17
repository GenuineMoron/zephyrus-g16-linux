# 11 - Display, colour, VRR, brightness (ROG Zephyrus G16 GU605MI)

Date: 2026-11-14. Read-only research. No state changed.

## 1. Panel identity (proven from EDID, /sys/class/drm/card1-eDP-1/edid, decoded with edid-decode)
- Samsung Display Corp, product "ATNA60DL01-0", SDC, made 2023. Matches ROG Nebula 2560x1600 OLED.
- Base block: 10 bpc, DisplayPort, 34 x 22 cm, gamma 2.2. DisplayID: 344.4 x 215.3 mm, native 12 bpc.
- Chromaticities (DisplayID, native): R (0.680, 0.320), G (0.237, 0.723), B (0.140, 0.050), W (0.313, 0.329). Red and blue are DCI-P3 D65. Green sits outside P3 (P3 green is about 0.265, 0.690), so this is slightly wider than P3 in green.
- Luminance (DisplayID): 400 cd/m2 full field, 616 cd/m2 at 10% window, min 0.0005 cd/m2.
- Interface features: DCI-P3 and BT.2020/PQ (ST 2084) colour space and EOTF combination. So the panel is an HDR-capable device.
- Timings: 2560x1600@240.000 (preferred), 2560x1600@60.000. The EDID's range descriptor says 48-240 Hz. niri only lists 60 and 240 because only those DTDs are advertised.
- Adaptive Sync: native-panel range 60-240 Hz and 48-60 Hz descriptors, seamless transition.
- niri 26.04 (`niri msg outputs`): "Variable refresh rate: supported, disabled". Current mode 2560x1600@240, scale 1.5.

## 2. Backlight and sensors (proven)
- Kernel cmdline has `i915.enable_dpcd_backlight=3`.
- /sys/class/backlight: intel_backlight (raw, max 512, brightness 154 = 30%) and nvidia_0 (max 100). nvidia_0 exists but is a dGPU fallback.
- noctalia's log picks intel_backlight as the exact eDP-1 match and prefers it over nvidia_0. Good.
- Oddity: intel_backlight actual_brightness reads 0 while brightness is 154. Unexplained. It may be a DPCD reporting quirk or the panel being blanked at read time. Open question.
- No IIO devices (/sys/bus/iio/devices absent). No ambient light sensor is exposed to Linux.
- asusd sees intel_backlight as the primary backlight.
- Keyboard backlight: asus::kbd_backlight at level 3.
- i915 params are unreadable without root (/sys/module/i915/parameters permission denied), so the runtime values of enable_dpcd_backlight, enable_psr and enable_fbc are unverified.

## 3. ASUS panel controls (proven)
- /sys/devices/platform/asus-nb-wmi/panel_od = 1. Panel overdrive is ON.
- asusctl 6.5.0 is installed (`asusctl armoury` and `asusctl backlight` subcommands exist).

## 4. External sources (web)
- i915 enable_dpcd_backlight values (per kernel source excerpts and patch threads): -1 = auto from VBT (default since the 2019-2020 patch), 0 = off, 1 = enable, 2 = force VESA, 3 = force Intel interface. Newer kernels make it 0400, so it is read-only at runtime. Sources: https://elixir.bootlin.com/linux/v4.14.70/source/drivers/gpu/drm/i915/i915_params.c ; https://lkml.iu.edu/hypermail/linux/kernel/2101.0/03009.html . Implication: 3 is a forced Intel DPCD interface. It is correct only if the panel really exposes Intel AUX backlight. The journal shows no DPCD backlight message, so whether it is actually in use is unproven.
- niri wp-color-management-v1 / HDR status for 2026: not found. The only niri-specific hit is an open discussion, https://github.com/niri-wm/niri/discussions/2685 , with no maintainer answer in the snippet. Treat niri as having no proven colour management or ICC support. Inferred: niri has no per-output ICC support as of 26.04.
- Protocol landscape: GNOME 48 (Mutter) merged wp_color_management_v1 (https://www.phoronix.com/news/GNOME-wp_color_management_v1). Qt now uses color-management-v1 (https://www.phoronix.com/news/Qt-color-management-v1). Wayland-protocols 1.47 revised it (https://phoronix.com/news/Wayland-Protocols-1.47).
- KDE Plasma: HDR is PQ with static metadata (https://planet.kde.org/xavers-blog-2023-12-17-an-update-on-hdr-and-color-management-in-kwin). Plasma 6.7 reportedly adds ICC profile support while HDR is active (https://news.lavx.hu/article/kde-plasma-6-7-brings-icc-profile-support-in-hdr-mode-and-direct-scan-out-improvements). This is unverified, and KDE bug 524038 shows a PQ-black crush regression with an ICC profile in 6.7.4 (https://bugs.kde.org/show_bug.cgi?id=524038). Long-standing bug: sRGB content over-saturated in HDR (https://bugs.kde.org/show_bug.cgi?id=486725).
- VRR on niri: `variable-refresh-rate on-demand=true` in an output block, with a window rule `variable-refresh-rate true` for matched apps. Source: https://niri-wm.github.io/niri/Configuration:-Outputs
- Panel spec sources: https://laptopmedia.com/laptop-specs/asus-rog-zephyrus-g16-gu605-115/display/ . Listed PWM 1000 Hz, sRGB 100%, dE 1.9 ( factory figure).
- No Linux ICC or colord/DisplayCAL profile for this panel was found.

## 5. Findings and recommendations (ranked)
1. Colour for design work (highest impact). The panel is about DCI-P3 with a green overshoot. Without compositor colour management, sRGB content will look over-saturated. Options:
   a. Keep the desktop in SDR sRGB and accept the gamut mismatch for general UI. For Resolve, use its own colour management (ACES or Resolve Colour Management), and keep the monitor as an SDR display. Verify the panel is not clipping at the Resolve output stage.
   b. Use a measured ICC profile (colord). Needs a colorimeter (e.g. i1Display or Spyder) and DisplayCAL. No compositor on niri applies it yet, so it helps only apps that read the profile (Resolve, Darktable, GIMP). Inferred.
   c. Use KDE Plasma 6.7+ for colour work if ICC-in-HDR works for this panel. Unverified, so test it before relying on it.
2. Battery: keep 60 Hz on battery. The EDID gives a 60 Hz mode. niri can switch with `niri msg output eDP-1 mode 2560x1600@60.000` (proven command syntax from `niri msg outputs`). Inferred power saving on OLED: fewer frames to drive. Measure with powertop or upower before claiming a number.
3. VRR: on-demand is the safe setting on niri. Enable it for games or video only.
4. Longevity: keep panel_od enabled only if motion matters. Overdrive increases drive stress on OLED. Inferred. Use dark UI, auto-hide bars, short screen-off timeouts. Static UI elements are the main burn-in risk.
5. Brightness: keep i915.enable_dpcd_backlight unchanged until its runtime value is confirmed. Check `journalctl -k | grep -i dpcd` after a reboot. Investigate the actual_brightness=0 oddity first.

## 6. Open questions
- Runtime values of i915 enable_dpcd_backlight, enable_psr and enable_fbc (needs root or dmesg).
- Why intel_backlight actual_brightness reads 0.
- niri colour management roadmap (check niri discussion 2685 and release notes).
- Does KDE Plasma 6.7 ICC-in-HDR work on this panel, and is it per output?
- Whether the panel's native green overshoot matters visually. Needs a colorimeter.
- Whether Armoury Crate's OLED Care features (pixel refresh, panel care) can be reached on Linux via asusctl. Not verified.
