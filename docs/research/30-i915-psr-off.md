# i915 PSR silent-disable paths (Linux v7.3, Meteor Lake display ver 14)

Sources: https://raw.githubusercontent.com/torvalds/linux/v7.3/drivers/gpu/drm/i915/display/ (saved locally; local working copy, not in the repo). Line numbers refer to those files. Claims are PROVEN (read in source) or INFERRED.

## (a) Table: path -> condition -> no_psr_reason set? -> file:line

Only `intel_psr.c` writes `psr->no_psr_reason` (grep over all fetched files). `psr->no_psr_reason` is cleared only in `intel_psr_activate()` (intel_psr.c:1969).

| Path | Condition | Reason set? | file:line |
|---|---|---|---|
| Compute | `psr_global_enabled()` false (debug mode DISABLE, or VBT psr.enable off) | No (dbg only) | intel_psr.c:225-238, 1853 |
| Compute | `sink_not_reliable` already set | No (dbg only) | intel_psr.c:1858 |
| Compute | interlaced mode / joiner | No (dbg only) | intel_psr.c:1864, 1875 |
| Compute | `CAN_PSR()` or `enable_psr` false | No | intel_psr.c:1660 |
| Compute | `crtc_state->vrr.enable` | No | intel_psr.c:1666 |
| Compute | entry setup timing not met | Yes ("PSR setup timing not met") | intel_psr.c:1674 |
| Compute late | Wa_18037818876 (display ver 20 only, N/A) | No | intel_psr.c:4558-4611 |
| Compute late | wake lines don't fit vblank | No (PR only) | intel_psr.c:4558-4611 |
| Pre-plane | `!new->has_psr` copies `new->no_psr_reason` (NULL if inactive crtc) | Overwrites to NULL | intel_psr.c:3153-3154 |
| Pre-plane | modeset, update_m_n, update_lrr, has_sel_update/su_region_et/panel_replay change, `!active_planes` | No (disables PSR; re-enabled in post) | intel_psr.c:3165-3174 |
| Pre-plane | `wm_level_disabled` (<11 only) | No | intel_psr.c:3165-3174 |
| Post-plane | `psr->sink_not_reliable` -> keep_disabled | **No (silent)** | intel_psr.c:3220-3226, 3241 |
| Post-plane | `!active_planes` | Yes ("All planes inactive") | intel_psr.c:3229 |
| Post-plane | Wa#1136 (skl/bxt) | Yes | intel_psr.c:3235 |
| Post-plane | early return if `!crtc_state->has_psr` (no disable here) | n/a | intel_psr.c:3205-3206 |
| Enable | `psr_interrupt_error_check()`: stale EDP_PSR_IIR error bit -> sets sticky flag, returns, PSR not enabled | **No (dbg only)** | intel_psr.c:2129-2157, 2187-2188 |
| Enable | `intel_psr_activate()` clears reason on success | clears | intel_psr.c:1969 |
| Disable | `intel_psr_disable()` from encoder disable (DPMS/modeset) | No | intel_psr.c:2402-2420; intel_ddi.c:3591 |
| Disable | `intel_psr_disable_locked()` from pre-plane etc. | No | intel_psr.c:2319-2400 |
| IRQ | `intel_psr_irq_handler()` PSR error bit -> `irq_aux_error`, work -> `intel_psr_handle_irq()` disables and sets sticky flag | No (drm_warn "PSR aux error" only) | intel_psr.c:419-467, 3507-3515; intel_display_irq.c:962-965, 1288-1305 |
| Work | `intel_psr_work()` `__psr_wait_for_idle_locked()` fails -> returns, PSR stays enabled | No (drm_err) | intel_psr.c:3517-3555, 3369-3399 |
| Short pulse | `intel_psr_short_pulse()`: only if `psr->enabled`; INTERNAL_ERROR or error bits -> disable + sticky flag | No (dbg only) | intel_psr.c:3853-3912 (3880-3881); intel_dp.c:5934 |
| Short pulse | `psr_capability_changed_check()` DP_PSR_CAPS_CHANGE -> disable + sticky flag | No (dbg only) | intel_psr.c:3822-3841 (3836-3837) |
| Short pulse | `psr_alpm_check()` alpm error -> disable + sticky flag | No | intel_psr.c:3809-3820 (3817-3818) |
| Debugfs | `intel_psr_debug_set()` stores `psr.debug` then fastset; mode DISABLE -> later compute silently has_psr=false | No | intel_psr.c:3464-3505; intel_psr.c:225-238 |
| Pause/resume | `intel_psr_pause()` / `intel_psr_resume()` (pause_counter) | No (exit, not disable) | intel_psr.c:2431-2500 |
| Frontbuffer | `intel_psr_flush/invalidate` only touch busy bits | n/a | intel_psr.c:3606-3700; intel_frontbuffer.c:100,141 |
| Pipe notify | `intel_psr_notify_pipe_change()` (Wa_16025596647) only applies underrun WA, never disables | n/a | intel_psr.c:4081-4130 |
| Commit | DSB disabled for has_psr crtcs (<20) | n/a | intel_display.c:7341-7356 |
| Link retrain | retrain refused while `psr.enabled` | n/a | intel_dp_link_training.c:2491 |
| Dump | `psr: enabled` = `has_psr && !has_panel_replay` | n/a | intel_crtc_state_dump.c:247 |

