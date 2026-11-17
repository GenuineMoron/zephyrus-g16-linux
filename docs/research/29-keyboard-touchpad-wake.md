# 29. Why the internal keyboard and touchpad cannot wake s2idle (Zephyrus G16 GU605MI)

Research note, read-only. Date 2026-11-15. Kernel 7.3.3 (CachyOS). No suspend, no writes to /sys or /proc, no lspci/nvidia tools, no msdm.dsl.

Labels: **PROVEN** = read from a file or sysfs during this pass. **INFERRED** = reasoning from the PROVEN facts, not directly observed.

## Bottom line

1. The keyboard is a USB 2.0 HID device on xHCI root port 6 (`3-6`). Its only wake path is USB remote wakeup, then the xHCI's ACPI `_PRW` GPE. In the firmware, that GPE is either 0x89 or 0x6D depending on an NVS byte (`GP1E`). Linux has a registered handler for 0x89 and none for 0x6D. (PROVEN for the handler state, INFERRED for which GPE is live.)
2. The touchpad is an I2C-HID device on I2C3 (00:15.3, `i2c-1`). Its ACPI GpioInt is wake-capable, so the i2c core arms its IRQ for wake only during suspend. The i2c-hid driver masks that IRQ on suspend (`disable_irq`) after sending SLEEP to the device. The likely failure is that the wake is lost at that masking step. (PROVEN for the code, INFERRED for the failure.)
3. Linux's s2idle wake filter (`acpi_s2idle_wake`) accepts a wake only from the SCI with a fixed event, a custom handler, or an enabled non-EC GPE with status set. Any other wake is re-armed and the system goes back to sleep. (PROVEN from source.)
4. Windows evaluates PEP constraints (PEPD `DEVY`, `CSD0`/`CSD3`) and the LPS0 DSM. Linux only evaluates LPI constraints when a non-default module parameter is set. This is a plausible Windows-side difference, not proven to matter. (PROVEN for both code paths, INFERRED for the effect.)

## (a) What the firmware declares

Source: `~/.local/src/acpi-tables/dsdt.dsl` (decompiled DSDT).

**XHCI (PC00, `_ADR 0x00140000`)** — dsdt.dsl:9615-9622, inside `Scope (_SB.PC00)` at 9328.
- `Name (PPID, 0x3A)` (9622).
- `_PRW` at 9623-9648. The GPE depends on `GP1E`:
  - 9629-9631: `If ((GP1E != Zero)) { Return (GPRW (0x89, DUWS)) }` (GPE 0x89).
  - 9635: `Return (GPRW (0x6D, DUWS))` (GPE 0x6D, the `GP1E == 0` case).
  - `GP1E` is an NVS byte at dsdt.dsl:2846 and `DUWS` at 3064. Their runtime values are not in the DSDT (**INFERRED: the live value is unknown statically**).
- `_S0W` returns 3 (D3hot) at 9725-9727: `Method (_S0W...) { Return (0x03) }`. This caps the wake-capable D-state at D3hot. (PROVEN)
- `_DSW` (9730) is empty. No LPS0 constraint is set for the XHCI here. (PROVEN)
- `_PS0` (9759-9760): `UPRU (Zero, 0xFFFFFFF7, Zero)`.
- `_PS3` (9774-9775): `UPRU (Zero, 0xFFFFFFFF, 0x08)`. `UPRU` calls `SBSC.PCAO(PPID, ...)` (dsdt.dsl:14652). PCAO does read-modify-write on a PCR register, so `_PS3` sets bit 3 and `_PS0` clears it. The meaning of that PCR bit is **INFERRED** (a vendor PME or power-gate bit is likely).
- The RHUB `_PS3` (9843-9844) calls `PS3X()` then `CSD3(0x16)`. `CSD3` (dsdt.dsl:8487) is a PEP-style handshake, not a Linux mechanism.

**No GPE handler for the XHCI wake GPEs.** A grep of every `.dsl` finds no `_L6D`, `_E6D`, `_L89` or `_E89`. `_L6B` and `_L6F` exist at dsdt.dsl:30097 and 30112. (PROVEN)

