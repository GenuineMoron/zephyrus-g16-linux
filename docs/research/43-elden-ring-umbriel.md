# 43. Elden Ring on Umbriel: white screen, then a swapchain crash (2026-11-17)

Hybrid mode (Intel drives the panel, the RTX 4070 renders via PRIME offload), NVIDIA open modules 620.70.06, Proton-CachyOS 11.0-20261015, Umbriel test build. First launch of the game under Umbriel (it had run under niri).

## Symptoms

1. **Xwayland (default):** a white window. `nvidia-smi` showed `eldenring.exe` holding 1.4 GB of VRAM but the GPU idling in P8 at 210 MHz and ~6 W, so the game ran but no frames reached the compositor.
2. **Native Wayland (`PROTON_ENABLE_WAYLAND=1`):** the game went fullscreen and closed within ~7 s. The Proton log:

```
err:vkd3d-proton:dxgi_vk_swap_chain_recreate_swapchain_in_present_task: Failed to create swapchain, vr -13
err:vulkan:vkGetPastPresentationTimingEXT Exception 0xc0000005 in Unix call.
```

`vr -13` is `VK_ERROR_UNKNOWN`. `vkcube` on the NVIDIA GPU (PRIME offload) presented normally in both Wayland and XCB mode, so cross-GPU presentation itself works; the failure is specific to the game's swapchain path.

## Cause and fix

VKD3D-Proton in this Proton build uses `VK_EXT_present_timing`, which NVIDIA 620 exposes. With PRIME offload that path fails (Wayland: swapchain creation, then a crash; Xwayland: presentation stalls). Disabling the extension for VKD3D fixes it:

```
PROTON_ENABLE_WAYLAND=1
VKD3D_DISABLE_EXTENSIONS=VK_EXT_present_timing
```

Result: the swapchain was created (2560x1600, 3 images), and the GPU ran at P0, 2535 MHz, ~57 W under load. Whether Xwayland also works with only the extension disabled was not tested; native Wayland is kept because it is also the route to HDR.

The settings live in [configs/home/.config/game-env/1245620.env](../../configs/home/.config/game-env/1245620.env). [gamemode-external](../../configs/home/.local/bin/gamemode-external), already in the game's launch options, now loads `~/.config/game-env/<SteamAppId>.env`, so per-game tweaks need no Steam edits.

## Profile, measured (2026-11-17, same busy area, 2 min each)

Frames counted with a bpftrace uprobe on winevulkan's `thunk64_vkQueuePresentKHR` (every present the game makes), alongside `nvidia-smi`, RAPL package energy, coretemp and the ASUS fan RPMs. The game caps at 60 fps; native resolution 2560x1600, High preset.

| | Performance | Balanced + `balance_performance` | Balanced (`balance_power`) |
| --- | --- | --- | --- |
| Average | 59.9 fps | 59.2 fps | 48.5 fps |
| Frames > 20 ms | 0.4% | 3.8% | 57% |
| p99 frame time | 18.9 ms | 21.9 ms | 27.9 ms |
| CPU package | 38.7 W, 95 °C | 39.3 W, 94 °C (max 99) | 19.9 W, 83 °C |
| GPU | 69 W (limit 81), 59% busy, 2519 MHz | 56 W (limit 56), 86% busy, 1879 MHz | 64 W (limit 75), 59% busy |
| Fans cpu / gpu / mid | 5267 / 4875 / 9033 rpm | 3958 / 3542 / 7958 rpm | 3667 / 3633 / 7217 rpm |

- **Balanced's default EPP is the bottleneck:** with `balance_power` the CPU (20 W) can't feed 60 fps while the GPU idles at 59%.
- **Balanced with `balance_performance` holds 60 fps and is about 1,000–1,300 rpm quieter on every fan,** with slightly more uneven frame times. This is the chosen default for this game.
- **The CPU needs about 39 W for 60 fps here in either mode**, so the fan curve mostly decides how loudly that heat is removed.
- **A 40 W RAPL cap alone changed nothing**, since the CPU wasn't above it. ASUS PPT writes return `EBUSY` unless a custom fan curve is active (asus-armoury).
- **One 113 ms hitch in the Performance run:** NVIDIA's shader cache for the game was empty. A 10 GiB, never-pruned cache is now set: `__GL_SHADER_DISK_CACHE_SIZE` and `__GL_SHADER_DISK_CACHE_SKIP_CLEANUP`, per game and in environment.d.

How it's applied:
- **Per-game profile:** `GAME_PROFILE=Balanced` and `GAME_BALANCED_EPP=2` in the game's env file.
- **Hand-off:** [gamemode-external](../../configs/home/.local/bin/gamemode-external) leaves a hint, and [gamemode-profile](../../configs/home/.local/bin/gamemode-profile) applies it at game start through asusd's `ProfileBalancedEpp`. It restores the original value and the AC/battery profile at the end.
- **Other games** still get Performance.

## Xid 31 at game exit (2026-11-18)

When Elden Ring exited on 18 Nov at 13:03:05, the driver logged `Xid 31` (MMU fault, engine CE2_PBDMA0, FAULT_PDE ACCESS) and then `Xid 154: GPU recovery action changed from None to OS Reboot`. `nvidia-smi -q` still reported `GPU Recovery Action: Reboot` three days later. The GPU kept working, but NVIDIA's guidance is to reboot. g16-doctor flags any Xid in the boot's log. If it happens again at exit, report it with an nvidia-bug-report.

## Open

- Report upstream (VKD3D-Proton and/or NVIDIA) with the log once the gameplay test confirms stability.
- Still to test: capping the CPU's top boost (cooler at the same smoothness?), limiter choice, P-cores only.
