# 19 - Boot chain and fast boot (wave 2 deep dive)

Read-only research, 2026-11-14, kernel 7.3.3-1-cachyos, BIOS GU605MI.329 (06/06/2025).
Sources: ACPI FPDT boot record (sysfs), systemd-analyze, journal (kernel + initrd + userspace),
efivars, /etc/default/grub, /boot/grub/grub.cfg (sudo read), mkinitcpio listing, unit files.
Web: three generic searches (lockdown/hibernate, GRUB shim_lock, ASUS Fast Boot).

## 1. Measured timeline (this boot)

FPDT boot record (ns since firmware reset-end, decoded from sysfs ASCII):

| Event | Time (s) |
|---|---|
| firmware_start (reset end) | 0.676 |
| bootloader_load (LoadImage GRUB) | 6.911 |
| bootloader_launch (StartImage GRUB) | 6.931 |
| ExitBootServices start | 9.969 |
| ExitBootServices end | 9.979 |

systemd-analyze: firmware 6.931 s + loader 3.047 s + kernel 0.448 s + initrd 2.089 s + userspace 4.156 s = 16.673 s. Graphical.target at 3.747 s userspace.

Consolidated timeline (firmware clock; 0 = reset end, power-button-to-reset not measured):

| Phase | Start-end (s) | Duration | Notes |
|---|---|---|---|
| Reset to firmware start | 0.00-0.68 | 0.68 | not in FPDT boot pointer; unmeasured remainder |
| Firmware POST/DXE/BDS | 0.68-6.91 | 6.23 | the dominant cost |
| LoadImage to StartImage | 6.91-6.93 | 0.02 | |
| GRUB | 6.93-9.97 | 3.04 | 1.0 s hidden timeout + about 2.0 s GRUB work |
| ExitBootServices | 9.97-9.98 | 0.01 | |
| Kernel (to initrd) | 9.98-10.43 | 0.45 | |
| Initrd | 10.43-12.52 | 2.09 | see section 4 |
| Userspace to greeter | 12.52-16.16 | 3.64 | greetd active at userspace 3.635 s |
| Userspace to graphical.target | 12.52-16.27 | 3.75 | |

Kernel-log clock (zero = kernel entry, about 9.98 on firmware clock): "Run /init" 0.545; vmd bound 0.716; NVMe probe 0.716-0.763; root partition found 0.894; initrd root device 0.910; hibernate-resume check 0.915 (no image, continues, 5 ms); sysroot.mount issued 1.518 (BTRFS mounted 1.531-1.539); i915 modules-load 0.86-2.396; switch-root 2.474. greetd started 6.174 kernel-clock (= 3.70 userspace). Greeter-to-login: the password is typed at kernel-clock 23.97, session open 24.11 (0.13 s; human time dominates).

Greeter path (userspace clock): greetd 3.635 gated by plymouth-quit-wait 3.536 (96 ms) <- systemd-user-sessions 3.530 <- network.target 3.528 <- wpa_supplicant 3.506 (started late; it is Before=network.target and After=dbus only). wpa_supplicant starts about 0.7 s after basic.target (2.83), which is the largest unexplained gap on the path to the greeter. ldconfig.service (216 ms) also sits on the chain to sysinit; it ran only because of today's package updates (ConditionNeedsUpdate), so it is not a steady-state cost.

graphical.target is 0.11 s after greetd. Its extra gates are tailscaled (239 ms, Wants from multi-user) and NetworkManager (670 ms). Those affect graphical.target, not the greeter.

Off-path units (blame, not gating greetd): boot-efi.mount 1.26 s (sits in local-fs.target, 5.07 kernel-clock; the mount waited on something after the fsck at 3.12; unexplained), dev-zram0.swap 0.21 s, a CIFS network-share automount 0.66 s (automount-triggered, not boot), ufw 0.71 s (started 1.15 s userspace, off-path), intel_lpmd 0.48 s, upower 0.40 s, g16-doctor 0.23 s, asusd 1.25 s, fwupd 2.67 s, grub-btrfs-snapper 2.05 s.

Notes on the blame entries:
- asusd: ExecStartPre=/bin/sleep 1, so 1 s of its 1.25 s is a hard-coded sleep. It is only wanted by asus-shutdown and the asus-nb-wmi device; nothing on the greeter path. Dropping the sleep is free.
- fwupd: greetd has After=fwupd.service, but the monotonic timestamp shows fwupd activated at 557 s (D-Bus activation later in the session), so it does not gate boot. Ignore it for the boot critical path.
- grub-btrfs-snapper: path-triggered oneshot (grub-btrfs-snapper.path), regenerates grub.cfg when snapshots change. It ran at 318 s in the journal (pacman snapshot), not at boot. Its blame figure is not a boot cost.

## 2. Firmware (ASUS / AMI Aptio, GU605MI.329)

