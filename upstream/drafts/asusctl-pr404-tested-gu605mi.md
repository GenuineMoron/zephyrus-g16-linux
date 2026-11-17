Tested on a **ROG Zephyrus G16 GU605MI** (2024, Core Ultra 9 185H, RTX 4070; BIOS 329, EC R3.27), CachyOS, kernel 7.3.3, asusctl 6.5.0 + this PR (both commits apply cleanly to the 6.5.0 tarball).

**Before (stock 6.5.0):** asusd holds `/dev/hidraw0` (0b05:19b6, N-KEY) and `/dev/hidraw1` (0b05:193b, Slash) open. Both devices had `runtime_suspended_time = 0` for the whole boot, even with `power/control=auto`. The xHCI then keeps reporting a ~51 µs LTR, which is below the package C10 threshold.

**After (this PR + `power/control=auto` on both):** `fuser` shows no holders, including after `asusctl leds set`, `asusctl aura effect static` and `asusctl slash get`. Both devices runtime-suspend about 2 s after the last input and resume on a key press. Profile switching, keyboard brightness (asus-nb-wmi on this model, so the hid-asus `-108` issue doesn't apply), Aura colour, Slash state and the charge limit all keep working, and asusd logs no errors. Typing has been normal over a few hours of use, with no lost first key press.

**Effect** (screen off, on battery, 20 s turbostat windows, alternated):

| | Pk%pc10 | PkgWatt | SysWatt (psys) |
|---|---|---|---|
| asusd holding both nodes | 0.4% | 2.02 W | 3.23 W |
| nodes released, devices suspended | 65–67% | 1.69–1.70 W | 2.38–2.47 W |
| asusd stopped, devices `on` (control) | 0.4% | 1.97 W | 3.04 W |

So the package C10 blocker is the devices being held at full power, not asusd's own activity. That's about 0.8 W saved at screen-off idle on this model.

**About #690 (19b6 firmware corrupting its USB context on resume while autosuspended):** as a guard we use a systemd sleep hook. It sets both devices to `power/control=on` (resumed) in `pre` and back to `auto` in `post`, so system sleep sees them exactly as with stock settings. I haven't put it through system sleep yet with autosuspend enabled and will report back after a few nights. Something like this might be worth shipping alongside the PR for users who enable autosuspend:

```sh
#!/bin/sh
# /usr/lib/systemd/system-sleep/10-asus-kbd-autosuspend
set_ctrl() { for d in /sys/bus/usb/devices/*; do
    [ "$(cat "$d/idVendor" 2>/dev/null)" = 0b05 ] || continue
    case "$(cat "$d/idProduct" 2>/dev/null)" in 19b6|193b) echo "$1" > "$d/power/control" ;; esac
done; }
case "$1" in pre) set_ctrl on ;; post) set_ctrl auto ;; esac
```

plus a udev rule to enable autosuspend at boot:

```
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0b05", ATTR{idProduct}=="19b6|193b", TEST=="power/control", ATTR{power/control}="auto"
```
