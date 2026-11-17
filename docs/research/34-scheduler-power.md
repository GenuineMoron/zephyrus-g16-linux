# 34 - sched_ext (scx_lavd / scx_bpfland) and intel_lpmd for battery drain

Status: research and planning only. No scheduler started, no setting changed.
Date: 2026-11-15. Machine: Core Ultra 9 185H (MTL-H), kernel 7.3.3-1-cachyos.

Labels: **PROVEN** = read in source/doc (file:line or URL). **INFERRED** = reasoning from proven facts, or a claim not yet measured here. **UNVERIFIED** = seen only in a secondary source I could not open.

Upstream sources saved locally (fetched from `sched-ext/scx` main, 2026-11-15; local working copy, not in the repo):
- `scheds_rust_scx_lavd_src_main.rs`, `..._src_bpf_power.bpf.c`, `..._src_bpf_main.bpf.c`, `..._src_bpf_lavd.bpf.h`, `..._src_bpf_intf.h`, `..._src_cpu_order.rs`, `..._README.md`
- `scheds_rust_scx_bpfland_src_main.rs`, `..._README.md`
- `scheds_rust_scx_utils_autopower.rs`

Not fetched: `scheds/rust/scx_lavd/src/bpf/cpu_order.bpf.c` and `cpuperf.bpf.c` (404 at those paths; the BPF side of CPU order is in `lavd.bpf.h` and `power.bpf.c`).

---

## 0. Local state (verified 2026-11-15)

| Item | Value | Source |
|---|---|---|
| CPU map | P-cores with HT: cpu0-11 (max 5.1/4.8 GHz). E-cores: cpu12-19 (3.8 GHz). LP-E: cpu20, 21 (2.5 GHz, own cluster 64) | `/sys/devices/system/cpu/cpu*/topology`, `cpufreq/cpuinfo_max_freq` (PROVEN) |
| Driver / EPP | intel_pstate active, EPP = `power` on all 22 CPUs | sysfs (PROVEN) |
| Platform profile | `quiet` | `/sys/firmware/acpi/platform_profile` (PROVEN) |
| sched_ext | `disabled` | `/sys/kernel/sched_ext/state` (PROVEN) |
| scx packages | scx-scheds 1.1.4-2, scx-tools 1.1.3-1.1 (scx_loader, scxctl), scx-manager 1.16.0-1. Installed 2026-11-11 | pacman (PROVEN) |
| intel_lpmd | enabled and running since 09:14 today. Preset: disabled. Active config `intel_lpmd_config_F6_M170.xml` | systemctl, /etc/intel_lpmd (PROVEN) |

Correction to `07-asus-cachyos-power-stack.md` and `12-performance.md`: they say scx_loader is not installed. It is now installed (scx-tools). The scheduler is still not running.

---

## 1. scx_lavd

### 1.1 Modes and how they are picked (PROVEN)

Options (`scx_lavd --help`, `main.rs:85-122`):
- `--autopilot`: picks performance / balanced / powersave from system load. **This is the default when no mode flag is given** (`main.rs` `can_autopilot`, the "When no option is specified" help text).
- `--autopower`: picks the mode from the active power profile (`main.rs:94-101`).
- `--performance`, `--balanced`, `--powersave`: fixed modes.
- `--no-core-compaction`: every online CPU stays active.

The autopower mapping comes from `scx_utils::autopower::fetch_power_profile`, which reads EPP from `policy0` (`scheds_rust_scx_utils_autopower.rs:46-59`):

| EPP on policy0 | PowerProfile | lavd mode (`main.rs:1103-1105`) |
|---|---|---|
| `performance` | Performance | PERFORMANCE |
| `balance_performance` | Balanced{power:false} | BALANCED |
| `balance_power` | Balanced{power:true} | BALANCED |
| `power` | Powersave | POWERSAVE |

Only when PPD is absent does the autopower fallback use `power-saver` / `balanced` / `performance` (`autopower.rs:62-68`). PPD is masked on this box, so EPP is what counts. asusd sets EPP per profile (notes 07: Quiet -> `power`, Balanced -> `balance_power`, Performance -> `performance`). So **autopower on this box would follow the asusd profile**. Right now EPP is `power`, so lavd autopower would pick POWERSAVE (INFERRED: follows from the mapping plus the current EPP reading).

