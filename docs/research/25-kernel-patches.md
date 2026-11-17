# 25 - Upstream kernel patch drafts (GU605MI, kernel 7.3.x)

Scope: read-only research. No build, no install, no email, no posting, no push.
Drafts: local working copy, not in the repo.
Source: torvalds/linux tag v7.3 (exists; fetched via raw.githubusercontent.com). Git history via the GitHub commits API.
Inputs: findings/01, research/01, research/02, research/06.

## Summary

| # | Topic | Draft | Confidence | Send? |
|---|---|---|---|---|
| 1 | ACPI Timer() across suspend | `01-acpi-os-get-timer-boottime-EXPERIMENT-do-not-send.patch` (experiment only) | Low on cause, high on the warning trap | No, needs a real fix and measurement |
| 2 | asus-nb-wmi codes 0x4F, 0xE5, 0x68 | none | n/a | No entry; test with evtest first |
| 3 | CS35L56 HDA hibernate hang | `03-cs35l56-hda-defer-fw-reload-on-hibernate-thaw.patch` | Medium-high on mechanism, low on the fix | After compile and hibernate tests |

## 1. ACPI Timer() (acpi_os_get_timer)

### Verified in v7.3 source
- `drivers/acpi/osl.c:661-665`: `return (get_jiffies_64() - INITIAL_JIFFIES) * (ACPI_100NSEC_PER_SEC / HZ);`
- Introduced by **83b2348e2755** (2018-10-18, Bart Van Assche, "ACPI / OSL: Use 'jiffies' as the time bassis for acpi_os_get_timer()"). Before that it was `ktime_to_ns(ktime_get()) / 100`.
- Reason given in the commit: `ktime_get()` was called from `acpi_os_get_timer()` during the hibernation snapshot (`irqrouter_resume` via `syscore_resume`), while timekeeping was suspended. That gave `WARN_ON` in `ktime_get()`. The commit's comment says jiffies do not advance while timekeeping is suspended, so the result is "unexpected".
- The same commit also touched the comment. It cites the ACPI 3.0 Timer operand and says "monotonically increasing ... with 100ns granularity".
- ACPI spec wording: only secondary sources found (kernel commit messages: ACPI 5.0 says monotonically increasing, 100 ns; interpreter commit: 64-bit monotonic). The spec text itself was not retrieved. Mark as unverified until the UEFI ACPI spec section is read.

### Other AML and ACPICA users
- ACPICA loop timeout: `drivers/acpi/acpica/dscontrol.c:87` (loop start deadline) and `:182` (`ACPI_TIME_AFTER(acpi_os_get_timer(), loop_timeout)`). Added by **164a08cee135** (ACPICA: "Introduce timeout mechanism for infinite loop detection"). A boottime clock would make a While loop that spans a suspend time out early. A jiffies clock lets it run longer across suspend. Low practical risk but a real behaviour change.
- This machine's AML (decompiled in `~/.local/src/acpi-tables/ssdt15.dsl`) uses `Timer` in more places than the PXP/RP12 code in research/01:
  - RP12 PXP `PON` residual `(Timer - WOFF)/0x2710` (lines 1099, 1460, 1870, 2422) and `WOFF = Timer` (1151, 1512, 1922, 2476).
  - Another device block using `(Timer - TD_C)/0x2710` (6427, 6566, 6706), with `ONTM = Timer` (6530, 6670, 6790).
  - `(Timer - \_SB.PC00.PAUD.ONTM)/0x2710` (6810), i.e. the same residual pattern on PAUD (audio). This needs checking, because the audio codec resume is a separate issue.
  - Debug prints `ToHexString(Timer)` (ADBG).
- Any change to the clock therefore changes every one of these residuals, not only the 171 ms case.

### Why the draft is an experiment, not a patch
- `ktime_get_boottime_ns()` is `ktime_get_with_offset()` underneath. In v7.3 `kernel/time/timekeeping.c:1043` contains `WARN_ON(timekeeping_suspended)`, and all `ktime_get_*` variants have the same check (WARN_ON at lines 977-1171 and 3160; 1263 in the snapshot path). So the obvious fix reintroduces the warning that 83b2348e2755 removed. The draft's commit message says so.
- A correct fix must return a value that advances across suspend without reading timekeeping while it is suspended. Options (none written): cache the suspended interval from a timekeeping resume notifier, or use a clock that does not warn. Both need maintainer input.
- The 171 ms is not proven. `ssdt15.dsl` also runs `Sleep(P0DL)` on the NVIDIA path and `Sleep(0x64)` (100 ms) at the end of every PON. The residual is only one candidate. Separate them before claiming the cause.
- Windows KeQueryInterruptTime / sleep-time semantics: not researched. No source fetched, so do not claim anything about Windows.

### Evidence still needed
1. Read PDOD and P0DL/PEP0 values (root, read-only, run manually).
2. Split 171 ms: vary active time before suspend (research/01 test 2). If the delay tracks active time, WOFF is the cause. If constant, P0DL is.
3. Measure CLOCK_MONOTONIC vs CLOCK_BOOTTIME across one s2idle (research/01 test 3).
4. Read the ACPI spec Timer() text (UEFI ACPI spec, section "Timer").
5. Check lore.kernel.org for prior discussion of acpi_os_get_timer after 2018.

## 2. asus-nb-wmi keymap: 0x4F, 0xE5, 0x68

