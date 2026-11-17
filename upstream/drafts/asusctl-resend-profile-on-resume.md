# Draft issue: asusd should re-send the platform profile after resume

**Repo:** OpenGamingCollective/asusctl · **Type:** feature / robustness

## Title

asusd: re-send the platform profile on wake (GU605MI/MV/CR firmware can lose it across sleep)

## Body

On wake, asusd re-applies the charge limit, but it re-applies the platform profile only when the power source changed while the laptop slept (`ctrl_platform.rs`, `create_tasks` → `if !sleeping … last_power_plugged != power_plugged`). Otherwise the kernel keeps reporting the profile it had before sleep, whatever the EC is actually doing.

G-Helper treats the Zephyrus G16 GU605MI, GU605MV and GU605CR as models whose EC can lose its thermal mode across sleep, and re-sends the current mode after every resume (`AppConfig.IsSleepReset()` → `ModeControl.SleepReset()`, which calls `DeviceSet(PerformanceMode, current)`). The firmware gives no way to check: on a GU605MI (BIOS 329) the WMI readback `DSTS 0x00120075` returns the constant `0x10003` in Silent, Balanced and Turbo alike, and the RAPL limits don't change with the mode (PL1 90 W / PL2 104 W in all three), so neither asusd nor the user can tell a lost mode from a kept one.

**Proposal:** on `PrepareForSleep(false)`, write the current platform profile again, unconditionally. Writing the same value is cheap and idempotent: `asus-wmi` issues the WMI call again, and asusd's existing profile-change path re-syncs the fan curves for that mode. A model quirk list isn't needed for something this harmless.

**Tested workaround (GU605MI, kernel 7.3.4, asusctl 6.5.0):** a `system-sleep` post hook doing `cat throttle_thermal_policy > throttle_thermal_policy`. asusd logged the re-sync (`write_profile_curve_to_platform: writing profile:(balanced)`); nothing else changed. Side effect worth knowing: on this model every thermal-mode write makes the EC send an NVPCF notify, which wakes the NVIDIA dGPU for a few seconds (same as pressing Fn+F5).

Hardware: ROG Zephyrus G16 GU605MI (2024), Core Ultra 9 185H, RTX 4070, BIOS 329.
