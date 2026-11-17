# 33 - Who wakes the runtime-suspended RTX 4070 Laptop GPU (nvidia-open 620.70.06, kernel 7.3.3)

Scope: read-only source research. No nvidia-smi, lspci, vulkaninfo, glxinfo, no module load/unload, no setting changes.
Sources fetched (raw.githubusercontent.com, tag 620.70.06; local working copy, not in the repo):
nv.c, nv-acpi.c, nv-pci.c, nv-pci-table.c, nv-reg.h, os-interface.c, nv.h, nv-linux.h (common/inc).
Kernel reference: torvalds/linux **master** (pci-driver.c, drivers/base/power/main.c, kernel/power/suspend.c).
Kernel 7.3.3 source was NOT fetched, so every kernel-side line is "master" and needs a 7.3.3 check.
RM core (src/nvidia/) is closed in the open tree, so anything RM does is INFERRED.
Decompiled ACPI: ~/.local/src/acpi-tables/ (dsdt.dsl, ssdt24.dsl).

Labels: PROVEN = read in the cited source. INFERRED = reasoning or an RM-internal behaviour not visible here.

## Live state (read-only)
- /sys/module/nvidia/version = 620.70.06. Kernel 7.3.3-1-cachyos.
- /sys/bus/pci/devices/0000:01:00.0/power/runtime_status = suspended (the only dGPU sysfs file read).
- /proc/driver/nvidia/gpus/0000:01:00.0/power: "Runtime D3 status: Enabled (fine-grained)", "Video Memory: Off",
  "S0ix Power Management: Enabled", "Notebook Dynamic Boost: Supported".
- /proc/driver/nvidia/params: DynamicPowerManagement=2, DynamicPowerManagementVideoMemoryThreshold=200,
  EnableS0ixPowerManagement=1, S0ixPowerManagementVideoMemoryThreshold=256, PreserveVideoMemoryAllocations=0,
  UseKernelSuspendNotifiers=1, EnableGpuFirmware=18, GpuInitOnProbe=2.
- /proc/cmdline sets nvidia.NVreg_PreserveVideoMemoryAllocations=0, NVreg_DynamicPowerManagement=0x02,
  NVreg_EnableS0ixPowerManagement=1. The driver default for PreserveVideoMemoryAllocations is 2 (auto) (nv-reg.h:568-582).
  This box overrides it to 0.
