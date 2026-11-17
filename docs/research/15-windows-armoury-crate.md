# 15. What Armoury Crate / ASUS System Control Interface does on Windows (GU605MI) and what Linux lacks

Research date: 2026-11-14. Read-only. Sources are the mounted Windows partition (/mnt/win/os), offline hives exported with hivexregedit, DriverStore binaries (strings only), and the live Linux sysfs/asusctl state. Nothing was written to the system. Nothing was run that touches the NVIDIA GPU.

Evidence tags: **[PROVEN]** read directly from a file/registry/sysfs value. **[STRINGS]** a function or feature name found in a binary, meaning is inferred from the name. **[INFERRED]** reasoning from the above. **[BLOCKED]** data exists but is encrypted.

## 0. Bottom line

1. **The per-mode power tables (PL1/PL2/PL3, NVIDIA TGP and dynamic boost per mode, fan curves per mode) are NOT readable.** They sit in `ThrottleGear_GU605MI.xml` (AES-256-CBC inside an XML wrapper, the CipherValue is a DPAPI-style blob) and in `AC_Config.PowerMode/TGP/VgaOc/FanAcoustic.*` (custom binary header, not plaintext). Decrypting them would mean extracting the key from ASUS binaries. That was not done (see section 7).
2. **Windows has a second layer that Linux does not mirror: Windows power schemes.** Armoury Crate switches three Windows power plans (exported as `GU605MI_{PS,BA,HP}PowerScheme.pwcfg`). Those are plain registry files and were read in full. They set EPP, minimum/maximum processor state, core parking, cooling policy, display brightness, and sleep timers per mode. asusd does EPP and platform_profile, but does not touch min processor state, core parking, or brightness. Section 3 lists the differences.
3. **Linux is already ahead on exposed knobs** (PL1/PL2, dynamic boost, nv_temp_target, GPU MUX, panel overdrive, charge limit, fan curves). The gaps are behavioural (OLED care, Windows power-plan parity, Armoury mode-to-PPT mapping which is only partly known), not missing attributes.
4. **The 80% battery limit matches on both OSes** [PROVEN]: Windows `ChargingRate = 0x50 (80)`, `ChargingSmart = 1`, `Customization.ini [BatteryHealthCharging] value=80`. Linux `charge_control_end_threshold = 80`.

## 1. Files and installation state

Installed on Windows [PROVEN from directory listing]:

- `ProgramData/ASUS/ARMOURY CRATE Config/Data/`: ThrottleGear XML, AC_Config.* (encrypted), three `*PowerScheme.pwcfg` (registry format), `InitialSetting.ini`, `ConfigInstaller.xml` (model GU605MI, Omaha ID).
- `ProgramData/ASUS/ASUS System Control Interface/`: `AsusOptimization/Customization.ini`, `AsusSystemDiagnosis/*.txt` (about 80 daily reports, Dec 2025 to Aug 2026), `log/ASUS_EC_Log_Diagnosis_*.txt`, `log/Filter_Updateitems.log`.
- `ProgramData/ASUS/AsusSurvey`, `AsusLumina` (colour), `GameVisual` (ICM colour profiles for the GU605MI panel, sRGB/DCI-P3/Display P3/mono), `GPU Tweak II/config.ini` (empty of settings), `MyASUS`, `GlideX`, `AuraProcess.ini`.
- `Windows/System32/DriverStore/FileRepository/asussci2.inf_amd64_*` (ASUS System Control Interface: `AsusOptimization.exe`, `AsusHotkey.exe`, `AsusOSD.exe`, `AsusSplendid.exe`, `AsusWiFiRangeboost.exe`, `AsusWmiAcpi.sys`, `AsusSAIO.sys`, `ASUSSoftwareManager`, `ASUSSwitch`).
- `Windows/System32/DriverStore/FileRepository/armourycratecontrolinterface.inf_amd64_*` (`ArmouryCrateControlInterface.exe`, `ArmouryCrateKeyControl.exe`).
- `Program Files/ASUS/`: only AsLogDumpTool, Hotplug Controller, Monitor Control, GlideX. **No Armoury Crate UI binary is installed in Program Files**, so the mode logic lives in the DriverStore packages.

