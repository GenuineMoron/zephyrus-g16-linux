# 32. G-Helper ASUS WMI map for ROG Zephyrus G16 GU605MI (2024)

Date: 2026-11-15. Read-only research. Nothing was written to sysfs, no asusctl set commands, no lspci/nvidia-smi/vulkaninfo.

Sources
- G-Helper (seerge/g-helper, main): app/AsusACPI.cs, app/AppConfig.cs, app/Mode/ModeControl.cs, app/Mode/Modes.cs, app/Mode/PowerNative.cs, app/Gpu/GPUModeControl.cs, app/Display/ScreenControl.cs, app/Battery/BatteryControl.cs, app/Program.cs, app/Slash.cs, app/USB/AsusHid.cs, app/USB/Aura.cs (partial). Local copies, not in the repo.
- Kernel v7.3: include/linux/platform_data/x86/asus-wmi.h, drivers/platform/x86/asus-armoury.h, asus-wmi.c, asus-nb-wmi.c. Local copies, not in the repo.
- DSDT: ~/.local/src/acpi-tables/dsdt.dsl (msdm.dsl not opened). Branch boundaries: DSTS (Local0==0x53545344) lines 77406-78385, DEVS (0x53564544) lines 78386-~78957.
- Live sysfs: firmware-attributes/asus-armoury, asus-nb-wmi, /etc/asusd/asusd.ron, intel-rapl, power_supply, PCI runtime_status (sysfs only).

## Findings

1. PROVEN: the "90 W / 135 W" figures are not the live battery limits. The kernel table for GU605M (asus-armoury.h ~1636) gives AC PL1 max 90, PL2 max 135, and DC (battery) PL1 25-35, PL2 38-53. The machine is on battery now (ACAD online=0, BAT1 Discharging). Firmware attributes read ppt_pl1_spl cur=35 (min 25, max 35) and ppt_pl2_sppt cur=53 (min 38, max 53).
2. PROVEN: RAPL package-0 constraint_0 (long_term) = 90 W and constraint_1 (short_term) = 104 W. The "90 W" figure shown by the tools is probably this MSR limit, not the ASUS EC limit.
3. PROVEN: the kernel's sysfs store rejects values outside [min,max] (asus-armoury.h:35-36). So Linux cannot request PL1 below 25 W or PL2 below 38 W on battery. G-Helper's 9 W / 10 W would be below both floors.
4. PROVEN (DSDT): PL1 (0x1200A3) and PL2 (0x1200A0) writes land in EC RAM fields PL01 (offset 0x9B) and PL02 (offset 0x9D) (DEVS 78806-78808 and 78790-78792; EC fields 75806-75808). The EC is what enforces them. DSTS for these IDs returns only a presence bit (0x00010000, DSDT 78243, 78258), so the sysfs "current_value" is not a live firmware readback. The live EC value can only be checked from EC RAM (see top-5 item 3). The kernel reports the DC default in sysfs, which is INFERRED from that DSTS shape.
5. PROVEN: asusd.ron has armoury_settings: {} and no PPT per profile. Quiet on battery changes only the platform profile and EPP (power). Nothing lowers PL1/PL2 on battery.
6. PROVEN: dGPU 0000:01:00.0 power/runtime_status = suspended, control = auto. The dGPU is not stuck in D0 right now.
7. PROVEN (single sample): BAT1 voltage_now 14.947 V x current_now 1.072 A = about 16.0 W at this moment. Load is unknown, so this is not an idle figure.
8. PROVEN: DSDT has no explicit branch for several IDs the kernel and G-Helper use (0x120075, 0x120057, 0x50019, 0x50021, 0x120031, 0x120012). They fall through to WCHK/W15H (SMI) at DSDT 78370 (DSTS) and 78935 (DEVS). So a DSDT grep does not prove absence. Runtime reads are the authority.
9. PROVEN: G-Helper GU605-specific quirks: IsSlash, IsFanRequired, IsChargeLimit6080 (charge limit only 60/80/100), DynamicBoost20 (GPU boost cap 20), IsStandardForceFix, IsSleepReset (GU605MI/MV/CR). The SleepReset() caller was not found in the fetched files.
10. PROVEN: G-Helper's per-source profile key is PowerLineStatus (Offline 0 = battery, Online 1 = AC): performance_0 vs performance_1 (ModeControl.cs:94; Program.cs PerformanceKey). ScreenControl.AutoScreen on battery sets refresh MIN_RATE (60 default) and panel overdrive 0 when screen_auto is set; on AC sets max refresh and overdrive 1. CPU boost (auto_boost) goes through the Windows power scheme, not ACPI (PowerNative.cs:124-155). GPU Eco (0x90020) is set on battery when GpuAuto is on and no dGPU use (GPUModeControl.cs ~250-300).