- Running: nvidia-powerd (pid 888), asusd-pr404 (31629), upowerd (926), kthreads "nvidia" (14683) and
  nvidia-modeset/*. Not verified: whether nvidia-powerd holds a /dev/nvidia* fd (the /proc/888/fd listing did not show one).

## Corrections to the earlier assumptions and to research/04-nvidia-power.md
1. PROVEN: nv_indicate_not_idle (nv.c:5795-5812) does NOT resume the device itself. It calls
   pm_runtime_get_noresume (nv.c:5803), sets is_forced_shutdown (nv.c:5805), then calls pci_bus_type.shutdown (nv.c:5806).
   The resume comes from the kernel: pci_device_shutdown calls pm_runtime_resume(dev) first (kernel pci-driver.c:557-562, master).
   The chain "nv_indicate_not_idle -> pm_runtime_resume" is therefore correct only through pci_device_shutdown.
   nv_pci_shutdown returns early for forced shutdown (nv-pci.c:1966-1969), so the device is not torn down.
2. PROVEN: nv_indicate_not_idle has no caller in the open tree. Its callers are in closed RM. INFERRED that RM calls it.
3. PROVEN: the PM_SUSPEND_PREPARE notifier runs BEFORE dpm_suspend_start (kernel suspend.c:385 vs :527, master).
   So the notifier (nv_pm_notifier) runs while the GPU is still runtime-suspended. 04-nvidia-power.md says the GPU is
   "resumed before the notifier chain". That is wrong on ordering.
4. PROVEN: with PreserveVideoMemoryAllocations=0 the dGPU still goes through the notifier path. nv_dev_needs_vidmem_preservation
   is true for any non-Tegra GPU (nv.h:1379-1385), and nv_suspend_devices calls nvidia_suspend(..., NV_TRUE) for it (nv.c:5112).
   The procfs flag makes the preserve-error check skip (nv.c ~4862-4866). So the notifier chain runs in full.
5. PROVEN: the NVIDIA PCI driver does NOT set DPM_FLAG_SMART_SUSPEND (only DPM_FLAG_NO_DIRECT_COMPLETE, nv-pci.c:1502-1503).
   The PCI core therefore calls pm_runtime_resume in pci_pm_suspend (kernel pci-driver.c:915, master) before the driver's
   suspend callback. This is a SECOND forced resume, independent of UseKernelSuspendNotifiers. 04-nvidia-power.md's claim
   that UseKernelSuspendNotifiers=0 "targets the wake" is probably wrong (see row 1 below).
6. PROVEN: the NPCF ACPI handler is installed on the wrong node. nv-acpi.c:361-364 sets nvpcf_device_handle = the device
   that HAS a child named NPCF. In the DSDT, NPCF is \_SB.NPCF (ssdt24.dsl:1547, "Scope (\_SB) Device (NPCF)"), so the
   handler goes on \_SB (nv-acpi.c:330). A Notify(NPCF, 0xC0) is delivered to NPCF's own handlers, not \_SB's.
   INFERRED: nv_acpi_nvpcf_event (nv-acpi.c:147-156) almost never fires. The live 0xC0 path is the PXSX one (path 2).
   Compare _PSR: psr_device_handle = ACAD, the device that owns _PSR (dsdt.dsl:74482-74490), so that handler is correct.
7. The "periodic kworker" (path 3) is NOT NVIDIA's shim. Every deferred job in the open shim uses an nv_kthread_q kthread,
   not a kernel workqueue: nv.c:604/616/1670/5893, os-interface.c:1364-1389 (os_queue_work_item -> nv_kthread_q).
   The only timers are rc_timer (1 s, nv.c:3285-3305, started by RM at nv.c:4470) and the snapshot timer (profiler only,
   nv.c:4527). Neither is a 4-5 min kworker.

## Per-path table

| Path | Cause (chain) | Code (file:line) | Avoidable? | How | Risk |
|---|---|---|---|---|---|
| 1a. s2idle, RM save | PM_SUSPEND_PREPARE -> nv_pm_notifier -> nv_set_system_power_state -> nv_suspend_devices -> nvidia_suspend(procfs) -> nv_power_management -> rm_power_management (closed). RM needs the GPU, so it force-resumes (INFERRED) via nv_indicate_not_idle -> pci_device_shutdown -> pm_runtime_resume. | nv.c:944-951 (register), 4676 (nv_pm_notifier), 4703 (call), 5159 (nv_set_system_power_state), 5040 (nv_suspend_devices), 5112 (nvidia_suspend), 4607 (nv_power_management), 4645/4659 (rm_power_management); nv.c:5795-5806; kernel suspend.c:385 | Partly. The notifier only does work for the save. Skipping it does not skip the resume (see 1b). | UseKernelSuspendNotifiers=0 removes this block only. PreserveVideoMemoryAllocations (0/1/2) and S0ixPowerManagementVideoMemoryThreshold (nv-reg.h:633-651) change the save size, not the resume. | UseKernelSuspendNotifiers=0 is a different resume path with a history of failures on this driver family (see 04 Q4). |
| 1b. s2idle, PCI core | DPM_FLAG_NO_DIRECT_COMPLETE forces full PCI suspend. pci_pm_suspend calls pm_runtime_resume because no DPM_FLAG_SMART_SUSPEND. Then nv_pmops_runtime_resume -> nvidia_transition_dynamic_power(FALSE) -> rm_transition_dynamic_power (closed), the ~2 s GSP boot. | nv-pci.c:1502-1503; nv.c:5382-5395; kernel pci-driver.c:905-916 (pci_pm_suspend), 1434 (pci_pm_runtime_resume); drivers/base/power/main.c:2295-2297 (direct_complete) | NO module option. Needs DPM_FLAG_SMART_SUSPEND plus runtime-suspend-aware callbacks (a driver patch). | No option. Driver patch: PROVEN the flag is absent, INFERRED it would be safe. | High (out-of-tree patch on a suspend path). |
| 2. ACPI notify (charger, profile, asusd) | ASL sends Notify(NPCF,0xC0) and Notify(^^RP12.PXSX,0xC0). The PXSX one is handled by NVIDIA. Sites: WMNB (dsdt.dsl:78720/78786/78842 NPCF; 78857 PXSX), _QA8 EC query 0xA8 (81163), SFMN profile change (81559/81565, plus DGPS -> Notify PXSX 0xC0 at 81775), SPAB (81691). Charger: ACAD _PSR -> nv_acpi_powersource_hotplug_event -> rm_power_source_change_event. | PXSX: nv-acpi.c:251-260 (nv_acpi_notify_event -> rm_acpi_notify) installed at 271 on the dGPU's ACPI handle. NPCF: nv-acpi.c:147-156 (rm_acpi_nvpcf_notify) installed at 330 on \_SB (see Correction 6). _PSR: nv-acpi.c:129-145, rm_power_source_change_event at 143. Notify is run by ACPI on kacpi_notify (ACPI core, INFERRED from the log). | No NVIDIA module option. reg.h has no NVPCF/Dynamic Boost key (grep: none). RegistryDwords could reach RM keys, but names are unknown (do not guess). | Stop the trigger at the source: change profiles/charger handling in asusd/asus-wmi, or an ACPI override (high risk). | Low for config. ACPI override = high. |
| 3. Periodic (4-5 min) "kworker" | Not from the NVIDIA shim (Correction 7). Candidates, all INFERRED: upowerd or other userspace battery poll; ACPI/EC polling (kacpi_notify); asusd or nvidia-powerd (pid 888) doing RM control calls through /dev/nvidiactl, which would need a GPU object to wake; RM-internal timers (not visible). | nv.c:3285-3305 (rc timer, 1 s, timer softirq, not kworker); nv.c:4527 (snapshot); os-interface.c:1364-1389 (kthread) | Unknown until the waker is identified. Only trace or stopping suspects can settle it. | Stop nvidia-powerd and measure (experiment 2). Trace with kprobes/tracepoints (experiment 1). | Low (stopping a daemon is reversible). |

Battery level: the shim has no battery notify handler. Only _PSR (ACAD), NPCF and the dGPU device are registered (nv-acpi.c:271, 330, 203). nv_acpi_is_battery_present (nv-acpi.c:1384-1389) is read-only for RM. INFERRED: a battery-percentage change does not reach NVIDIA through ACPI. The "battery-level" correlation is coincidental, or it goes through an RM poll.

## Why the wake costs ~2 s (INFERRED)
Runtime resume = nv_pmops_runtime_resume -> rm_transition_dynamic_power(FALSE). The GSP boot and the RM state restore happen inside that call (closed). The 500 ms autosuspend delay (nv.c:6287-6288) only applies to the idle-timer path, not to forced resumes.

## Ranked experiments (manual; none run here)
Each experiment: one change, a 20x cycle test with timestamps, and a restore step.

1. Attribute every wake (no config change, needs root). Use bpftrace or ftrace kprobes/tracepoints on:
   nv_pmops_runtime_resume, nv_indicate_not_idle, nv_acpi_notify_event, nv_acpi_nvpcf_event, nv_acpi_powersource_hotplug_event,
   nv_pm_notifier, and the rpm:rpm_resume tracepoint with kernel stacks. Note the comm (kworker, kacpi_notify, nvidia-powerd, upowerd).
   This classifies path 3, and it confirms or kills Correction 6 (whether nv_acpi_nvpcf_event ever fires). Run it first.
2. Stop nvidia-powerd for about 1 h (systemctl stop, then start). If the 4-5 min resumes stop, path 3 is that daemon.
   If not, look at upowerd and the ACPI/EC poll. Measure battery drain with and without it (Dynamic Boost needs it, check).
3. Toggle the AC adapter and a profile change with the trace from (1) running. This attributes path 2 to PXSX (DGPS/WMNB)
   or NPCF (only if nv_acpi_nvpcf_event fires).
4. NVreg_UseKernelSuspendNotifiers=0 (modprobe option, next boot). PREDICTION: the wake moves to pci_pm_suspend (pci-driver.c:915)
   and still happens. Test with the trace from (1). Resume reliability over 20+ cycles is the real risk. Do not run this
   unless (1) shows the notifier path is the one that matters.
5. NVreg_S0ixPowerManagementVideoMemoryThreshold = 0 and 4096, and NVreg_PreserveVideoMemoryAllocations = 0/1/2. These
   tune the save size (nv-reg.h:568-651). Expect them to change suspend time, not the wake count. Measure the time from
   suspend start to resume.
6. NVreg_EnableS0ixPowerManagement=0. Expect a different RM save path. Measure whether the S0ix-specific wake disappears.
7. Path 2 mitigation (no driver change): avoid asusd profile or charger switches during standby. Test: sleep right after a
   profile change versus after a 10 min gap.
8. Driver patch with DPM_FLAG_SMART_SUSPEND (path 1b). Only after (1) and (4) show the PCI-core resume is the main cost. High risk.

Do not change: RegistryDwords with guessed RM keys. Do not set DynamicPowerManagement=0 (keeps the GPU on).

## Open questions
- Does nv_acpi_nvpcf_event ever fire on this box (Correction 6)? Needs experiment 1.
- Kernel 7.3.3 PCI/PM code: fetch the 7.3.3 tag and recheck pci-driver.c:557-565, 905-916 and suspend.c:385-527.
- Who calls nv_indicate_not_idle in RM (closed). Needs an RM trace or a kprobe on it.
- Whether nvidia-powerd holds a /dev/nvidia* fd (the /proc/888/fd check was inconclusive).
- The 4-5 min source (experiment 1 and 2).
- The asusd logic for battery and nvidia-powerd is not in this tree and was not checked.