Services in the SYSTEM hive [PROVEN]: `ASUSOptimization`, `ASUSSoftwareManager`, `ASUSSwitch`, `ASUSSystemAnalysis`, `ASUSSystemDiagnosis`, `ATKWMIACPIIO` (start=1), `ArmouryCrateControlInterface`, `ArmouryCrateDownloadTool`, `AsusAppService`, `AsusSAIO` (start=3), `AsusKeyboard`, `AsusPTPDrv`, `ROGKB`, `ROGMS`, `nvpcf` (NVIDIA Power Control Framework, which carries Dynamic Boost).

Hardware IDs [PROVEN]: ACPI `ASUS2018` and `ASUS9001` devices under `Enum\ACPI` (the ASUS WMI/ASUS ACPI pair; the Linux asus-wmi/asus-armoury equivalents bind to the WMI GUID, not these IDs).

EC/BIOS identity from the Windows EC diagnosis log [PROVEN]: EC FW `ITEEC136.GU605 I.327`, chip `5570VG`, `MBDesignPower = 0xC8 (200 W)`, `DGPU_LIMIT = 1`, `THRO_CPU_L = 0`, fan count 3 (RPM 1810/1711/3850 at the sampled moment). Note the BIOS version is 329; the EC FW string above is a separate version.

## 2. Power modes: the names and the files

Windows Armoury modes (the names appear in the power-scheme FriendlyName fields and in `asusd` terms):

| Armoury mode | Windows plan file | FriendlyName in file | Linux asusd equivalent |
|---|---|---|---|
| Silent | `GU605MI_PSPowerScheme.pwcfg` | Silent | platform_profile quiet, EPP power |
| Performance | `GU605MI_BAPowerScheme.pwcfg` | Performance | platform_profile balanced, EPP balance_power (AC) |
| Turbo | `GU605MI_HPPowerScheme.pwcfg` | Turbo | platform_profile performance, EPP performance |

File-name prefixes (BA/HP/PS) are probably Balanced / High Performance / Power Saver (Windows plan names), **[INFERRED]**. The FriendlyName strings are what Armoury Crate shows.

ThrottleMode indices in `InitialSetting.ini` [PROVEN values]: `ThrottleModeOnAC=2`, `ThrottleModeOnDC=1`. The index-to-name mapping is **not** stated in any plaintext file. **[INFERRED]** AC defaults to the top mode and battery to the middle mode. Linux asusd does the opposite (AC Balanced, battery Quiet). Worth checking.

Linux ASUS thermal policy numbering (asus-wmi, from wave-1 note 02) [PROVEN in the notes]: throttle_thermal_policy 0 = balanced, 1 = performance/turbo, 2 = quiet. Windows "Turbo" should therefore send 1 and "Silent" 2. **[INFERRED]** not measured.

## 3. Windows power-plan differences per mode (the part Linux does not mirror)

Read from `*.pwcfg` (exported with `hivexregedit`, then parsed). Values are the AC/DC "SettingIndex" DWORDs, decimal. GUID-to-name labels are from memory of the Windows power GUID table, so treat the names as **[INFERRED]** where marked.