**Keyboard port.** `PC00.XHCI.RHUB.HS06` (dsdt.dsl:10090-10094) is `Device (HS06) { Name (_ADR, 0x06) }`. It has no `_UPC`, `_PLD`, `_DSD` or `_PRW`. HS08 (3-8) is the same at 10106-10110. The keyboard's wake therefore goes through the XHCI `_PRW`, not through the port. (PROVEN)

**Touchpad (ASUP1207).**
- Four `TPD0` variants exist, one per I2C scope. The active one is under `Scope (_SB.PC00.I2C3)` at dsdt.dsl:62484, because `i2c-1` is PCI 00:15.3 (`/sys/bus/i2c/devices/i2c-1`) and `I2C3 _ADR 0x00150003` is at dsdt.dsl:11341. (INFERRED for the variant choice, PROVEN for the PCI mapping.)
- Variant gate: `_STA` returns 0x0F only if `((TPDT != 0) && (I2CN & 1))` (dsdt.dsl:62712 onward). `I2CN = SDS3` (62491), an NVS field at dsdt.dsl:1691.
- GpioInt, wake-capable: `GpioInt (Level, ActiveLow, ExclusiveAndWake, PullDefault, ...)` at dsdt.dsl:62507. `Interrupt (..., ExclusiveAndWake, ... _Y66)` at 62516. (PROVEN)
- `Name (_S0W, 0x03)` at 62693. (PROVEN)
- No `_PRW`, `_PS0` or `_PS3` on TPD0 in the I2C0 variant (dsdt.dsl:61046-61287, PROVEN). I did not fully verify the I2C3 variant's absence of `_PRW`, so this is **INFERRED** for that variant.
- The I2C3 controller `_PS3` calls `SOD3 (IC03, One, One)` (dsdt.dsl:11331). (PROVEN)
- A second `GpioInt` with `Exclusive` (not wake) appears at dsdt.dsl:62751. I did not analyse what it belongs to.

**LPS0 / PEP.** `Device (PEPD)` at dsdt.dsl:50516, `Name (DEVY, Package (0x78))` at 50561, LPS0 `_DSM` UUID `c4eb40a0-...` at 52953. (PROVEN)

**EC.** The lid wakes via `LID0`, which is enabled in `/proc/acpi/wakeup` (PROVEN, see the live-state section).

## (b) What Windows configures

**Blocked for the live hive.** `/mnt/win/os` is an empty, unmounted directory. The NTFS partition `/dev/nvme0n1p3` is `root:disk 0660`, the login account is not in `disk`, and `ntfs-3g` is not installed. The plan was to copy the SYSTEM hive from the mounted partition. That is not possible without a privileged mount, which I did not attempt. (PROVEN)

**Fallback source used.** A `SYSTEM.reg` file (local working copy, not in the repo) is a text export of a Windows SYSTEM hive (file mtime 2026-11-14 20:26). I did not verify that it is a faithful copy of the current install. (INFERRED that it is the same install.) I read only the device keys below.

| Device | Key | Power/wake values (PROVEN from the export) |
|---|---|---|
| Keyboard 0B05:193B (port 3-8) | `ControlSet001\Enum\USB\VID_0B05&PID_193B\5&1423acb5&0&8\Device Parameters` | `SelectiveSuspendEnabled=1`, `DeviceSelectiveSuspended=1`, `AllowIdleIrpInD3=1`, `EnhancedPowerManagementEnabled=1` |
| Keyboard 0B05:19B6 (port 3-6) | `ControlSet001\Enum\USB\VID_0B05&PID_19B6\5&1423acb5&0&6\Device Parameters` | `SelectiveSuspendEnabled=1`, `DeviceSelectiveSuspended=1`, `AllowIdleIrpInD3=1`, `EnhancedPowerManagementEnabled=1`. Device-level `Capabilities=0x80` (SurpriseRemovalOK only). |
| Touchpad ASUP1207 (ACPI) | `ControlSet001\Enum\ACPI\ASUP1207\4&1907dced&0` | `Capabilities=0x20`, no WakeFromD* bits. `Device Parameters\e5b3b5ac-...` has `D3ColdSupported=1`. `Device Parameters` has `EnhancedPowerManagementEnabled=1`. |
| xHCI 8086:7E7D | `ControlSet001\Enum\PCI\VEN_8086&DEV_7E7D&SUBSYS_201F1043&REV_20\3&11583659&0&A0` | `Capabilities=0x480` (WakeFromD2 bit and SurpriseRemovalOK), `D3ColdSupported=1`, `WDF\IdleInWorkingState=1`. |