**Status output (PROVEN, intel_psr.c:4261-4300):** `PSR mode: disabled` is printed when `!psr->enabled`, and the reason line only when `no_psr_reason` is set. When `!psr->enabled` the function also prints `PSR sink not reliable: yes|no` (intel_psr.c:4283), which is the sticky flag. The earlier read reportedly had no reason line; check whether that `sink not reliable` line was present in the same output.

**Sticky flag (PROVEN):** `sink_not_reliable` is only ever set to true (grep: intel_psr.c:2149, 3512, 3818, 3837, 3881). Nothing clears it except driver reload.

## (b) Three most likely explanations

1. **Sink-not-reliable flag, silent at post-plane (intel_psr.c:3225, 1858).** Set by a silent path (stale IIR bit at 2148, IRQ at 3512, short pulse at 3881, capability change at 3837). Once set it silently blocks re-enable forever (until reboot). It fits "PSR stays disabled, no reason" and the boot-time recovery. It does not fit the third modeset succeeding, since the flag would then make compute return has_psr=false, so check the status line first.
2. **Pre-plane disable without a completed post-plane (intel_psr.c:3165-3174 vs 3241).** Pre-plane disables for update_m_n / update_lrr (60<->240 Hz) and for modeset. Post-plane re-enables. If a commit fails after pre-plane but before post-plane, PSR stays off while the crtc state still reads `has_psr` true, with no reason. This fits the two failing modesets. INFERRED: needs an aborted commit to confirm.
3. **Debugfs mode write and failed fastset (intel_psr.c:3464-3505, 225-238).** Writing 0x1 makes compute return has_psr=false silently; a subsequent 0x0 fastset that fails leaves psr off with reason NULL, matching "writing 0x1 then 0x0 sometimes left PSR disabled". INFERRED.

Also check whether VRR is enabled (intel_psr.c:1666). A silent has_psr=false there would also match.

## (c) Probe points (checked with `sudo grep -E ' intel_psr' /proc/kallsyms`)

Present in the i915 module (`[i915]`, not `[xe]`):
- `intel_psr_disable_locked` (arg0 `struct intel_dp *`)
- `intel_psr_disable` (arg0 intel_dp, arg1 old_crtc_state)
- `intel_psr_activate` (arg0 intel_dp; marks a successful enable)
- `intel_psr_pre_plane_update` / `intel_psr_post_plane_update` (arg0 state, arg1 crtc)
- `intel_psr_short_pulse` (arg0 intel_dp)
- `intel_psr_irq_handler` (arg0 intel_dp, arg1 psr_iir)
- `intel_psr_debug_set` (arg0 intel_dp, arg1 val)
- `intel_psr_pause`, `intel_psr_resume`, `intel_psr_compute_config`, `intel_psr_work`, `intel_psr_exit`

Absent (inlined, cannot probe): `intel_psr_enable_locked`, `psr_interrupt_error_check`, `_psr_compute_config`. Use `intel_psr_activate` for enables.

Suggested fields for `intel_psr_disable_locked` (entry, before the early return): `((struct intel_dp *)arg0)->psr.enabled`, `.sel_update_enabled`, `.sink_not_reliable`, `.debug`, `.pipe`, `.pause_counter`, `.no_psr_reason`, plus `kstack`. Module BTF is required; check `/sys/kernel/btf/i915` (INFERRED that bpftrace accepts `kprobe:i915:<fn>`; verify).

## Not checked
- Commit-abort path after pre-plane (explanation 2): not traced through intel_atomic_commit_tail error handling.
- intel_dmc.c only has a DC-related PSR reference (intel_dmc.c:776-778); no disable path found.
- intel_dp.c:6390 calls `intel_psr_init_dpcd` on detect for non-eDP only.
- Live state was not read (no debugfs read or write, no sysfs).
