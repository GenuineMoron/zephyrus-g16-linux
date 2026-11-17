#!/usr/bin/env python3
"""app-launch.py - launch latency: exec -> first buffered Wayland commit -> first eDP-1 flip.

usage:  python3 app-launch.py [--runs N] [--settle S] -- <command> [args...]
e.g.    python3 app-launch.py --runs 5 -- zenity --info --timeout=2 --text=probe
        python3 app-launch.py --runs 5 -- alacritty -e true

How it works (all timestamps CLOCK_BOOTTIME ns, from bpftrace nsecs(boot)):
  bpftrace is armed first; then the app is started as your user. It records
  EXEC    sched:sched_process_exec, first exec of the app's comm after arming (= our PID)
  BUFFER  uprobe libwayland-client wl_proxy_marshal_flags / _array_flags for wl_surface.attach
          with a non-NULL buffer (opcode 1), then
  COMMIT  wl_surface.commit (opcode 6) by that PID, first one after a buffer attach
  FLIP    drm:drm_vblank_event_delivered on crtc 0 (eDP-1) after COMMIT
Reports exec->commit, commit->flip and exec->flip per run, plus min/median/max.
Accuracy: ~us for the kernel/uprobe stamps. Flip = queued to niri; photon ~ +1 vblank (4.2 ms).
Probe cost: uprobes fire on every libwayland call in every process, so the run takes a few ms
of extra CPU per run. Fine for this test; do not leave it armed with a busy session.
Needs: sudo, bpftrace. Output: out/app-launch-<comm>.bt and stdout.
"""
import argparse, os, re, signal, statistics, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = "/usr/lib/libwayland-client.so.0"

BPF = r'''
BEGIN { printf("ARMED %lld\n", nsecs(boot)); }

tracepoint:sched:sched_process_exec
/comm == "@COMM@" && @pid == 0/
{
    @pid = pid;
    printf("EXEC %lld %d\n", nsecs(boot), pid);
}

uprobe:@LIB@:wl_proxy_marshal_flags
/pid == @pid && @pid != 0/
{
    if (str(*(uint64 *)(*(uint64 *)arg0)) == "wl_surface") {
        if (arg1 == 1 && arg5 != 0) { @buffered = 1; }
        if (arg1 == 6 && @buffered == 1 && @commit == 0) {
            @commit = 1;
            printf("COMMIT %lld\n", nsecs(boot));
        }
    }
}

uprobe:@LIB@:wl_proxy_marshal_array_flags
/pid == @pid && @pid != 0/
{
    if (str(*(uint64 *)(*(uint64 *)arg0)) == "wl_surface") {
        if (arg1 == 1 && arg5 != 0 && *(uint64 *)arg5 != 0) { @buffered = 1; }
        if (arg1 == 6 && @buffered == 1 && @commit == 0) {
            @commit = 1;
            printf("COMMIT %lld\n", nsecs(boot));
        }
    }
}

tracepoint:drm:drm_vblank_event_delivered
/@commit == 1 && @flip == 0 && args.crtc == 0/
{
    @flip = 1;
    printf("FLIP %lld\n", nsecs(boot));
}
'''

def run_once(argv, settle, outdir):
    comm = os.path.basename(argv[0])[:15]
    script = os.path.join(outdir, f"app-launch-{comm}.bt")
    with open(script, "w") as f:
        f.write(BPF.replace("@COMM@", comm).replace("@LIB@", LIB))
    bt = subprocess.Popen(["sudo", "-n", "bpftrace", "-q", script],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = []
    def reader():
        for l in bt.stdout:
            lines.append(l.strip())
    threading.Thread(target=reader, daemon=True).start()
    t0 = time.time()
    while not any(l.startswith("ARMED") for l in lines):
        if time.time() - t0 > 15 or bt.poll() is not None:
            bt.kill()
            raise SystemExit("bpftrace did not arm: " + "\n".join(lines))
        time.sleep(0.05)
    app = subprocess.Popen(argv)
    try:
        app.wait(timeout=30)
    except subprocess.TimeoutExpired:
        app.kill()
    time.sleep(settle)  # let the first flip land
    subprocess.run(["sudo", "-n", "pkill", "-INT", "-f", f"bpftrace -q {script}"])
    bt.wait(timeout=20)
    t = {}
    for l in lines:
        parts = l.split()
        if len(parts) >= 2 and parts[0] in ("EXEC", "COMMIT", "FLIP", "ARMED"):
            t.setdefault(parts[0], int(parts[1]))
    return t, app.pid

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    argv = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not argv:
        ap.error("give the command after --")
    outdir = os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)

    rows = []
    for i in range(a.runs):
        t, pid = run_once(argv, a.settle, outdir)
        if "EXEC" not in t or "COMMIT" not in t:
            print(f"run {i+1}: no exec/commit captured ({sorted(t)}); command may not be a Wayland client")
            continue
        ex = (t["COMMIT"] - t["EXEC"]) / 1e6
        fl = (t["FLIP"] - t["COMMIT"]) / 1e6 if "FLIP" in t else float("nan")
        tot = (t["FLIP"] - t["EXEC"]) / 1e6 if "FLIP" in t else float("nan")
        rows.append((ex, fl, tot))
        print(f"run {i+1}: pid={pid} exec->commit {ex:8.2f} ms   commit->flip {fl:6.2f} ms   exec->flip {tot:8.2f} ms")
    if rows:
        for idx, name in enumerate(["exec->commit", "commit->flip", "exec->flip"]):
            vals = [r[idx] for r in rows if r[idx] == r[idx]]
            if vals:
                print(f"{name:14s} min {min(vals):8.2f}  median {statistics.median(vals):8.2f}  max {max(vals):8.2f}  (n={len(vals)}) ms")

if __name__ == "__main__":
    main()
