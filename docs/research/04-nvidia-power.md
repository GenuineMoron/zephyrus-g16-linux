# 04 - NVIDIA open driver 620.70.06 power management (ROG G16 GU605MI, Hybrid)

Scope: read-only research. No lspci/nvidia-smi/vulkaninfo/glxinfo/eglinfo, no /sys/class/drm status reads.
Sources: NVIDIA open-gpu-kernel-modules tag 620.70.06 (kernel-open/nvidia/nv-reg.h, nv-acpi.c, nv.c, nv-pci.c),
NVIDIA README ch. 22 (RTD3) at download.nvidia.com/XFree86/Linux-x86_64/580.95.05/README/dynamicpowermanagement.html,
local decompiled ACPI at ~/.local/src/acpi-tables/ (ssdt24.dsl, ssdt15.dsl, ssdt14.dsl, dsdt.dsl).
Raw source copies: local working copy, not in the repo.

NOT covered: src/nvidia/ (RM core, where S0ix/GC6/PFM code lives) is not in kernel-open, and was not fetched.
Anything about RM internals below is INFERRED.

## Live state (read-only sysfs and /proc, 2026-11-14)
- /proc/driver/nvidia/version: 620.70.06 (open).
- Params as configured: DynamicPowerManagement=2, DynamicPowerManagementVideoMemoryThreshold=200,
  EnableS0ixPowerManagement=1, S0ixPowerManagementVideoMemoryThreshold=256, PreserveVideoMemoryAllocations=0,
  UseKernelSuspendNotifiers=1, EnableGpuFirmware=18, GpuInitOnProbe=2.
- 0000:01:00.0/power: control=auto, runtime_status=suspended, runtime_suspended_time=4061515 ms,
  runtime_active_time=452167 ms (GPU is in D3 about 90% of cumulative time; RTD3 is working on this kernel).
  wakeup=disabled. Reading power/autosuspend_delay_ms returns EIO, cause unknown.
- Source: nv.c:6287 sets autosuspend delay to 500 ms with use_autosuspend.

## Q1. What happens on s2idle for a runtime-suspended GPU
Proven from source:
- nv_pm_notifier (nv.c:4676) is registered as a PM notifier. PM_SUSPEND_PREPARE sets power_state IN_STANDBY and
  calls into RM. It is only used when UseKernelSuspendNotifiers=1 (nv-reg.h:591-603).
- nv_indicate_not_idle (nv.c:5795) does pm_runtime_get_noresume() then pci_bus_type.shutdown(dev) and sets
  is_forced_shutdown. nv_idle_holdoff does pm_runtime_get_noresume(). These are the calls that take a
  runtime-suspended device back to active. The measured chain (nv_pm_notifier -> nvidia_suspend ->
  rm_power_management -> nv_indicate_not_idle -> pm_runtime_resume) matches this code.
- nv_platform_supports_s0ix (nv.c:6158) only checks FADT ACPI_FADT_LOW_POWER_S0. nv_s2idle_pm_configured
  (nv.c:6175) reads /sys/power/mem_sleep. So S0ix mode is selected only when both are true.
- nv-pci.c:1502 sets DPM_FLAG_NO_DIRECT_COMPLETE. The PM core then does not use direct-complete for this device,
  so the device's system-sleep callbacks run even when it is runtime-suspended. This is why the GPU is resumed
  before the notifier chain.
- Per nv-reg.h:608-651 (EnableS0ixPowerManagement and S0ixPowerManagementVideoMemoryThreshold):
  with S0ix on, if VRAM use is above the threshold (256 MB), VRAM is kept in self-refresh while the GPU core is
  powered down. Otherwise the driver copies VRAM to system memory and powers VRAM off.
  Interpretation: "wake the GPU" is likely the RM state-save step, which needs the GPU powered. This is INFERRED.

Inferred (RM, not verified): the ~1.8 s GPU/GSP init is the cost of re-powering the GPU and the GSP firmware
handshake that the driver runs when it is powered up for the save. The VRAM copy path may add more time when VRAM
use is below 256 MB. That is the likely case here, since the GPU is mostly idle.

Supported options to skip or change the wake:
- UseKernelSuspendNotifiers=0 (nv-reg.h:591-603): the driver uses PCI PM callbacks instead of the notifier. With
  PreserveVideoMemoryAllocations=0, no VRAM save is needed. Whether this avoids the wake depends on the PCI PM
  path. Also with DPM_FLAG_NO_DIRECT_COMPLETE the PM core may still resume the device first. Test it. Risk: a
  different and less-tested resume path on this driver version.
- S0ixPowerManagementVideoMemoryThreshold: raising it (up to usage) keeps VRAM in self-refresh and skips the
  copy. Lowering it to 0 forces the copy path. Only affects the VRAM step, not the wake. Measure, don't assume.
