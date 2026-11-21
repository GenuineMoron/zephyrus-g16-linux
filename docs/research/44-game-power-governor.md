# 44. Game power: a frame target, an efficient default, and a governor (2026-11-21)

Goal: every game runs as quietly as it can while still hitting its frame target, gets full power automatically when it needs it, and nothing is throttled blindly.

## What the measurements said ([43](43-elden-ring-umbriel.md))

- **Fixed power caps don't help.** A 40 W CPU cap changed nothing, because the CPU wasn't above it. A cap low enough to matter would cost performance exactly when a game needs it.
- **Noise follows wasted work.** Frames beyond what's shown, and CPU boost steps that buy little, both become heat.
- **Profile mostly sets the fan curve and the shared CPU/GPU budget.** With the CPU allowed to run efficiently fast (`balance_performance`), Balanced held 60 fps in a busy Elden Ring area, roughly 1,000–1,300 rpm quieter than Performance. With Balanced's default `balance_power` the CPU starved the game (48 fps).

## Design

1. **A frame target per game.** The default is 120 fps on the charger and 60 on battery. Without VRR, the 240 Hz panel paces evenly only at divisors of 240 (60, 80, 120). Proton games are capped there by DXVK/VKD3D's own limiters (`DXVK_FRAME_RATE`, `VKD3D_FRAME_RATE`); games that cap themselves (Elden Ring at 60) keep their own limiter and tell the governor their target.
2. **An efficient start.** Every game starts in Balanced with the CPU at `balance_performance` (asusd's `ProfileBalancedEpp` set to 2 for the session, then restored).
3. **[game-governor](../../configs/usr/local/sbin/game-governor)** (root; started by [game-governor@.path](../../configs/etc/systemd/system/game-governor@.path) when the wrapper hands it the targets):
   - **Frame counting:** counts the game's presents with a bpftrace uprobe on Proton's winevulkan `vkQueuePresentKHR` thunk, covering all installed Protons.
   - **Escalate:** switches to Performance after the target is missed for 10 s. If Performance doesn't raise fps by 5 % (or reach the target) within 30 s, it goes back and treats that frame rate as the game's own cap for 5, then 10, then 20 minutes.
   - **Drop back:** returns to Balanced after 3 minutes at the target with the GPU at most 75 % busy. If the target is then missed, it goes back to Performance and waits twice as long before trying again.
   - **On battery:** never escalates.
   - **No frame signal** (native games, a failed probe): Performance for the session. Never throttle without measuring.
   - **GPU safety:** it never queries the NVIDIA GPU unless it is already awake.
   - **Logging:** every decision, plus a per-session summary, in `journalctl -u 'game-governor@*'`. Live state is in `$XDG_RUNTIME_DIR/game-governor.status`.
   - **Optional `GAME_CPU_MAX_MHZ`:** caps the CPU's top boost while efficient, lifts it in Performance, and always restores it at exit. Off until measured per game.
4. **[gamemode-external](../../configs/home/.local/bin/gamemode-external)** is the single entry point (Steam launch options: `gamemode-external %command%`).
   - **Settings:** it reads [default.env](../../configs/home/.config/game-env/default.env), then the game's `<SteamAppId>.env`.
   - **Hand-off:** it sets the limiter, starts the governor, and registers with GameMode without `LD_PRELOAD`.
   - **Ordering:** it stops the governor before GameMode's end hook restores the normal profile.
   - **Fixed mode:** `GAME_GOVERNOR=fixed` with `GAME_PROFILE` pins one profile for the whole session.
5. **Measuring a game:** `sudo game-capture [seconds]` ([tools/game-capture](../../tools/game-capture)). It reports average fps, 1 % / 0.1 % lows, frame-time percentiles, slow frames, fps per 10 s, GPU busy/power/limit/clock/temperature, CPU package power and temperature, and fans.

## Tested

- **Decision logic,** in simulation with a fake clock and no hardware changes:
  - a game holding its target stays efficient;
  - a game that needs Performance gets it, then drops back when the scene lightens;
  - a self-capped game below the target is detected, and retries back off;
  - a CPU-bound game where Performance helps 8 % keeps it.
- **Service lifecycle:** it starts on the hand-off file, writes its status, exits when the file goes, and leaves the profile untouched with the GPU asleep.
- **Frame probe:** it attaches to all three installed Protons, including paths with spaces.
- **CPU cap:** the P-cores went from 4.8/5.1 GHz to 4.2 and were restored exactly.
- **Not yet:** a real session with the governor running.

## Not done, on purpose

- **No custom fan curves.** The firmware curves react to real heat, and less wasted power already slows them. Revisit only if a measurement shows a mode too loud at a given load. (A custom curve is also what asus-armoury requires before PPT power limits can be changed.)
- **No global CPU or GPU power caps.**