| Setting (GUID, name if confident) | Silent (PS) AC / DC | Performance (BA) AC / DC | Turbo (HP) AC / DC |
|---|---|---|---|
| EPP `36687f9e-...-6863` (energy perf pref, **probable**) | **45** / 50 | **0** / 50 | **0** / 0 |
| Min processor state `893dee8e-...-964c` (PROCTHROTTLEMIN, **probable**) | not set (default) | **100** / 5 | **100** / 5 |
| Max processor state `bc5038f7-...` (PROCTHROTTLEMAX) | not set (default) | 100 / 100 | 100 / 100 |
| Core parking min cores `0cc5b647-...` | 4 / 4 | 4 / 4 | 4 / 4 |
| Perf increase threshold `06cadf0e-...` (probable) | not set | 30 / 30 | 30 / 30 |
| Perf decrease threshold `12a0ab44-...` (probable) | not set | 10 / 10 | 10 / 10 |
| Boost/increase policy `465e1f50-...`, decrease policy `40fbefc7-...` (probable) | not set | 2 / 1 | 2 / 1 |
| Cooling policy `94d3a615-...` (SYSCOOLPOL, probable) | not set | 1 (active) on DC | 1 on DC |
| Display brightness `aded5e82-...` (probable) | not set | **53** / 53 | **76** / 76 |
| Unnamed video-subgroup setting `8ec4b3a5-...` (name not confirmed) | 60 / 60 | 60 / 60 | 60 / 60 |
| Sleep (hibernate) `9d7815a6-...` | 0 / 21600 s | 0 / 21600 s | 0 / 21600 s |
| Turn off display after `3c0bc021` / `17aaa29b` | 300 / 180 and 600 / 240 s | same | same |

Two readings worth acting on, both **[INFERRED from the table]**:

- **Turbo and Performance on AC pin minimum processor state at 100%.** Wave-1 note 07 says the Linux intel_pstate has `min_perf_pct=8`. Windows keeps the cores from downclocking to idle on AC in those modes. The idle-power cost is likely small on this 185H, but this is a real behavioural gap.
- **EPP is 0 (max performance) on AC for Performance and Turbo, and 45 for Silent.** asusd sets EPP `performance` for the Performance profile, and `balance_power` for Balanced. Windows Performance (BA) is at EPP 0 on AC, which is closer to asusd's Performance profile than its Balanced profile. The Linux AC default "Balanced" maps to a Windows mode that is less aggressive than Windows' own AC default. Check this on measurement.

What is **not** in these files: PL1, PL2, PL3, TGP, dynamic boost, fan curves. They are in the encrypted ThrottleGear/AC_Config files (section 4).

## 4. Encrypted per-mode tables (BLOCKED)

| File | Size | Header / format | Status |
|---|---|---|---|
| `ThrottleGear_GU605MI.xml` | 18 KB | XML `<ThrottlePluginConfig ... Cryptography="Encrypted">`, AES-256-CBC element; CipherValue starts `AQAAAAAAAAAE...`, the .NET/DPAPI-style header | **[BLOCKED]** |
| `AC_Config.PowerMode.GU605MI.enc` | 1.2 KB | binary, starts `07 46 42 fa 5b 2d cc 87` | **[BLOCKED]** |
| `AC_Config.TGP.GU605MI.enc` | 496 B | same header | **[BLOCKED]** (likely NVIDIA TGP/dynamic boost per mode) |
| `AC_Config.VgaOc.GU605MI.enc` | 1.1 KB | same header | **[BLOCKED]** |
| `AC_Config.FanAcoustic.GU605MI.cfg` | 3.5 KB | binary, starts `f5 31 c4 b0`, not XML/INI | **[BLOCKED]** (likely fan curves per mode) |

I did not try to decrypt these. The key would have to come out of `ArmouryCrateControlInterface.exe` or the ASUS plugin DLLs. That is reverse engineering vendor-protected config, so I stopped there (section 7).

Also not readable without the Windows machine key: DPAPI-protected user secrets. I did not open `NTUSER.DAT` or anything under the personal profile. Only `AppData/Local/ASUS/ASUS System Control Interface/AsusSoftwareManager` exists there (not read).

## 5. Feature inventory: Armoury Crate / ASUS SCI vs Linux