What the export does not contain: `RemoteWakeEnabled`, `WaitWakeEnabled` or any "allow this device to wake" flag for these devices. (PROVEN absence in the export.) The Windows wake toggle is therefore stored elsewhere or was never written. **INFERRED.**

Windows' evidence that the hardware can wake (PROVEN in the Windows event log, see 27-windows-standby-drain.md): exit reasons 31 (keyboard) and 33 (touchpad) from ≥90% hardware DRIPS. Those reasons come from the PMC's own wake path. Linux s2idle does not use DRIPS.

## (c) What Linux does differently (kernel v7.3 source, fetched from raw.githubusercontent.com)

**Touchpad path**
- `drivers/hid/i2c-hid/i2c-hid-core.c:980-1000` `i2c_hid_core_suspend`: line 992 sends `I2C_HID_PWR_SLEEP` unless `I2C_HID_QUIRK_NO_SLEEP_ON_SUSPEND` (quirk BIT(5), line 52). Line 994 calls `disable_irq(client->irq)`. Line 996 powers the device off only if it is not wake-capable. (PROVEN)
- `i2c-hid-core.c` never calls `enable_irq_wake` or `dev_pm_set_wake_irq` (grep, PROVEN).
- The wake IRQ is set up in `drivers/i2c/i2c-core-base.c:517-521` (`I2C_CLIENT_WAKE` from a wake-capable GpioInt, via `i2c-core-acpi.c:222`) and `:551-562` (`device_init_wakeup` plus `dev_pm_set_wake_irq`). (PROVEN)
- `gpiolib-acpi-core.c:228` calls `enable_irq_wake` only for ACPI `_AEI` events that are `irq_is_wake`. It does not cover the i2c client's GpioInt. (PROVEN)
- Consequence: the wake IRQ is armed by the PM core during device suspend, then `disable_irq` masks the line in i2c-hid. **INFERRED** that the masked line cannot deliver the wake.

**Keyboard / xHCI path**
- `drivers/usb/host/xhci.c:879-899` `xhci_disable_hub_port_wake` clears `PORT_WAKE_BITS` if `do_wakeup` is false. Called from `xhci_suspend` at `xhci.c:968-969`. (PROVEN)
- `drivers/usb/host/xhci-hub.c:1702` `wake_enabled = hcd->self.root_hub->do_remote_wakeup`. With root-hub wakeup disabled (the current `usb3` state), port wake bits are cleared (`xhci-hub.c:1782-1783`). (PROVEN)
- `xhci-hub.c:1767-1774`: for a connected port (keyboard), the kernel sets `WKOC|WKDISC` and clears `WKCONN` (line 1770). USB2 remote resume is not governed by these bits (INFERRED). (PROVEN code, INFERRED effect.)
- `drivers/usb/host/xhci-pci.c:814-846` `xhci_pci_suspend`: D3cold is disabled only for `XHCI_COMP_MODE_QUIRK` or `XHCI_BROKEN_D3COLD_S2I`. The latter is set only for AMD Renoir (`xhci-pci.c:343-345`). (PROVEN)
- `drivers/pci/pci-acpi.c:918-940` `acpi_pci_choose_state`: `d_max = D3COLD` because `d3cold_allowed=1`. The `_S0W=3` ceiling then restricts the wake-capable state to D3hot. (PROVEN code; the D3hot outcome matches the earlier dynamic-debug log.)
- `pci-acpi.c:1173-1179` `acpi_pci_wakeup` calls `acpi_pm_set_device_wakeup` for the XHCI, which routes to its `_PRW` GPE. (PROVEN)

