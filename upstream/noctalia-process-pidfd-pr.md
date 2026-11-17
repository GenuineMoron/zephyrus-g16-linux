# Noctalia PR draft: event-driven process wait (2026-11-15)

Opened as [noctalia-dev/noctalia#5395](https://github.com/noctalia-dev/noctalia/pull/5395) (branch `perf/event-driven-process-wait`, rebased on c1a7283). Title: `perf(process): wait for child exit on a pidfd instead of polling every 100 ms`. The text below is what was submitted.

---

## Summary

The worker thread behind `process::runAsync`/`runSync` now waits on the child's pidfd as well as its pipes, so it sleeps until there is output, the child exits, or the deadline passes, instead of waking every `kProcessPollInterval` (100 ms) to call `waitpid(WNOHANG)`.

- **Cancellation:** it is still the existing `std::atomic<bool>` flag, so no caller changes. While a cancellable run is otherwise idle, the flag is checked once a second (`kCancelCheckInterval`).
- **Without `pidfd_open`:** where it is unavailable (kernels before 5.3, or a seccomp filter), the loop keeps today's timed behaviour.

## Motivation

Every long-lived `noctalia.runStream` (`gdbus monitor`, `umbriel subscribe`, …) costs a worker thread that wakes 10 times a second for its whole life, even when the child never prints. With four plugin streams on my laptop, Noctalia showed four threads each sitting in `poll(fds, 2, 100)`, adding about 40 wake-ups/s to an otherwise idle, locked session.

Measured with `bpftrace` (scheduler switches of the test process, one idle cancellable `sleep 30` stream, 6 s):

| | Wake-ups in 6 s |
| --- | --- |
| before | 59 |
| after | 6 |

It also fixes a hang. Once a child closed both stdout and stderr but kept running, the loop fell back to a blocking `waitpid()` and could no longer be cancelled; a stream whose command does `exec >/dev/null 2>&1` would outlive its plugin. It now keeps waiting on the pidfd and honours the flag.

## Type of Change

- [x] Bug fix

## Testing

- `meson setup build-debug -Dtests=enabled`, `meson compile -C build-debug process_test plugin_process_test`, `meson test -C build-debug process plugin_process`: both pass.
- New tests in `tests/process_test.cpp`:
  - `cancelStopsIdleStream`: a cancelled child that never prints or exits is terminated.
  - `cancelStopsChildThatClosedItsOutput`: the hang above. Against the old `process.cpp` this test fails: `process_test.cpp:137: check failed: cv.wait_for(...)`.
  - `timeoutStopsIdleChild`: a deadline still ends an idle child on time, now that waits can be long.
- `clang-format` 23.1.5 on both files; `clang-tidy -p build-debug --warnings-as-errors='*' src/system/process.cpp tests/process_test.cpp`: no findings.
- The wake-up numbers above come from a throwaway measurement hook in the test binary, not part of this PR.

I have not yet run a full shell built from this branch as my daily session; the change is confined to the process wait loop, which the tests exercise directly.

## Checklist

- [x] This PR is ready for review, or it is marked as Draft.
- [x] I read and followed the relevant guidance in `CONTRIBUTING.md`.
- [x] I ran `just format` with clang-format v23+ installed, or this PR has no code changes.
- [x] I ran the relevant build or test commands, or explained why they were not run.
- [x] I self-reviewed the changes.
- [x] I checked for new warnings or errors.
- [x] I updated user-facing documentation in [`docs/user/`](../docs/user/) when this PR changes documented behavior or configuration, or this PR does not require documentation changes.
- [x] I added or updated `assets/translations/en.json`, or this PR adds no new user-facing strings.
- [x] I did not edit non-English translation files unless this PR is explicitly for translation tooling, an import/export sync, or a maintainer-requested locale change.
- [x] I used the existing canonical names for config keys, IPC names, paths, and identifiers.

## Additional Notes

- **Getting to zero wake-ups:** the remaining once-a-second check exists only because cancellation is an atomic that a sleeping `poll()` cannot see. If you want zero, a small follow-up could give `RunOptions` an eventfd-backed cancel type that `cancel()` signals. That touches the eight call sites that create cancel flags, so I kept it out of this fix; happy to send it if you'd like it.
- **Disclosure:** written with AI assistance (Claude). I reviewed the change, measured it, and checked the new test fails without the fix.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
