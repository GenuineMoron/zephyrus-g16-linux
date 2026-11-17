### What happened?

With `vrr = "fullscreen"`, VRR never turns on for fullscreen content on this laptop's internal panel (Intel i915, eDP, 48–240 Hz, `vrr_capable = 1`). Each time it is tried, the log shows `failed to enable VRR` and the commit fails with `EINVAL`. Umbriel then seems to try again on the next frame: one ~25 s fullscreen mpv session produced 343 `Atomic commit failed: Invalid argument` lines.

The kernel side (`drm.debug=0x06`) shows why: on this hardware, enabling VRR is not a fastset, so it needs a full modeset (`DRM_MODE_ATOMIC_ALLOW_MODESET`):

```
[drm:intel_pipe_config_compare [i915]] [CRTC:153:pipe A] fastset requirement not met in set_context_latency (expected 1, found 0)
[drm:intel_pipe_config_compare [i915]] [CRTC:153:pipe A] fastset requirement not met in hw.pipe_mode.crtc_vblank_start (expected 1601, found 1600)
[drm:intel_pipe_config_compare [i915]] [CRTC:153:pipe A] fastset requirement not met in hw.adjusted_mode.crtc_vblank_start (expected 1601, found 1600)
[drm:intel_atomic_check [i915]] [CRTC:153:pipe A] fastset requirement not met, forcing full modeset
[drm:intel_crtc_state_dump [i915]] vrr: yes, fixed rr: no, vmin: 1776, vmax: 8880, flipline: 1776, ...
```

Two possible improvements:
1. After a VRR commit fails, stop retrying it every frame (for example until the next fullscreen enter/leave or config change). The retries are wasted commits at 240 Hz.
2. Optionally allow a modeset for the VRR transition when entering fullscreen, since some drivers need one. The HDR switch already does a full modeset on this machine (pipe bpp 24→30), so the two could share it.

### How can we reproduce it?

`[output.eDP-1] vrr = "fullscreen"`, then play any video fullscreen in mpv (or start a fullscreen game), and watch `journalctl --user -u umbriel`.

### Umbriel version

umbriel 0.1.0 (88ba829c6152), CachyOS package 0.1.0.r1569.88ba829-1

### System details

ASUS ROG Zephyrus G16 GU605MI (2024): Core Ultra 9 185H (Meteor Lake, Arc iGPU, i915), RTX 4070 excluded via `[drm] ignored_pci_addresses`. Internal Samsung ATNA60DL01 OLED, 2560x1600@240 Hz, PSR1, eDP with DSC. Kernel 7.3.3 (CachyOS), wlroots 0.20.2, Mesa 26.2.6.

### Logs

```
[WRN] [output] output 'eDP-1': failed to enable VRR
[ERR] [wlr] [backend/drm/atomic.c:82] connector eDP-1: Atomic commit failed: Invalid argument
(repeated every frame while fullscreen)
```