**s2idle wake filter**
- `drivers/acpi/sleep.c:733-752` `acpi_s2idle_prepare`: `enable_irq_wake(SCI)`, `acpi_enable_wakeup_devices`, `acpi_enable_all_wakeup_gpes`. (PROVEN)
- `drivers/acpi/sleep.c:758-820` `acpi_s2idle_wake` accepts a wake only if:
  - the SCI was not armed (`771`: "Wakeup unrelated to ACPI SCI"), or
  - a fixed event status is set (`780`), or
  - a custom wakeup handler fires, or
  - `acpi_ec_dispatch_gpe()` returns true (`795`: "ACPI non-EC GPE wakeup").
  Otherwise it rearms the SCI and returns false (`812`: "Rearming ACPI SCI for wakeup"). (PROVEN)
- `drivers/acpi/ec.c:2170-2195` `acpi_ec_dispatch_gpe`: returns true only if `acpi_any_gpe_status_set(first_ec->gpe)`, i.e. an enabled GPE other than the EC's has status set. A GPE with no handler, or one that is not enabled, does not count. (PROVEN)
- `drivers/acpi/x86/s2idle.c:31-33`: `check_lps0_constraints` defaults to false. Lines 518-525 and 545-546 evaluate and check LPI constraints only when it is set. Linux therefore never applies the PEP-style per-device constraints that Windows applies. (PROVEN code; **INFERRED** that this is the Windows-side difference.)
- `s2idle.c:642` `.wake = acpi_s2idle_wake`. (PROVEN)

## Live state (read-only, this pass, not during a suspend)

- `/proc/acpi/wakeup`: `LID0 enabled`; `XHCI *disabled` (`pci:0000:00:14.0`); all others disabled. (PROVEN)
- `/sys/firmware/acpi/interrupts/gpe89`: `0 disabled unmasked` (a handler exists, not currently enabled). `gpe6D`: `0 invalid unmasked` (no handler). Both counts are 0. (PROVEN)
- `/sys/firmware/acpi/interrupts/gpe00`: disabled. `gpe0C`: disabled. `gpe_all`: 247. (PROVEN)
- Touchpad IRQ 200 (`intel-gpio`, pin 352): `/sys/kernel/irq/200/wakeup = disabled`. Expected outside suspend (**INFERRED**). (PROVEN as a reading)
- `/sys/class/wakeup/wakeup64` `i2c-ASUP1207:00`: `event_count=63633`, `wakeup_count=0`. `wakeup54` `3-6`: `event_count=2`, `wakeup_count=0`. (PROVEN)
- `/sys/bus/usb/devices/3-6`: `power/wakeup=enabled`, `power/control=on`, `power/persist=1`. `usb3` root hub: `power/wakeup=disabled`. (PROVEN)
- `/sys/bus/pci/devices/0000:00:14.0`: `power/wakeup=disabled`, `d3cold_allowed=1`, `power/control=auto`. (PROVEN)
- `/sys/bus/i2c/devices/i2c-ASUP1207:00/power/wakeup=enabled`. (PROVEN)

## (d) Ranked hypotheses and tests

Tests are manual. Each one needs a suspend. Record the counters before and after each attempt.

**H1. The XHCI wake GPE is 0x6D, which has no handler, or 0x89 is not enabled during suspend.**
Evidence: gpe6D has no handler, gpe89 has one. The GPE choice depends on `GP1E`. Confirmed or refuted by which counter moves.
Test: note `cat /sys/firmware/acpi/interrupts/gpe89 /sys/firmware/acpi/interrupts/gpe6D /sys/firmware/acpi/interrupts/sci` and `/sys/class/wakeup/*` for `3-6`. Enable the XHCI wake (`echo enabled > /sys/bus/pci/devices/0000:00:14.0/power/wakeup`, `echo enabled > /sys/bus/usb/devices/usb3/power/wakeup`, `echo XHCI > /proc/acpi/wakeup`). Suspend, press a key, resume, read the counters again.
- gpe89 +1: the GPE path works; go to H4.
- gpe6D +1 with no handler: the wrong GPE; H1 confirmed.
- none moved: the PME never reached ACPI; go to H2.