### Verified
- `drivers/platform/x86/asus-nb-wmi.c:586` `asus_nb_wmi_keymap[]`. A grep of asus-nb-wmi.c and asus-wmi.c at v7.3 finds **no** entry for 0x4F, 0xE5 or 0x68. Finding 02 is correct.
- EC/ACPI sources of these codes (research/02): 0x4F from `_Q2E`, `_QA6`; 0xE5 from `_QAE`, `_QB4`, `_QDB`; 0x68 from `_QDC`.

### Not supported well enough for a draft
- 0x4E is documented in asus-wmi.c as the Fn-lock toggle (`NOTIFY_FNLOCK_TOGGLE`), per a web search. This is a different code, and a web source only; re-check in the tree before relying on it.
- No source found for 0xE5 or 0x68 meanings. A Jan 2026 ROG HID patch (linux-input) lists other codes (0xea, 0xec, 0x02, 0x8a, 0x9e), not these three.
- The keymap is a static table. Adding entries with a guessed KEY_* would send a wrong key to userspace. Do not draft one.

### Testing needed (manual, on the laptop)
- `sudo evtest /dev/input/event10` (Asus WMI hotkeys), then press each Fn/ROG key that is not mapped (Armoury, fan/profile, mic mute, airplane, touchpad, screenshot).
- Record which key produces which EV_MSC/EV_KEY and whether the press matches 0x4F, 0xE5 or 0x68. Note that unmapped codes may produce no event. Check `dmesg` for "unknown event code" messages from asus-wmi.
- To confirm the ACPI side: enable the ASUS WMI debug output (`asus_wmi` debug) and log the raw code per key press.
- Compare on the Windows side: Armoury Crate key map (not a source for codes, only the action).

## 3. CS35L56 HDA hibernate hang

### Verified in v7.3 (`sound/hda/codecs/side-codecs/cs35l56_hda.c`)
- `cs35l56_hda_pm_ops` (~line 1236): `SYSTEM_SLEEP_PM_OPS(suspend, resume)` maps thaw and restore to `cs35l56_hda_system_resume`, and freeze and poweroff to `cs35l56_hda_system_suspend`. Verified in `include/linux/pm.h:314-320`.
- `cs35l56_hda_system_suspend` (~834) calls `cs35l56_hda_wait_dsp_ready()` (which is `flush_work(&dsp_work)`, line 55), then pauses playback and calls `pm_runtime_force_suspend`.
- `cs35l56_hda_system_resume` (~918) queues `dsp_work` on `system_long_wq` when `cs35l56_is_fw_reload_needed() > 0`, then calls `cs35l56_hda_play()` if playing.
- `cs35l56_hda_dsp_work` (672) calls `cs35l56_hda_fw_load` -> `request_firmware` path. Matches the stacks in finding 01.
- Thaw and restore share one callback, so the thaw in the image-writing kernel and the restore in the new boot take the same path.

### Draft
`03-cs35l56-hda-defer-fw-reload-on-hibernate-thaw.patch` (touches `cs35l56_hda.c` and `cs35l56_hda.h`):
- Split resume into a helper plus separate `.thaw` and `.restore`/`.resume` entries. The `.thaw` path does not queue the reload. It sets `cs35l56->fw_reload_pending`.
- `cs35l56_hda_play()` queues the deferred reload in process context. System suspend (poweroff) is unchanged, but it no longer blocks, because nothing is queued during thaw.
- Restore keeps the old behaviour.
- The patch applies cleanly to pristine v7.3 (`patch -p1` dry run and real apply in a scratch copy). **Not compiled.** Build check still needed.

### Risks of this draft
1. An aborted hibernate (the image write fails and the kernel keeps running after thaw) leaves the amps unloaded until the next playback. Only `cs35l56_hda_play()` handles the deferred load, so a path that does not go through play (for example a mixer control only) stays broken. Needs a test.
2. Playback is not restarted during thaw. If audio was playing before hibernate and the abort path is taken, the state may be inconsistent with `cs35l56->playing`. Needs a test.
3. The fix only covers the hibernate thaw. Other callers of `queue_work` (bind, runtime paths) are unchanged. A workqueue frozen during any other system transition would still hang the same way. Not analysed.
4. The `pm_sleep_ptr` expansion was written by hand. Check that it matches the other drivers in the tree.
5. Maintainers may prefer deferring every firmware load to first use (research/06 option c), which is a bigger change.

### Evidence still needed
- Compile with `W=1` for cs35l56 modules.
- Hibernate test with the patched module (~20 GB in use): `systemctl hibernate` must power off, and hibtrace must not fire. Test `HibernateMode=shutdown` and platform too.
- Abort test: force a hibernate write failure (for example a full swap file) and check that audio still plays after recovery.
- A system with the existing workaround removed (the 30-cs35l56-hibernate unbind hook disabled).
- Check whether thaw callbacks on any other PM path (s2idle) are affected. They should not be, but test one s2idle cycle.

## Caveats
- All source is v7.3 tag, read via raw.githubusercontent.com. History via GitHub API (`commits?path=`, `search/commits`).
- The ACPI spec text was not read directly.
- Drafts carry placeholders for author and Reported-by, plus an AI Co-Authored-By line. Check kernel AI-disclosure policy before sending.
- Nothing was sent, posted or pushed.
