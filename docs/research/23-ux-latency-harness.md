# 23 UX latency harness (wave 2, deep dive)

Goal: measure perceived latency (wake to frame, launch latency, boot to desktop, frame pacing) so each
optimisation can be shown to help. All tools live in [`../../tools/harness/`](../../tools/harness/). Usage is in the header
comment of each file. Nothing here suspends, reboots, changes config, installs, or touches the dGPU
(NVIDIA was checked only via `power/runtime_status`, which reads `suspended` before and after the launch tests).

## Tools

| file | measures | clock | accuracy / caveat |
|---|---|---|---|
| `frame-pacing.bt` | eDP-1 flips/s, flip interval histogram, skipped vblanks, pipe-update critical section, input to next flip | monotonic (no suspend in window) | per-event bpf stamps (ns); "flip" = event queued to niri, photon about +1 vblank (4.2 ms at 240 Hz) |
| `suspend-trace.bt` + `suspend-arm.sh` + `suspend-report.py` | lid to backlight off to freeze to firmware to wake to first IRQ to first panel flip to first frame delivered to niri | CLOCK_BOOTTIME (keeps counting across suspend), anchor file maps to realtime | kernel view only; ACPI wake IRQ not visible (FIRST_IRQ = first IRQ after firmware returns); logind not traced (only systemd-sleep hook exec) |
| `app-launch.py` | exec to first buffered `wl_surface.commit` to first flip on eDP-1, per app | boottime (bpf) | uprobe on libwayland-client (`wl_proxy_marshal_flags` and `_array_flags`, covers C and Rust clients); exec to commit includes the app's own startup, which is the number to track |
| `boot-milestones.py` | boot to desktop milestones from system and user journal; systemd "Startup finished" line; `--save-cursor` / `--cursor-file` for after-cursor windows | journal `__MONOTONIC_TIMESTAMP` (per boot) and `__REALTIME_TIMESTAMP` | log lines, so "component says it did X", not pixels; do not use monotonic across a suspend |

Probe check: `suspend-trace.bt` compiles and attaches 29 probes; `frame-pacing.bt` runs; `app-launch.py` runs on
zenity and alacritty; the arm/stop cycle of `suspend-arm.sh` works.

Kernel facts used (verified): `drm:drm_vblank_event_delivered` (crtc, seq); `i915:intel_pipe_update_start/end`,
`intel_crtc_flip_done`, `intel_pipe_update_vblank_evaded` (pipe_name is a char, compare with 65 = 'A');
`power:suspend_resume` (action, start, val); `irq:irq_handler_entry`; `power:wakeup_source_activate`;
`sched:sched_process_exec`; fentry `vmlinux:input_event`; fentry i915 `intel_display_driver_pm_suspend(_late)`,
`intel_display_driver_pm_resume_early`, `*disable_backlight`, `intel_backlight_disable`. eDP-1 is i915 pipe A =
DRM crtc 0 (from `i915_display_info`). The lid is `Lid Switch` (EV_SW), so `input_event` type 5 code 0 is the lid.
`nsecs(boot)` works in bpftrace 0.27 (`%lld` format; `%d` truncates).

## Sample results (normal operation, 2026-11-14)

**Frame pacing, idle desktop (20 s):** 4 to 8 flips/s (niri presents only on damage). Min interval 4.12 ms
(240 Hz). Intervals bimodal: about 4.2 ms and about 8.3 ms, the latter a skipped vblank. Earlier 15 s run:
194 flips, 18 skipped-vblank flips (<12 ms apart). Pipe update critical section avg 25 to 26 us (range 18 to 36 us).
`vblank_evaded` fires exactly once per flip (122 of 122), so it is a commit counter, not a jank signal.
Input to flip: not measured (no input during the window; the `inputs` counter reads 0). Re-run with the mouse moving.
Interpreting skips: a late commit that slips one vblank is normal at 240 Hz under light load; a count that scales with
animation, not idleness, is the signal to chase.

