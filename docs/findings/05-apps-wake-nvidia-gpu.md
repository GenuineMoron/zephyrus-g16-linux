# 05: Ordinary app launches wake the NVIDIA GPU (+2.6 s per launch)

**Status:** fixed, and the fix needs no per-game setup (2026-11-14).

## Symptom

- **Nautilus held the GPU open.** It had `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-modeset` and NVIDIA's render node open, although it has no reason to use the RTX 4070.
- **Every GTK4 app launch woke the GPU from D3cold.**

## Measurements

The test app is `zenity --info --timeout=2` (GTK 4.24). Each run starts with the GPU runtime-suspended (D3cold).

| Environment | GPU awake during run | Wall time |
|---|---|---|
| Default | 4.4 s | 5.0 s |
| NVIDIA EGL vendor hidden, Vulkan visible | 3.9 s | 4.5 s |
| NVIDIA Vulkan ICD hidden, EGL visible | **0 s** | 2.9 s |
| Nothing hidden, `GSK_RENDERER=gl` | **0 s** | 3.0 s |
| `GSK_RENDERER=vulkan`, NVIDIA EGL hidden | 3.9–4.4 s | 5.0 s |

## Cause

GTK 4.16+ renders with **Vulkan** by default. Creating a Vulkan instance loads every ICD, and NVIDIA's ICD powers the GPU up (the ~2 s GSP boot from [02](02-standby-nvidia-wakes-idle-gpu.md)) just to enumerate it. Probing NVIDIA's EGL vendor does **not** wake the GPU.

## Fix: like Windows, with no per-game configuration

On Windows:
- the iGPU drives the screen;
- apps can enumerate GPUs without waking the dGPU;
- games get the dGPU because they ask DirectX for the "high performance" adapter.

On Linux, almost every game (Proton's DXVK and VKD3D, and native Vulkan ports) picks the discrete GPU through Vulkan by itself. So:

- **NVIDIA stays fully visible to Vulkan and EGL.** New games need no setup: they find the RTX 4070 themselves.
- **GTK draws with OpenGL instead of Vulkan.** [configs/home/.config/environment.d/50-gtk-gl-renderer.conf](../../configs/home/.config/environment.d/50-gtk-gl-renderer.conf) sets `GSK_RENDERER=gl`, GTK's GL renderer and its default until 4.16. GTK apps then draw through EGL on the Intel GPU and never touch NVIDIA.
- **Any app that wakes the GPU gets named.** [configs/usr/local/sbin/gpu-wake-log](../../configs/usr/local/sbin/gpu-wake-log), run by [gpu-wake-log.service](../../configs/etc/systemd/system/gpu-wake-log.service), puts a kprobe on `nv_pmops_runtime_resume` in a private ftrace instance. It logs to `journalctl -t gpu-wake` which processes held the GPU open when it woke. Nobody has to hunt for the next app that misbehaves like GTK did.

An earlier version of this fix hid NVIDIA's Vulkan ICD from the whole session. That worked, but it made games need wrappers (`with-nvidia`, `prime-run`, Lutris env), so it was replaced the same day.

## Verified

| Check | Result |
|---|---|
| GTK app launched as a systemd unit (how the shell launches apps) | GPU stayed asleep (0 ms awake); ~0.15 s start-up |
| `vulkaninfo` with no wrapper | sees the Intel GPU (integrated) and the RTX 4070 (discrete), so games pick the RTX 4070 |
| Waking the GPU with `vulkaninfo` | logged: `apps holding it open: vulkaninfo(…)` |

## WebKitGTK apps (2026-11-17)

Apostrophe woke the GPU (~20 s awake) each time its preview opened; it stayed asleep with the preview off. A uprobe on libdrm's mode-setting calls, reading the return address from the stack, showed the caller: `libwebkitgtk-6.0` itself, in the app's own process, calling `drmModeGetResources`, `drmModeGetConnector` (8 times) and `drmModeGetEncoder`. This is WebKit's DRM vblank monitor: it opens each DRM card and reads its connectors to find the screen's refresh timing. On the NVIDIA card that query goes `nvidia-drm` → `nvRmGetConnectedDpys` → `nvDpyGetDynamicData` → runtime resume.

`WEBKIT_WEB_RENDER_DEVICE_FILE`, `WEBKIT_DISABLE_DMABUF_RENDERER` and `WEBKIT_DMABUF_RENDERER_DISABLE_GBM` did not help. `WEBKIT_FORCE_VBLANK_TIMER=1` did: 0 wakes with the preview open. It is set for the session in [52-webkit-vblank-timer.conf](../../configs/home/.config/environment.d/52-webkit-vblank-timer.conf), so it covers every WebKitGTK view.

## Notes

- **The GPU is available on battery too.** The laptop stays in Hybrid mode (asusd; supergfxctl is retired); Integrated was rejected so heavy apps keep the GPU everywhere.
- **Native OpenGL games are the exception.** They render on the GPU driving the display unless started with `prime-run %command%`, the same as before this change. Most Linux games use Vulkan or Proton.
- **Apps started by the compositor itself** (keybinds) pick up `GSK_RENDERER` after the next login.
