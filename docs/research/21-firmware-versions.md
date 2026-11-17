# Firmware versions audit: ROG Zephyrus G16 GU605MI (2024, Core Ultra 9 185H)

Audit date: 2026-11-14. Kernel 7.3.3-1-cachyos. Read-only; nothing installed, flashed or updated.
Privacy: serials, MACs, UUIDs and account names from the logs were deliberately left out.

## Component table

| Component | Installed | Latest known | Source for "latest" | How to update | Notable fixes / advisories |
|---|---|---|---|---|---|
| BIOS (system firmware) | GU605MI.329, dated 2025-06-06 (dmidecode; Platform FW rev 5.32) | Not verified. ASUS support page for GU605MI fetched but returned no BIOS list. Search found only GU606 (2026 model) results. fwupd shows no LVFS update. | ASUS support "Drivers and manuals" (manual check needed). fwupd: "System Firmware" has no update. | EZ Flash 3 from the BIOS menu (USB) or ASUS Armoury Crate on Windows. Not fwupd (no LVFS BIOS for this model). | Unknown changelog. Check the 329 to newer changelog for Intel CSME, microcode and Thunderbolt fixes. |
| EC firmware | 3.27 (dmidecode type 0) | Not verified. | ASUS support (bundled with BIOS, usually). | Bundled with BIOS update (EZ Flash). | None found. |
| Intel CSME / ME | 18.0.5.2141 (`/sys/class/mei/mei0/fw_ver`; fwupd "csme18 v18.0.5.2141: Valid") | Not verified against a 2026 build. | fwupd HSI reports it valid. | Comes with BIOS update. Not separately updatable. | INTEL-SA-01371 (CVE-2026-6727, CVSS 4.0 8.5, CSME/SPS privilege escalation): the advisory lists no Meteor Lake or 18.0.x entries, so it does not confirm exposure. INTEL-SA-01372 (CVE-2026-6726): its table shows 18.1.21 for Core Ultra Series 1, so 18.0.5 looks below the fixed branch, but this is unconfirmed. INTEL-SA-01315 (2026.1 IPU, out-of-bounds read). Intel says: use the latest manufacturer-supplied version, so the BIOS update is the path. |
| CPU microcode | 0x2b (`/proc/cpuinfo`, family 6, model 170 (0xAA), stepping 4). Early-loaded from 0x1c at boot. | 0x2b. A German report (PCGH) says Intel raised MTL 06-aa-04 from 0x28 to 0x2b on 2026-09-25. Sources disagree on the timeline. | intel-ucode 20261110-1 (installed, Arch). Phoronix on microcode-20261110: client updates cover RPL, Wildcat Lake and Panther Lake, not MTL. | Automatic via initramfs (`intel-ucode` package, already active). | microcode-20260812 reportedly removed MTL 06-aa-04 C0 due to functional issues, which may explain the 0x2a/0x28 history. Unconfirmed. |
| NVMe SSD (WD PC SN5000S 2TB, MN SDEQNSJ-2T00-1002) | 34230100 (`nvme id-ctrl` fr; `fw-log` frs1 = 34230100) | Not verified. Only older PC SN5000S firmware found (512GB: 34012142, SmartHDD). | No WD release notes for 2026 found. fwupd: "WD PC SN5000S: no available firmware updates" (LVFS has the device). | WD Dashboard (Windows only) or SanDisk support download. No Linux path with a verified image. | WD/SanDisk shipped Windows 11 24H2 BSOD fixes for SN5000 family (HMB related). Windows only. Linux health: 0 media errors, 3% used, 115 unsafe shutdowns, 1199 power-on hours, temp 30 °C, 100% spare. The 115 unsafe shutdowns are notable; check whether they come from hard power-offs or hibernate. |
| Thunderbolt / USB4 controller and retimer NVM | Not exposed. `/sys/bus/thunderbolt/devices/0-0` has no `nvm_version` attribute. Host Gen14 router visible, `authorized=1`. | Not verified. | fwupd lists no Thunderbolt or retimer device on this machine. | Would come with the BIOS (Intel TBT NVM via BIOS). Not separately updatable from Linux here. | None checked. |
| Wi-Fi (Intel AX211) firmware | iwlwifi `89.b20dcd1f.0` (`ma-b0-gf-a0-89.ucode`) | 89 is the highest ucode API in the installed linux-firmware 20261019-1 (`iwlwifi-ty-a0-gf-a0-89.ucode`). `checkupdates` shows no linux-firmware update pending. | Arch repo (checkupdates). | `pacman -Syu` (linux-firmware). | None found. Note the kernel log line "BIOS contains WGDS but no WRDS" is a benign ACPI note. |
| Bluetooth (Intel AX211, ibt) | Firmware build 4027, timestamp 2026.29, version 187-29.26, `intel/ibt-0180-0041.sfi`, DDC applied. Loaded OK. | Installed file in linux-firmware 20261019-1. No newer package pending. | Arch repo. | `pacman -Syu` (linux-firmware). | None checked. |
| Intel GPU GuC | 70.53.0 (`i915/mtl_guc_70.bin`), submission, SLPC and RC enabled | 70.53.0 is the installed package version. No newer upstream check done. | Arch linux-firmware 20261019-1. | `pacman -Syu`. | None. |
| Intel GPU HuC | 8.5.4 (`mtl_huc_gsc.bin`), authenticated for all workloads | Installed package version. | Arch repo. | `pacman -Syu`. | None. |
| Intel GPU DMC | v2.23 (`mtl_dmc.bin`) | Installed package version. | Arch repo. | `pacman -Syu`. | None. |
| Intel GPU GSC | r102.1.15.1926, svn 1 (`mtl_gsc_1.bin`), PXP up | Installed package version. | Arch repo. | `pacman -Syu`. | None. |
| CS35L56 amps (x2, SPI, Rev B0) | DSP firmware 3.11.16 (`cirrus/cs35l56-b0-dsp1-misc-10431c63-spkid0.wmfw`, amp fw 3.4.4 OTP3). Calibration applied; tuning PID 0x531116. | Windows DriverStore csaudioext has CS35L56_Rev3.11.16 (also 3.11.6 and 3.9.2). Linux has 3.11.16 and 3.11.11 too. | Compared directly (see note below). | `pacman -Syu` (linux-firmware-cirrus). | None known. |
| NVIDIA GSP firmware | 620.70.06 (`/lib/firmware/nvidia/620.70.06/`, ad107 path for RTX 4070 Laptop, AD107) | 620.70.06 (installed); no nvidia-utils update pending. | Arch repo. A pending `linux-cachyos-nvidia-open` 7.3.3 to 7.3.4 update exists. | `pacman -Syu`, then reboot. | Driver 620.70.06 is the one in use. Prior RTD3 regression is tracked in another note. |
| Webcam (USB2.0 FHD UVC, 3277:0051) | 2.2 (fwupd, Shinetech USB 0x3277). Device flag "Updatable". | No fwupd update offered. | fwupd. | fwupd, if an update appears on LVFS. | None. |
| Keyboard MCU (ITE 8910, 0B05:19B6 and 0B05:193B) | bcdDevice 0x0003 and 0x000e (USB descriptor value, not a verified FW revision) | Not verified. | ASUS (no LVFS entry). | ASUS Armoury Crate on Windows, or bundled with BIOS. | Not seen in fwupd. |
| Touchpad (I2C HID, ASUP1207, PixArt 093A:3012) | Firmware revision not exposed in sysfs. | Not verified. | ASUS / Windows driver package. | Windows driver or ASUS tools; not on Linux. | None. |

