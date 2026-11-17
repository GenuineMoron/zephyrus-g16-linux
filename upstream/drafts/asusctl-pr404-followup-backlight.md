Two more findings from running this PR on the GU605MI with keyboard autosuspend on (`power/control = auto` for `0b05:19b6`). Neither is caused by the PR; both were hidden while asusd held `/dev/hidraw0` open, because hidraw's open takes `hid_hw_power(PM_HINT_FULLON)` and the keyboard never suspended.

**1. Brightness writes don't reach a suspended keyboard.** The kernel's write fails:

```
asus 0003:0B05:19B6.0001: Asus failed to set keyboard backlight: -108
```

Brightness goes through the LED class (`asus::kbd_backlight`) → hid-asus's worker → `hid_hw_raw_request()`, and hid-asus takes no runtime-PM reference for it. asusd's own `Brightness` setter uses the same path. What the user sees:
- An idle "backlight off" leaves the light on.
- Brightness changes made with the touchpad do nothing.
- The next key press resumes the keyboard, and `asus_resume()` applies the stored level, late.

**Kernel fix:** take `hid_hw_power()` around the worker's feature-report writes. With the keyboard autosuspended, I wrote four brightness levels through `/sys/class/leds/asus::kbd_backlight`:
- Stock 7.3.4 module: the keyboard stayed suspended and logged `-108` four times.
- Patched module: each write resumed the keyboard and applied, with no errors, and it autosuspended again afterwards.

The patch applies cleanly to hid.git `for-next` and will go to linux-input.

**Userspace workaround until then:** before changing the brightness, re-send `LedPower` with its current value. asusd writes it through hidraw, and the open wakes the keyboard. Re-sending `LedMode` works too, but it also re-applies asusd's stored brightness (and turns Off into Med).

**2. A lit Num Lock or Caps Lock LED stops autosuspend.** `usbhid_suspend()` returns `-EBUSY` while any keyboard LED is on (`hidinput_count_leds()`, unless `usbhid.ignoreled=1`). A compositor setting that turns Num Lock on at login (niri's `numlock`, Umbriel's `numlock_toggle`) keeps the keyboard awake all session. The GU605MI has no numpad, so on these laptops it's worth leaving that setting off. Turning Num Lock off let the keyboard autosuspend again within 2 s.

Should asusd write brightness through its own hidraw path when the kernel LED is present? That would make asusd's setter work whatever the kernel version.