**GPU (intel_gpu_top, 2 samples):** idle RC6 39 to 65 percent, GPU 0.18 to 0.39 W, package 3.7 to 8 W.

**App launch (exec to first buffered commit, then commit to eDP-1 flip):**
- zenity `--info --timeout=2` (GTK3), 3 runs: exec to commit 337 / 344 / 357 ms (median 344); commit to flip 3.9 / 6.3 / 9.3 ms.
- alacritty `-e true`, 3 runs: exec to commit 134 / 138 / 147 ms (median 138); commit to flip 1.2 / 2.8 / 7.7 ms.
- The dGPU stayed runtime-suspended during these runs.

**Boot to desktop (current boot, from journal):**

| milestone | mono s | vs login (s) |
|---|---|---|
| firmware 6.93 + loader 3.05 + kernel 0.45 + initrd 2.09 + userspace 4.16 = 16.67 s | | |
| initrd switch root | 2.43 | |
| greetd up | 6.17 | |
| greeter first frame | 9.03 | |
| greeter login submit | 23.97 | -0.08 |
| greeter auth ok | 24.05 | 0 |
| niri Wayland socket and IPC | 24.79 | +0.74 |
| noctalia unit start | 24.89 | +0.84 |
| noctalia bar on eDP-1 | 25.40 | +1.35 |
| xwayland :0 ready | 30.04 | +5.99 |

Findings:
1. The greeter's first scene draw took 394 ms ("scene draw took 394.1ms", then "presented first frame"). That is the
   largest single cost before the greeter is usable. Likely first-use shader or GL setup; check on the next boots.
2. Login to bar is 1.35 s, so the boot-to-desktop cost after the human step is already small. The greeter waits 15 s
   for input, which dominates the overall wall time but is not a system cost.
3. Every GTK launch logs `gtk-dark.css:3792` parse errors (known) and a `GSK_RENDERER=ngl` deprecation warning
   ("renamed to gl"). Set in `~/.config/environment.d/50-gtk-gl-renderer.conf`. Switching to `gl` is probably
   right, but I did not verify that the dGPU stays asleep under `gl`.
4. noctalia idle "screen-off" (120 s) is a second backlight-off path. A BACKLIGHT_OFF with no LID line is idle
   blanking, not a suspend.

**Suspend trace:** not exercised (no suspend in this pass). The parser was checked on a synthetic log with known values
(wake to client frame 260 ms, sleep 7000 ms). That is a parser test only. Expect a real measurement on the next
suspend.

## How to use around a suspend

```
H=<repo>/tools/harness
$H/suspend-arm.sh start          # arms in background (needs sudo); prints log + anchor
# suspend via lid or `systemctl suspend`, let it resume normally
$H/suspend-arm.sh stop           # flushes; the log is only written at stop
python3 $H/suspend-report.py $H/out/suspend-<stamp>.log --timeline
python3 $H/boot-milestones.py    # after a reboot, not needed for suspend
```

The anchor file (`out/suspend-<stamp>.anchor`) gives CLOCK_BOOTTIME and realtime at arm time. Use it to match
boottime stamps to wall-clock logs, for example `journalctl -k -b -o short-precise | grep "suspend exit"`.
`frame-pacing.bt` is standalone (`sudo timeout 30 bpftrace frame-pacing.bt`); run it during a light-load window
and move the mouse to get input-to-flip samples.

Limits and risks:
- bpftrace is a userspace process, so it is frozen with the session and resumes. Kernel events buffer in the
  ring; a flood of wakeup sources could drop some. Wakeup sources are capped at 50 per wake.
- The uprobes in `app-launch.py` fire on every libwayland call in every process. Fine for a test, not for
  leaving armed.
- Not yet covered: ACPI wake GPIO identity, logind's PrepareForSleep timing (use journal), input-to-photon.
- "Frame" means the flip event reaching niri (eDP-1 at 240 Hz). Add about one vblank for scanout.