- Firmware is 6.2 s from reset-end to LoadImage. That is long for a modern Intel laptop. Typical AMI-based Intel boards show about 2-4 s with fast boot, but I have no measured reference for this board, so the figure is not a claim about what Fast Boot would save here.
- efivars present: FastBootOption (its device path is the NVMe controller, so it records the last boot device, not the on/off state), LastBoot, LastBootFailed, Timeout, AsusSetupVariable, AsusSetupItemVariable, Setup, MemoryOverwriteRequestControl. The on/off state of Fast Boot is in the Setup variable at an ASUS-private offset I could not decode offline. Read it in the BIOS UI (Boot > Fast Boot) instead.
- BBS boot entries exist (CD/DVD, Removable, Network, BBS 129-131), plus a UEFI HTTP IPv4 network card entry. These imply legacy/CSM-era and network option ROM enumeration; disabling CSM and the network stack (PXE/HTTP boot) is a plausible firmware-time reduction. Unmeasured.
- Web search (ASUS support FAQ 1044641) confirms the UI path: Advanced Mode > Boot > Fast Boot > Disabled, save with F10. ASUS's own description on NUC models says Fast Boot skips network, optical and removable boot enumeration. No ASUS laptop seconds-figure was found; one anecdotal desktop report showed no difference. So any savings figure is an estimate.
- Measurement method: FPDT boot records (above) give firmware time exactly; toggle Fast Boot in BIOS, reboot, reread /sys/firmware/acpi/fpdt/boot/*. Two or three samples per state.
- Side effects of Fast Boot: slower or skipped USB keyboard init, which can cost F2/Esc/DEL access in the first seconds; boot-menu key F8 may need a different key; USB boot is skipped; Windows dual-boot unaffected (Boot0003 is a plain NVRAM entry). Reaching setup without the key: `systemctl reboot --firmware-setup` (systemd supports this; the firmware must advertise OsIndications bit, which systemd reports as "Boot into FW: supported" in bootctl status).
- Memory training: no MRC training-cache variable is visible in efivars, so cached training may not be in use. Unverified.

## 3. Loader

GRUB (current):
- Measured GRUB work: 3.04 s total, of which 1.0 s is the hidden GRUB_TIMEOUT=1. The remaining about 2.0 s is GRUB itself: gfx init (efi_gop, all_video, gfxterm, gfxmenu), font loads (unicode.pf2 is 2.4 MB, plus terminus and ubuntu pf2), theme PNG (background.png 166 KB), and reading vmlinuz (17.5 MB) plus initramfs (25.8 MB) through GRUB's btrfs driver. The split is an estimate; no GRUB timing tracing was done (would need a boot with debug output).
- grub.cfg is root-only (mode 0600), so the menu structure was read with sudo. It contains a 42_fallback_no_aspm custom entry, a snapshot submenu and LTS entries.
- GRUB_DISABLE_BOOTNEXT=true, and the Restart-into-Windows action uses grub-reboot.

Options:
1. GRUB with GRUB_TIMEOUT=0 (hidden style kept). Saves about 1.0 s. Menu via ESC is lost, but grub-reboot still works (it sets the next-boot entry in grubenv, honored even with timeout 0). Lowest risk, fastest single win.
2. GRUB removed from the path: UKI on the ESP (\EFI\Linux\cachyos-<kver>.efi, built by ukify or mkinitcpio's uki preset), registered directly in NVRAM with efibootmgr pointing at the UKI (EFI stub is enabled: CONFIG_EFI_STUB=y). Firmware loads it directly: no GRUB, no font/theme work, no 1 s timeout. Expected loader time: about 0.1-0.3 s (UKI PE load of about 45 MB plus stub) instead of 3.05 s. Savings about 2.7-2.9 s.
   - Windows: keep Boot0003 in BootOrder; firmware boot menu still shows Windows Boot Manager.
   - Restart into Windows: `efibootmgr --bootnext 0003` plus `systemctl reboot`. Needs a root helper or polkit rule (the current grub-reboot path is also root). Do not change now.
   - Hibernate resume: resume=UUID=... resume_offset=... goes into the UKI's cmdline section (or the stub cmdline via efibootmgr -u). Unchanged.
   - Snapshot rollback: one UKI per snapshot (ukify with --cmdline and the snapshot subvol as rootflags) written to the ESP on each pacman/snapper event; the firmware boot menu or a systemd-boot entry selects them. grub-btrfs has no equivalent, so this is new work. The UKI-per-kernel + fallback UKI covers the common case.
   - Risk: no interactive menu, so a broken UKI means a firmware-menu boot to Windows or another Boot entry. Keep the GRUB binary as Boot0000 fallback until the UKI path is proven.
3. systemd-boot + UKI: adds a menu and Type-1/Type-2 entries with boot counting. Costs about 0.1-0.2 s more than direct NVRAM UKI. Better for snapshot entries. It supports `bootctl set-oneshot` for Restart-into-Windows (loader one-shot), which is cleaner than efibootmgr. Note: bootctl status currently reports "Failed to read /boot/efi/EFI/systemd" because /boot/efi is root-only; that is expected for an unprivileged read.

Expected design: systemd-boot with a hidden menu and timeout 0, UKIs for the default kernel plus one per snapshot, Windows as a firmware entry. Loader time about 0.3 s (saves about 2.7 s).

## 4. Initramfs

Current image: 25.8 MB file (initramfs-linux-cachyos.img). mkinitcpio listing: early CPIO (microcode) 6.58 MiB uncompressed, main 18.01 MiB zstd (54.8 MiB uncompressed, estimated decompression 0.09 s). Hooks: base systemd autodetect microcode kms modconf block keyboard sd-vconsole plymouth filesystems. MODULES=(vmd). Explicit modules: i915 (plus about 33 autodetected: nvme, nvme-core, nvme-auth, nvme-keyring, rtsx_pci, uas, usb-storage, virtio_scsi, mmc_block, intel-lpss, idma64, dw_dmac, spi-intel, asus-wmi, hid-asus, hid-multitouch, drm_buddy, ttm, video, wmi, serio_raw and others). No NVIDIA modules in the initramfs (good).

Critical path inside the initramfs:
- 0.55-0.91: vmd bind, NVMe, root found (0.36 s). vmd is required (RST/VMD remaps NVMe); must stay early.
- 0.91-1.52: 0.6 s unexplained gap between initrd root device and sysroot.mount. Candidates: plymouth start ordering, udev settle, or systemd waiting on a device. Not diagnosable from the existing journal (rd.udev.log_level=3 hides it). Needs a one-off debug boot (systemd.log_level=debug) to confirm.
- 0.86-2.40: systemd-modules-load runs `modprobe i915` synchronously. i915 probe itself: DMC 0.935, GuC 0.956-0.995, GSC 1.135, HuC 1.156, then a silent 1.2 s until "Initialized i915" at 2.388 (display/AUX/eDP probe, unlogged). This 1.5 s is serial on the critical path to Initrd Default Target, because the initramfs waits for modules-load. This is the single largest initrd cost.

Opportunities:
- Drop i915 from the initramfs (MODULES/kms-hook list) and let udev load it in the real root. Saves up to about 1.5 s from initrd. Cost: plymouth splash starts later (it needs KMS), and the splash will not show until i915 binds in the real root. Net effect on the greeter: positive, since i915 would load in parallel with other userspace work. Risk: plymouth in the real root needs i915 to be ready for the splash handoff; test.
- Alternative if the splash must stay: keep i915 early but load it asynchronously (a modules-load drop-in is not possible; use udev rule with modprobe --async or remove from the early list and rely on the kms-hook). Same effect; verify plymouth still hands off cleanly.
- Compression: zstd (current) decompresses in about 0.09 s estimated. lz4 would save about 0.05 s and cost about 6 MB more; not worth it. Keep zstd (level default).
- Microcode: 6.58 MiB uncompressed cpio; trivial time. Keep.
- Plymouth: about 0.3 s in userspace (plymouth-start 98 ms, plymouth-read-write 176 ms, quit 96 ms, quit-wait 96 ms). Plymouth is needed for the splash; cannot be dropped without losing the slick boot.
- systemd initrd vs busybox: systemd hook is correct here (switch-root and resume integrate). Keep.
- Resume path: systemd-hibernate-resume costs 5 ms when no image is present; keep resume= on the cmdline (required for the swapfile path).
- Initramfs size: no meaningful effect on time, since decompression is about 0.09 s. Dropping unused modules (usb-storage, uas, virtio_scsi, mmc_block, rtsx_pci) saves little time but reduces attack surface and cleans the image.

## 5. Userspace priorities (for the greeter, not graphical.target)

- Greeter gate chain: wpa_supplicant (late start, ~0.7 s after basic.target) -> network.target -> systemd-user-sessions -> plymouth-quit-wait -> greetd. Investigate why wpa_supplicant starts late (its ordering is only After=dbus; it may be waiting on the wifi device or on rfkill). Possible saving up to about 0.5 s if the wait is removable. Cheap test: systemd-analyze critical-chain wpa_supplicant.service on the next boot.
- Do not defer tailscaled and NetworkManager for the greeter, they are not on that path. They only delay graphical.target (0.11 s).
- asusd: drop ExecStartPre=/bin/sleep 1 (1 s saved on its own timeline; not on greeter path).
- ufw, intel_lpmd, upower, g16-doctor: off-path; cosmetic only.
- boot-efi.mount: 1.26 s in local-fs.target; /boot/efi is only needed for bootctl/grub updates. Making it x-systemd.automount (or noauto) removes it from boot. Off-path for the greeter today, but it does sit in local-fs.target.
- zram swap: 0.21 s, off-path.
- grub-btrfs-snapper: runs on snapshot events only; no boot cost.

## 6. Secure Boot

Current state: SecureBoot=0 (efivar), SetupMode=0 (user mode, PK/KEK/db/dbx enrolled, so Microsoft keys present). Kernel: CONFIG_MODULE_SIG=y, MODULE_SIG_FORCE not set, CONFIG_SECURITY_LOCKDOWN_LSM=y, CONFIG_INTEGRITY_PLATFORM_KEYRING=y, CONFIG_LOAD_UEFI_KEYS=y, CONFIG_EFI_STUB=y.

Findings:
- vmd (out-of-tree DKMS, signer "DKMS module signing key") is currently loaded unsigned-trusted: the kernel logs "module verification failed ... tainting kernel". With SB on, lockdown integrity forces signature verification. vmd is in the initramfs and is needed for the NVMe root. If the module is not trusted, the root device disappears and the system does not boot. NVIDIA modules (signer "Build time autogenerated kernel key", i.e. the kernel's ephemeral key) have the same problem for the dGPU path.
- Kernel lockdown under SB blocks hibernation. Web search confirms distros (Ubuntu, Fedora, Debian) turn lockdown on with SB and that hibernation is then restricted with no option to change it. This project depends on hibernate (swapfile resume), so enabling SB is a direct functional regression unless the hibernate restriction is lifted (not found upstream).
- GRUB without shim: with SB on, GRUB's shim_lock verifier is required for the `linux` command and it blocks unsigned files (fonts were a reported trigger). Enabling SB here means either shim + MOK (adds MOK enrollment) or moving to systemd-boot/UKI or direct UKI (which needs no shim_lock).
- Practical path if desired: own sbctl keys (clear PK in BIOS to enter setup mode, enroll with -m to keep Microsoft db/KEK so Windows still boots), sign UKIs and GRUB/systemd-boot, sign vmd and nvidia DKMS modules with the sbctl key and confirm the kernel trusts it (CONFIG_INTEGRITY_PLATFORM_KEYRING is set, but whether module verification consults the platform keyring on 7.3 is not verified here). Each step needs a test boot with a fallback.
- Security benefit: boot-chain integrity against offline tampering; no direct benefit to the laptop's daily threat model. Cost: hibernate lost while lockdown is in effect. Recommendation: leave SB off for now, or revisit after hibernate is confirmed working under lockdown.

## 7. Recommended "fastest slick boot" design

Ordered by expected greeter-time saving:

| Change | Expected saving | Risk |
|---|---|---|
| Replace GRUB with direct UKI (or systemd-boot + UKI), keep Windows firmware entry, per-snapshot UKIs | about 2.7-2.9 s (GRUB 3.04 s to about 0.3 s) | medium: needs new snapshot/restart tooling; keep GRUB as fallback until proven |
| Remove i915 from early initramfs (let udev load it in the real root) | up to about 1.5 s on initrd | medium: plymouth splash starts later; test handoff |
| Firmware: disable CSM/network boot, re-test Fast Boot, measure via FPDT | unknown; plausibly 1-3 s, to be measured | low-medium: F2/Esc/USB keyboard access during Fast Boot |
| Investigate wpa_supplicant late start and the 0.6 s initrd sysroot gap | up to about 0.5 s each | low (diagnosis first) |
| asusd sleep removal, boot-efi.mount automount | 1 s off asusd timeline; 1.26 s off local-fs chain | low |

Expected result after items 1-2 with firmware unchanged: firmware 6.9 s + loader about 0.3 s + kernel 0.45 s + initrd about 0.6-0.9 s + userspace to greeter about 3.0-3.6 s, so the greeter appears at roughly 11-12 s instead of 16.2 s (about 4-5 s saved). Firmware reduction would be additional and is the biggest unknown.

## 8. Open questions

1. Exact Fast Boot state and its Setup offset: read in BIOS UI (Boot > Fast Boot). Measure FPDT with it on and off.
2. What the 0.6 s initrd gap (0.92-1.52 s) and the silent i915 1.2 s gap (1.19-2.38 s) are; need one debug boot with systemd.log_level=debug and rd.debug (one-off via grub-reboot, not a permanent change).
3. boot-efi.mount 1.26 s: which dependency it waits on after fsck.
4. Whether module verification under SB consults the platform keyring on this kernel (for vmd/nvidia signing).
5. Whether hibernate can be made to work under integrity lockdown (not found upstream).
6. GRUB internal split (font loads vs btrfs reads); only measurable with GRUB debug timing.
7. Reset-to-firmware-start 0.68 s and power-button-to-reset: not captured by FPDT; would need an external measurement.
