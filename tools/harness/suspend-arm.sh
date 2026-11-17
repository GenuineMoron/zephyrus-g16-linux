#!/bin/bash
# suspend-arm.sh - arm the suspend/wake/first-frame tracer BEFORE a suspend, then stop it after resume.
#
# usage:  tools/harness/suspend-arm.sh start    # arm (background, root bpftrace)
#         ... suspend the machine (lid / systemctl suspend) and resume ...
#         tools/harness/suspend-arm.sh stop     # flush and stop
#         tools/harness/suspend-arm.sh status
#         python3 tools/harness/suspend-report.py <printed log path>
#
# Output: out/suspend-<stamp>.log (events) and out/suspend-<stamp>.anchor (CLOCK_BOOTTIME and
# realtime at arm time, to line the boottime stamps up with wall-clock logs such as the journal).
# bpftrace is a normal userspace process: it is frozen during suspend and resumes with the session.
set -u
H=$(dirname "$(readlink -f "$0")")
OUT=$H/out
PAT="[b]pftrace -q $H/suspend-trace.bt"
mkdir -p "$OUT"
case "${1:-status}" in
start)
    if sudo -n pgrep -f "$PAT" >/dev/null 2>&1; then echo "already armed"; exit 1; fi
    stamp=$(date +%Y%m%d-%H%M%S)
    log=$OUT/suspend-$stamp.log
    python3 -c 'import time; print("ARM_BOOTTIME_NS", time.clock_gettime_ns(time.CLOCK_BOOTTIME), "ARM_REALTIME_NS", time.time_ns())' > "$OUT/suspend-$stamp.anchor"
    sudo -n true || { echo "needs passwordless sudo"; exit 1; }
    setsid -f sudo -n bpftrace -q "$H/suspend-trace.bt" > "$log" 2>&1 < /dev/null
    for _ in $(seq 100); do grep -q '^T ARMED' "$log" 2>/dev/null && break; python3 -c 'import time; time.sleep(0.1)'; done
    if grep -q '^T ARMED' "$log"; then
        echo "armed: $log"; cat "$OUT/suspend-$stamp.anchor"
    else
        echo "failed to arm, see $log"; cat "$log"; exit 1
    fi
    ;;
stop)
    sudo -n pkill -INT -f "$PAT" && echo "stopping (flushing)..." || echo "not armed"
    ;;
status)
    if sudo -n pgrep -f "$PAT" >/dev/null 2>&1; then echo "ARMED"; else echo "not armed"; fi
    ls -t "$OUT"/suspend-*.log 2>/dev/null | head -3
    ;;
*) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
