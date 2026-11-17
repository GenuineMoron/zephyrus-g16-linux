### What happened?

During ordinary desktop use (scrolling pages in a Firefox-based browser, opening apps), Umbriel logs many `Atomic commit failed: Device or resource busy` errors on the internal panel. Each one is a dropped frame, which shows up as small stutters. It's never seen at idle.

| Session | Length | EBUSY commit failures |
|---|---|---|
| Umbriel, browsing | 25 min | 249 |
| Umbriel, browsing | 16 min | 234 |
| Umbriel, mostly idle | 9 min | 0 |
| niri 26.04, same machine and apps | 274 min | 18 page-flip failures |

So it is roughly 10–15 per minute of activity under Umbriel, against well under one per ten minutes with niri, on the same kernel, Mesa and panel. This looks like the wlroots/Intel issue in wlroots#3507 and sway#9179, where a commit lands while the previous flip is still pending. In the sway report, limiting the render deadline (`max_render_time`) made it go away. Umbriel has no equivalent setting, as far as I can tell.

Could Umbriel's frame scheduling avoid committing while a page flip is still pending, or expose a render-time/deadline option like sway's `max_render_time`?

### How can we reproduce it?

Internal 240 Hz eDP panel on i915, scale 1.5, `sdr_gamut = "srgb"` (so every frame is composited; direct scanout is inactive with "color conversion"). Scroll a long page in the browser for a minute and count `Atomic commit failed: Device or resource busy` in `journalctl --user -u umbriel`.

### Umbriel version

umbriel 0.1.0 (88ba829c6152), CachyOS package 0.1.0.r1569.88ba829-1

### System details

ASUS ROG Zephyrus G16 GU605MI (2024): Core Ultra 9 185H (Meteor Lake, Arc iGPU, i915), RTX 4070 excluded via `[drm] ignored_pci_addresses`. Internal Samsung ATNA60DL01 OLED, 2560x1600@240 Hz, PSR1 enabled. Kernel 7.3.3 (CachyOS), wlroots 0.20.2, Mesa 26.2.6.

### Logs

```
13:50:15.141 [ERR] [wlr] [backend/drm/atomic.c:82] connector eDP-1: Atomic commit failed: Device or resource busy
13:50:16.412 [ERR] [wlr] [backend/drm/atomic.c:82] connector eDP-1: Atomic commit failed: Device or resource busy
13:50:21.674 [ERR] [wlr] last message repeated 2 times
13:50:30.352 [ERR] [wlr] last message repeated 4 times
```

Happy to collect a `drm.debug` trace around a failure if that helps.
