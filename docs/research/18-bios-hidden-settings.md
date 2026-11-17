# 18 - BIOS setup options, hidden items and current values (GU605MI, BIOS 329)

Status: PARTIAL. The image was obtained, unpacked and the NVRAM stores were read, but the
main AMITSE "Setup" form tree (CPU/PCH/SA/Power/ASPM/PEP/TBT menus, SuppressIf/GrayOutIf
logic) could NOT be recovered. Every "option name" claim below is therefore unverified.
Byte offsets are given where they are known from the raw NVRAM; names are not.

## 1. Firmware image

- Source: Windows partition (read-only mount), `/mnt/win/os/Windows/Firmware/{ec482301-caf6-5316-8b75-b6850400831e}/GU605MI.329`.
  Copied out (local working copy, not in the repo). Size 38,928,384 bytes, sha256 `46c95b99...61f12e`.
- Identity: the running firmware reports `bios_version = GU605MI.329`, `bios_date = 06/06/2025`
  (sysfs DMI, read-only). The image strings include GU605MI and an ASUS board tag (`GU605_MB2`).
  Version match confirmed against the running system; ASUS support page was NOT fetched.
- Format: AMI PFAT / BIOS Guard capsule (`_AMIPFAT` header at 0x8, `AMI_BIOS_GUARD_FLASH_CONFIGURATION` block),
  wrapping an Aptio (AMI) firmware volume set. Not a plain 16 MB SPI dump.
- Windows-side `eSupport/eDriver` holds only the ASUS utility package (md5 list), no BIOS image.
  `myasus` and `restore` contain no BIOS image.

## 2. Extraction work

Tools (downloaded locally, run unprivileged):
- UEFIExtract NE A76 (linux x64), IFRExtractor-RS v1.6.1 (linux).
- `uefiextract GU605MI.329 unpack` produced `GU605MI.329.dump/` (4154 objects) and `GU605MI.329.report.txt`.
  The dump is kept as a local working copy, not in the repo.
- All 4154 extracted objects were scanned with `ifrextractor ... list`. No HII form packages in any of them.
  Every IFR-bearing module sits inside a compressed section.

Blocking point:
- One GUID-defined section (GUID `EE4E5898-3914-4259-9D6E-DC7BD79403CF`, the EDK2 LZMA-custom GUID,
  image offset 0xCDBB4, size 0x72D994) holds the big DXE volume (FFSv3 at 0xCDB24, size 0x9C5000).
  UEFIExtract fails with "Customized decompression failed".
- Manual decode: the payload header is standard LZMA-alone (props 0x5D, dict 16 MB).
  - liblzma (Python `lzma`) decodes 6,792,514 bytes, then "Corrupt input data".
  - 7-Zip (`/usr/bin/7z`) decodes 7,070,001 bytes, then "Data Error".
  - Dict sizes 16 to 256 MB and the x86 BCJ filter did not change this. Embedded LZMA headers were not found.
  - Entropy is flat (~7.997 bits/byte) across the payload, so the failure is not a visible plaintext boundary.
  - Hypothesis (unverified): the PFAT/BIOS-Guard layer encrypts or re-chunks part of the payload.
    The proper unwrapper is `platomav/BIOSUtilities` `ami_pfat_extract`, which depends on external
    Windows-oriented helpers (BigScriptTool, Tiano/szip). Not run.
- What the partial 6.79 MB output yields (`sec_big_partial.bin`): four HII form-package sets, all Intel ME/AMT/
  EFI-shell/boot/network/VTIO/genesis UI. Titles include "Removable Drive", "MEBx", "Intel(R) Platform Service Record",
  "Intel(R) AMT Configuration", "CD/DVD Drive", "VTIO". They reference VarStores MebxCfg (0x8888, size 0xBB4),
  PsrCfg (0x5566, 0x1560), VtioCfg (0x15C7, 0x154). The VarStore sizes agree with the efivar sizes
  (MebxCfg efivar 3000 bytes = 0xBB4 + 4), which validates the variable mapping.
- Not present in the partial output: any CPU/PCH/SA/Power/PEP/ASPM/TBT/Fast Boot/Overclock/C-state text.
  Searching both UTF-16 HII strings and ASCII found none of these.

Next steps to get the real Setup IFR (not done here):
1. Run BIOSUtilities `ami_pfat_extract` on the capsule (needs its externals; unprivileged, no install)
   to get the un-PFAT'd SPI image, then rerun UEFIExtract and IFRExtractor on the full image.
2. Or find the AMITSE module by GUID (`C811FA38-42C8-4579-A9BB-60E94EDDFB34` AMITSESetup) once decoded.

## 3. Setup variable stores: current (efivarfs) vs stored NVAR image

Current values read via `sudo cat` of `/sys/firmware/efi/efivars/*` (4-byte attribute header stripped).
The "NVAR" column is the image's stored copy of the same variable (UEFIExtract NVAR entry). It is probably
the factory/default image, so the diff approximates "user changed". This is an inference.

| Variable (GUID) | Size | Bytes that differ from NVAR image |
|---|---|---|
| `Setup` (EC87D643-EBA4-4BB5-A1E5-3F3E36B20DA9) | 3309 | 11 bytes: 0x002 (100 -> 80), 0x015, 0x01B, 0x024, 0x025, 0x027 (0 -> 1), 0x030 (0 -> 9), 0x825 (0 -> 1), 0x871 (0 -> 2), 0xCDA (0 -> 2), 0xCE2 (1 -> 0) |
| `CpuSetup` (B08F97FF-E6E8-4193-A997-5E9E9B0ADB32) | 1503 | 75 bytes, clustered at 0x000-0x002 and 0x0B7-0x0DB+ (table-like values 1..8, 31, 38, 48, 51) |
| `PchSetup` (4570B7F1-ADE8-4943-8DC3-406472842384) | 6082 | 6 bytes: 0x000, 0x002, 0x003 (125), 0x03B, 0x03C, 0x16E2 (4 -> 1) |
| `SaSetup` (72C5E28C-7783-43A1-8767-FAD73FCCAFA4) | 736 | 9 bytes: 0x000, 0x07E-0x07F, 0x0A7 (4 -> 2), 0x0EF, 0x0F2, 0x130, 0x14F, 0x16E |

