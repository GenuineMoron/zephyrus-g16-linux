# Status

The first table lists the issues; the "Next" column for each open one is in the second table. "Proven" means traced to code, firmware or a kernel trace; "measured" means numbers exist, but the cause is not yet fully traced.

| # | Issue | State |
|---|---|---|
| 1 | Hibernate hangs at power-off with heavy memory use | **Fixed**, proven ([01](findings/01-hibernate-hang-cs35l56.md)) |
| 2 | Shell + lock screen die when a launched app is OOM-killed | **Fixed** ([04](findings/04-shell-killed-by-oom.md)) |
| 3 | Text console flashes on every standby (`chvt 63`) | **Fixed:** NVIDIA sleep services masked ([02](findings/02-standby-nvidia-wakes-idle-gpu.md)) |
| 4 | Every standby wakes the idle NVIDIA GPU (+2.7 s entry, +0.55 s wake) | Proven, NVIDIA design |
| 5 | Wake 1.7 s on AC: 0.65 s is the audio codec | Proven: CachyOS `power_save=0` on AC |
| 6 | One night at ~5 W in standby | **Open**. The "8% S0ix" was a kernel counter bug ([03](findings/03-standby-s0ix-and-wake-timeline.md)); the next battery night (2026-11-14/15) was 0.86 W with ~100% S0i2.1 |
| 7 | S0i2.2 never reached | Measured; likely not reachable on Linux MTL-H; low value |
| 8 | ASUS ITE keyboard/lighting USB devices have autosuspend off | **Fixed** with #13 (udev rule; a lit Num Lock LED also blocks it, so the compositor no longer turns Num Lock on) |
| 9 | Hibernate save/resume speed (~33 s resume with 12 GB image, LZO) | Measured |
| 10 | Upstream reports: Cirrus CS35L56, NVIDIA open modules | NVIDIA: the battery-tick wakes are already reported (#1300) and fixed in a future driver; Cirrus still to write |
| 11 | Ordinary app launches wake the NVIDIA GPU (+2.6 s each) | **Fixed**: GTK `GSK_RENDERER=gl`; NVIDIA stays visible to games; wake log ([05](findings/05-apps-wake-nvidia-gpu.md)) |
| 12 | Kernel under-reports hardware sleep over 71.6 min (`last_hw_sleep` truncated to u32 µs) | Proven; patch drafted ([03](findings/03-standby-s0ix-and-wake-timeline.md)) |
| 13 | CPU almost never reaches PC10 at idle: asusd holds the keyboard/Slash USB chips awake | **Fixed** 2026-11-15 (patched asusd + autosuspend + sleep guard), proven 0.4% → 65% PC10 with the screen off ([06](findings/06-keyboard-usb-blocks-deepest-idle.md)) |
| 14 | Keyboard backlight changes fail (`-108`) while the keyboard is autosuspended | **Fixed**: hid-asus patch (DKMS), A/B tested; upstream patch ready ([42](research/42-audit-2026-11-16.md)) |
| 15 | On battery the NVIDIA GPU wakes ~23 s on every 1% of charge (firmware `_QB6` → `Notify(NPCF, 0xC0)`) | Proven; NVIDIA fix queued for a future driver (bug 4084236) ([42](research/42-audit-2026-11-16.md)) |

| # | Next |
|---|---|
| 4 | Stay in Hybrid mode (decision 2026-11-14: the GPU must stay available on battery); report to NVIDIA |
| 5 | Leave as is; on battery the codec sleeps |
| 6 | Keep logging: EC dGPU flags + RAPL SoC/platform split per stretch will localise it if it recurs |
| 7 | Not pursued |
| 8 | Done |
| 9 | Test LZ4 compressor and a smaller `image_size` |
| 10 | Use the stacks and traces in findings 01 and 02 |
| 11 | Re-login to apply to keybind-launched apps; watch `journalctl -t gpu-wake` |
| 14 | Send the hid-asus patch to linux-input (needs a Signed-off-by); keep the DKMS package until it lands |
| 15 | After each NVIDIA driver update, check for the NVPCF deferral (NVIDIA bug 4084236) and re-measure with `journalctl -t gpu-wake` |
| 13 | Watch typing feel and #690 across long sleeps; drop the override when Arch ships PR #404 |
| 12 | Run the patched `intel_pmc_core` for one long standby, then send upstream |
