# 14 - Health, logs, security audit (2026-11-14)

Read-only audit. Kernel 7.3.3-1-cachyos. Boots inspected: current (0), -1, -2, plus the 19-second boot -3 for context.

## 0. Volume summary

| Boot | Window (local time) | Warnings (`-p warning`) | Dominant source |
|---|---|---|---|
| -2 | 11:49 - 12:32 | 903 | intel_lpmd (608), UFW (34), ACPI/NVRM |
| -1 | 12:32 - 17:59 | 5636 | intel_lpmd (4522), UFW (~187), kernel |
| 0 (current, ~1h20m) | 17:59 - now | 290 | UFW, kernel one-offs, zenity/GTK theme |
| -3 | 11:49:06 - 11:49:19 | n/a | tailscaled stop timeout (SIGKILL) during a fast reboot |

Journal size on disk: 44.9 MB (active plus archived). No journald.conf overrides exist, so defaults apply.

Largest per-unit volume in boot 0 (all priorities): kernel 2859 lines, systemd 905, noctalia 473, bash 360, tailscaled 304, sudo 261, NetworkManager 240, xwayland-satellite 235, bluetoothd 157, asusd 144, niri 84, tailscale-mounts-healthcheck 75.

Per-unit bytes in boot 0: kernel 2.0 MiB, user@1000 (desktop session) 1.7 MiB, init.scope 0.7 MiB, grub-btrfs-snapper 0.36 MiB (its regen prints the snapshot menu each run), tailscaled 0.33 MiB.

Failed units: none (system or user). Timers: 14 listed, all sane. The only fast-running one is the Tailscale mount healthcheck (see P1-3).

## 1. Pattern-by-pattern log audit

Counts are for boot -1 / boot -2 / boot 0 unless stated.

### A. intel_lpmd "read_aperf_mperf_tsc_perf failed for cpu = N" (the big one)
- Count: 4522 / 608 / 0.
- Source: `intel_lpmd` (Intel Low Power Mode daemon, enabled but its preset is disabled; running with `--systemd --dbus-enable`). Config dir `/etc/intel_lpmd/`, active file `intel_lpmd_config_F6_M170*`.
- Meaning: lpmd samples APERF/MPERF per logical CPU and fails the read on some CPUs. Failures hit CPUs 1-19 across boot -1 (one line per CPU per cycle, about 19 lines per cycle, roughly every 30 s, not "every minute").
- Severity: papercut. No functional symptom seen, but it is pure journal spam and the cause is unknown.
- Correlation (strong, 3 of 3 boots): the lpmd spam tracks hibernation attempts, not uptime.
  - Boot -2: 3 "PM: hibernation: hibernation entry" events, 608 lpmd lines.
  - Boot -1: 5 hibernation entries plus one `cs35l56-hda ... Hibernate wake failed: -5`, 4522 lpmd lines (first failure 12:39, about 5 min after the 12:34 hibernation entry).
  - Boot 0: 0 hibernation entries, 0 lpmd lines (only the startup banner).
  - Hypothesis: after the hibernate/resume path (the suspend-then-hibernate design), APERF/MPERF reads on some CPUs stop working until reboot. Unverified; no upstream report checked.
- Fix options, in order:
  1. Evaluate whether lpmd is needed at all. Power is already managed by asusd / platform_profile (power-profiles-daemon is masked, but `platform_profile` reads `balanced`). If it adds nothing, `systemctl disable --now intel_lpmd`. This is a state change, so it is not done here.
  2. If kept, reboot after hibernate-cycle testing and watch whether the spam returns. Consider reporting upstream (intel-lpmd project) with the hibernate correlation.

### B. "[UFW BLOCK] ..." (kernel, from iptables LOG at warning level)
- Count: 187 in boot -1, 34 in boot -2, 197 in boot 0.
- Source: ufw logging (`Logging: on (low)`) on the Wi-Fi interface.
- Breakdown in boot -1: 111 are to 224.0.0.1 (all-hosts multicast, mostly IGMP). The rest are inbound UDP to random high ports and TCP SYN probes, mostly from one LAN peer.
- Severity: harmless, but it is the main journal noise and it lands at warning level, which is why it dominates `-p warning`.
- Fix: `sudo ufw logging off` (silences all) or keep logging and filter it in journald/rsyslog. Inbound is correctly denied (see security). Silencing is the simplest; it is a state change, so not done here.