## Notes

- **CS35L56 check.** The Windows `CS35L56_Rev3.11.16.wmfw` (both the Jamerson/Firmware copy and the System32/csaudio copy) and the Linux `cirrus/cs35l56/CS35L56_Rev3.11.16.wmfw.zst` decompressed have the same SHA-256 (`12c6d4fe…eff58`). The Linux tuning binaries (`amp1`/`amp2.bin`) are per-unit and were not compared against Windows.
- **fwupd HSI** (`fwupdmgr security`): HSI:1! (v2.1.9) with a runtime suffix "!". Passing: BIOS updates enabled; MEI key manifest valid; SPI write disabled, SPI lock enabled; Boot Guard enabled with a valid OTP fuse; IOMMU enabled; pre-boot DMA protection enabled; CET supported; SMAP enabled; TPM 2.0 found and PCRs valid. Failing: Locked MTD (not supported); encrypted RAM disabled; hardware disk encryption not supported; Linux kernel lockdown disabled; Linux swap unencrypted; Linux kernel tainted (expected with the NVIDIA proprietary module); UEFI Secure Boot disabled; S3 disabled (s2idle in use).
- **Blockers for fwupd:** fwupd does not offer a BIOS, EC or Thunderbolt update for this model. Some UEFI CA entries report "No vendor ID set". The HSI result cannot be fixed by firmware updates alone (Secure Boot and lockdown are OS settings).
- **Kernel log items worth watching:** "ACPI: video: [Firmware Bug] PXSX defines _DOD but not _DOS" and "wmi_bus: WQ00 data block query control method not found". Both are firmware-side ACPI quirks and worth checking against the next BIOS changelog.

## Recommendations

1. Get the newest GU605MI BIOS from ASUS's "Drivers and manuals" page for this model (not the GU606 2026 page). Read the changelog for CSME, microcode and Thunderbolt. Apply through EZ Flash only on AC power, and only after reading the changelog and backing up.
2. Check WD Dashboard on Windows for the SN5000S firmware. Do not use `nvme fw-download` on Linux.
3. Keep linux-firmware, intel-ucode and the NVIDIA driver current with pacman. Everything loaded matches the newest Arch package.
4. Keep the pending kernel and NVIDIA module updates (7.3.4) in mind, since the NVIDIA module version changes with the kernel.

## Open questions

- Is 329 still the newest BIOS for GU605MI? The ASUS page did not load a list. A manual check is needed.
- Is WD SN5000S 34230100 current? The only verifiable older version is 34012142 (512GB model).
- Does CSME 18.0.5.2141 need a fix from INTEL-SA-01371 or 01372? The advisories do not name the 18.0.x branch for this platform. The BIOS vendor should confirm.
- The 115 unsafe shutdowns on the NVMe are worth explaining (hibernate hang workarounds, hard power-offs).
