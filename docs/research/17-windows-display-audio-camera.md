# 17 - Windows-side display, audio and camera assets (ROG Zephyrus G16 GU605MI)

Date: 2026-11-14. Read-only. Windows partitions read via /mnt/win (no writes). Registry read with hivexregedit. No personal files opened (AppData only for ASUS ProArt log, colour keys only). Nothing sent to the web except two generic searches with no personal data.

Asset copies: 17 files, original names, sources below (local working copy, not in the repo).

## 1. Colour

### Proven
- Factory profiles live in ProgramData/ASUS/GameVisual/. Relevant ones:
  - GU605MI_8086_834C41A3_CMDEF.icm (Intel iGPU variant, colour-mode definition with MHC2 and a Dolby Vision DVB1 block). Its D65-adapted primaries are R(0.680,0.320) G(0.237,0.723) B(0.140,0.050). These match the panel's own DisplayID chromaticities from wave 1 exactly.
  - GU605MI_8086_834C41A3.icm (same panel, no CMDEF). Primaries are wider in green, G(0.230,0.737). Its vcgt is absent. TRC is a 256-entry curve, gamma about 2.2.
  - ASUS_sRGB.icm, ASUS_DisplayP3.icm, ASUS_DCIP3.icm: the GameVisual gamut modes. Their D65-adapted primaries match sRGB, P3-D65 and DCI-P3 respectively.
  - GMMP tag in the 834C41A3 profile maps GameVisual modes to those three files.
  - All GU605MI profiles are class mntr, PCS XYZ, version 2.2, D50-relative primaries (adapted to D65 by Bradford in my analysis). Descriptions say "Calibrate by ACMP (V2.3.0)".
  - Profile naming: the 834C41A3 suffix matches the panel's PnP product code (registry DISPLAY\SDC41A3, Samsung), so the ID encodes the panel. Inferred from that match.
- Factory measurement tables: ProgramData/ASUS/AsusLumina/MainPanel_sRGB.txt and MainPanel_DisplayP3.txt (34 patches each, XYZ and dE vs target).
  - sRGB mode: average dE 0.342, max 1.11, gamma 2.24. Measured primaries R(0.641,0.330) G(0.300,0.600) B(0.150,0.059), white Y=347 at xy(0.312,0.329).
  - DisplayP3 mode: average dE 0.355, max 0.81, gamma 2.24. Measured primaries R(0.679,0.320) G(0.265,0.693) B(0.151,0.058).
  - So the factory calibration is real and is sRGB/P3 accurate at about dE 0.35 on the panel.
- Windows ICM state: the ProArt log (AppData/Roaming/AsusProArt/Log) says advancedColorSupported=1, advancedColorEnabled=0, hdrEnable=0. Windows runs the panel in SDR mode.
- The Windows colour-management registry (SOFTWARE ICM\RegisteredProfiles) lists generic profiles only. The per-display default profile association is in the per-user hive (NTUSER/UsrClass), which I did not open (personal). So the default GameVisual mode/association is NOT determined.
- No vcgt tag in any GU605MI profile, so Windows does no GPU-level calibration. Only colour-managed apps use the profile. Linux is equivalent.
- The DriverStore has generic third-party monitor ICMs only. None are for this panel.
- ASUS Monochrome profile exists (Asus_Monochrome.icm), not copied.

### Use on Linux
- The profile correctly describes the panel. It helps only colour-managed apps: Resolve (its own colour management; keep the monitor profile for UI only if Resolve supports it), GIMP, Darktable, Krita, mpv (icc-profile), Firefox/Chromium (color management settings).
- colord: `colormgr import-profile` plus `colormgr device-add-profile` for the eDP output, then set default. Done via user session, no root needed.
- niri does not apply ICC (wave 1 finding stands). KDE Plasma 6.7+ may apply ICC (unverified).
- Recommendation: use GU605MI_8086_834C41A3_CMDEF.icm as the panel's native profile for colour work (it matches EDID and factory measurements). Use ASUS_sRGB.icm as the sRGB-target profile when a viewer needs sRGB clamping. Test before relying on it, because there is no vcgt to correct the TRC.

