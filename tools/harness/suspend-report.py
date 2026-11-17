#!/usr/bin/env python3
"""suspend-report.py - turn a suspend-trace.bt log into per-cycle timelines and metrics.

usage: python3 suspend-report.py out/suspend-<stamp>.log [--timeline]

Per suspend cycle (a WAKE line ends a cycle):
  lid->backlight off   LID value=1 -> first BACKLIGHT_OFF / PIPE_DISABLE / I915_SUSPEND
  lid->firmware        LID value=1 -> machine_suspend start (kernel freeze + device suspend + s2idle entry)
  sleep                machine_suspend start -> end (CLOCK_BOOTTIME, so it includes the sleep)
  wake->first IRQ      WAKE -> first IRQ handled after firmware returned (name shows the source)
  wake->resume done    WAKE -> PM resume_console end
  wake->i915 commit    WAKE -> first pipe-A atomic commit
  wake->panel flip     WAKE -> first pipe-A flip done (frame on the panel)
  wake->client frame   WAKE -> first flip event delivered to a DRM client (niri)
Missing stages print "-" (for example no LID line if the lid was not used).
Accuracy: stamps are per-event bpf readings (~us). The lid and backlight stages depend on the
events really firing; the log is the source of truth, not this summary.
"""
import re, sys

LINE = re.compile(r"^T (\S+) (\d+)\s*(.*)$")

def parse(path):
    ev = []
    for raw in open(path, errors="replace"):
        m = LINE.match(raw.strip())
        if m:
            ev.append((m.group(1), int(m.group(2)), m.group(3)))
    return ev

def ms(a, b):
    return f"{(b - a) / 1e6:10.2f}" if a is not None and b is not None else f"{'-':>10s}"

def cycles(ev):
    """one cycle per WAKE. entry = events since the previous cycle's post-wake window closed;
    post = events after this WAKE until the next WAKE or the next lid-close (next cycle's entry)."""
    out, pos = [], 0
    for i, (tag, _, _) in enumerate(ev):
        if tag != "WAKE":
            continue
        entry = ev[pos:i]
        j = i + 1
        while j < len(ev) and ev[j][0] != "WAKE" and not (ev[j][0] == "LID" and "value=1" in ev[j][2]):
            j += 1
        out.append((entry, ev[i], ev[i + 1:j]))
        pos = j
    return out

def first(seq, tag, pred=lambda d: True, after=None):
    for t_, ts, d in seq:
        if t_ == tag and pred(d) and (after is None or ts >= after):
            return ts
    return None

def main():
    path = sys.argv[1]
    timeline = "--timeline" in sys.argv
    ev = parse(path)
    print(f"{len(ev)} events from {path}")
    for n, (entry, wake_ev, after) in enumerate(cycles(ev), 1):
        wake = wake_ev[1]
        lid = None
        for tag, ts, d in reversed(entry):
            if tag == "LID" and "value=1" in d:
                lid = ts
                break
        bl = first(entry, "BACKLIGHT_OFF", after=lid) or first(entry, "PIPE_DISABLE", after=lid) \
             or first(entry, "I915_SUSPEND", after=lid)
        ms_start = first(entry, "PM", lambda d: "machine_suspend" in d and "start=1" in d)
        ms_end = first(entry, "PM", lambda d: "machine_suspend" in d and "start=0" in d) or wake
        irq = first(after, "FIRST_IRQ")
        irq_name = next((d for t, ts, d in after if t == "FIRST_IRQ"), "")
        resume_done = first(after, "PM", lambda d: "resume_console" in d and "start=0" in d)
        commit = first(after, "WAKE_COMMIT")
        flip = first(after, "WAKE_FLIP_DONE")
        frame = first(after, "WAKE_FRAME")
        srcs = [d for t, ts, d in after if t == "WAKESRC"][:6]
        print(f"\n== cycle {n}  (wake at {wake})")
        print(f"  lid->backlight off   {ms(lid, bl)} ms")
        print(f"  lid->firmware        {ms(lid, ms_start)} ms")
        print(f"  sleep (boottime)     {ms(ms_start, ms_end)} ms")
        print(f"  wake->first IRQ      {ms(wake, irq)} ms  {irq_name}")
        print(f"  wake->resume done    {ms(wake, resume_done)} ms")
        print(f"  wake->i915 commit    {ms(wake, commit)} ms")
        print(f"  wake->panel flip     {ms(wake, flip)} ms")
        print(f"  wake->client frame   {ms(wake, frame)} ms   <- headline: wake to first frame delivered to niri")
        if srcs:
            print("  wakeup sources:      " + ", ".join(srcs))
        if timeline:
            base = lid if lid is not None else (ms_start or wake)
            print("  -- timeline (ms from " + ("lid" if lid is not None else "first entry event") + ")")
            for t, ts, d in entry + [wake_ev] + after:
                print(f"  {(ts - base) / 1e6:12.2f}  {t:18s} {d}")

if __name__ == "__main__":
    main()
