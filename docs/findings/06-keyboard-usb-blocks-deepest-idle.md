# 06: asusd keeps the keyboard's USB chips awake, so the CPU almost never reaches its deepest idle state

**Status:** root cause proven and measured; fix applied 2026-11-15 (patched asusd + autosuspend + a sleep-time guard). Still watching for keyboard issues and the #690 firmware bug across long sleeps.

## Symptom

With the laptop idle, Linux asks for the deepest package C-state (PC10) about 81% of the time, but the package reaches it only about 0.3% of the time ([research/20](../research/20-intel-pmt-telemetry.md)). The PCH reports a 51 µs latency tolerance (LTR) from the USB controller, below the ~325 µs that C10 needs.

## Cause

Two ASUS USB devices on the internal xHCI controller never runtime-suspend:

| USB | ID | What | Driver |
|---|---|---|---|
| 3-6 | 0b05:19b6 | N-KEY keyboard controller (keys, Aura lighting) | `hid-asus` |
| 3-8 | 0b05:193b | Slash LED bar controller | `hid-generic` |

`asusd` opens `/dev/hidraw0` and `/dev/hidraw1` at start and keeps them open for its whole lifetime (`rog-platform/src/hid_raw.rs`, `file: RefCell<File>`). The kernel holds a USB HID device at full power while its hidraw node is open: `hidraw_open()` calls `hid_hw_power(hdev, PM_HINT_FULLON)`, and the matching release happens only on close. Both devices had `runtime_suspended_time = 0` for the whole boot. Separately, USB devices default to `power/control=on`, so the kernel would not autosuspend them anyway.

Windows lets the same keyboard suspend: its registry has `SelectiveSuspendEnabled=1`, `DeviceSelectiveSuspended=1` ([research/29](../research/29-keyboard-touchpad-wake.md)).

## Measurements

Screen off, on battery, 20 s turbostat windows (`Pk%pc10`, `PkgWatt`, `SysWatt` = RAPL psys):

| Condition | PC10 | PC8 | PC6 | Package | Platform |
|---|---|---|---|---|---|
| Normal: asusd holding both chips | 0.4% | 33% | 27% | 2.02 W | 3.23 W |
| asusd stopped, chips `power/control=auto` (suspended) | **65%** | 4.4% | 1.5% | 1.70 W | 2.47 W |
| Same, repeated | **67%** | 3.8% | 1.7% | 1.69 W | 2.38 W |
| asusd stopped, chips `on` (awake) | 0.4% | 34% | 28% | 1.97 W | 3.04 W |

Stopping asusd alone changes nothing; the chips being able to suspend is what lets the package reach PC10. Platform power drops by up to ~0.8 W (about 25%) with the screen off. Some windows were disturbed because starting or stopping asusd wakes the NVIDIA GPU for a few seconds (`journalctl -t gpu-wake`).

## Fix (applied 2026-11-15)

- **asusd:** open hidraw per write. This is upstream [OpenGamingCollective/asusctl#404](https://github.com/OpenGamingCollective/asusctl/pull/404) (open, approved by one reviewer, 2026-10). On a GU605CW its author measured 16.8 W → 11.4 W with the screen off. Both commits apply cleanly to the 6.5.0 release. Built here and run through a drop-in that keeps all of asusd's sandboxing: [configs/etc/systemd/system/asusd.service.d/50-pr404.conf](../../configs/etc/systemd/system/asusd.service.d/50-pr404.conf).
- **Autosuspend:** `power/control=auto` for 3-6 and 3-8: [configs/etc/udev/rules.d/71-asus-kbd-autosuspend.rules](../../configs/etc/udev/rules.d/71-asus-kbd-autosuspend.rules).
- **Guard:** [configs/usr/lib/systemd/system-sleep/10-asus-kbd-autosuspend](../../configs/usr/lib/systemd/system-sleep/10-asus-kbd-autosuspend) sets both to `on` (resumed) before any system sleep and back to `auto` after, so system sleep sees them exactly as with stock settings.
- **Known risk being watched:** asusctl #690 reports that the 19b6 keyboard firmware can corrupt its USB context on resume from s2idle when autosuspend is enabled, especially after 2+ hours or hibernation (`invalid context state for evaluate context command`, then an xHCI reset that cascades to all USB devices). The guard above is the mitigation; the health check watches the kernel log for it.
- **Keyboard backlight:** affected. On this model `asus::kbd_backlight` is driven by `hid-asus` on the 19b6 USB device, and its writes failed with `-108` while the keyboard was autosuspended. Fixed with a `hid-asus` patch, tested A/B ([research 42](../research/42-audit-2026-11-16.md)).
- **Lock-key LEDs:** usbhid refuses to autosuspend a keyboard while any of its LEDs is lit, so Num Lock left on (a compositor `numlock` option) keeps it awake. This laptop has no numpad; leave Num Lock off.

## Verified after applying

- No process holds the two hidraw nodes (`fuser`), including after Aura and brightness writes.
- `asusctl profile get`, `leds set low/med`, `aura effect static`, `slash get` and the 80% charge limit all work, and asusd logs no errors.
- Both chips runtime-suspend within seconds of the last input (`runtime_status=suspended`) and resume on a key press.
- The health check flags (a) an asusctl package update while the override still runs the 6.5.0 build, (b) anything holding these hidraw nodes, and (c) `invalid context state` errors (#690).

## How to build the patched asusd

```
curl -LO https://github.com/OpenGamingCollective/asusctl/archive/6.5.0.tar.gz   # sha256 edceeab0…d8fca8 (Arch PKGBUILD)
tar xf 6.5.0.tar.gz && cd asusctl-6.5.0 && git init -q && git add -A && git commit -qm base
curl -L https://github.com/OpenGamingCollective/asusctl/pull/404.patch | git am
cargo build --release --locked -p asusd
sudo install -D -m 755 target/release/asusd /usr/local/libexec/asusd-pr404
# then the drop-in above, daemon-reload, restart asusd
```

## Related upstream

- asusctl #744: a G16 2024 Intel owner reports idle power far above Windows.
- asusctl #262: "High power consumption from N-Key Device" (2022).