- EnableS0ixPowerManagement=0: falls back to the non-S0ix path. Not supported on this platform as a skip. It
  mostly changes whether the GPU is powered off in S3-like states. Untested here.
- DynamicPowerManagement 0x03 (default): per the README, on Ampere-or-later notebooks 0x03 maps to fine-grained,
  which is the same as 0x02 here. No behavioural change expected. Verified by README text only.
- DynamicPowerManagement 0x00: keeps the GPU powered always. This is a battery loss, not a fix.
- DynamicPowerManagementVideoMemoryThreshold (README): default 200 MB, max 1024 MB, 0 keeps VRAM from being
  turned off. Affects runtime D3 entry, not suspend.
- RegistryDwords / RegistryDwordsPerDevice (nv-reg.h:206-386): no documented key for skipping the suspend wake.
  Do not guess undocumented RM keys.

Tradeoffs: UseKernelSuspendNotifiers=0 is the only candidate that targets the wake itself. It is an untested
driver path with a resume-failure risk. Changing S0ix thresholds only tunes the copy step.

## Q2. ACPI side
Decoded from ~/.local/src/acpi-tables:
- ssdt24.dsl:1188-1340 (Scope \_SB.PC00.RP12.PXSX) defines GC6I (line 1190) and GC6O (line 1199). GC6I is
  DL23 then SGPO(TRSG, TRSP, 1), which powers the GPU off. GC6O is the reverse, then waits for VEID == 0x10DE,
  then restores LREN and CEDR.
- NVJT (line ~1210) is the _DSM handler for GUID cbeca351-067b-4924-9cbd-b46b00b86f34 (the NVIDIA "JT"
  GUID):
  - Function 0 returns support bits 0x1B.
  - Function 1 returns the JT caps buffer. Its fields are JTEN, SREN, PLPR, SRPR, FBPR, GUPR, GC6R, PTRH, MHYB
    (bit 0x0D), RPCL, GC6V, GEIS, GSWS, JTRV=0x0200.
  - Function 3 (POWERCONTROL) drives GPPC 1 to 4 to GC6I or GC6O, and the DFGC/DGCX path.
- ssdt24.dsl:513-600 defines the PXSX _DSM. It also accepts GUID a3132d01-8cda-49ba-a52e-bc9d46df6b81 (routed to
  GPS). GUID a486d8f8 sets OPCI, and d4a50b75 sets NBCI. These are the NVIDIA GPS (dynamic boost) and OPCI/NBCI
  power-control GUIDs. Identification is INFERRED from common knowledge of NVIDIA ACPI, not from a spec fetched here.
- ssdt24.dsl:1375+ and 1520+ define GPS_ and CAFL helpers. The GPS path is probably where dynamic boost power
  requests are answered.

Errors in the log:
- "ACPI BIOS Error ... \_SB.PC00.RP12.PXSX._DSM.MHYB AE_NOT_FOUND": MHYB is a CreateField bit inside NVJT's
  JTCA buffer (ssdt24.dsl:1249). It is not an ACPI object in the namespace. The driver is probably trying to
  evaluate it as a path. AE_NOT_FOUND is consistent with that. INFERRED: harmless. This is also the common
  "Could not resolve symbol ... AE_NOT_FOUND" noise. The search found only similar reports, none tying it to
  failure.