## Table: ID / setting -> G-Helper on GU605MI -> Linux -> DSDT -> value

| ID / setting | G-Helper behaviour (GU605MI) | Linux equivalent | DSDT | Potential value |
|---|---|---|---|---|
| 0x120075 PerformanceMode | Balanced/Turbo/Silent per source (performance_0/1); SleepReset for GU605MI | throttle_thermal_policy, platform_profile (now quiet = 2) PROVEN | no branch; WCHK fallthrough 78370/78935 | UX / battery |
| 0x90020 GPUEco (dGPU off) | Eco on battery when GpuAuto; Standard when plugged; Optimized | dgpu_disable (same ID; refuses if gpu_mux_mode=0). Now 0, not auto-driven | DSTS 78342; DEVS 78896 (CUMA, WOSR, GPCE, UMAF, PXSX Notify 0x81/0x03) | battery (large if dGPU wakes) |
| 0x90016 GPUMux | Ultimate / Hybrid | gpu_mux_mode (now 1 hybrid) PROVEN | DSTS 78358 (DGPM) | perf (Ultimate) |
| 0x1200A3 PL1 SPL (limit_total) | SetPower writes EC PL01; 5-150 W range | ppt_pl1_spl (DC 25-35; cur 35) | DSTS 78258; DEVS 78806 -> EC PL01 (75806) | battery under load |
| 0x1200A0 PL2 SPPT (limit_slow) | EC PL02 | ppt_pl2_sppt (DC 38-53; cur 53) | DSTS 78243; DEVS 78790 -> EC PL02 (75808) | battery under load |
| 0x1200C1 fPPT | AMD-only path in G-Helper | ppt_fppt legacy node only, not in fw-attributes; write likely fails (INFERRED) | DSTS 78278 present; DEVS 78846 unsupported | none on Intel |
| 0x1200A1 EDC / 0x1200A2 TDC | defined, not in SetPower | missing | DSTS 78248/78253 unsupported | none known |
| 0x1200B0 APU sPPT / 0x1200B1 Platform sPPT | AMD-only path | not created | DSTS 78263/78268 unsupported | none |
| 0x1200C0 GPU Boost (NV dyn boost, 5-20 for GU605) | G-Helper MaxGPUBoost 20 | nv_dynamic_boost (AC 5-20; DC range 0/0 PROVEN, now 0) | DSTS 78273; DEVS 78822 (NBFM/DBAC) | perf on AC |
| 0x1200C2 NV temp target (75-87) | GPU temp target | nv_temp_target (fw 87; legacy node reads 75, unexplained) | DSTS 78283; DEVS 78851 (PXSX.TGPU) | perf / thermal |
| 0x120098 GPU TGP (GPU_POWER, 0-75) | sets NPCF.ACBT = value*8 | MISSING: no attribute, GU605M kernel entry has no nv_tgp (GU605MU entry 55-85) | DSTS 78228; DEVS 78785 | perf on AC (dGPU) |
| 0x120099 GPU base TGP (read only) | read | missing | DSTS 78236 | none |
| 0x1200D2/D3/D4 E/P core counts | defined (Cores); PCoreMin 4, PCoreMax 16 | missing as ASUS attr; runtime equivalent via cpu online (INFERRED) | DSTS 78298/78306/78314 present | battery (light load) |
| 0x1200E2 MCU powersave | not used on GU605 | mcu_powersave not created | DSTS 78327 returns 0 (absent) | none |
| 0x120057 battery limit (RSOC) | 60/80/100 only on GU605 | charge_control_end_threshold (asusd = 80) PROVEN | SMI fallthrough | battery life |
| 0x12006C charger mode | defined; no use in fetched files | charge_mode RO (cur 0; 0;1;2) PROVEN | DSTS 78145 | none |
| 0x110013/14/31 fan RPM; 0x110024/25/32 curves; 0x110026/27/33 floors | custom curves forced on power change for GU605 | hwmon5 fan1-3, hwmon6 asus_custom_fan_curve PROVEN; asusd fan_curves.ron | DSTS 77808/78017/78032; DEVS 78713 (EC) | UX / acoustics |
| 0x110034 fan hysteresis | set on apply | missing | SMI fallthrough | small |
| 0x110018 fan boost mode | defined | fan_boost_mode not created (PROVEN absent) | DSTS 77854, DEVS 78608 -> unsupported | none |
| 0x50019 panel overdrive | screen_auto: on AC 1, on battery 0 | panel_overdrive RW (cur 1) PROVEN | SMI fallthrough | battery (small) / UX |
| 0x50020 overdrive support | gate check | missing (not needed) | SMI | none |
| 0x5001E / 0x5002E mini-LED | only G834/G835 force | none (correct: DSTS returns 0 = absent) | DSTS 77917/77922 | none |
| 0x5001C FHD toggle | ScreenFHD | none | DSTS 77907 unsupported | none |
| 0x50071 HDR; 0x5002A auto brightness | HDR/ambient | none | SMI | UX (INFERRED unavailable) |
| 0x50001 ALS enable | AmbientLight | als_enable not created (PROVEN absent) | DSTS 77519 unsupported | none |
| 0x120031 lid resume | not used | lid_resume not created | SMI | none |
| 0x130022 boot sound | not used | boot_sound RW (cur 0) PROVEN | DSTS 77490 present | none |
| 0x50021 kbd brightness; 0x100057 kbd power state | sleep forces brightness 0 on GU605 (SleepBrightness) | asus::kbd_backlight LED present | SMI | battery (tiny) / UX |
| Aura / Slash (USB HID, VID 0x0B05) | Slash on/off, dim on low battery; Aura | asusd slash.ron, aura_19b6.ron present (INFERRED mapping) | not ACPI | UX |
| CPU boost (Windows power scheme) | auto_boost per mode | /sys/devices/system/cpu/intel_pstate/no_turbo = 0 PROVEN | n/a | battery under load |
| Windows power mode / EPP | powermode | energy_performance_preference = power (Quiet) PROVEN | n/a | battery |
| Refresh rate (non-ASUS) | 60 Hz on battery, max on AC | compositor (niri) outside ACPI | n/a | battery (likely largest display item) |