### 1.2 What each mode does (PROVEN)

`power.bpf.c:569-625` (`do_set_power_profile`):
- PERFORMANCE: `no_core_compaction = true`, `is_powersave_mode = false`. All CPUs active.
- BALANCED: core compaction on, `is_powersave_mode = false`.
- POWERSAVE: core compaction on, `is_powersave_mode = true`.

Core compaction (`calc_nr_active_cpus`, `power.bpf.c:242-290`): computes required capacity from average utilization plus 25% headroom (`calc_required_capacity`). It then walks the CPU preference order and counts how many CPUs are needed to cover that capacity. Without an energy model (`no_use_em`), `pco_idx` is 0 in powersave and max otherwise. Only the first N CPUs in the preference order are active. Other CPUs are not used for new work.

CPU preference order (`cpu_order.rs:217-273`):
- Powersave with big/little (`has_biglittle` true): prefers the LITTLE core with the larger cache first (`cpu_order.rs` case 2).
- Performance: prefers higher capacity first (cases 3 and 4).

**Hybrid handling on this box (INFERRED):** `has_little_cores()` is topology based, and LP-E cpu20/21 (2.5 GHz) are clearly smaller than E-cores (3.8 GHz) and P-cores. So in POWERSAVE, the LP-E cores would be tried first, then E-cores, and P-cores last. That is good for idle power and bad for any single-thread burst, such as a game's main thread. Confirm by running `scx_lavd --log-level=debug` for a few seconds (the debug output prints the CPU classification, `main.bpf.c:2782-2784`).

There is also a 1 s user-space loop (`main.rs` `run`), and the scheduler reads the profile again every second when `--autopower` is set.

### 1.3 Published measurements

- **Proven in source only:** lavd's README says it was "initially motivated by gaming", aims to "improve interactivity and reduce stuttering", and is "production ready" for hybrid systems (`scheds_rust_scx_lavd_README.md`). It gives no power figures.
- **UNVERIFIED (secondhand):** LWN reports Changwoo Min saying at LPC 2025 that LAVD gave higher frame rates than EEVDF "while using slightly less power and with fewer stutters" (lwn.net/SubscriberLink/991205). I could not open the talk or LWN text.
- **UNVERIFIED:** Phoronix articles on LAVD gaming and LPMD gaming exist (phoronix.com/news/LAVD-Scheduler-Linux-Gaming, /news/Intel-LPMD-Linux-Gaming). Both returned HTTP 403 when fetched, so no numbers were read.
- **UNVERIFIED:** A CachyOS forum post says performance flags use maximum power and may not suit battery devices (discuss.cachyos.org, topic 2890).
- **No independent battery-life measurement of lavd POWERSAVE on MTL was found.** The "less power" claim above is the only one and is secondhand.

---

## 2. scx_bpfland and other battery-aware schedulers

### 2.1 scx_bpfland (PROVEN)

- `--throttle-us` / `-t`: "Throttle the running CPUs by periodically injecting idle cycles. This option can help extend battery life on portable devices..." Default 0 = off (`scheds_rust_scx_bpfland_src_main.rs`, help text).
- `--primary-domain`: `performance` (fastest CPUs first), `powersave` (slowest first), `auto` (powersave under the power-saver profile, else performance), `turbo`, `cores`, `all` (`main.rs:83-94`, `preference()` at `main.rs:191-201`).
- `auto` reads the profile from **power-profiles-daemon over D-Bus first** (`power_profile()`, `main.rs:210-214`). Only if that returns Unknown does it fall back to EPP. PPD is masked here, so `auto` will use EPP (INFERRED from notes 07 and the code).
- `--idle-resume-us` (`-I`): sets CPU idle QoS. Default -1 (disabled). Lower values keep CPUs out of deep idle, which costs power and helps latency (help text).
- Default `--slice-us` is 1000 and `--slice-us-lag` is 40000 (help text).

### 2.2 Others

- `scx_cosmos`, `scx_rustland`, `scx_flash`: no battery-specific mode found in the code I looked at. Not checked further.
- scx_loader modes: `auto`, `gaming`, `lowlatency`, `powersave`, `server` (per-scheduler `[scheds.X]` in `/usr/share/scx_loader/config.toml`; the file comments show the names). A `powersave_mode` exists for schedulers that define one. Exact flags per scheduler were not enumerated (INFERRED: `scxctl modes` lists them).