Windows features, from the registry (`HKLM\SOFTWARE\ASUS\ASUS System Control Interface\AsusOptimization\ASUS Keyboard Hotkeys`, `...\ScreenXpert`, `\OLEDCare`, `\VBIOS`), and from `AsusOptimization.exe` function names [STRINGS]:

| Feature (Windows) | Windows value on this unit [PROVEN] | Linux now | Replicable? |
|---|---|---|---|
| Battery health charge limit | `ChargingRate=0x50` (80%), `ChargingSmart=1`, `BatteryHealthCharging v3 value=80` | `charge_control_end_threshold=80` (asusd) | **Yes, already** |
| Instant full charge (24 h window) | `InstantFullChargeTime=0x15180` (86400 s), `PromptFullChargeCount=0` | none | Partly: asusd has no equivalent; treat as a UX-only feature |
| ScreenXpert battery care | `BatteryCare=1`, `FanMode=0` | n/a | Same as charge limit |
| Fan mode / Quiet Fan | `QuietFanPowerMode=2`, `QuietFanSupported=0`, `DesktopFan=0`, `FanOverboost=0`, `Switch fan mode from Fn+F` [STRINGS] | asusd platform_profile; asusd fan curves (quiet has CPU curve enabled) | **Yes** (profile-level) |
| Dynamic Boost (NVIDIA) | `nvpcf` service present; Windows value not readable here | `nv_dynamic_boost=20` (max) | **Yes**, already |
| NVIDIA thermal target | not readable | `nv_temp_target=87` (max) | **Yes**, already |
| GPU MUX / Optimus | `GraphicsOptimizedMode=0`, `GraphicsModeSupported=0`, `LockGpuMode=0`, `SetMuxSwitch` [STRINGS] | `gpu_mux_mode=1` (Hybrid), supergfx Hybrid | **Yes** |
| Panel overdrive | `APanelOLED=0`, OLED panel status strings [STRINGS] | `panel_overdrive=1` | **Yes** |
| OLED pixel shift / pixel refresh | `EnablePixelShift=1`, `PixelShiftStartup=1`, `OLEDProtect=1`, `OLEDProtectScreensaver=0x708` (1800 s idle), `SetOLEDProtect`, `ServiceLoopThread, OLEDPROTECT` [STRINGS] | none | **No.** Needs a daemon: idle timer then a full-white pixel refresh pass, or pixel shift. Doable with niri idle hooks + a fullscreen short-lived window. Also check whether the OLED "Panel Power Saver" in the wave-1 notes matches `APanelOLED`. |
| Auto refresh rate (dynamic) | `AutoRefreshRate=0x200000` (not set), `MultipleRefreshRate=0`, `Auto-switching refresh rate 1nd/2nd is supported` [STRINGS] | niri: manual `niri msg output eDP-1 mode ...` | Partly: write a battery-aware niri script |
| Colour presets (Splendid / GameVisual) | ICM profiles for sRGB, DCI-P3, Display P3, mono; `SetSplendidColorMode`, `Eyecare`, `Monochrome` [STRINGS] | none (no ICC profile; wave-1 note 11) | Partly: the ICM files are ASUS-specific, but the gamut ICMs (`ASUS_DCIP3.icm`, `ASUS_sRGB.icm`) are plain ICC. Could be loaded through colord. Needs measurement. |
| Keyboard backlight auto dim/battery | `AutoKeybdLight`, `KeybdBatteryAutoLight=1`, `KeybdBatteryThreshold=20`, `TurnOffKeybdLight=60 s` | asusd aura (static, brightness Med) | **Yes**: asusd aura timeout and battery-based brightness |
| Power plan switching (Windows scheme) | three pwcfg plans, section 3 | asusd EPP + platform_profile only | **Partly**: add min_perf_pct and core-parking changes (section 6) |
| Speaker volume boost / mic effect | `SpeakerVolumeBoost=2`, `MicrophoneEffectKey=0x14`, `AI noise canceling` flag | Dolby/Realtek in Windows; Linux CS35L56 (wave-1 note 06) | Out of scope |
| Wi-Fi RangeBoost / Smart Connect | `AsusWiFiRangeBoost*.dll`, `SmartAntenna=1`, `WiFiRoaming=0` [STRINGS] | none | No Linux equivalent |
| Lid-closed thermal protection | "Lid closed thermal protection is supported" [STRINGS] | ACPI/EC handles it | Unknown |
| Hotkeys (Fn+F, profile key, ROG key) | AsusHotkey.exe | asus-nb-wmi hotkeys on event10 (wave-1 note 13) | Yes, keycodes unverified |
| ASUS software updates, survey, telemetry | AsusSurvey, AsusBI, DataCollection BigData files | none | Not wanted |