**H2. The XHCI PME is never asserted in D3hot (vendor PCR bit or PME enable).**
Evidence: `_PS3` sets PCR[0x3A] bit 3 (dsdt.dsl:9775, via `PCAO`). Linux's xHCI D3hot path does not clear it.
Test: `sudo modprobe acpi_call`, then read PCR PID 0x3A offset 0 through the same `PCRR` helper that `PCAO` uses (dsdt.dsl:14652 area; verify the exact scope path in the .dsl first, since `PCRR` is not in SBSC's own block). Read it in D0, then after a `_PS3` (for example via a suspend attempt or a `_PS3` call), and compare bit 3. Then test whether keyboard wake works with the bit forced clear (a test-only ASL patch, not for production).

**H3. The wake is seen but rejected as spurious by s2idle.**
Evidence: `acpi_s2idle_wake` (sleep.c:758-820) rearms and returns false when the only wake source is a non-EC GPE that is not enabled or has no handler.
Test: `echo 'file kernel/power/suspend.c +p' > /sys/kernel/debug/dynamic_debug/control` and the same for `drivers/acpi/sleep.c` and `drivers/acpi/ec.c`. Suspend, press a key, then grep `journalctl -k` for "Rearming ACPI SCI" (812) and "ACPI non-EC GPE wakeup" (795). Many "Rearming" lines with no matching wake means H3 is the mechanism.

**H4. The touchpad IRQ is masked during suspend (`disable_irq`) so its wake is lost.**
Evidence: `i2c-hid-core.c:994` masks the IRQ. `i2c-core-base.c:551-562` arms it. `/sys/kernel/irq/200/wakeup` is not readable during suspend.
Test: before suspend, record `/sys/class/wakeup/*/event_count` for `i2c-ASUP1207:00`. Suspend, touch the pad, resume. If the count stays flat, no wake was delivered. Also `journalctl -k | grep i2c-ASUP1207` for "failed to set up wakeup irq" (i2c-core-base.c:568).

**H5. The touchpad SLEEP command (`i2c-hid-core.c:992`) stops the device from raising its IRQ.**
Evidence: the driver sends SLEEP unconditionally unless the quirk is set. Windows' HID-I2C stack may not do this.
Test: needs a test kernel with `I2C_HID_QUIRK_NO_SLEEP_ON_SUSPEND` applied to `ASUP1207`. Then repeat the touch-wake test and compare. This needs a rebuild, not a runtime setting.

**H6. Keyboard port is not in U3 at suspend (runtime PM on), so the device cannot signal wake.**
Evidence: `3-6 power/control=on` (no selective suspend), while Windows has `SelectiveSuspendEnabled=1` for both keyboard endpoints (export). **INFERRED** as a difference.
Test: `echo auto > /sys/bus/usb/devices/3-6/power/control` before suspend, then suspend and press a key. If the keyboard now wakes, the failure is port state.

**H7. The Windows PEP constraints (DEVY, CSD3/CSD0, LPS0) keep the XHCI and I2C3 in a state where wake is kept alive. Linux applies none of them.**
Evidence: `s2idle.c:31, 520-525` (constraints off by default). Windows exits with reasons 31 and 33 from DRIPS.
Test: boot with `check_lps0_constraints=1`, suspend, and read dmesg for "LPI: Constraint not met" for the XHCI (`PC00.XHCI`) and I2C3 entries. This is a diagnostic, not a fix.

## Not done / blocked

- (b) The live Windows hive was not read (unmounted, root-only). The local export was used instead and is labelled as such. To finish: mount the Windows partition read-only, then `hivexregedit --export` on a copy of `Windows/System32/config/SYSTEM` into a local working directory. Also search `DriverStore/FileRepository` for `VID_0B05`, `PID_19B6` and `ASUP1207`.
- The `GP1E` and `DUWS` values could not be determined statically. H1's test resolves this.
- Kernel source was fetched to a local working directory (untrusted downloads, not run; not in the repo). `xhci-hub.c`, `sleep.c`, `ec.c`, `gpiolib-acpi-core.c`, `i2c-core-base.c` and `i2c-core-acpi.c` were fetched in addition to the five requested files.