- "osCallACPI_DSM subfunction 0x13/0x2a status 0x59": the subfunctions and the 0x59 status are RM-internal
  (the driver's osCallACPI_DSM). No decoder was available in kernel-open. UNKNOWN. Not confirmed harmless.
- "pfmreqhndlrCallACPI PFM_REQ_HNDLR_PSHAREPARAMS": PFM = platform power-management request handler, PSHAREPARAMS
  = platform shared (power budget) parameters. This is the Dynamic Boost style request path. If the request
  fails, Dynamic Boost budget may not be applied. INFERRED. Check whether asusctl or nvidia-powerd see
  power-budget changes. The forum reports below show this family of errors is common and not always fatal.

Verdict: the MHYB error is most likely harmless. The osCallACPI_DSM 0x59 and PSHAREPARAMS errors are UNKNOWN and
are the ones to chase if Dynamic Boost looks inactive.

## Q3. nvidia-powerd
Not verified in this pass. The dynamicboost README (chapter 23) was not fetched. Working model, INFERRED:
nvidia-powerd is a userspace daemon that calls the PXSX GPS _DSM (a3132d01) to share power budget between CPU and
GPU (Dynamic Boost). It polls on a timer, which keeps a small amount of CPU wakeup activity. It does not hold the
GPU awake by itself. Whether it should run here: on a 2024 ASUS ROG with Dynamic Boost, yes, if Dynamic Boost is
wanted. Battery cost is small, but measure it (powertop, or the RAPL/battery rate with the daemon stopped and
started).
Open: fetch dynamicboost.html from the same NVIDIA release for the exact daemon behaviour.

## Q4. Known issues (links)
- CachyOS thread: dGPU runtime D3 "Not supported" on linux-cachyos 7.3.0-4 with nvidia-open 615.78.08, works on LTS.
  https://discuss.cachyos.org/t/nvidia-open-615-78-08-dgpu-runtime-d3-not-supported-on-linux-cachyos-7-3-0-4-works-on-lts-6-18-55-2/38181
  Relevant: same kernel family. Our box is RTD3-working on 620.70.06 / kernel 7.3.3 (sysfs above), consistent with
  the RTD3 fix in the 7.3.0-5+ builds.
- open-gpu-kernel-modules PR #1074: nv_indicate_idle never called, so runtime suspend is not reached.
  https://github.com/NVIDIA/open-gpu-kernel-modules/pull/1074
- GSP Xid 120 panic during s2idle with NVreg_DynamicPowerManagement=0x02:
  https://forums.developer.nvidia.com/t/gsp-xid-120-panic-during-s2idle-suspend-with-nvreg-dynamicpowermanagement-0x02/369568
- Resume failure after long s2idle, Dell Precision 7780, 610.43.03, nv_pm_notifier in trace:
  https://forums.developer.nvidia.com/t/regression-resume-failure-after-long-s2idle-on-dell-precision-7780-rtx-3500-ada-610-43-03-nvevbdisablevblanksemcontrol-nv-pm-notifier/377732
- Suspend black screen, Lenovo LOQ RTX 4060, open 610.43.03, ACPI symbol errors on _DSM:
  https://forums.developer.nvidia.com/t/suspend-failure-black-screen-on-lenovo-loq-ryzen-7435hs-rtx-4060-with-open-kernel-module-610-43-03/377642
- Platform power mode from SBIOS failure (PFM-style error), RTX 4050 Laptop:
  https://forums.developer.nvidia.com/t/nvrm-failed-to-get-target-temp-from-sbios-failed-to-get-platform-power-mode-from-sbios-on-rtx-4050-laptop-gpu/375988
- XID 79 / GSP heartbeat timeout in nvidia-powerd (RTX 5060 laptop, 610.43.02):
  https://forums.developer.nvidia.com/t/610-43-02-rtx-5060-laptop-lenovo-83ly-reproducible-xid-79-and-gsp-heartbeat-timeout-in-nvidia-powerd-gsp-rm-control-0x2080a613/378142
- Suspend never completes after BAR1 exhaustion, 615.71.09: https://forums.developer.nvidia.com/t/nvidia-open-615-71-09-xid-79-gpu-fell-off-the-bus-after-bar1-va-space-exhaustion-subsequent-s2idle-suspend-never-completes/384448
Not found: an issue explicitly about "slow suspend from waking RTD3" or "GSP boot time on resume" or
"PSHAREPARAMS". Those are open gaps. Searches for them returned nothing direct.

## Q5. Recommended settings (Hybrid, battery + fast sleep + GPU available)
Keep as is (proven good or safe):
- DynamicPowerManagement=2 (0x03 is identical here per README). Do not use 0x00.
- Keep nvidia-drm.modeset=1, fbdev=1.
- Keep EnableS0ixPowerManagement=1 unless a test shows the S3-like path is better on this firmware.

Experiments, in order, one change at a time, each with a 20 times repeat of suspend/resume and timestamps:
1. Check that the overnight drain is not the GPU. Compare runtime_status and runtime_suspended_time before and
   after an overnight s2idle (read-only sysfs). If the GPU stays suspended, the 5 W drain is elsewhere.
2. S0ix VRAM threshold: try 0 and 4096 MB, measure suspend time and resume time. The copy path vs self-refresh
   path tradeoff is INFERRED to matter; measure.
3. UseKernelSuspendNotifiers=0 (modprobe option, not runtime-changeable): measure wake, check resume reliability
   with many cycles. This is the only candidate that targets the wake. Expect a different risk profile.
4. nvidia-powerd: measure battery with and without. Keep only if Dynamic Boost is used.

Do not change: RegistryDwords for undocumented RM keys.

## Open questions
- RM source for S0ix save, GC6 and PFM handling is not checked. Fetch src/nvidia/ for the exact function that
  calls rm_power_management and whether the wake is required.
- Meaning of osCallACPI_DSM subfunction 0x13/0x2a and status 0x59.
- Whether PSHAREPARAMS failures stop Dynamic Boost budget changes on this unit.
- Why power/autosuspend_delay_ms returns EIO.
- nvidia-powerd and dynamicboost.html not yet read.
