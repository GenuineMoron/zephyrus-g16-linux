# 44. Game power: frame targets and an always-on governor (2026-11-21)

Goal: every game runs as quietly as it can while still hitting its frame target, and gets full power automatically when it needs it. Nothing is throttled blindly, and there are no per-game launch wrappers to maintain.

## What the measurements said ([43](43-elden-ring-umbriel.md))

- **Fixed power caps don't help.** A 40 W CPU cap changed nothing, because the CPU wasn't above it.
- **Noise follows wasted work.** Frames nobody sees, and the CPU's top boost steps, both turn into heat.
- **The profile mostly sets the fan curve and the shared CPU/GPU budget.** With the CPU allowed to run efficiently fast (`balance_performance`), Balanced held 60 fps in a busy Elden Ring area, about 1,000–1,300 rpm quieter than Performance. Balanced's default `balance_power` starved the CPU (48 fps).

## What others do

- **Launch wrappers.** CachyOS `game-performance`, `gamemoderun` and SteamTinkerLaunch go in each game's launch options. STL can also be the default compatibility tool, but it is a large layer between Steam and Proton.
- **Process detection.** [falcond](https://github.com/PikaOS-Linux/falcond) (Nobara/PikaOS) spots games by their processes and applies per-game profiles from a community repository: a power profile, an sched_ext scheduler, vcache. It needs no launch options, but it doesn't measure frame rates.
- **Frame limiters.** libstrangle has a separate battery cap; MangoHud and gamescope have their own.
- **Taken from these:** game detection that needs no per-game setup (like falcond), plus a decision loop that measures frame rates, which none of them has.

## Design

1. **Session-wide defaults:** [57-proton-game-defaults.conf](../../configs/home/.config/environment.d/57-proton-game-defaults.conf) in environment.d, so Steam and other launchers pass them to every game.
   - `VKD3D_DISABLE_EXTENSIONS=VK_EXT_present_timing`, the fix from [43](43-elden-ring-umbriel.md).
   - `DXVK_FRAME_RATE` and `VKD3D_FRAME_RATE` set to 120. That is an even divisor of the 240 Hz panel without VRR, and the default target. Games capped lower in-game run lower.
   - The NVIDIA shader cache (10 GiB, never pruned), in `56-nvidia-shader-cache.conf`.
2. **[game-governor](../../configs/usr/local/sbin/game-governor):** a root service, always on ([unit](../../configs/etc/systemd/system/game-governor.service)).
   - **Detection:** a kernel uprobe event, in a private ftrace instance, sits on the `vkQueuePresentKHR` thunk in every installed Proton's `winevulkan.so` (Steam's Protons, Proton-CachyOS, umu). A process presenting at 20 fps or more for 3 s is a game; the session ends when that process exits.
   - **Idle cost:** it blocks on `trace_pipe` and wakes once a minute to check whether Proton was updated, by inode and mtime only. Measured: 5 wake-ups in 125 s, ~17 MB.
   - **Settings:** read from `~/.config/game-env/default.env`, then `<SteamAppId>.env` (only `GAME_*` keys).
     - `GAME_FPS_TARGET_AC/BATTERY`: frame target, 120/60 by default.
     - `GAME_GOVERNOR`: `auto`, `fixed` or `off`.
     - `GAME_PROFILE`: the profile for `fixed` mode.
     - `GAME_BALANCED_EPP`: the CPU setting for Balanced during the session, default 2.
     - `GAME_CPU_MAX_MHZ`: an optional boost cap.
   - **`auto` mode:**
     - **Start:** efficient, meaning Balanced plus `balance_performance`.
     - **Escalate:** Performance after 10 s below the target (on AC only), kept only if fps rises 5 % or reaches the target. If it doesn't help, the game is treated as capped at that frame rate for 5, then 10, then 20 minutes.
     - **Drop back:** to efficient after 3 min at the target with the GPU at most 75 % busy. If the target is then missed, it waits twice as long before trying again.
   - **At the end:** Balanced's EPP, the CPU cap and asusd's profile for the current power source are restored. A crash is repaired at the next start.
   - **Logging:** every decision, plus a per-game summary (average fps, share of time in Performance, with a hint when a lower graphics setting would make it quieter), in `journalctl -u game-governor`.
3. **Per-game launch options only where proven necessary:** Elden Ring and Nightreign get `PROTON_ENABLE_WAYLAND=1 __NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only %command%`. They were set with Steam closed, after checking that the `localconfig.vdf` round trip was byte-identical, and with a backup.
4. **GameMode:** no longer used for power. [gamemode.ini](../../configs/home/.config/gamemode.ini) pins the `powersave` governor, so a game that calls `gamemoderun` can't override the EPP strategy.
5. **Measuring a game:** `sudo game-capture [seconds]` ([tools/game-capture](../../tools/game-capture)).

## Tested

- **Decision logic:** simulated with a fake clock.
  - A game holding its target stays efficient.
  - A game that needs Performance gets it, then drops back when the scene lightens.
  - A self-capped game is detected, and retries back off.
  - A CPU-bound game where Performance helps 8 % keeps it.
  - Fixed mode holds its profile.
- **Detection and session lifecycle:** a fake frame source driving the real main loop. A session started 3 s after presents began, measured 60 fps, and on process exit restored EPP 3, uncapped the CPU and returned to the AC profile.
- **The uprobe path:** a test binary called the probed symbol 300 times and 300 were counted. That covers the offset computation from the PT_LOAD headers, the symlinks needed for paths with spaces, and the trace_pipe parsing.
- **Not yet:** a real game session.

## In-game settings

These matter more than any power setting, and Linux has no equivalent of NVIDIA's "optimal settings" (Windows only). What helps:
- **The governor's summary is the feedback loop.** A game that often needs Performance at its settings is a candidate for one notch lower (or upscaling), and a game that never leaves efficient with the GPU half idle has room for more.
- **In-game features that adapt by themselves:** dynamic resolution with a frame-rate target, and upscalers (DLSS, FSR, XeSS). Elden Ring and Nightreign have neither.
- **Optional tools:**
  - OptiScaler adds or updates upscalers in games.
  - lsfg-vk adds frame generation.
  - gamescope can render below native resolution and upscale with FSR.
  None of them is installed: each changes how a game looks or feels, so it is a per-game choice.

## Not done, on purpose

- **No custom fan curves.** The firmware curves react to real heat, and less wasted power already slows them. (asus-armoury also only accepts PPT changes once a custom curve is active.)
- **No global CPU/GPU power caps.**