Other setup-like vars present (sizes): AMITSESetup 81, MeSetupStorage 16, FastBootOption 138, SiSetup 7,
AmiWrapperSetup 4, AsusSetupItemVariable 155 (flag bytes 0/1), BiosSettingMappingTable 28 (a list of
16-bit ids, likely ASUS item-to-offset map, not decoded), PCIEPowerControl 4, SioSetupData 1, SecureBootSetup 11,
IntelVmdDeviceInfo 424, IntelVmdOsVariableV2 99, CpuSetupVolatileData 13, TbtSetupVolatileData 10.

Important: the offset-to-option mapping is NOT known. These diffs cannot be labelled with option
names until the IFR is decoded.

Not a Setup option: PDOD / P0DL / PEP0 (wave-1 notes) are ACPI GNVS runtime fields at `0x45BFDB6F` / `0x45BFD070`,
not NVRAM Setup values. Do not treat them as BIOS settings.

## 4. CPU lock state (read-only MSRs)

- `rdmsr -p0 0xE2` (MSR_PKG_CST_CONFIG_CONTROL) = `0x74008008`.
  - Bit 15 (CFG Lock) is SET. Bit 3 is set. Bits 2:0 (package C-state limit) = 0, i.e. C0/C1 limit at MSR level.
  - Bit meanings from memory of the Intel SDM, not re-checked.
- `rdmsr -p0 0x194` (FLEX_RATIO) = `0x100000`. Bit 20 (OC / flex-ratio lock) is SET.
- `rdmsr -p0 0x150` (OC mailbox, extra read) = `0`. No voltage-offset state visible.

Interpretation: the BIOS has CFG lock and overclock lock enabled. The MSR-level lock matches a
"Overclocking Lock" or CFG-lock Setup option being on. Undervolt via the 0x150 mailbox is locked in
the stock configuration. Whether any Setup item can unlock it on this BIOS is unknown (no IFR).

## 5. Research (not executed): changing hidden settings on AMI Aptio / ASUS

From memory, not verified on this unit:
- Methods: (a) efivarfs write of the `Setup` GUID variable (kernel allows it on Linux, but it
  is a runtime-accessible NVRAM write, which is the risk; not done); (b) `setup_var` / `setup_var_4.x`
  from a UEFI shell or a GRUB module, which needs the exact offset and value from the IFR; (c) SREP or
  an AMIBCP-modded BIOS image (requires SPI flashing; out of scope and risky).
- Brick risks: writing a wrong value into a Setup-consumed field (power limits, C-state, PCIe) can make
  POST hang; the NVRAM copy is also checksummed in some AMI builds. Recovery usually means a CMOS clear;
  ASUS G16 CMOS-clear procedure is not confirmed here.
- Boot Guard / BIOS Guard: this board is a PFAT capsule. Flash writes are guarded by BIOS Guard and SPI lock
  (BIOS_CNTL BLE/BWP). Setup-variable edits do not need a flash write but still run through firmware.
- Undervolt feasibility on Meteor Lake: the 0x150 mailbox offset path depends on the OC lock and
  Intel's per-generation mailbox support. Meteor Lake support is doubtful. Treat it as not feasible
  without a BIOS-level unlock; this is a judgement, not a tested result.

## 6. Ranked opportunities (candidates; none verified against names)

| # | Candidate | Risk | Status |
|---|---|---|---|
| 1 | Decode the main AMITSE Setup IFR so every option below gets a name, offset and default | none (analysis only) | Blocked by the LZMA/PFAT issue in section 2 |
| 2 | Map the 11-byte `Setup` diff and the 75-byte `CpuSetup` diff to names | low | Depends on 1 |
| 3 | Find Setup items for C-state/package C-limit, C1E, ASPM per port (PEG/RP12, VMD NVMe), PEP, Modern Standby | medium (S0ix/power changes) | Unknown until 1 |
| 4 | Overclock/CFG lock state: MSR shows both locked. Any unlock is an OC change | high (CPU limits, brick) | Lock confirmed; no unlock path known |
| 5 | Undervolt via OC mailbox | high | Judged not feasible |

## 7. Open questions

1. Recover the full Setup IFR: unwrap the PFAT capsule (BIOSUtilities) or find the second copy of the
   AMITSE/Setup volume elsewhere in the image.
2. Confirm whether the 6.79 MB partial decode and the 7-Zip result differ in content after 6.79 MB (not checked).
3. Confirm the `Setup` 11-byte diff (0x002 100 -> 80 and 0x30 0 -> 9) against an IFR before reading meanings.
4. Verify MSR 0xE2 bit meanings against the SDM before claiming a C-state limit.

## Files

All of these are a local working copy, not in the repo.

- Image: `GU605MI.329`
- Dump: `GU605MI.329.dump/`, report `GU605MI.329.report.txt`
- Extracted IFR (partial) and NVAR table: `ifr.txt`
- Partial HII decode: `sec_big_partial.bin.*.en-US.uefi.ifr.txt`
- Current variable dumps: `efi/`
- Tools: `uefiextract` (UEFITool), `ifrextractor` (IFRExtractor-RS)