## 2. Speakers (CS35L56 + ALC285 + Dolby DAX3)

### Proven
- Windows driver package csaudioext.inf_amd64_7236d3620c7fc0a7 (Cirrus, DriverVer 25.26.50.500) contains:
  - Jamerson/Firmware/CS35L56_Rev3_11_16/CS35L56_Rev3.11.16.wmfw. sha256 12c6d4fe...eff58. Byte-identical to /usr/lib/firmware/cirrus/cs35l56/CS35L56_Rev3.11.16.wmfw.zst after zstd -d. Also 3.11.6 and 3.9.2 variants (not in Linux firmware here).
  - Jamerson/Tuning/ASUS_GU605_10431C63_240426/: V0_A0, V0_A1, V1_A0, V1_A1 -init.bin (8192 B). sha256 values match the Linux files exactly:
    - V0_A0 5732e3ba = cs35l56-b0-dsp1-misc-10431c63-spkid0-amp1.bin
    - V0_A1 4000b879 = spkid0-amp2.bin
    - V1_A0 e34ae31e = spkid1-amp1.bin
    - V1_A1 30c8e8c6 = spkid1-amp2.bin
  - Conclusion: the speaker amp firmware and per-unit ASUS tuning/calibration on Linux are already the same bits Windows loads. Nothing to gain from the amp tuning itself. The wave-1 "misc" tuning string and calibration are confirmed.
- Windows audio processing for the internal speakers is the Dolby DAX3 chain (dax3_ext_rtk, dax3_swc_aposvc, HDX_AsusExt_DOLBY_DSP_Wrap) bound to INTELAUDIO\FUNC_01&VEN_10EC&DEV_0285&SUBSYS_10431C63 (ALC285 on 1043:1c63).
- Per-model DAX3 tuning file: DEV_0285_SUBSYS_10431C63_PCI_SUBSYS_1C631043.xml (tuning_version 26, tuning_date 2023-12-04, DAX 3.7.1). 10 profiles: dynamic, movie, music, game, voice, voice_onlinecourse, personalize_user1-3, off.
- Default for internal speakers: operator_settings_asus_rog_game.json sets default_profile = game for internal_speaker (spatial on and off). So the Windows default speaker profile is "game". (Inferred that the app honours operator defaults.)
- Game profile (index 3) values:
  - IEQ off; graphic EQ off (all zero); dialog enhancer off; surround-boost 0; bass-enhancer off; calibration-boost 0; process-optimizer off; mb-compressor off; noise gate off.
  - Virtualizer: front speaker angle 10, height 10, surround 10 (stereo widening).
  - surround-decoder on; processing_mode 11; mix_matrix 16384,0,0,16384 (Q14, 1.0).
  - Volume leveler ON (drc on, amount 0, in/out target -320).
  - Regulator ON (relaxation 96, timbre preservation 12, distortion slope 16, speaker distortion enabled).
  - Audio optimizer ON: 20-band curve per channel (ch_00 and ch_01 identical): 0,32,24,24,24,24,8,-16,0,0,8,-16,-16,0,0,-8,-8,-16,-24,-32.
  - Sliding bass ON: xo 180 Hz, band boundary 6, attack 712, release 500, max level 52, gain curve 48,56,56,48,48.
  - speaker-peq-enable 1, but speaker-peq-filters is EMPTY in every profile (no biquads in this file).
  - Band centre frequencies (48 kHz, band_20_freq): 47,141,234,328,469,656,844,1031,1313,1688,2250,3000,3750,4688,5813,7125,9000,11250,13875,19688 Hz.
