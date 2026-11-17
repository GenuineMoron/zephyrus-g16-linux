# 01: Hibernate never powers off when lots of memory is in use

**Status:** root cause proven, worked around, verified (2026-11-14).
**Upstream:** not fixed. Cirrus CS35L56 HDA driver + btrfs during hibernation.

## Symptom

- **Hibernate saves the image, then never powers off.** It happens whenever a lot of memory is in use (~20 GB of 31). The keyboard stays lit, the screen is black, the machine draws 20–30 W, and only holding power recovers it. The image is complete, so the next boot restores it fine.
- **The low-memory cases looked healthy:** with little memory in use, or right after boot, hibernate worked every time.
- **Both power-off methods hung:** `HibernateMode=platform` (S4) and `shutdown` (S5).

## What was ruled out (with tests)

| Suspect | Test | Result |
|---|---|---|
| NVIDIA driver | all NVIDIA modules unloaded | still hangs |
| zram | zram swap off | still hangs |
| Kernel memory reserve | `reserved_size` 1 GiB | still hangs |
| SSD path | normal-operation swap-out to the swap file | 5 GB in ~4 s, fine |
| Firmware S4 entry | `HibernateMode=shutdown` (S5 instead) | still hangs |

## How it was found

Ordinary logging cannot see this. Everything after the hibernation snapshot is lost when power is held, and the kernel's hung-task detector is switched off for the duration of hibernation. The Intel TCO watchdog is locked by the BIOS (see [lessons](../lessons.md)).

So we built a small kernel module, [tools/hibtrace](../../tools/hibtrace/). It arms a watchdog when hibernation starts. If hibernation is still running 120 s later, it:
1. prints every blocked task's stack and every CPU's backtrace;
2. panics, so the log is written to EFI variables (pstore);
3. lets the laptop restart itself (`kernel.panic=10`).

After restoring from the image, the records were read directly from `/sys/firmware/efi/efivars/dump-type0-*`. The pstore filesystem does not list them after a hibernate restore.

## Evidence (stack traces from the saved panic log)

```
systemd-sleep  D  ... dpm_suspend_start -> dpm_suspend -> device_suspend
                  -> cs35l56_hda_system_suspend -> __flush_work -> wait_for_completion
kworker/0:1    D  Workqueue: events_long cs35l56_hda_dsp_work
                  cs35l56_hda_dsp_work -> cs35l56_hda_request_firmware_file
                  -> firmware_request_nowarn -> _request_firmware -> fw_get_filesystem_firmware
                  -> filp_open -> path_openat -> pick_link -> page_get_link
                  -> btrfs_read_folio -> btrfs_read_extent_buffer -> read_extent_buffer_pages
                  -> io_schedule            (never returns)
btrfs-transaction, flush-btrfs writeback: also stuck in read_extent_buffer_pages
```

NVIDIA's own power-off callback returned in microseconds. The hang sits entirely in the speaker-amplifier driver.

## Root cause

1. **Hibernation shrinks memory first.** It must free memory for the snapshot copy, so it evicts the page cache, which holds file data and btrfs metadata.
2. **The amps reload firmware after the snapshot.** Devices are resumed ("thaw") so the image can be written. On thaw, the CS35L56 HDA driver queues `cs35l56_hda_dsp_work`, which reloads its firmware with `request_firmware()`. That includes lookups through the `/lib` → `usr/lib` symlink and of the `.zst` firmware names.
3. **The reload needs disk reads that can never finish.** Its firmware data is no longer cached, so the files must be read from btrfs. btrfs completes reads on workqueues that hibernation keeps frozen until resume, so those reads never complete. The image itself is written straight to the swap file through the block layer, which is why saving always succeeds.
4. **Power-off then waits forever.** At power-off, `cs35l56_hda_system_suspend()` flushes the amp's DSP work. That work is stuck behind the frozen reads, so the deadlock never ends.

This explains why only heavy memory use triggers it. With little memory in use nothing is evicted, the firmware lookups hit the cache, and the work finishes instantly.

The same class of bug has been reported upstream ("Root filesystem read access for firmware load during hibernation image writing", LKML 2024; "request_firmware() in resume callback with firmware on btrfs", 2020). There is no fix as of kernel 7.3.

## Fix (workaround)

[configs/usr/lib/systemd/system-sleep/30-cs35l56-hibernate](../../configs/usr/lib/systemd/system-sleep/30-cs35l56-hibernate) unbinds both amps from `/sys/bus/spi/drivers/cs35l56-hda`, only for the hibernate step. It does this for `SYSTEMD_SLEEP_ACTION=hibernate` or `hybrid-sleep`, which also covers the hibernate step of suspend-then-hibernate. It rebinds them afterwards.

- **Unbind order:** reverse order, because the two amps share a reset GPIO.
- **Rebind cost:** the amps reload firmware and calibration in ~0.3 s.

## Verification (each with ~21 GB of 31 GB in use)

| Test | Result |
|---|---|
| `systemctl hibernate`, platform mode | powered off, RTC woke it (observed) |
| `HibernateMode=shutdown` | powered off properly |
| Real lid close, suspend-then-hibernate (2 min standby) | standby → hibernate → power button → restored; sound OK |
| hibtrace watchdog in all of the above | never fired |

## Proper upstream fix (not done yet)

The CS35L56 HDA driver should not request firmware from the filesystem during the hibernation thaw phase. It could skip the DSP reload on thaw (the amp is powered off again moments later), or use the firmware cache. This is worth reporting to Cirrus Logic (`patches@opensource.cirrus.com`, linux-sound) with the stacks above.
