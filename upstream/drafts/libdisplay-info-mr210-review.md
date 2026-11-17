Another real-world panel for testing, since that came up above: **Samsung ATNA60DL01** (2560x1600@240 OLED) in an ASUS ROG Zephyrus G16 GU605MI (2024), Intel Meteor Lake i915 eDP. Its EDID is attached: [atna60dl01.edid](/uploads/da4407244b8163f5ab1d287fba53558c/atna60dl01.edid) (it has no serial number). The panel declares HDR only in a DisplayID 2.0 extension and has no CTA-861 block:

- Display Interface Features (0x26): combination byte `0x50` = DCI-P3/DCI-P3 + BT.2020/SMPTE ST 2084; RGB only (the YCbCr colour depth bytes are 0)
- Display Parameters (0x21): native max luminance 400 cd/m² (full coverage), 616 cd/m² (10% window), min 0.0005 cd/m²

With 0.3.0, `di_info_get_hdr_static_metadata()` reports no PQ, so wlroots compositors never offer HDR. With this MR, PQ and BT.2020 RGB are detected. Thanks for working on it!

Three things I ran into when using it end to end with wlroots 0.20.2 (Umbriel compositor):

1. **`type1` stays false, so wlroots still doesn't offer PQ.** `backend/drm/util.c` requires `hdr_static_metadata->type1 && hdr_static_metadata->pq` (plus the HDR_OUTPUT_METADATA property). DisplayID has no metadata-type field. A PQ sink on DP/eDP receives the CTA-861.3 static metadata (HDR Metadata InfoFrame/SDP), which is Static Metadata Type 1, so setting `type1 = pq || hlg` in the DisplayID fallback seems right. With that, the compositor offers PQ and switches the panel into HDR (XR30, PQ, BT.2020) for HDR10 video. Visually confirmed with a PQ test pattern: 400/616/1000-nit patches step up above SDR white.
2. **Luminance stays 0.** Display Parameters (0x21) carries the native luminance range as IEEE 754 half floats (payload offsets 21, 23, 25). Mapping 10% window → desired max, full coverage → max frame-average, min → min gives compositors a tone-mapping target (616 / 400 / 0.0005 here). It may be a separate MR, but it would make this fallback complete.
3. **`bt2020_ycc` is set for any BT.2020 combination.** The same block says whether YCbCr is supported at all (the 4:4:4/4:2:2/4:2:0 colour depth bytes). This panel is RGB-only, so gating `bt2020_ycc` on a non-zero YCbCr depth would avoid over-claiming.

For reference, the 0.3.0 backport I'm running locally does exactly that in `derive_edid_hdr_static_metadata()`:

```c
hsm->pq = displayid2_has_combo(d, BT2020, ST2084);
hsm->hlg = displayid2_has_combo(d, BT2020, HLG);
hsm->type1 = hsm->pq || hsm->hlg;
if ((hsm->pq || hsm->hlg) && d->has_display_params) {
	hsm->desired_content_max_luminance = d->native_max_luminance_10pct;
	hsm->desired_content_max_frame_avg_luminance = d->native_max_luminance_full;
	hsm->desired_content_min_luminance = d->native_min_luminance;
}
```