---

## 3. intel_lpmd

### 3.1 What LP mode does on MTL (PROVEN from shipped docs)

Local docs: `/usr/share/doc/intel-lpmd/README.md`, `WLT_proxy.md`, and `man intel_lpmd`.
- LP mode "puts the system into Low Power Mode by activating the power-efficient CPUs and disabling the rest, and restores ... by activating all CPUs" (README intro).
- Three things it can do (`man intel_lpmd`): choose the CPU set, choose EPP/EPB, pick the SoC power slider.
- Modes (`intel_lpmd_config_F6_M170.xml`, `<Mode>1</Mode>`): 0 = cgroup v2, 1 = cgroup v2 isolate, 2 = CPU idle injection (config comments).
- Dynamic CPU selection is **off by default**. The README says this is so benchmarks that only use the CPUs present at start do not break (README "Dynamic CPU Selection").
- WLT proxy (`WLT_proxy.md`): replaces hardware WLT hints with a software state machine on CPU load (C0 residency, spikes). It sets EPP/EPB. Per the doc, it "applies only in balanced power profile" and needs `BalancedDef` set to 0 (auto) or 1.

### 3.2 Current config and why it does nothing much (PROVEN + INFERRED)

Active M170 config values:
- `lp_mode_cpus` empty, `Mode` 1.
- `PerformanceDef`, `BalancedDef`, `PowersaverDef` all -1 (force off).
- `WLTHintEnable` 1, `WLTProxyEnable` 1.
- `util_entry_threshold` and `util_exit_threshold` are empty, so the util monitor is off.
- `IntelPstateMode` 0.

So LP-mode force-entry never happens. The WLT proxy is enabled, but the doc says it only acts in the balanced profile with BalancedDef auto. With BalancedDef at -1, its EPP/EPB changes are INFERRED to be inactive. The live EPP is `power`, which matches the quiet profile, so there is no visible lpmd override. **Unknown:** whether WLT proxy is writing EPP at all. Check with `journalctl -u intel_lpmd -b` at debug level, or by reading EPP over a profile change (notes 07 already lists this test).

### 3.3 Why CachyOS/Arch ship it disabled (PROVEN where cited)

- The README says the installed configs "disable lpmd by default" and "serve as templates of best practices" (README "Before You Start").
- The systemd preset is disabled (`systemctl` shows `preset: disabled`). The package is CachyOS 0.1.1-2.
- Fedora bug 2338017 asks for intel-lpmd to be enabled by default on workstations. The request implies it is not (`bugzilla.redhat.com/show_bug.cgi?id=2338017`).
- The cgroup-restriction reason above is the proven rationale.

### 3.4 Published measurements / known issues

- **UNVERIFIED (blog, single author):** engineered.at "squeezing every watt out of a meteor lake linux laptop" reports idle falling from roughly 8-10 W to about 3.5 W when intel-lpmd is combined with explicit low-power E-core selection. Also about 93% S0i2.2 residency and an estimated 8-9 hours of battery. These are the author's estimates.
- **UNVERIFIED (blog):** blog.fsck.com/2026/03/30/linux-power-tuning-meteor-lake reports about 4 W idle and says deep-sleep (S0ix) problems were the bigger issue.
- **Known bug (PROVEN, GitHub issue):** intel-lpmd 0.1.0, "AUTO mode is not reliably restored after suspend/resume or a power-profile switch", leading to higher idle draw (github.com/intel/intel-lpmd/issues/106, reached via search snippet).
- **Local log issue (PROVEN, notes 14):** lpmd spams `read_aperf_mperf_tsc_perf failed for cpu = N` and correlates with hibernation attempts. Not measured here.
- No independent controlled A/B of lpmd on MTL was found.

---

## 4. Risks

