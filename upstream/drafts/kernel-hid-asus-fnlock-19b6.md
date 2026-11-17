# Note: hid-asus Fn-lock quirk reaches every 0b05:19b6 keyboard

**Where:** linux `drivers/hid/hid-asus.c` (linux-input) · **Severity:** low, cosmetic on the GU605

Commit f631011e36b8 ("HID: hid-asus: Implement fn lock for Asus ProArt P16", 2025-12) adds `QUIRK_HID_FN_LOCK` to the `USB_DEVICE_ID_ASUSTEK_ROG_NKEY_KEYBOARD2` (`0x19b6`) entries. That ID is shared by many ROG laptops, not only the ProArt P16. On each probe the driver now sends `5a d0 4e 01` ("Fn-lock on"), and toggles it on `KEY_FN_ESC`.

On a Zephyrus G16 GU605MI the keyboard ignores the command (no hardware Fn-lock: the top row always sends F1-F12, and Fn+key the printed function), and Fn+Esc sends a plain Esc, so nothing breaks. Two loose ends:

- The quirk is keyed on a USB ID that doesn't identify the ProArt; a DMI match (or `asus-wmi`'s `fnlock_default`, which the driver could honour) would keep it to the models that have the feature.
- There's no way to choose the default. Users who want media keys by default on models where it does work get Fn-lock forced on at every boot.

What G-Helper does: hardware Fn-lock only for Vivobook/Zenbook/ProArt (`IsHardwareFnLock`); on other models it emulates Fn-lock in software. On Linux the same software swap is a udev hwdb keymap (see `configs/etc/udev/hwdb.d/90-asus-g16-fnkeys.hwdb`).

Not filed; worth raising only if someone reports a 19b6 model where the forced Fn-lock does take effect unwanted.
