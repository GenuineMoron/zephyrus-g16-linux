### What happened?

Sharing this in case others hit it: HDR is never offered on this laptop's internal OLED, although the panel, the kernel and Umbriel all support it. `umbriel color` shows `supported transfer functions: none`.

The cause is upstream of Umbriel. The panel (Samsung ATNA60DL01, also used in other 2024 laptops) declares HDR only in a **DisplayID 2.0** extension: BT.2020/SMPTE ST 2084 in the Display Interface Features block (0x26), and its luminance (400 cd/m² full screen, 616 cd/m² 10% window) in the Display Parameters block (0x21). There is no CTA-861 extension. libdisplay-info 0.3.0 only reads CTA-861 HDR metadata, so `di_info_get_hdr_static_metadata()` reports no PQ, and wlroots never sets `WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ`.

- Upstream fix in progress: libdisplay-info MR 210 (https://gitlab.freedesktop.org/emersion/libdisplay-info/-/merge_requests/210). Note that wlroots also requires `type1` in `backend/drm/util.c` (`type1 && pq`), which that MR doesn't set yet; I'm raising that on the MR.
- With a patched libdisplay-info (0.3.0 + DisplayID 2.0 fallback, `type1` set, luminance from 0x21), `umbriel color` shows `supported transfer functions: PQ; primaries: BT.2020`. `hdr = "auto"` then switches to XR30/PQ for fullscreen HDR10 video and back to SDR afterwards, with no black screen on i915. Visually confirmed with a PQ test pattern.

One thing that might be worth a line in the HDR docs: mpv's default `--target-colorspace-hint-mode=target` tags the surface with the output's SDR description (`umbriel color` showed mastering 0.195–80 cd/m², MaxCLL 80), so `hdr = "auto"` correctly stays in SDR. `--target-colorspace-hint-mode=source` passes the video's own HDR10 metadata and triggers HDR. Also, mpv needs `gpu-api=vulkan`: the OpenGL path doesn't tag the surface.

### How can we reproduce it?

Any panel whose EDID has HDR only in a DisplayID 2.0 extension (`edid-decode` shows "Display Interface Features Data Block … BT.2020/SMPTE ST 2084" and no CTA-861 block).

### Umbriel version

umbriel 0.1.0 (88ba829c6152)

### System details

ASUS ROG Zephyrus G16 GU605MI (2024), Meteor Lake i915 eDP, Samsung ATNA60DL01 OLED, kernel 7.3.3, wlroots 0.20.2, libdisplay-info 0.3.0, Mesa 26.2.6.
