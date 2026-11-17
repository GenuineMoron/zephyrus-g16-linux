#!/usr/bin/env python3
"""boot-milestones.py - boot-to-desktop timeline from the journal (system + user manager).

usage:
  python3 boot-milestones.py                      # current boot (journalctl -b)
  python3 boot-milestones.py --boot-id <id>       # a previous boot
  python3 boot-milestones.py --cursor-file F      # only entries after the cursor saved in F
  python3 boot-milestones.py --save-cursor F      # write the current journal cursor to F and exit
                                                  #   (run this before a session restart / login test)

Times are __MONOTONIC_TIMESTAMP (CLOCK_MONOTONIC since boot, us): per-boot and immune to
wall-clock steps (NTP, RTC). Monotonic stops across suspend, so do NOT use this across a suspend;
use __REALTIME_TIMESTAMP (printed as the last column) for that.
Milestones are log lines, so they measure "the component said it did X", not pixels on screen.
"""
import argparse, json, re, subprocess, sys

MILESTONES = [
    ("initrd->root switch",  "system", r"^Reached target Switch Root\.$"),
    ("greetd up",            "system", r"^Started Greeter daemon\.$"),
    ("greeter first frame",  "system", r"presented first frame"),
    ("greeter login submit", "system", r"greetd: create_session for"),
    ("greeter auth ok",      "system", r"authentication successful"),
    ("graphical.target",     "system", r"^Reached target Graphical Interface\.$"),
    ("niri wayland socket",  "user",   r"listening on Wayland socket"),
    ("niri IPC up",          "user",   r"IPC listening on"),
    ("niri eDP-1 connected", "user",   r"new connector: eDP-1"),
    ("noctalia unit start",  "user",   r"^Started Noctalia desktop shell"),
    ("noctalia bar on eDP-1","user",   r"\[bar\] creating #0.*eDP-1"),
    ("noctalia notif. bus",  "user",   r"listening on org\.freedesktop\.Notifications"),
    ("xwayland :0 ready",    "user",   r"Connected to Xwayland"),
]

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

def message(d):
    """journald stores MESSAGE as a byte array when it has ANSI escapes or non-UTF-8 bytes."""
    m = d.get("MESSAGE", "")
    if isinstance(m, list):
        m = bytes(m).decode("utf-8", "replace")
    return ANSI.sub("", m) if isinstance(m, str) else ""

def journal(scope, args):
    cmd = ["journalctl", "-o", "json", "--no-pager"]
    if scope == "user":
        cmd.append("--user")
    if args.cursor_file:
        cur = open(args.cursor_file).read().strip()
        cmd += ["--after-cursor", cur]
    elif args.boot_id:
        cmd += ["-b", args.boot_id]
    else:
        cmd += ["-b"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    for line in out.splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot-id")
    ap.add_argument("--cursor-file")
    ap.add_argument("--save-cursor")
    a = ap.parse_args()
    if a.save_cursor:
        cur = subprocess.run(["journalctl", "-n0", "--show-cursor", "--no-pager"],
                             capture_output=True, text=True).stdout.strip().split("\n")[-1]
        cur = cur.replace("-- cursor: ", "")
        open(a.save_cursor, "w").write(cur + "\n")
        print("cursor saved to", a.save_cursor)
        return

    hits = {}  # name -> (mono_us, realtime_us)
    startup = None
    for scope in ("system", "user"):
        for d in journal(scope, a):
            msg = message(d)
            if msg.startswith("Startup finished in") and "(kernel)" in msg:
                startup = (msg, int(d["__MONOTONIC_TIMESTAMP"]), int(d["__REALTIME_TIMESTAMP"]))
            for name, src, pat in MILESTONES:
                if src != scope or name in hits:
                    continue
                if re.search(pat, msg):
                    hits[name] = (int(d["__MONOTONIC_TIMESTAMP"]), int(d["__REALTIME_TIMESTAMP"]))

    import datetime
    ref = hits.get("greeter auth ok", (None, None))[0]
    print(f"{'milestone':24s} {'mono_s':>9s} {'vs auth_s':>9s}  realtime (UTC)")
    for name, _, _ in MILESTONES:
        if name in hits:
            m, r = hits[name]
            ts = datetime.datetime.fromtimestamp(r / 1e6, datetime.timezone.utc).strftime("%H:%M:%S")
            rel = f"{(m - ref)/1e6:+9.3f}" if ref is not None else " " * 9
            print(f"{name:24s} {m/1e6:9.3f} {rel}  {ts}")
        else:
            print(f"{name:24s} {'(not found)':>9s}")
    if startup:
        print("\nsystemd:", startup[0])
    else:
        print("\nsystemd: (no 'Startup finished' line in this journal window)")
    print("\nnote: 'greeter first frame' includes the greeter's own first-scene render; check the 'scene draw took' line in the journal.")

if __name__ == "__main__":
    main()
