# 37: HDR under Umbriel: root cause, fix, verification (2026-11-15)

**Result: HDR works** on the internal OLED under Umbriel. For fullscreen HDR10 video it switches to XR30 / PQ / BT.2020, and back to SDR afterwards, with no black screen. Visually confirmed with a PQ test pattern: the 400, 616 and 1000-nit patches step up above SDR white (203). The NVIDIA GPU stays asleep.

## Why HDR was missing
| Layer | State |
|---|---|
| Panel (Samsung ATNA60DL01) | Declares HDR **only in DisplayID 2.0**: 0x26 Display Interface Features byte `0x50` (DCI-P3, BT.2020/ST 2084); 0x21 Display Parameters 400 (full) / 616 (10%) / 0.0005 cd/m². No CTA-861 block. No serial number in the EDID. |
| Kernel (i915, eDP) | Fine: `HDR_OUTPUT_METADATA`, `Colorspace` (BT2020_RGB), `max bpc`; `i915.enable_dpcd_backlight=3` (Intel HDR AUX interface) |
| libdisplay-info 0.3.0 | Reads HDR from CTA-861 only, so it reported no PQ and no BT.2020 |
| wlroots 0.20.2 `backend/drm/util.c` | Offers PQ only if `type1 && pq` and the HDR_OUTPUT_METADATA prop exists |
| Umbriel | `umbriel color` showed `supported transfer functions: none` |

## Fix
- [packaging/libdisplay-info-displayid-hdr](../../packaging/libdisplay-info-displayid-hdr/): 0.3.0 + one patch (same ABI). It adds a DisplayID 2.0 fallback, following upstream MR 210's interpretation. It also sets `type1` (MR 210 doesn't, so MR 210 alone would *not* enable HDR in wlroots), takes luminance from 0x21, and claims BT.2020 YCbCr only when the panel supports YCbCr. Installed as `libdisplay-info 0.3.0-1.3`.
- After installing, the compositor must restart, because a running process keeps the old library mapped. A compositor re-reads EDID only when a display connects. To force that without a restart, write `off` to the connector's `status`, send a synthetic `change <uuid> HOTPLUG=1` uevent (with a temporary /run/udev rule mapping `SYNTH_ARG_HOTPLUG` → `HOTPLUG`), then write `detect`. The kernel alone doesn't send a hotplug event for the forced off.

## Players
- mpv: `~/.config/mpv/mpv.conf` sets `vo=gpu-next`, `gpu-api=vulkan` and `target-colorspace-hint-mode=source`.
  - The default `target` mode sends the screen's SDR description (MaxCLL 80), so `hdr = "auto"` rightly stays SDR.
  - The OpenGL path can't tag PQ.
  - The `~/.local/bin/mpv` wrapper sets `VK_DRIVER_FILES` to Intel only. Listing Vulkan devices otherwise loads NVIDIA's driver and wakes the RTX 4070 for ~2.3 s. `vulkan-device=` makes it worse, because mpv validates that option by listing every device.
- Test clip: [tools/hdr/make-hdr-test-clip.sh](../../tools/hdr/make-hdr-test-clip.sh).

## Other findings during the test
- **VRR never enables under Umbriel** (`failed to enable VRR`, `EINVAL`). On this pipe, enabling VRR is not a fastset in i915: `set_context_latency` and `crtc_vblank_start` change, so it needs a full modeset. Umbriel commits it without `ALLOW_MODESET` and retries every frame (343 failed commits in about 25 s). Reported as umbriel#809.
- **Dropped frames:** about 10–15 `EBUSY` atomic commit failures per minute while browsing, none at idle. niri had 18 in 274 min. Reported as umbriel#810.
- **Idle power, screen on, battery:** Package 2.05–2.35 W, platform 4.87–5.66 W (keyboard backlight at level 2), PSR self-refresh 100%, Umbriel CPU 0.05%. Same as niri (research/36: 2.22 W, about 5.0 W).
- ICC: the ASUS CMDEF profile is rejected (per-channel TRCs differ by up to 2%). Its primaries equal the EDID's to within 0.0004, so the EDID fallback loses almost nothing.

## Upstream
- umbriel #809 (VRR), #810 (EBUSY), #811 (HDR on DisplayID 2.0 panels; mpv tips)
- libdisplay-info MR 210 review: `type1`, luminance from 0x21, YCbCr over-claim, plus this panel's EDID. Draft: [upstream/drafts/libdisplay-info-mr210-review.md](../../upstream/drafts/libdisplay-info-mr210-review.md)
