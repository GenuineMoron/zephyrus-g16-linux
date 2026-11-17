#!/bin/bash
# Record one standby (s2idle) cycle with full timing, using only trace-cmd
# (official package) and the kernel's ftrace. Produces <outdir>/trace.dat and
# <outdir>/report.txt; summarise with tools/analyze-standby-trace.py.
#
# Records:
#   power:suspend_resume           phase begin/end markers
#   power:device_pm_callback_*     every driver's suspend/resume callback
#   kprobe on acpi_os_sleep        every BIOS (AML) Sleep() with its length
#   function_graph (optional)      call tree under the functions you name
#
# usage: sudo tools/trace-standby.sh <outdir> [seconds=20] [graph-function ...]
# e.g.   sudo tools/trace-standby.sh traces/s2idle-1 20 pci_pm_resume_noirq nv_pm_notifier
#
# The laptop sleeps for <seconds> and wakes by itself (RTC). The suspend is
# started by writing /sys/power/state directly, so systemd sleep hooks do not
# run - this measures the kernel/firmware path only.
set -eu
out=${1:?outdir}; secs=${2:-20}; shift $(( $# > 1 ? 2 : 1 ))
T=/sys/kernel/tracing
mkdir -p "$out"
graph=()
for f in "$@"; do graph+=(-g "$f"); done
[ ${#graph[@]} -gt 0 ] && graph=(-p function_graph "${graph[@]}" --max-graph-depth 9)

grep -q '^p:kprobes/acpisleep ' $T/kprobe_events 2>/dev/null || echo 'p:acpisleep acpi_os_sleep ms=%di:u64' >> $T/kprobe_events
trap 'echo "-:acpisleep" >> $T/kprobe_events 2>/dev/null || true' EXIT
echo 0 > /sys/class/rtc/rtc0/wakealarm
sync
trace-cmd record -q -b 131072 -o "$out/trace.dat" \
    -e power:suspend_resume -e power:device_pm_callback_start -e power:device_pm_callback_end \
    -e kprobes:acpisleep "${graph[@]}" \
    -- sh -c "echo +$secs > /sys/class/rtc/rtc0/wakealarm; echo freeze > /sys/power/state" >/dev/null 2>&1
trace-cmd report -i "$out/trace.dat" > "$out/report.txt" 2>/dev/null
[ -n "${SUDO_USER:-}" ] && chown -R "$SUDO_USER": "$out"
echo "wrote $out/trace.dat and $out/report.txt"
