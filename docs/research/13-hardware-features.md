# 13 - Hardware feature audit: ROG Zephyrus G16 GU605MI (Linux, kernel 7.3.3-1-cachyos)

Scope: read-only audit (no installs, no state changes, no pairing, no lspci / nvidia-smi / vulkaninfo / drm status reads).
Sources: sysfs (/sys/bus/*, /sys/class/*), lsusb, journalctl -b, v4l2-ctl, iw, nmcli, bluetoothctl / btmgmt, fwupdmgr (get-devices, get-remotes, get-updates; no refresh), asusctl read-only queries, pacman -Q.
Identifiers (MACs, serials, SSIDs, hostnames, user names inside firmware paths) deliberately omitted.

BIOS at time of audit: GU605MI.329 (06/06/2025). Kernel boot taint: out-of-tree `vmd` module (covered in the storage notes).

---

## 1. Status summary

| # | Feature | Hardware | Linux status | Verdict |
|---|---|---|---|---|
| 1a | Colour webcam | Shinetech USB2.0 FHD UVC 3277:0051, interface 3-7:1.0 | uvcvideo, MJPG 1920x1080@30, YUYV 1080p@5, 720p@10 | Works |
| 1b | IR camera (Windows Hello) | Same USB device, interface 3-7:1.2 "USB2.0 IR UVC WebCam" | Enumerated as /dev/video2 (+video3 meta), GREY 640x360@15 | **Present, not used** (no howdy, no IR-emitter tool installed) |
| 2a | Mic array | Intel SOF (snd_sof_pci_intel_mtl), DMIC | Input nodes present (HDA Intel PCH Mic x2) | Feature present; see the audio notes (06) |
| 2b | Headphone jack | ALC285 (SSID 1043:1c63) | Headphone pin 0x21 reported | Present; jack detection untested |
| 2c | Speakers | 2x Cirrus CS35L56 over SPI (CSC3556) | Both amps bound, DSP firmware loaded | Works (see 06) |
| 3a | Bluetooth | Intel AX211 BT over USB (8087:0033), fw ibt-0180-0041 | Loaded, secure boot OK, firmware 187-29.26 | Works |
| 3b | BT codecs | BlueZ 5.87 + PipeWire 1.6.11 plugins | SBC, AAC, aptX, aptX HD, aptX LL, FastStream, LDAC, Opus, LC3 plugin present | Codecs registered; **untested** (no device paired) |
| 3c | LE Audio | btmgmt: cis-central / cis-peripheral supported | Controller capable; liblc3 present | Capable, untested |
| 3d | Battery reporting (BT devices) | BlueZ Battery Provider Manager active | Active | Untested |
| 4a | Wi-Fi | Intel Wi-Fi 6E AX211 160 MHz (PCI 8086:7e40), iwlwifi | Firmware 89.b20dcd1f.0, iwlmvm | Works; live link 5 GHz, 80 MHz, 866.7 Mb/s, -50 dBm |
| 4b | Wi-Fi 6E (6 GHz) | Band 4 channels present in phy0 info (53 6 GHz freq entries) | Regdom set | Present; needs a 6 GHz AP to verify |
| 4c | Wi-Fi 7 | n/a (AX211 is 6E, no EHT) | - | Not supported by hardware |
| 4d | Power save | iw: "Power save: on"; iwlmvm power_scheme=2 (balanced) | Default | Works |
| 5a | USB4 / TB4 controller | Intel Gen14 host router (0000:00:0d.2), domain security = user | thunderbolt driver, USB4 _OSC granted (DP, PCIe, USB3, XDomain) | Works, but no authorisation daemon |
| 5b | DP alt-mode | USB-C ports via i915 (card1: DP-1..DP-4) | Routed through Intel iGPU | Present; untested with a monitor |
| 5c | HDMI 2.1 | Wired to NVIDIA (card0 HDMI-A-1) | nvidia driver | Present; **HDMI keeps dGPU awake** (see section 5) |
| 5d | USB-C PD charging | UCSI (USBC000:00), 2 ports, sink-only | UCSI_GET_PDOS fails (-70) | Power charging works (ACAD online); PD wattage reporting broken |
| 6 | SD card reader | Realtek RTS525A (10ec:525a) on 0000:2c:00.0 | rtsx_pci + rtsx_pci_sdmmc; runtime PM control=auto, runtime_status=suspended | Works; does NOT pin package C-states while idle |
| 7a | Keyboard (USB) | ITE 0b05:19b6 (hid-asus bound) + ITE 0b05:193b (second HID iface) | Keyboard, mouse, rfkill sub-devices | Works |
| 7b | Keyboard backlight | leds asus::kbd_backlight, levels 0-3 | Present (asus-nb-wmi), restored at boot | Works |
| 7c | Keyboard RGB | asusd config aura_19b6.ron (Static, zone-capable) | asusctl 6.5.0 | Partial (verify modes/zones with asusctl) |
| 7d | Fn / Armoury / fan / ROG keys | "Asus WMI hotkeys" event10 (asus-nb-wmi); ITE event4 | Keycodes not yet verified | Needs an evtest run while pressing the keys |
| 7e | Mic-mute LED | No micmute LED class present | - | **Missing** (see gaps) |
| 7f | Lid switch | Lid Switch input, state open | Works | Works |
| 7g | Ambient light sensor | ACPI ASUS9001:00 (\_SB_.ARLS), status 15 (present) | No driver bound, no IIO device | **Not usable** (auto-brightness) |
| 7h | Accelerometer / hall sensor | none in IIO or I2C | - | Absent |
| 7i | Fingerprint | none on USB / I2C; fprintd not installed | - | Absent |
| 8 | Touchpad | ASUP1207 (093A:3012) on I2C, i2c_hid_acpi + hid-multitouch | Clickpad (BUTTONPAD), 5 MT slots, multitouch works | Works; libinput-tools not installed so gestures/palm config not inspected |
| 9a | Battery health | BAT1: full 4825 mAh vs design 5650 mAh (per µAh field values) | ~85% of design | Degraded but normal for age (cycle count unreliable) |
| 9b | Charge limit | charge_control_end_threshold=80; `asusctl battery info` = 80% | Works | Works |
| 9c | Charge mode (ASUS) | asus-nb-wmi charge_mode=1 | Present | Read only; meaning of value not verified |
| 10 | Firmware updates | fwupd 2.1.9, LVFS remote enabled | BIOS locked from fwupd; LVFS metadata cached 2026-10-26 | Partial (see section 10) |
| - | ASUS tuning | platform_profile (quiet/balanced/performance), asusctl profile, panel_od, gpu_mux_mode, nv_dynamic_boost, PPT limits, fan curves | All exposed | **Linux is ahead** of stock (Armoury Crate features exposed) |

---

## 2. Webcam and IR (Windows Hello)

**Facts**
- One USB device, 3277:0051, five interfaces (3-7:1.0 to 1.4):
  - 1.0 and 1.1: "USB2.0 FHD UVC WebCam" colour stream -> /dev/video0 (capture) and /dev/video1 (metadata)
  - 1.2 and 1.3: "USB2.0 IR UVC WebCam" -> /dev/video2 (capture, GREY 640x360 @15 fps) and /dev/video3 (metadata)
  - 1.4: "Camera DFU Device" (class 0xfe, no driver)
- Colour formats on /dev/video0: MJPG 1920x1080@30, 1280x720@30, 800x600, 640x480 and smaller. YUYV tops out at 1080p@5 fps, 720p@10 fps.
- Media controller: /dev/media0 and /dev/media1 present; the IR path shows a "Video Pixel Formatter" entity.
- fwupd: webcam firmware 2.2 "Updatable" flag set, but no LVFS update is offered.

**Conclusion:** The camera hardware *does* include an IR sensor. Windows Hello face login is therefore possible in principle. The earlier assumption that there is no IR camera is wrong for this unit.

**What Linux is missing**
- `howdy` (face auth via PAM) is not installed. It is AUR-only, not in the official repos.
- `linux-enable-ir-emitter` (turns on the IR emitter via UVC XU control) is not installed. Most laptop IR cameras need an emitter switched on; without it the GREY stream is dark. Whether this Shinetech module needs a specific XU command is unknown until someone tests it.

**Test plan (read-only checks first; note the capture turns on the camera LED)**
1. `v4l2-ctl -d /dev/video2 --stream-mmap --stream-count=5` and check mean brightness with and without ambient light. A dark frame with no emitter is expected.
2. If dark, try `linux-enable-ir-emitter` in configure mode, then re-test.
3. If it works, `howdy add` for a test user, then add `auth sufficient pam_howdy.so` to a PAM service (sudo first, then greetd/login). Keep a root shell open while testing.

**Worth it?** For a Windows-Hello-style workflow, yes. Face unlock is the single biggest Windows-only convenience this device has. Risks: a bad PAM edit can lock you out, so test in a second TTY. Howdy is a face-recognition auth path, so it should stay behind the password for sudo and encryption unlock.

---

## 3. Microphones, jack, speakers (summary only; drivers are covered in 06)

- SOF stack loaded: snd_sof_pci_intel_mtl, soundwire_intel, soundwire_cadence. sof-firmware 2026.09.2-1 installed. ALC285 codec on HDA with two CS35L56 amps (spi1-CSC3556:00).
- Input nodes: "HDA Intel PCH Mic" x2, "HDA Intel PCH Headphone". Internal DMIC array presence is confirmed by SOF; per-mic routing is not verified here.
- Amps: both CS35L56 Rev B0, OTP fw 3.4.4, DSP firmware loaded. The DSP "misc" file path is a Windows-built path (a file that came from the vendor). This is normal Cirrus behaviour and works.
- Gap: **no mic-mute LED** (see table row 7e).

---

## 4. Bluetooth

**Facts**
- Controller: Intel AX211 BT (USB 8087:0033), bus 3. Firmware: intel/ibt-0180-0041.sfi, FW 187-29.26 (fseq 00.00.03.94), DDC applied. Secure boot enabled on the controller, OTP and API locks set (normal for Intel).
- btmgmt: supported settings include `le`, `br/edr`, `secure-conn`, `ll-privacy`, `wide-band-speech`, **`cis-central`, `cis-peripheral`** (LE Audio capable), `phy-configuration`. Advertising: 1M/2M/Coded PHY.
- bluetoothd 5.87 registered endpoints: A2DP sink/source for SBC, AAC, aptX, aptX HD, aptX LL (plus duplex), LDAC, Opus (opus_g), and FastStream support in the PipeWire plugins. LC3 and hfp-lc3 codec plugins are installed (libspa-codec-bluez5-lc3, -hfp-lc3-a127, -hfp-lc3-swb).
- libfreeaptx 0.2.2 and libldac 2.0.2.6 are installed.
- No Bluetooth device is paired or connected at the time of audit (no pairing performed; read-only audit).

**Gaps / known risks**
- Codec negotiation (LDAC/aptX HD/LC3) is untested. Confirm with a paired headset: `pw-cli`/`wpctl` shows the active codec, and the PipeWire log shows the negotiated codec.
- LE Audio (LC3 / BAP) needs WirePlumber's LE Audio support enabled. I found no `bluez5.enable-lc3`-style override in the default config. Check `wpctl status` and `/usr/share/wireplumber/bluetooth.lua.d/` after pairing a LE Audio headset.
- Noctalia logs "registered BlueZ agent" and bluetoothd logs "Battery Provider Manager created". Battery reporting for headsets depends on the device (BAS/HFP indicators). Untested.
- Known MTL/BE200 issues: none observed in this boot's journal. Watch for "hci0: command 0x... tx timeout" under heavy Wi-Fi coexistence.

**Test plan**
1. Pair one LDAC-capable headset. Confirm codec with `pactl list cards | grep -i codec` and check whether aptX HD / LDAC is chosen by default.
2. Pair one LE Audio headset (if available) and see whether the LC3 profile appears.
3. Check battery %: `busctl` or `upower -d` after pairing.

---

## 5. Wi-Fi, ports, display outputs, power delivery

**Wi-Fi**
- Card: Intel Wi-Fi 6E AX211 160 MHz (PCI 8086:7e40, rev 0x441). iwlwifi firmware 89.b20dcd1f.0 with iwlmvm.
- Regdom set on the card (self-managed PHY, DFS-UNSET). 6 GHz band 4 channels (5955 MHz and up) are exposed.
- Live link: 5 GHz, 80 MHz, MCS 9 NSS2 (866.7 Mb/s), signal -50 dBm.
- Power save: `iw` reports on. iwlmvm power_scheme=2 (balanced). iwlwifi power_save=N and uapsd_disable=3 (defaults).
- Journal: "BIOS contains WGDS but no WRDS". The BIOS does not supply the Wi-Fi regulatory override (WRDS). Harmless but means the country comes from cfg80211 only.
- Journal: the WFPM_*_PD_NOTIFICATION lines are informational noise.
- Suspend/resume (18:17 test cycle) completed cleanly for iwlwifi.
- Open question: the kernel cmdline sets `pcie_aspm=force pcie_aspm.policy=powersupersave`. That is aggressive. It can cause Wi-Fi/NVMe/SD link drops on some hardware. No drops observed in this boot. Recommend a 24 h soak test with a Wi-Fi throughput check before keeping it.

**Thunderbolt / USB4**
- Host router: Intel Gen14 (device 0-0). domain0 security = **user**. No external TB device is connected.
- USB4 _OSC granted DP tunnelling, PCIe tunnelling, USB3 and XDomain.
- boltd / boltctl are **not installed** (`bolt` package missing). With security=user, the kernel will not authorise a dock automatically. Devices have to be authorised manually via sysfs (`echo 1 > .../authorized`, which is a state change) or install bolt.
- Recommendation: install `bolt` and enrol devices with `boltctl enroll` when a dock or eGPU is used. Do not test with a live dock until the security mode is decided.

**Display routing**
- card0 = NVIDIA (01:00.0, nvidia driver). Outputs per the inventory: HDMI-A-1, DP-5, eDP-2.
- card1 = Intel i915 (00:02.0). Outputs: DP-1..DP-4, eDP-1.
- gpu_mux_mode = 1 (Optimus/hybrid). The internal eDP is driven by the Intel GPU and USB-C DP alt-mode goes through i915.
- HDMI-A-1 is wired to the NVIDIA GPU. An HDMI monitor therefore keeps the dGPU out of D3 and costs battery life. Recommend a documented power note: for HDMI-heavy use, switch to USB-C DP or a dock instead.
- Not verified: HDMI 2.1 modes (48 Gb/s / FRL) and DP 2.1 over USB-C. Test with a real monitor. Do not probe connectors from the command line, since that reads DRM status.

**USB-C power delivery and charging**
- Both UCSI ports (port0, port1) report data role host/device and power role sink. There are no typec partners attached at the time of the audit.
- ACAD (mains) reports online=1, so the system is on AC power.
- Journal: `ucsi_acpi USBC000:00: UCSI_GET_PDOS failed (-70)` at boot. This means the kernel cannot read source capabilities (PDOs) from the port controller. Charging still works, but PD negotiation details and the reported wattage are not available on Linux.
- Gap: this needs a test with a PD charger to see whether the charger is negotiated or ignored. Windows is likely to read the PDOs through its own UCSI driver.

---

## 6. SD card reader

- Realtek RTS525A (10ec:525a) on 0000:2c:00.0, driver rtsx_pci, sub-driver rtsx_pci_sdmmc.
- Runtime PM: power/control = auto, runtime_status = suspended. The reader is not blocking package C-states while idle.
- Link L1 ASPM = 1 (enabled). Under the forced powersupersave policy the device may still drop link states. Not observed.
- No SD card is present now (no mmc device), so card detection and read/write were not tested.
- Test: insert a card and check `journalctl -k | grep mmc`. Then check `cat /sys/bus/pci/devices/0000:2c:00.0/power/runtime_status` during idle.

---

## 7. Keyboard, hotkeys, sensors, lid

**Keyboard**
- ITE 0b05:19b6 (USB bus 3, port 6). hid-asus is bound (the HID device is listed as "asus 0003:0B05:19B6.0001"). Sub-inputs: keyboard, mouse, "Wireless Radio Control" (rfkill), and consumer controls.
- ITE 0b05:193b on port 8: vendor HID interface (hidraw1), no input device attached (hid-generic only). Likely the Aura or vendor control channel. Its function is unknown.
- Keyboard backlight: asus::kbd_backlight, brightness 0-3 (max 3), restored at boot by systemd.
- RGB (Aura): asusd config /etc/asusd/aura_19b6.ron exists (Static mode, zone-capable, colour config saved). asusctl 6.5.0 is installed. Confirm supported zones and effects with `asusctl aura`. Do not assume per-key.

**Hotkeys**
- "Asus WMI hotkeys" input (event10, from asus-nb-wmi) and the ITE keyboard (event4) both produce keys. Keycodes were not captured, because capturing needs a human pressing keys.
- Test: `sudo evtest /dev/input/event10`, then press Armoury Crate, mic mute, fan/profile key, airplane, touchpad toggle and screenshot keys. Record which events fire, and on which device.
- Profile key: `platform_profile` (quiet, balanced, performance) and asusctl profile are both present. The fan/profile hotkey should map to these through asusd or asus-nb-wmi.

**Lid**
- Lid Switch input (event1), state = open. Standard ACPI. Works. No hall sensor separate from the lid switch.

**Ambient light sensor**
- ACPI ASUS9001:00 (path \_SB_.ARLS) is present and enabled (status 15). No driver is bound and there is no IIO device, so brightness cannot follow ambient light.
- Possible fix: an ALS driver for the ASUS9001 HID (kernel patch or out-of-tree). Not attempted.

**Accelerometer, hall, fingerprint**
- No IIO devices exist (/sys/bus/iio/devices is absent). No accelerometer on I2C.
- No fingerprint sensor on USB or I2C. fprintd is not installed. Windows Hello PIN/face only.

---

## 8. Touchpad

- ASUP1207:00 093A:3012 on I2C (i2c-ASUP1207:00, bus 1, i2c_hid_acpi). Input nodes: Mouse (event8) and Touchpad (event9). Driver: hid-multitouch (I2C HID v1.00).
- Capabilities: INPUT_PROP_POINTER + INPUT_PROP_BUTTONPAD (clickpad, no separate buttons). Five MT slots (ABS bitmap 2e0800000000003).
- Precision-touchpad features (palm rejection, pinch/swipe, three-finger gestures) depend on libinput. **libinput-tools is not installed** (only the library is), so `libinput list-devices` and `libinput debug-events` are unavailable. Palm rejection and gesture configuration were not inspected.
- Haptics: none (no haptic actuator enumerated).
- Test: install libinput-tools (optional), then `sudo libinput debug-events --device` and check for palm detection (contact sizes) and tap settings.

---

## 9. Battery

- BAT1 (Li-ion): charge_full 4825000 µAh, charge_full_design 5650000 µAh -> **85% of design capacity**. Capacity now 96%. Status "Not charging" (because the battery is at its 80% limit while on AC).
- cycle_count reports 0. This is almost certainly the driver/firmware not reporting it. Do not trust it. Count cycles from the battery's own history if needed (not available here).
- Charge limit: charge_control_end_threshold = 80. `asusctl battery info` agrees (Current battery charge limit: 80%). This works.
- ASUS battery extension ACPI hook is present ("ACPI: battery: new hook: ASUS Battery Extension").
- Windows-only: the Armoury Crate "Full charge" / "Balanced charge" options. The asus-nb-wmi charge_mode attribute (value 1) probably maps to one of them, but its meaning is not verified. Test by reading the attribute with the AC cable connected.

---

## 10. Firmware updates

| Device | Current | fwupd status |
|---|---|---|
| System BIOS (Internal SPI Controller BIOS) | GU605MI.329 (06/06/2025) | Updatable flag, but "Device firmware has been locked" (BIOS write-protection is on). No update offered. |
| Intel ME | 18.0.5.2141 | Updatable flag, no update offered |
| TPM | 700.19.5.2141 | Updatable flag, no update offered |
| CPU (Core Ultra 9 185H, microcode) | 0x2b | Info only |
| SSD WD PC SN5000S (Sandisk) | 34230100 | Updatable flag, no update offered |
| Webcam (Shinetech 3277:0051) | 2.2 | Updatable flag, no update offered |
| Thunderbolt retimer / EC / keyboard | - | Not listed by fwupd |

- fwupd 2.1.9. Remotes: lvfs (enabled), vendor-directory (enabled), lvfs-testing and lvfs-embargo (disabled).
- The lvfs metadata cache was last written 2026-10-26, about three weeks before this audit. "No updatable devices" may therefore be stale. A `fwupdmgr refresh` would update it, but that is a network write and was not run.
- Conclusion: **BIOS cannot be flashed from fwupd on this unit** (SPI locked). Use ASUS EZ Flash 3 from the BIOS setup screen with a FAT32 USB stick and the ASUS .CAP file for GU605MI. This is also how Windows users update it, and it does not need Windows.
- The EC on this model has no fwupd entry. Thunderbolt NVM is not listed either. Both are Windows-only as far as this device is concerned.

---

## 11. ASUS platform controls (Linux advantages)

Exposed via asus-nb-wmi (/sys/devices/platform/asus-nb-wmi/): panel_od (1), gpu_mux_mode (1, hybrid), dgpu_disable (0), nv_dynamic_boost (5), nv_temp_target (75), ppt_pl1_spl / ppt_pl2_sppt / ppt_fppt (5), throttle_thermal_policy (0), charge_mode (1), boot_sound (0), cpufv, plus firmware-attributes under asus-armoury.

- supergfxd reports Hybrid mode. Runtime PM for the NVIDIA GPU is "Enabled (fine-grained)" and the GPU is in D3 (runtime_status = suspended) at audit time.
- The 2024 G16 Dynamic Boost, PPT limits and panel overdrive can all be set from Linux.
- The journal shows the old `asus_wmi: Accessing attributes through /sys/bus/platform/asus_wmi is deprecated`. Migrate to /sys/class/firmware_attributes when asusd is updated.

---

## 12. Ranked gaps and fixes

| Rank | Impact | Gap | Fix | Effort / risk |
|---|---|---|---|---|
| 1 | High | IR camera present but Windows Hello face login not possible | Install howdy (AUR) + linux-enable-ir-emitter; calibrate emitter on /dev/video2; add PAM rule after password testing | Medium. Risk: PAM lockout. Test in a second TTY. |
| 2 | High | BIOS update path unclear (fwupd cannot flash SPI) | Use EZ Flash 3 from USB. Refresh LVFS metadata (`fwupdmgr refresh`) so fwupd's view is current | Low. Mains power required, no interruptions. |
| 3 | Medium | USB-C PD source capabilities unreadable (UCSI_GET_PDOS -70) | Test with a known 100 W PD charger and check reported power and negotiation. If broken, check kernel/UCSI patch status | Investigate, no fix known |
| 4 | Medium | Thunderbolt security = user, no bolt daemon | Install bolt, `boltctl enroll` for docks | Low. Only needed for docks/eGPU. |
| 5 | Medium | HDMI wired to dGPU keeps NVIDIA awake (battery) | Document: use USB-C DP for battery-sensitive use. Consider MUX mode trade-off | Policy decision |
| 6 | Medium | No mic-mute LED class | Check if HDA codec exposes micmute LED (see the audio notes, 06); otherwise a udev/hid patch | Investigate |
| 7 | Low-Med | ALS (ASUS9001 ARLS) not bound | Investigate ALS driver for ASUS9001 (kernel source or out-of-tree) | High effort |
| 8 | Low-Med | Hotkey keycodes unverified | evtest on event10 and event4 while pressing keys | Low (manual key presses) |
| 9 | Low | libinput-tools missing (touchpad diagnostics) | Install libinput-tools, check palm/gesture behaviour | Low |
| 10 | Low | Forced ASPM policy (pcie_aspm=force, powersupersave) | 24 h soak test; revert to default if drops appear | Low |
| 11 | Low | Battery cycle_count reports 0 | Track separately; not fixable from here | - |
| 12 | Low | Out-of-tree vmd module taints kernel | Covered in the storage notes | - |

---

## 13. Test checklist (manual; not run during this audit)

1. IR: `v4l2-ctl -d /dev/video2 --stream-mmap --stream-count=5` (camera LED will turn on). Check image brightness.
2. Keys: `sudo evtest /dev/input/event10` then press each ROG/Fn key. Note keycodes.
3. Bluetooth: pair an LDAC headset; `wpctl status` and codec logs.
4. USB-C PD: plug a 100 W charger into a USB-C port; `journalctl -k -f | grep -i ucsi`.
5. HDMI: attach a 4K 120 Hz monitor on the HDMI port and check negotiated mode and dGPU state.
6. Dock: after `bolt` is installed, plug a TB4 dock; authorise it.
7. Touchpad: `libinput debug-events` after installing libinput-tools; check palm rejection.
8. BIOS: EZ Flash update procedure from the vendor page (not run).

---

## 14. Open questions

- Does the IR emitter on this Shinetech module respond to linux-enable-ir-emitter? Needs a live test.
- Are the `ITE 193b` HID interface and the keyboard Aura controls fully driven by asusd, or is there a second protocol to reverse-engineer?
- Does `charge_mode=1` map to the Armoury "Full / Balanced" charge option?
- Is the ALS ASUS9001 usable through any existing kernel driver in 7.3?
- Does the PD controller issue (-70) affect power negotiation or only reporting?
- Is the lvfs cache stale enough to hide a BIOS update? Refresh and recheck.