## 6. Recommendations (ranked)

1. **Per-mode PPT and dynamic boost are the largest unknown, and cannot be settled from files.** Measure instead (section 8). Do not set PL values from guesses.
2. **Match the Windows plan on AC for Performance and Turbo.** Propose an asusd-independent drop-in that sets, per profile: min_perf_pct (100 on AC for Performance/Turbo, keep 8 on battery), EPP as in section 3, and nothing else. Measure idle power on battery (must not regress) and frame times in a game.
3. **Build an OLED care daemon.** Idle 30 min (matches the Windows 1800 s) then a short pixel refresh (fullscreen black/white cycle for about 1 min), plus pixel shift on resume. This is the most visible Armoury feature without a Linux equivalent. Use niri's idle or a systemd timer, plus a fullscreen layer surface. Verify the `APanelOLED` flag does not require the WinUSB panel path.
4. **Confirm the battery mode mapping.** `charge_mode` = 1 on Linux. The Windows Armoury "Balanced/Full" choice maps to something in `ChargingRate`/`ChargingSmart` and `InstantFullChargeTime`. Set nothing; read on AC with the cable plugged in, then compare with the registry values above.
5. **Align the AC default profile with Windows.** `InitialSetting.ini` says Windows defaults to the high mode on AC. Consider asusd `platform_profile_on_ac: Performance` (or measure first). Keep battery on Quiet.
6. **Keep `ppt_pl2_sppt` at 135 only after resolving the 104 vs 135 mismatch** (wave-1 note 12). RAPL short_term reads 104 W while asus-armoury says 135 W. Test under a 60 s all-core load with `turbostat` and a load-matched RAPL sample, before touching it.
7. **Do not copy the Armoury fan curves yet.** They are encrypted. Linux quiet curve (CPU enabled, 62 to 82 °C) is the only enabled curve. Measure temperature and fan RPM under a fixed load on Linux and on Windows (if Windows and Armoury Crate can be run for the same load) before writing a new curve.

## 7. Open questions and decision needed

- **Decrypt the ThrottleGear/AC_Config tables?** This would give PL1/PL2/PL3, NVIDIA TGP/dynamic boost, and the fan curves per mode, which is the largest missing piece. The key is in ASUS binaries, which means reverse engineering vendor-protected config. I did not do this; it is an open decision. The alternative is to measure on Windows (section 8).
- The Windows `ThrottleModeOnAC=2` index mapping is unknown. Needs the Armoury UI or the decrypted tables.
- The 104 W vs 135 W PL2 mismatch (wave-1 note 12) is still open.
- The "Optimized" GPU mode auto-switching logic: `GraphicsOptimizedMode=0` suggests it is off here, but the mode string is not confirmed.
- What `charge_mode` 0/1/2 means on this model.
- Whether `APanelOLED` is the Panel Power Saver flag from wave-1 note 11.

## 8. Experiments (read-only where possible, otherwise run manually)