### C. "ACPI BIOS Error (bug): Could not resolve symbol [\_SB.PCN.RPN.PXSX._DSM.MHYB], AE_NOT_FOUND" and "ACPI Error: Aborting method \_SB.PCN.RPN.PXSX._DSM"
- Count (MHYB symbol message): 6 / 10 / 0. Total PXSX-related lines: 14 / 22 / 2.
- Source: ASUS firmware (DSM method on a PCIe root port, RP12 in the ACPI namespace).
- Severity: harmless firmware bug. The kernel skips the method and continues.
- Fix: none in userspace. Check for a newer BIOS via fwupd (the BIOS in use is GU605MI.329, 2025-06-06). Do not silence.

### D. "NVRM: osCallACPI_DSM ... Error during ... DSM subfunction ..." and "PlatformRequestHandler failed to get platform power mode / target temp from SBIOS" and "pfmreqhndlrCallACPI: Unable to retrieve PFM_REQ_HNDLR_PSHAREPARAMS"
- Count: osCallACPI_DSM 10 / 0 (boot -2 / boot 0 respectively; boot -1 had 6). The PlatformRequestHandler assertion lines appear in boots -2 and -1 only.
- Source: NVIDIA open kernel module (driver 7.3.x series, nvidia-open) asking the ASUS SBIOS for power / thermal platform data that this firmware does not implement.
- Severity: harmless to cosmetic. The GPU works. Its dynamic power management (RTD3) is a separate concern covered in 04-nvidia-power.md.
- Fix: none in userspace. Silence only if it becomes a nuisance, via a driver/firmware update. Note: `NVreg_DynamicPowerManagement=0x02` is set on the cmdline, which matches the RTD3 notes.

### E. "tpm_crb_acpi MSFT0101:00: Ignoring error -5 while suspending"
- Count: 7 / 2 / 0 (boot 0 has 12 tpm_crb lines in total, most are not this message).
- Source: TPM CRB driver during suspend, device returns -5 (EIO).
- Severity: harmless. The driver explicitly ignores it and suspend proceeds. The TPM is present and functional (`/dev/tpm0`, TPM 2.0, see security).
- Fix: none needed. Silence would require a driver change. Leave it.

### F. "ACPI Error: No installed handler for fixed event - PowerButton (2), disabling"
- Count: 1 in boot -1 (17:53:30), 0 elsewhere.
- Source: ACPI core (kernel `evevent`) after the firmware's power-button fixed event is hit with no handler, so the kernel disables it.
- Severity: papercut, not a current failure. The button still works: systemd-logind logged "Power key pressed short" at 17:59:08 after a suspend cycle, because logind reads the input device, not the ACPI fixed event.
- Open question: confirm that the power button still powers off and suspends from a cold state. The message appeared right before a suspend at 17:53.

### G. "NetworkManager: device (p2p-dev-wlo1): error setting IPv4 forwarding to '0': Resource temporarily unavailable" (also "...: Success")
- Count: 12 + 5 in boot -1, 2 in boot -2, 3 in boot 0 (some lines are the duplicate "Success" wording).
- Source: NetworkManager trying to write `ip_forward` for the Wi-Fi Direct (P2P) virtual device, which has no such sysctl.
- Severity: harmless. Pure noise from the P2P device NM creates.
- Fix: silence by setting NM to not manage P2P devices, or accept. Low priority.

