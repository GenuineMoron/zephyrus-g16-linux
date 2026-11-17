# 31: Screen-on idle power, controlled A/B (2026-11-15)

**How:** on battery, screen on at normal working brightness, hands-off (no input during the run). noctalia idle screen-off and lock were paused. An empty workspace was shown, so no terminal output redrew the screen. Each window was 10 s settle + 45 s measure, with alternating order. Columns: turbostat `Pkg%pc6/pc8/Pk%pc10`, `PkgWatt`, `SysWatt` (RAPL psys, the whole platform), and battery V×I averaged over the window (lags and smooths). PSR1 was enabled in every window. Windows in which the NVIDIA GPU woke are excluded.

| Window | PC6 | PC8 | PC10 | Package W | Platform W | Battery W |
|---|---|---|---|---|---|---|
| base (240 Hz, keyboard light 2) | 21.2 | 40.1 | 0.6 | 1.96 | 4.71 | 8.90 |
| keyboard light off | 22.6 | 38.8 | 0.2 | 1.97 | 4.14 | 6.95 |
| base | 22.8 | 38.4 | 0.3 | 1.96 | 4.74 | 7.90 |
| keyboard light off | 21.2 | 38.3 | 0.6 | 2.00 | 4.31 | 6.93 |
| 60 Hz | 24.1 | 36.8 | 0.3 | 1.97 | 4.70 | 7.94 |
| asusd stopped, keyboard chips `on` | 22.6 | 38.9 | 0.8 | 1.95 | 4.59 | 7.86 |
| asusd stopped, chips `auto` (suspended) | 22.9 | 38.9 | 0.4 | 1.95 | 4.58 | 7.83 |
| asusd stopped, chips `auto` | 21.6 | 41.8 | 0.1 | 1.92 | 4.46 | 9.48 |

## Results

- **Keyboard backlight (level 2) costs ~0.5 W** at idle: 4.71/4.74 → 4.14/4.31 W platform, consistent in both pairs. That is about 10% of screen-on idle power. → An idle timeout like Armoury's (off after 60 s, back on input) is now a noctalia idle behavior: [configs/home/.local/bin/kbd-light-idle](../../configs/home/.local/bin/kbd-light-idle).
- **60 Hz vs 240 Hz: no difference on a static screen** (4.70 vs 4.71–4.74 W). With PSR1 active the panel refreshes itself, so the refresh rate barely matters at idle. It may still matter with moving content (scrolling, video). That is not measured yet.
- **Keyboard USB chips: no PC10 gain with the screen on.** With the screen off they unblock PC10 (0.4% → 65%, [finding 06](../findings/06-keyboard-usb-blocks-deepest-idle.md)). With the screen on, PC10 stays below 1% either way, so a display-side blocker dominates. The next step is the PMT block-cause counters and LTR with the screen on.
- **NVIDIA wakes during the test:** two came from a kernel worker (10:56:04, 11:00:50, 4 min 46 s apart, no app holding the GPU), and two from ACPI notifies when settings changed. A `__pm_runtime_resume` stack tracer is running to catch the worker's caller.
- **Firmware notifications that wake the NVIDIA GPU:** `Notify(NPCF, 0xC0)` (NVIDIA Dynamic Boost controller, `NVDA0820`) is sent from EC query `_QA8` (Dynamic Boost toggle), `SFMN`/`SPAB` (via `_QD4`), and ASUS WMI `WMNB` device `0x001200C0` (dsdt.dsl 76634, 78720–78842, 81163, 81559–81691). The NVIDIA driver resumes the GPU to handle each one. This happens on charger and profile changes and asusd start/stop. Candidate upstream report: defer NPCF handling while runtime-suspended.