## Top 5 to try on Linux (ranked)

1. Stop dGPU wakes on battery with dgpu_disable (same 0x90020 as G-Helper GPUEco). Current state: gpu_mux_mode=1, dgpu_disable=0, dGPU suspended.
   - Read: `cat /sys/bus/pci/devices/0000:01:00.0/power/runtime_status /sys/bus/pci/devices/0000:01:00.0/power/runtime_suspended_time` (sysfs only, does not wake the GPU).
   - Write (not run): `sudo sh -c 'echo 1 > /sys/class/firmware-attributes/asus-armoury/attributes/dgpu_disable/current_value'`. Revert with 0. Verify no GPU user process first. Reboot requirement is INFERRED unknown.
2. Cap refresh at 60 Hz on battery (G-Helper screen_auto). Non-ASUS, compositor side.
   - Read: `niri msg outputs` (lists modes and current rate).
   - Write (not run): `niri msg output eDP-1 mode 2560x1600@60.000`, then measure BAT1 current_now for 5 min static desktop, A/B.
3. Lower the battery ceiling to the DC floors, then check whether the EC honours it. Rank 3 because the idle effect is small (PL only caps load).
   - Read: `cat /sys/class/powercap/intel-rapl:0/constraint_0_power_limit_uw /sys/class/powercap/intel-rapl:0/constraint_1_power_limit_uw`; `cat /sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl{1_spl,2_sppt}/current_value`; EC readback if permitted: `sudo od -An -tu1 -j 155 -N1 /sys/kernel/debug/ec/ec0/io` (PL01, EC 0x9B) and `-j 157` (PL02, 0x9D). Debugfs EC node exists but is root-only (INFERRED offset mapping).
   - Write (not run): `sudo sh -c 'echo 15 > .../ppt_pl1_spl/current_value'` should be refused (below 25). Then `echo 25 > .../ppt_pl1_spl/current_value` and `echo 38 > .../ppt_pl2_sppt/current_value`. Run a fixed CPU load for 5 min and log BAT1 current_now and RAPL energy_uj. Revert to 35 and 53.
4. Turn off CPU turbo on battery (G-Helper auto_boost).
   - Read: `cat /sys/devices/system/cpu/intel_pstate/no_turbo` (currently 0).
   - Write (not run): `echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo`. Measure a fixed-load run and an idle run. Revert with 0.
5. Turn off panel overdrive on battery (G-Helper screen_auto).
   - Read: `cat /sys/class/firmware-attributes/asus-armoury/attributes/panel_overdrive/current_value` (currently 1).
   - Write (not run): `echo 0 | sudo tee /sys/class/firmware-attributes/asus-armoury/attributes/panel_overdrive/current_value`. A/B with item 2 on a static desktop. Expected effect small (INFERRED).

Also worth a look (not top 5): TGP 0x120098 is absent from Linux, so dGPU power on AC cannot be tuned. Check after resume that throttle_thermal_policy keeps its value, since G-Helper re-applies the mode on GU605MI. Core parking via CPU online is a runtime alternative to the ASUS core-count IDs.

## Caveats
- asusctl #744 (another owner's report, about 18 W idle floor) and the Windows 8-9 W idle figures were not verified here.
- Idle power is driven mostly by the dGPU, panel, and platform states, not by PL caps. Expect PL changes to show up under load only.
- The DSDT has no explicit branch for 0x120075, so the throttle path is SMI-backed. A DSDT grep is not a presence test.