- Units of the DAX3 numbers are NOT established. The mix_matrix suggests Q14 coefficients. Gains like the audio-optimizer curve could be 1/256 dB (about +/-0.1 dB, negligible) or 1/8 dB (about +/-4 dB, audible). Not resolved from files here.
- Other Windows INFs: Realtek UAPO2 and APOT files, HDXSSTASUS with RTAIODAT.DAT (59 MB; contains ASUS pin/quirk tables, not EQ). No SonicStudio and no Waves on this machine.
- Dolby VLLDP and Dirac libraries (mtl_vlldp15x_2inst_lib.bin, mtl_dirac_lib.bin) sit in DriverStore intcoed_oemlibpath. They are the Intel SST DSP-side effects, used by the INTELAUDIO path. The per-model DAX3 tuning (tuning-vlldp block) targets those libs. Inferred.
- Linux audio path (journal): snd_hda_intel with ALC285 in plain HDA mode. No SOF lines in the boot log. So Windows runs DAX3 on the SST/DSP path, while Linux runs no equivalent processing.

### Feasibility on Linux
- Feasible and cheap: a PipeWire filter-chain (or EasyEffects) with the 20-band audio-optimizer curve as peaking biquads at the band frequencies above, plus a stereo widener and a volume leveler. The exact gains depend on the unit question above. Start by measuring the speakers, then decide. The 20-band curve is a mild correction (~-4 to +4 dB if 1/8 dB units), so test it by ear with a reference track.
- Sliding bass maps to a 180 Hz low-shelf/high-pass split with a mild bass lift (not exact).
- Not feasible to exactly reproduce the Dolby IEQ/VLLDP DSP (no IEQ target used in the game profile anyway; the ieq_balanced target only applies to dynamic/music).
- Speaker protection (regulator) is already in the CS35L56 firmware. Do not duplicate it.

### Open
- Units of the DAX3 numbers (1/256 dB vs 1/8 dB) for audio-optimizer and sliding-bass. Settle by measuring Windows output (not possible without Windows running; could run Windows, but out of scope for this read-only task).
- Which Windows profile was actually selected (per-user hive, not read).
- Whether Windows DAX3 is bypassed by a Realtek APO path for speakers.

## 3. Camera (USB 3277:0051, Shinetech "USB2.0 FHD UVC WebCam")

### Proven (sysfs descriptors, no /dev/video opened, no streaming)
- Source: /sys/bus/usb/devices/3-7/descriptors. Copy: usb_3277_0051_descriptors.bin (local working copy, not in the repo).
- Interfaces:
  - 1.0 VideoControl (colour): units 2 processing, 3 output, 4/7/8 extension units.
  - 1.1 VideoStreaming (colour), 1.2 is VC of IR (UVC 1.5 proto 01 on iface 2).
  - Iface 2 (VideoControl, proto 01 IR): input 9, output 12, extension units 11, 10, 14.
  - Iface 3 (VideoStreaming, IR, endpoint 0x82): IR stream.
  - Iface 4 class fe/01/01 (DFU-like): no driver bound.
- Extension units (XU), parsed from descriptors:
  - Colour: unit 4 GUID 1229a78c-47b4-4094-b0ce-db07386fb938, 2 controls, bmControls 00060000. Unit 7 GUID 26b8105a-0713-4870-979d-da79444bb68e, 1 control, bmControls 00100000. Unit 8 GUID 0f3f95dc-2632-4c4e-92c9-a04782f43bc8, 1 control, bmControls 00010000.
  - IR: unit 11 GUID 45b5da73-23c1-4a3d-a368-610f078c4397, 0 controls. Unit 10 GUID 1229a78c-47b4-4094-b0ce-db07386fb938, 2 controls, bmControls 00060000. Unit 14 GUID 0f3f95dc-2632-4c4e-92c9-a04782f43bc8, 2 controls, bmControls 20010000.
  - IR candidates for the emitter: units 10 and 14 (the same GUIDs as colour units 4 and 8). Control selectors per bmControls: unit 10 selectors 10 and 11 (bits 9,10); unit 14 selectors 6 and 9 (bits 5,8). Selector numbering is inferred from bit position (bit n = selector n+1).
