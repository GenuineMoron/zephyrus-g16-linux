# 28: BIOS settings as shipped (from photos of the setup screens, 2026-11-15)

Read from photos of the ASUS BIOS (AMI Aptio, "Version 2.20.0049"). The BIOS image itself could not be decoded ([18](18-bios-hidden-settings.md)), so the photos are the inventory of the visible options. Serial numbers are omitted.

| Item | Value |
|---|---|
| BIOS / GOP / EC | 329 / 22.0.1031 / R3.27 |
| RTC | Keeps UTC (the BIOS clock shows UTC), which is correct for Linux. |
| Passwords | None set |

**Advanced**

| Option | Setting | Notes |
|---|---|---|
| ErP | Disabled | When enabled, cuts standby power to USB and other devices in the off/hibernated state. To test with night mode: hibernated drain with ErP off, then on |
| ArmouryCrate Control Interface Support | Enabled | The ACPI `ASUS9001` device ([22](22-ec-hotkeys-als.md)) |
| Hyper-Threading, VT-x, AES-NI, VT-d | Enabled | |
| Display Mode | Dynamic | The GPU MUX setting (hybrid with switching) |
| Auto-install app service mechanism | Toggle Off | ASUS's firmware-installed Armoury Crate helper is off |
| Active Performance-cores / Efficient-cores | All / All | |
| Submenus | Shipping mode, ASUS EZ Flash 3, Intel Rapid Storage Technology, SMART Settings, Network Stack Configuration, USB Configuration, Graphics Configuration, VMD setup menu, Animation Post Logo Configuration | Not photographed yet: Animation Post Logo, Graphics, USB, VMD, Network Stack |

**Boot:** Fast Boot **Enabled**. Boot order: cachyos, Windows Boot Manager, UEFI OS (the fallback `bootx64.efi`). There is **no CSM / legacy boot option**: Meteor Lake platforms are UEFI-only, so there is nothing to turn off. Network boot is off.

**Security:** I/O Interface Security and Secure Boot submenus (not photographed yet).

## What this means for boot time

The 6.2 s of firmware time ([19](19-boot-chain-fastboot.md)) is already **with** Fast Boot on. What is left to try:
- **The animated ROG POST logo** ("Animation Post Logo Configuration"): a likely candidate for a second or more.
- **VMD/RST:** stays. Its storage stalls are fixed by the patched `vmd` module, and turning VMD off would need a Windows safe-mode switch.
