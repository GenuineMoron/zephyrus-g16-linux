# 02: Every standby wakes the idle NVIDIA GPU (and why waking takes 0.55 s longer)

**Status:** measured and traced to source code and firmware (2026-11-14). Integrated
mode on battery was evaluated and rejected: the GPU has to stay available on battery.

## Measurements

Each measurement below is one standby on AC, recorded with [tools/trace-standby.sh](../../tools/trace-standby.sh) and summarised with [tools/analyze-standby-trace.py](../../tools/analyze-standby-trace.py).

| Step | Time |
|---|---|
| `suspend_enter` (sync → freeze processes) | 2.92 s |
| └ NVIDIA PM notifier (`nv_pm_notifier`) | 2.67 s |
|   └ `rpm_resume` of the GPU: it was asleep in D3cold | 2.04 s |
|     └ BIOS `Sleep()`s while powering the slot on | 0.22 s (35 + 100 + 5×16 ms) |
|     └ GPU init after power-on (GSP firmware boot) | ~1.8 s |
| `dpm_resume_noirq` on wake | 0.548 s |
| └ `pcieport 0000:00:01.0` (the GPU's root port) | 0.542 s |
|   └ BIOS `Sleep()`s while powering the slot on | 0.386 s (171 + 35 + 100 + 5×16 ms) |

The GPU was runtime-suspended (D3cold) before standby and has nothing to do. Even so, it is fully powered up and booted on the way into standby, then powered up again on the way out.

## Why: NVIDIA driver source (open-gpu-kernel-modules 620.70.06)

- **`kernel-open/nvidia/nv-pci.c`, at probe:**
  ```c
  dev_pm_set_driver_flags(nvl->dev, DPM_FLAG_NO_DIRECT_COMPLETE);
  ```
  This stops the PM core from leaving a runtime-suspended GPU alone during system sleep.
- **`kernel-open/nvidia/nv.c`, `nvidia_suspend()`:** this calls `nvidia_modeset_suspend()` and then `nv_power_management()` → `rm_power_management()`.
- **Inside RM:** RM calls `nv_indicate_not_idle()` → `pm_runtime_resume()`. That is the 2.04 s in the trace.
- **Both entry points do this.** Kernel PM notifiers (`NVreg_UseKernelSuspendNotifiers=1`) and the legacy `.suspend` callback both reach `nvidia_suspend()`, so no module option avoids it.

## Why the slot takes 0.39 s of BIOS waits: ACPI (SSDT "MtlP_Rvp")

The GPU's root port is `\_SB.PC00.RP12`, powered by `PowerResource (PXP)`.

**`_ON`, for an NVIDIA card in hybrid mode:**
- `PON()`, then `L23D()`;
- then it polls the vendor ID (`Sleep(1)` loop);
- then it sets `VGAT` in the EC.

**`PON()`:**
```
if WOFF != 0: Sleep(PDOD - elapsed_since_power_off)     <- 171 ms on wake
\PIN.ON(PWRG); Sleep(P0DL)                              <- 35 ms
SPCO(SCLK, 1)                                           ;  clock on
\PIN.OFF(RSTG); Sleep(0x64)                             <- 100 ms (PERST# release)
```
`L23D()` then polls the link out of L2/L3 (`Sleep(16)` × 5 observed).

The 171 ms wait exists only on resume. It is the "minimum power-off time" guard (`PDOD`), measured with the ACPI `Timer`. The GPU had been off for 16 s, so the guard should not have fired.

**Hypothesis (unproven):** the ACPI timer does not advance during S0ix, so the BIOS believes the GPU was switched off only moments earlier.

## Also changed: NVIDIA's suspend/resume systemd services masked

`nvidia-suspend.service`, `nvidia-resume.service`, `nvidia-hibernate.service` and `nvidia-suspend-then-hibernate.service` run `nvidia-sleep.sh`, which does `chvt 63`. Every standby therefore switches the console to an empty VT and back. The compositor loses the display, and a text console flashes on screen.

With the open kernel modules and `NVreg_UseKernelSuspendNotifiers=1`, the driver handles suspend itself (NVIDIA README, "Power Management" chapter). The services are redundant, so they are masked. Standby is verified afterwards.

## What Windows does

Windows does not power up an idle dGPU for Modern Standby.

On Linux, the only way to keep NVIDIA out of the sleep path is to remove the GPU: supergfxctl **Integrated** mode. That trades away the outputs wired to the NVIDIA GPU, which are **HDMI** and one USB-C port (`card0-DP-5`), and any CUDA or NVENC use.

**Decision (2026-11-14):** stay in Hybrid mode everywhere, so games and heavy apps keep the GPU on battery; accept the extra ~2.7 s standby entry. (supergfxctl has since been retired; asusd switches modes now.)

## Upstream

NVIDIA could skip the system-suspend work for a GPU that is already runtime-suspended. That would mean allowing direct-complete, or not calling `nv_indicate_not_idle()` from `rm_power_management()`. This is worth an issue at NVIDIA/open-gpu-kernel-modules with these traces.
