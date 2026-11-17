#!/usr/bin/env bash
# Minimal wake policy. The main fix is acpi.ec_no_wakeup=1 on the kernel
# cmdline, which stops the Embedded Controller waking the machine on
# battery-level / charger / thermal events - the documented cause of
# spurious s2idle wakes on modern laptops.
#
# This only additionally disables root ports that serve no wake purpose on
# a laptop that is woken by its lid or power button.
set -u
for dev in XHCI TXHC TDM0 TRP0 RP04 RP12; do
    if grep -qE "^${dev}\b.*\*enabled" /proc/acpi/wakeup 2>/dev/null; then
        echo "$dev" > /proc/acpi/wakeup 2>/dev/null && echo "disabled: $dev"
    fi
done
# Must stay enabled.
for f in /sys/devices/platform/PNP0B00:00/power/wakeup \
         /sys/devices/platform/PNP0C0D:00/power/wakeup \
         /sys/devices/platform/PNP0C0C:00/power/wakeup; do
    [ -w "$f" ] && echo enabled > "$f" 2>/dev/null
done
exit 0
