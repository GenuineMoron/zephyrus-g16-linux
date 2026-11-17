# Methodology: measure, trace to the cause, change one thing, measure again

## Rules

1. **Start from a number.** "Wake feels slow" becomes "resume_noirq 548 ms, of which `pcieport 0000:00:01.0` is 542 ms".
2. **Find the code.** The kernel source, the driver source, and the decompiled BIOS (ACPI). If you can't point at the line, it's still a hypothesis.
3. **One change at a time,** with the same measurement before and after.
4. **Make every fix durable,** and have the health check verify it survives updates.
5. **Don't let the measurement change the system.** For example, `lspci` and reading a DRM connector's `status` both wake a sleeping NVIDIA GPU.

## Toolbox

| Question | Tool |
|---|---|
| Which driver makes suspend/resume slow? | [tools/trace-standby.sh](../tools/trace-standby.sh) + [analyze-standby-trace.py](../tools/analyze-standby-trace.py): `trace-cmd` with `power:suspend_resume`, `power:device_pm_callback_*`, a kprobe on `acpi_os_sleep` (every BIOS `Sleep()` and its length), and optional `function_graph` under named functions |
| Same, as a visual HTML timeline | Intel pm-graph `sleepgraph` (github.com/intel/pm-graph), e.g. `sleepgraph.py -m freeze -rtcwake 20 -f -mincg 1` |
| What does the BIOS do? | `acpidump -b` then `iasl -d` per table; find a device's ACPI path with `cat /sys/bus/pci/devices/<addr>/firmware_node/path`. **Never publish the MSDM table:** it contains the Windows product key |
| How deep does standby go, and what blocks it? | `/sys/kernel/debug/pmc_core/`: `substate_residencies`, `substate_requirements` (Status column), `lpm_latch_mode` (latch at `S0i2.0` entry), `ltr_show`, `pch_ip_power_gating_status`; plus `/sys/power/suspend_stats/{last,total}_hw_sleep` |
| Why does hibernate hang? | [tools/hibtrace](../tools/hibtrace/): watchdog → stacks → panic → EFI pstore → auto-restart. After a hibernate restore, read the records from `/sys/firmware/efi/efivars/dump-type0-*-cfc8fc79-…` (skip the 4-byte header, raw deflate) |
| What happened before a crash? | EFI pstore (boot parameter `efi_pstore.pstore_disable=0`), archived on the next boot by `systemd-pstore.service` into `/var/lib/systemd/pstore` |
| Per-stretch standby log | [configs/…/system-sleep/40-sleep-stats](../configs/usr/lib/systemd/system-sleep/40-sleep-stats) |
| Power while awake | `turbostat`, RAPL (`/sys/class/powercap`), battery `power_now` on battery |

## Hibernate tests: rules learned the hard way

- **Fill memory to reproduce memory-dependent bugs.** Use a capped scope, e.g. `systemd-run --scope -p MemoryMax=20G -p MemorySwapMax=0 python3 …`. Never fill memory inside your desktop's cgroup.
- **Use the RTC to wake the laptop,** but don't trust timing alone. If someone holds the power button at the RTC time, it looks exactly like a pass. Ask whoever is watching what the keyboard light did.
- **Never write the RTC** (see [lessons](lessons.md)).