### H. Bluetooth (hci0)
- "Bluetooth: hci0: Opcode 0x... failed: -N" and "unexpected event for opcode 0x...": 1 to 3 per boot.
- "bluetoothd: Failed to remove UUID: Failed (0x...)" (3 in boot 0).
- "wireplumber: spa.bluez.midi: org.bluez.GattManager1.RegisterApplication() failed: AlreadyExists" (5 in boot -1).
- "bluetoothd: a security policy denied ... org.bluez.GattProfile1.Release" (3 in boot -2).
- Severity: papercut. Typical of a BLE controller reacting to re-registration (WirePlumber's BlueZ MIDI GATT app being re-registered on each session start) and a stale profile. Audio and pairing work.
- Fix: if MIDI-over-BLE is not used, disable the WirePlumber bluez-midi monitor. Otherwise accept.

### I. niri "DRM node ... is not a render node"
- Count: 7 in boot 0 (only at session start / reconfig times 18:00-18:26), 13 in boot -1.
- Source: niri, tty backend, probing `/dev/dri/by-path/pci-0000:01:00.0-card` (the NVIDIA dGPU). The config `~/.config/niri/cfg/misc.kdl` already sets `render-drm-device` to the iGPU and `ignore-drm-device` for the dGPU card node.
- Severity: harmless. The warning is niri's probe on the device it is told to ignore.
- Fix: silence is not needed. Possible cleanup: ignore the dGPU by its render node too, if niri supports it.

### J. "Theme parser error: gtk-dark.css:... Expected color stop/number" (zenity, nautilus, xdg-desktop-portal-gnome)
- Count: about 10 across boots. "gtk.css" variant appears once or twice.
- Source: the WhiteSur GTK theme's CSS being parsed by GTK 4 / libadwaita-era parsers (theme is AUR `whitesur-gtk-theme 2025.04.03`).
- Severity: papercut. Cosmetic: some gradient colors fall back to defaults in these apps.
- Fix: either update/replace the theme, or accept. Also "zenity: The new GL renderer has been renamed to gl" is harmless (set `GSK_RENDERER=gl` to silence).

### K. NVIDIA / kernel, hardware one-offs (each 1-4 times per boot)
- "pcieport ...: Primary bus is hard wired to 0" (boot -1: 6, boot -2: 6, boot 0: 6 across cards). Harmless topology note.
- "pcieport ...: can't derive routing for PCI INT A/C", "PCI INT C: no GSI", "nvme ...: PCI INT A: no GSI". Harmless legacy IRQ routing noise, because MSI-X is used.
- "intel_pmc_core: Invalid LTR scale factor". Firmware quirk, harmless.
- "hpet_acpi_probe: no address or irqs in _CRS". Harmless, HPET is not used.
- "wmi_bus ...: [Firmware Bug]: WQN data block query control method not found". Harmless firmware bug.
- "iwlwifi: BIOS contains WGDS but no WRDS". Harmless, regulatory table fallback.
- "spi-nor spi0.0: supply vcc not found, using dummy regulator". Harmless.
- "i8042: PNP: PS/2 appears to have AUX port disabled". Harmless (no PS/2 mouse on this machine).
- "virt/tdx: TDX not supported by the host platform". Harmless.
- "block nvme0n1: No UUID available providing old NGUID". Harmless.
- "caller igen6_edac ... mapping multiple BARs". Harmless, EDAC driver quirk.
- "ENERGY_PERF_BIAS: Set to 'normal', was 'performance'" (17:59:36, boot 0). Written at boot by a tuning service (likely ananicy/asusd). Harmless but worth knowing which unit writes it, if the profile is intended to stay 'performance'.
- "ucsi_acpi USBC000:00: UCSI_GET_PDOS failed (-70)" and "failed to re-enable notifications (-5)" (boot -2, around 11:49-11:53). USB-C PD negotiation failure at boot. Papercut. Watch whether USB-C power negotiation (charging over USB-C) is affected.
- "usb 3-8/3-10: WARN: invalid context state for evaluate context command" (12 in boot -1, 9 in boot -2). Harmless xHCI noise during port enumeration/resume.
- "BTRFS warning: block groups with swapfile extents will not be scrubbed or balanced". Real but benign: the 32 GB `/swap/swapfile` on btrfs is excluded from scrub and balance. Accept, or move swap to a non-btrfs partition or a dedicated subvolume.
- "wpa_supplicant: nl80211: kernel reports: multicast RX registrations are not supported" and "PKCS#11 provider not present". Harmless.
- "warning: kdeconnectd uses wireless extensions which will stop working..." Harmless deprecation warning from the KDE Connect daemon.
- "vmd: loading out-of-tree module taints kernel." Expected: this is the project's `vmd-mtl016` DKMS module (see maintenance).
- "CIFS: VFS: \\...\<share> Close interrupted / cancelled mid failed rc:-..." (one each, boot 0). Interrupted close on a CIFS network mount, possibly when the healthcheck lazy-unmounts or remounts it. Papercut, relates to P1-3.
- "systemd-journald: File ... corrupted or uncleanly shut down, renaming and replacing: Device or resource busy" (once). Harmless, a journal from an unclean shutdown was rotated.
- "greetd: gkr-pam: unable to locate daemon control file", "accounts-daemon: Unable to open /etc/tcb", "dbus-broker-launch: Activation request for 'org.freedesktop.home1' failed", "couldn't list homed users". Harmless: no systemd-homed on this system.
- "xdg-desktop-portal: Inhibiting other than idle not supported" and "xwayland-satellite: No last focused toplevel, cannot focus window" (3 times). Harmless, sessions that cannot inhibit a non-idle reason or focus stale windows.
- "tracker indexer unit failed" (nautilus). Harmless. Tracker miner is not running. Silence by disabling the miner if unused.
- Spotify: "libayatana-appindicator is deprecated". Harmless.

### L. Serious kernel events (checked, not just the warning list)
- Boot -2, 12:27:44: `Oops: invalid opcode ... RIP: do_kernel_cp_fault` (a control-protection fault, CET-style) while the process `insmod` loaded an out-of-tree, UNSIGNED module (`Tainted: O E`). Caused by a manual `insmod` of an unsigned test module, most likely a dev/testing action on the project tree. It was not a boot-time or idle failure. Do not `insmod` unsigned modules on the production kernel; test in a VM or with signed modules.
- Boot -1, 14:46:55 and 15:01:20 (and 15:01:55 Call Trace): `page allocation failure: order:0, mode:0xc0de0(GFP_KERNEL|...|__GFP_NOMEMALLOC)`, triggered by `systemd-sleep` at 14:46 and `python3` at 15:01. Stack: `isolate_lock_cluster` / `cluster_alloc_swap_entry` (swap-entry allocation on the btrfs swapfile). Context: hibernation entries at 14:28 and 14:39 precede these; the 14:46 failure is inside systemd-sleep during the hibernate path. Free memory was ~18 GiB, so this is not a real OOM. It is the swap-cluster allocator failing under the hibernate path with `__GFP_NOMEMALLOC`. Hibernate image size is 13.1 GB (`/sys/power/image_size`). Real but rare; relates to the s2h design. Track it with the hibernate work.
- Boot -1 hibernate: "cs35l56-hda ...: Hibernate wake failed: -5" at 12:46:08 (one of two speaker amps). Relates to the earlier hibernate power-off hang fix (see ../findings/01-hibernate-hang-cs35l56.md, cs35l56 hook). Real. Confirm the `30-cs35l56-hibernate` hook still runs on each hibernate.
- Boot -1, 17:53 to 17:59: several suspend/resume cycles plus a hibernation entry at 17:59:08 (before the boot ended). Check before retesting; not a fault.
- pstore: `efi_pstore` dumps from earlier panics were archived at boot -1 start (`/var/lib/systemd/pstore/`, 6 dirs). They match the boot -2 Oops window. Review or delete after reading; they are only copies of dmesg.

### M. Tailscale and the desktop session (benign but worth watching)
- tailscaled: 304 lines in boot 0, almost all info-level magicsock / netcheck / DERP lines. Harmless. Boot -3 ended with `tailscaled.service: Failed with result 'timeout'` (SIGKILL on stop) during a 19-second boot: a stop-timeout on shutdown. Papercut. Check `TimeoutStopSec` if it recurs.
- noctalia.service: SIGKILL (status=9) at 18:11:31 and 18:13:03. Not an OOM (no OOM lines found). Likely a manual or scripted restart. Open question, see section 7, Q2.
- `run-p*-i*.service` exit-code failures at 18:50 and 19:04. Transient `systemd-run` units (probably pacman/automation). Harmless.
- sudo: 261 lines in boot 0, 97 root sessions by the login user, most from automated read-only audit commands (`COMMAND=/usr/bin/dmesg`, `cat /sys/kernel/debug/...`). They also flood the journal.

## 2. Failed and flapping units, timers

- Failed units: none. `systemctl --failed` and `--user --failed` both empty.
- **tailscale-mounts-healthcheck.timer**: `OnBootSec=30s`, `OnUnitActiveSec=2min`. Runs every 2 minutes (confirmed: boot -1 shows runs roughly every 2 min, about 37 runs in boot 0 alone). Each run `stat`s three remote mounts (two sshfs, one CIFS) with 5-10 s timeouts. That keeps the network and the remote hosts busy, and produces ~333 lines per boot.
  - The automounts (`mnt-*.automount`) already trigger on access. The timer is redundant for the common case and adds a recurring probe.
  - Also, the script force-unmounts (`umount -l` for CIFS, `fusermount3 -uz` for sshfs) when a mount is "unresponsive". That is aggressive and may contribute to the CIFS "close interrupted" messages.
  - Fix: raise `OnUnitActiveSec` to 10-15 min, or remove the timer and rely on automount idle timeouts (`x-systemd.idle-timeout=`). Make the forced-unmount path opt-in.
- **health-check (g16-doctor).timer** (custom): `OnBootSec=5min` plus the pacman hook `99-g16-doctor.hook` (on linux-cachyos, nvidia, vmd, mkinitcpio). Runs once, exit 0, 0.26 s wall. Fine.
- **snapper-timeline.timer** (hourly) and **snapper-cleanup.timer**: enabled, normal.
- **fstrim.timer**, **paccache.timer**, **btrfs-scrub@-.timer** (monthly): enabled, normal.
- **shadow.timer**, **plocate-updatedb**, **logrotate**, **man-db**, **systemd-tmpfiles-clean**, **archlinux-keyring-wkd-sync**, **cachyos-rate-mirrors**: normal. `cachyos-rate-mirrors` runs weekly and touches mirrorlists; leave it.
- Pointless on this machine (candidates, not changed):
  - `avahi-daemon` (mDNS on all interfaces, 42 lines per boot): disable if no printer or `.local` discovery is needed.
  - `intel_lpmd` (see 1-A): enabled with a disabled preset, redundant with asusd/platform_profile.
  - `kdeconnectd` (listens on TCP and UDP 1716 on all interfaces, blocked by ufw default-deny): fine if unused, or disable.
  - `tracker-miner-fs` (Nautilus indexer unit fails): disable if not wanted.
  - `bpftune` (listens on loopback only): harmless, keep if desired.

## 3. Security posture

- Secure Boot: **disabled**. `bootctl status` reports "Secure Boot: disabled (unknown)". EFI variable `SecureBoot` = 0, `SetupMode` = 0. `mokutil` and `sbctl` are **not installed**, so no key-enrollment tooling is available. Both kernel and modules are unsigned in effect (`vmd-mtl016` DKMS, `OOT_MODULE, UNSIGNED_MODULE` taint).
- TPM: present and TPM 2.0 (`/dev/tpm0`, `/dev/tpmrm0`, `tpm_version_major` = 2). fwupd HSI-1 "TPM v2.0: Found", "TPM PCR0 reconstruction: Valid".
- Kernel lockdown: `none` (`/sys/kernel/security/lockdown` = `[none] integrity confidentiality`).
- fwupd HSI (`fwupdmgr security --force`, HSI:1!, v2.1.9): all HSI-1 items Enabled/Valid/Locked (BIOS updates enabled, SPI write/lock/BIOS region locked, platform debugging disabled, TPM found). HSI-2: BootGuard enabled and valid, ACM protected, IOMMU enabled, Intel GDS mitigation enabled. Two "Locked MTD: Not supported" (expected on this platform, not a problem).
- Firewall (ufw): **active**, `Default: deny (incoming), allow (outgoing), disabled (routed)`, `IPV6=yes`. **No user rules** (`/etc/ufw/user.rules` has an empty RULES section). Inbound is denied everywhere, including the Tailscale UDP port (direct paths use outbound NAT traversal, so this works in practice). Logging on (low), which causes the UFW BLOCK spam.
- Listening sockets (`ss -tulpn`):
  - `systemd-resolved` on 127.0.0.53 and 127.0.0.54 (loopback, tcp and udp 53). Fine.
  - `avahi-daemon` udp 5353 on all interfaces (mDNS). Information exposure on the LAN, not a remote risk while ufw denies inbound. Disable if unused.
  - `tailscaled` udp 41641 (all interfaces) and tcp on the tailscale0 address. Normal.
  - `kdeconnectd` tcp and udp 1716 on all interfaces. ufw has an app profile for KDE Connect, but no rule enables it, so phone pairing is blocked. If KDE Connect is used, add a ufw rule only on the LAN interface.
  - `bpftune` tcp 127.0.0.1 (ephemeral). Loopback only.
  - A development tool's local listener on 127.0.0.1 (ephemeral port). Loopback only, expected.
  - NetworkManager dhcpv6-client on link-local udp 546. Normal.
- SSH server: `sshd` **disabled and inactive**. Good.
- sudoers:
  - Keep sudo NOPASSWD rules narrow (one command each); avoid blanket NOPASSWD drop-ins.
  - `/etc/sudoers.d/50-reboot-to-windows` (0440): NOPASSWD for one command, `/usr/local/bin/reboot-to-windows`. Narrow and intended.
  - `/etc/sudoers.d/10-installer` (0440, root-only read): not inspected for content (no NOPASSWD lines found via `sudo grep`). Worth a look.
  - `/etc/sudoers`: the only NOPASSWD mention is commented out (`# %wheel ... NOPASSWD`). Fine.

## 4. Update and maintenance hygiene

- Pacman hooks: `/etc/pacman.d/hooks/` contains only `99-g16-doctor.hook` (custom; runs `health-check (g16-doctor) --after-update` after linux-cachyos, nvidia, vmd-mtl016-dkms, mkinitcpio). `/usr/share/libalpm/hooks/` has the standard set, including `grub.hook`, `70-dkms-install`/`upgrade`/`remove`, `90-mkinitcpio-install`, `cachyos-reboot-required`, and `snap-pac` pre/post. Good.
- Snapper (root only): TIMELINE_CREATE=yes, LIMIT_HOURLY=10, DAILY=7, WEEKLY=4, MONTHLY=2, YEARLY=0, NUMBER_LIMIT=50 (important 15). Cleanup enabled. The grub-btrfs regeneration logs in boot 0 (six runs) list snapshot entries in the GRUB submenu; the exact number of entries in the menu was not counted. Reasonable; the GRUB menu will be long.
- grub-btrfs: `grub-btrfs-snapper.service` is static and regenerates the menu on each snapshot (it is why grub-btrfs-snapper uses 362 KiB of journal per boot). `grub-btrfsd` is disabled, which is fine.
- DKMS: `vmd-mtl016/7.3.1` built for 7.3.3-1-cachyos (installed, "Original modules exist"). `hid-xpadneo/v0.10.5` built for both 7.3.3-1-cachyos and 6.18.60-2-cachyos-lts. Both current. The vmd module is out-of-tree and taints the kernel (expected); the hook above rebuilds it on each kernel update.
- Orphaned packages (`pacman -Qdtq`): **0**.
- .pacnew files under /etc: **none**.
- AUR and foreign packages (`pacman -Qm`, 16): asusctltray-upgraded-git, davinci-resolve-studio, game-devices-udev, kora-icon-theme, noctalia-git, noctalia-greeter-git, python-uinput, supergfxctl, vmd-mtl016-dkms, whitesur-gtk-theme, whitesur-icon-theme, plus other user apps. Git-tracking AUR packages (noctalia-git, noctalia-greeter-git, asusctltray-upgraded-git) will drift; expect rebuilds.
- paccache.timer: enabled (cache pruning). fstrim.timer: enabled. btrfs-scrub monthly: enabled.
- Kernel and boot: current kernel 7.3.3-1-cachyos. Earlier notes were written against 7.3.0-4; the system is on 7.3.3, so the vmd and nvidia fixes need re-checking against this version.

## 5. Prioritized fix list

**P1 - real issues to act on**
1. **Hibernate path reliability** (boots -2 and -1): `cs35l56-hda Hibernate wake failed: -5`, 3 and 5 hibernation entries, and `page allocation failure ... cluster_alloc_swap_entry` under the hibernate writes. Confirm the `30-cs35l56-hibernate` hook is still applied. Consider reducing the hibernate image size or moving swap off btrfs. Track with the hibernate work (../findings/01-hibernate-hang-cs35l56.md).
2. **Keep sudo NOPASSWD narrow.**
3. **Stop the 2-minute healthcheck timer** (or lengthen to 10-15 min). It is the only recurring probe that touches remote hosts and it force-unmounts on "unresponsive". Make the forced unmount opt-in.
4. **Decide on intel_lpmd**: disable it (it duplicates asusd/platform_profile and its spam tracks hibernation) or keep it and report upstream. Expected to remove about 4500 warnings per session.

**P2 - papercuts**
5. Turn off UFW logging, or filter it (`ufw logging off`). It produces ~200 warning-level lines per session and 111 of them are IGMP to 224.0.0.1.
6. Disable `avahi-daemon` if mDNS is not needed (exposes udp 5353 on all interfaces).
7. Decide on `kdeconnectd` (listens on tcp and udp 1716, blocked by ufw). Either add a LAN-only ufw rule or disable it.
8. Verify the power button still powers off and suspends from cold (ACPI PowerButton fixed event disabled at 17:53).
9. Check which unit writes `ENERGY_PERF_BIAS` to `normal` at boot (it reverts a 'performance' setting).
10. Look at `tailscaled` shutdown timeout (boot -3 SIGKILL) if it recurs; consider `TimeoutStopSec`.
11. Replace or update `whitesur-gtk-theme` to clear the GTK "Theme parser error" lines; the WhiteSur GTK CSS parse errors are cosmetic.

**P3 - cosmetic / silence later**
12. Bluetooth opcode failures and the WirePlumber bluez-midi `AlreadyExists` loop (disable the bluez MIDI monitor if BLE MIDI is unused).
13. NetworkManager `p2p-dev-wlo1` IPv4 forwarding warnings (ignore or unmanage P2P devices).
14. Disable `tracker-miner-fs` if not used (Nautilus indexer error).
15. niri "not a render node" probe on the ignored dGPU card node: already handled by config; optional cleanup.
16. Firmware-level, no userspace fix: ACPI PXSX `_DSM.MHYB` errors, NVRM `osCallACPI_DSM` / SBIOS platform-power lines, `tpm_crb` "Ignoring error -5 while suspending", pcieport IRQ routing, wmi_bus WQN, intel_pmc_core LTR, hpet_acpi, iwlwifi WGDS, spi-nor vcc, PS/2 AUX, TDX, nvme NGUID. Check for a newer BIOS (GU605MI.329 is from 2025-06) via fwupd.

## 6. Harmless noise to silence (quick list)
- ufw BLOCK (logging), intel_lpmd aperf (after decision), NM p2p forwarding, bluez MIDI AlreadyExists, WhiteSur theme parser errors, `zenity` GL renderer rename (set GSK_RENDERER=gl), kdeconnect wext deprecation, libayatana appindicator deprecation (spotify), tracker indexer, dbus homed activation, accounts-daemon /etc/tcb, gkr-pam control file, xdg-portal "inhibit" not supported, xwayland-satellite focus message, PKCS#11 provider, multicast RX registrations, pcieport/NVMe IRQ routing messages.

## 7. Open questions
1. Why does intel_lpmd spam only in boots that hibernated? (Hypothesis: APERF/MPERF reads after hibernate resume.) Test after a hibernate cycle with lpmd disabled vs enabled.
2. What stopped and started the noctalia.service SIGKILLs at 18:11 and 18:13? Not OOM. Likely a manual restart; confirm.
3. Which process ran `insmod` of the unsigned module at 12:27 (boot -2 Oops)? Expected a dev test; confirm and avoid unsigned insmod on this kernel.
4. Is the ACPI power-button disable (PowerButton fixed event) affecting cold power-off or suspend from the button? Verify by hand.
5. Does KDE Connect need inbound 1716 on the LAN? If not, disable kdeconnectd.
6. Boot -3 (19 s) ended with `tailscaled` stop timeout: a fast reboot, not a crash. Confirm nothing else was wrong at that time.
7. The `10-installer` sudoers drop-in is root-only readable and was not inspected for content.
8. Secure Boot is off and `mokutil` / `sbctl` are not installed. If Secure Boot is ever wanted, the tooling has to be installed first (not done here, read-only).
9. `fwupd` lists two "Locked MTD: Not supported" HSI items. Expected on this platform; confirm after the next firmware check.
10. Is the 32 GB btrfs swapfile still the right choice given the hibernate page-allocation failures (P1-1)?