| Area | Risk | Basis |
|---|---|---|
| Gaming / Proton / gamemode | POWERSAVE and BALANCED compact onto LP-E/E-cores first. Single-thread game threads can land on the slow cores, costing frame time. PERFORMANCE mode is the gaming-safe mode. | PROVEN compaction logic (power.bpf.c:242-290, cpu_order.rs:217-273). Frame impact INFERRED. |
| Gamemode | gamemode sets nice and governor. Whether lavd honors nice/`SCHED_*` the same way as EEVDF was not checked. | INFERRED. Check lavd's `--help` on nice (not read). |
| NVIDIA / Proton | sched_ext does not touch the GPU driver or the RTD3 path. The main concern is CPU placement for the render thread, as above. | INFERRED. |
| Audio xruns | PipeWire runs RT/rtkit. sched_ext ranks below RT/DL classes (kernel sched_ext docs), so RT audio should preempt it. Xruns under compaction would come from wakeup placement. | INFERRED. Needs a test (`pw-top` xrun counters, `journalctl`). |
| intel_lpmd interaction | lpmd writes EPP/EPB (WLT proxy) and CPU sets (cgroup isolate). lavd does not write EPP, it only reads it (autopower). Two CPU-set managers at once could fight over cpusets. Keep lpmd LP mode off (current) during the test. | PROVEN lavd is read-only on EPP (`autopower.rs:46-59`). Fight risk INFERRED. |
| EPP / asusd | Changing the asusd profile flips EPP and therefore lavd autopower mode mid-test. Freeze the profile during each run. | PROVEN mapping. |
| Stability | sched_ext scheduler crash falls back to EEVDF. Kernel docs say the scheduler is unloaded on error. | INFERRED. Kernel doc not fetched. |

---

## 5. A/B measurement protocol (manual, hands-off)

Goal: decide whether lavd (autopower/powersave) or bpfland `-t` lowers idle-on-battery draw without hurting responsiveness or gaming. Pre-register the criteria below before running.

### 5.1 Preconditions (set once, before the test)

1. On battery (AC unplugged). Screen brightness fixed (write one value, e.g. `brightnessctl set 40%`, and record it).
2. Freeze the asusd profile for the whole run: `asusctl profile get` should say Quiet. Record it. Do not change it during a run.
3. Kill any browser or game. Use an empty workspace (niri), notifications off, `systemctl --user stop` for any non-essential timers.
4. Record the current EPP, platform_profile, lpmd state, and kernel:
   ```
   cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
   cat /sys/firmware/acpi/platform_profile
   systemctl is-active intel_lpmd
   cat /sys/kernel/sched_ext/state
   uname -r
   ```
5. Check that sched_ext is disabled (`disabled`), and that `scx_lavd --help` and `scxctl --help` still work (they parse args and load nothing).

### 5.2 Switch commands and restore

The direct binary is simpler and fully reversible. Run it inside its own unit so it can be stopped cleanly:

Start lavd (powersave via autopower):
```
sudo systemd-run --unit=scx-ab --scope /usr/bin/scx_lavd --autopower --log-level=info
```
Verify it loaded: `cat /sys/kernel/sched_ext/state` should show `enabled`, and `cat /sys/kernel/sched_ext/root/ops` should show `lavd` (INFERRED paths; confirm on first run).

Start bpfland with throttle off, for the second condition:
```
sudo systemd-run --unit=scx-ab --scope /usr/bin/scx_bpfland --primary-domain auto
```
(Use `-t 20000` for the throttle variant only if a separate condition is wanted. Keep it out of the first pass.)

Stop and restore to EEVDF:
```
sudo systemctl stop scx-ab.scope    # or: sudo pkill -INT scx_lavd / scx_bpfland
cat /sys/kernel/sched_ext/state     # must read: disabled
```
Verify the restore: EPP unchanged from the recorded value, `intel_lpmd` still active and unchanged, no `scx` process left (`pgrep -a scx_`).

Alternative with scxctl (not used in the first pass, flags unverified): `scxctl start --help`, then `scxctl stop`. Confirm the exact flags before using.

### 5.3 Conditions (A/B/C/D)

- A: EEVDF (baseline, sched_ext disabled). Keep lpmd LP mode off (current config).
- B: scx_lavd `--autopower` (follows EPP, here = powersave).
- C: scx_lavd `--performance` (control: if C is worse than A in power, something else is wrong).
- D: scx_bpfland `--primary-domain auto` (no throttle).

Keep the same lpmd config for all conditions. An lpmd on/off variant is a separate pass, run only if B or D shows a gain.

### 5.4 Workloads (each run, same order within a repeat)