- Payload: not present in descriptors. Windows INF/registry has no XU payload (no INF references the camera PID 0051 or an emitter; Hello uses Platform DMFT, group "Rts-DMFT-Group", and SdcaMfd is SoundWire, not camera). USBCAMD2.sys is the generic Microsoft camera driver. So the payload must be found by probing (linux-enable-ir-emitter `configure` with the camera) which I did NOT do (it would open /dev/video*).
- Registry: Hello face enrolment keys reference "Rts-DMFT-Group" (Realtek DMFT). PID 0051 device-class GUID {24e552d7-6523-47f7-a647-d3465bf1f5ca} is registered for the camera interface.

### Web
- Search for 3277:0051 in linux-enable-ir-emitter returned no entry for this device. The upstream wiki describes a semi-automatic configure mode (emitter count, resolution) for unknown cameras.
- Search for XU GUID 1229a78c returned only a gist (HP HD camera 05c8:0808, unit 4, 2 controls) and UVC kernel docs. No function description.

### Recommendation
- Run `linux-enable-ir-emitter configure` (semi-automatic) with the IR interface only, after reading its safety notes. It will probe XU selectors on units 10 and 14 (or the IR VC) and save a payload. Then enable the systemd unit. This is the path for howdy.
- Expect the emitter to be controlled by unit 10 or 14. Those are the candidates; the test must confirm which one flashes the emitter.

## 4. Microphones

### Proven
- Windows DMIC: INTELAUDIO\CTLR_DEV_51CA...DEV_AE20... Intel DMIC extension INFs (intcdmicext*). ASUS-specific INFs exist for many SSIDs, but none matched 10431C63 in a grep of all Intel DMIC INFs. So the GU605MI mic on Windows uses the generic Intel DMIC extension with no ASUS-specific noise-suppression block. Voice Clarity EP (voiceclarityep_audio_component) is the generic Windows effect.
- Linux: journal shows snd_hda_intel with ALC285; no SOF topology lines. Mic is the HDA path (wave 1 concurs). The Windows noise processing (Intel SST Voice Clarity / DMIC ext) does not have a Linux equivalent here; Linux would need PipeWire echo-cancel (webrtc) or EasyEffects if wanted.
- No Windows-side mic tuning file found to copy.

## 5. Ranked recommendations
1. Camera IR (highest everyday impact): run linux-enable-ir-emitter configure on 3277:0051, testing XU units 10 and 14. Run it manually from a normal desktop login, not from an automated research script.
2. Colour: use GU605MI_8086_834C41A3_CMDEF.icm via colord for colour-managed apps; verify against a colorimeter. Check KDE 6.7 ICC-in-HDR only if colour work requires it.
3. Speakers: no amp firmware change needed (already identical). Optional PipeWire filter-chain using the game-profile audio-optimizer curve, only after measuring the units question.
4. Mic: nothing to copy from Windows; treat as parity-not-needed.

## 6. Open questions
- DAX3 units (1/256 dB vs 1/8 dB).
- Default GameVisual mode and per-display ICM association (per-user hive not opened).
- Which XU selector flashes the IR emitter (needs a manual probe).
- Whether Windows Realtek APO overrides DAX3 for speakers.

## Sources (asset copies kept locally, not in the repo)
- ProgramData/ASUS/GameVisual/*.icm, ConfigInstaller.xml
- ProgramData/ASUS/AsusLumina/MainPanel_{sRGB,DisplayP3}.txt
- DriverStore/FileRepository/dax3_ext_rtk.inf_amd64_e1e11033913edfed/{DEV_0285_SUBSYS_10431C63_...xml, operator_settings_asus_rog*.json}
- DriverStore/FileRepository/csaudioext.inf_amd64_7236d3620c7fc0a7/Jamerson/{Firmware,Tuning}/...
- DriverStore/FileRepository/usbvideo_ext.inf_amd64_7c9573a9d564f57e/usbvideo_ext.inf (no 0051 entry; copied for reference)
- /sys/bus/usb/devices/3-7/descriptors
- Web: https://github.com/EmixamPP/linux-enable-ir-emitter/wiki/Semi-automatic-configuration ; https://gist.github.com/dalgaaf/bdef40f8e8b31c3a4c79ad7ec2b6b10b
