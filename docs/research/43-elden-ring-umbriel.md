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

## Open

- Report upstream (VKD3D-Proton and/or NVIDIA) with the log once the gameplay test confirms stability.
- The planned measured test session (frame times, GPU power, powerd cap, limiter) still to run.