1. **Idle, screen on, empty workspace:** 10 min (after a 2 min warm-up). Primary target.
2. **Light video playback:** a fixed local H.264 file in `mpv --no-audio --fs` (or with audio, to test xruns), 10 min. Audio on is the xrun test.
3. **Light web:** Firefox with a fixed set of 5 pages, scripted scroll with `xdotool` (or skip if no automation is possible; record as not run).
4. **Compile burst:** a fixed build, e.g. `make -j"$(nproc)" -C <fixed tree>` (clean build dir each time), 3 repeats. Records wall time and energy. Judge throughput loss here.
5. **Responsiveness:** `cyclictest -m -p95 -D 60 -q` for wakeup latency. Plus a scripted keypress latency test if feasible. Otherwise record as not run.
6. **Gaming (only if one fixed title can be run):** a fixed benchmark scene, `MangoHud` frame log, 3 repeats. Compare 99th percentile frame time and 1% low, not average FPS. Skip if the title cannot be scripted.

### 5.5 Metrics

- **Power:** `sudo turbostat --quiet --interval 10 --show Busy%,Bzy_MHz,PkgWatt,SysWatt,Pk%pc10,CPU%c6 --out <file>`. Record mean PkgWatt, mean SysWatt, mean Pk%pc10. Battery `energy_now` delta over the run is a cross-check (`/sys/class/power_supply/BAT*/energy_now`).
- **Per-core busy%:** from turbostat per-CPU rows. Record the share of busy time on cpu0-11 (P), cpu12-19 (E), and cpu20-21 (LP-E). The LP-E share is the number that tells whether powersave uses the right cores.
- **Wakeups:** `perf stat -a -e context-switches sleep 60` (permissions may need `kernel.perf_event_paranoid` checked; if denied, record as not run).
- **Responsiveness:** cyclictest max and p99 latency (us). Input latency from a scripted test, if available.
- **Frame pacing (gaming):** MangoHud log, p99 frame time.
- **Throughput:** compile wall time.
- **Audio:** xrun count (`pw-top` or pipewire log), must stay at 0.

### 5.6 Duration and repeats

- Idle: 10 min per run, 3 runs per condition, randomized order across A/B/C/D.
- Warm-up 2 min and cool-down 2 min before each run (let the platform settle to the same temperature).
- Compile and video: 3 runs each.
- Total for the core test (idle + video + compile, 4 conditions, 3 repeats): roughly 4 x 3 x (10 + 10 + ~15) min, about 3.5 hours on battery. Run it with the screen and session left alone.

### 5.7 Pass / fail rules (set before running)

- **Power pass:** B or D lowers mean SysWatt on idle by at least 0.5 W (about 10%) against A, with spread (max-min over 3 runs) below that gain. Otherwise no gain.
- **Responsiveness pass:** cyclictest p99 and the scripted latency test are no worse than A by more than 10%.
- **Gaming pass:** p99 frame time no worse than A by more than 5%. If gaming is not run, B and D cannot be recommended for a gaming-capable profile, only for an idle/battery profile.
- **Compile pass:** wall time no worse than A by more than 10%.
- **Audio pass:** zero xruns in any run.
- Any kernel log error, scheduler crash, or failed restore = fail.

### 5.8 Restore (always, even on failure)

1. Stop the scheduler (see 5.2). Confirm `cat /sys/kernel/sched_ext/state` reads `disabled`.
2. Restore brightness to the recorded value.
3. Confirm EPP and platform_profile match the recorded values.
4. Confirm `intel_lpmd` is still active with the same config (no edits made).
5. Record every run's raw file path and summary in a new results file, kept apart from the downloaded sources.

---

## 6. Open questions / next steps

1. Does lpmd WLT proxy actually write EPP on this box with BalancedDef=-1? Test: change the asusd profile, read EPP after 10 s.
2. What does lavd's debug log say about the CPU classification for cpu20/21 (`--log-level=debug`)?
3. Does gamemode nice/policy reach lavd tasks as expected? Read `scx_lavd --help` for the nice options and test with `gamemoderun`.
4. Whether turbostat on this kernel exposes `Pk%pc10` as the column name (check `turbostat --list`).
5. The Phoronix and LWN primary numbers. Try them later from a browser (the automated fetch returned 403).