1. **Per-mode PPT on Linux (state change, run manually):** for each of quiet/balanced/performance: `asusctl profile set <x>`, wait 30 s, read `/sys/class/firmware-attributes/asus-armoury/attributes/ppt_pl{1_spl,2_sppt}/current_value` and `/sys/class/powercap/intel-rapl:0/constraint_{0,1}_power_limit_uw`. Record the table. This answers whether the profile changes PL on this unit, which is not shown by any file yet.
2. **Windows reference (run on Windows, once):** with Armoury Crate in each mode, run HWiNFO64 (sensor-only, no changes) and record PL1/PL2 (Intel "Package Power Limit"), NVIDIA "Power Limit" and "Dynamic Boost" (from HWiNFO's GPU section), and fan RPM under a fixed 3DMark/Cinebench or Cinebench 2024 multi-core loop. Save the screenshots or CSV, not the hardware IDs.
3. **min_perf_pct A/B:** on Linux, set `min_perf_pct` (intel_pstate sysfs) to 100 for 10 minutes in a controlled load, then back to 8, measuring battery draw (`upower`) at idle for 10 minutes each. Only do this if the state change is acceptable.
4. **EPP AC default check:** `cat /sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference` under AC Balanced vs AC Performance (sysfs only). No GPU wake.
5. **OLED care timing:** log idle to the niri screen-off event, then measure burn-in risk with a static-image test pattern separately (not in this audit).

## 9. Tools I would want

- HWiNFO64 on the Windows side (read-only sensor logging), to capture the per-mode PL/TGP/boost numbers without decrypting anything.
- `turbostat` and `powerstat` on Linux (already in CachyOS repos) for PL and idle draw with the battery measurement.
- A small `hivexregedit`/`hivexget` script (present) to diff pwcfg files after future Armoury updates.
- `strings`/`objdump` on ArmouryCrateControlInterface.exe, read-only, only if the decryption route in section 7 is taken.

## 10. Sources and file paths (for re-checking)

- `/mnt/win/os/ProgramData/ASUS/ARMOURY CRATE Config/Data/InitialSetting.ini`
- `/mnt/win/os/ProgramData/ASUS/ARMOURY CRATE Config/Data/ThrottleGear_GU605MI.xml` (encrypted)
- `/mnt/win/os/ProgramData/ASUS/ARMOURY CRATE Config/Data/GU605MI_{PS,BA,HP}PowerScheme.pwcfg` (exported to `.reg`; local working copy, not in the repo)
- `/mnt/win/os/ProgramData/ASUS/ASUS System Control Interface/AsusOptimization/Customization.ini` (UTF-16)
- `/mnt/win/os/ProgramData/ASUS/ASUS System Control Interface/log/ASUS_EC_Log_Diagnosis_20260831070428.txt`
- `/mnt/win/os/Windows/System32/config/SOFTWARE` (exported to `SOFTWARE.reg`; local working copy, not in the repo): `ASUS\ASUS System Control Interface\AsusOptimization\ASUS Keyboard Hotkeys`, `ASUS\OLEDCare`, `ASUS\VBIOS`, `ASUS\Config`
- `/mnt/win/os/Windows/System32/config/SYSTEM` (exported to `SYSTEM.reg`; local working copy, not in the repo): `Services\AsusSAIO`, `Services\ATKWMIACPIIO`, `Services\nvpcf`
- `/mnt/win/os/Windows/System32/DriverStore/FileRepository/asussci2.inf_amd64_3eb06da3aad59dcc/ASUSOptimization/AsusOptimization.exe` (strings only)
- Linux: `/etc/asusd/asusd.ron`, `/etc/asusd/fan_curves.ron`, `/sys/class/firmware-attributes/asus-armoury/attributes/*`, `/sys/class/powercap/intel-rapl:0/*`, `/sys/firmware/acpi/platform_profile`, `asusctl battery info` (80%), `asusctl armoury list`, `supergfxctl -g` (Hybrid).

Note: the research notes in this directory were consulted (notes 02, 07, 11, 12, 13). None of the Windows-side findings above were in them, except the ASUS WMI IDs.
