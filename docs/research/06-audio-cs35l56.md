# 06 - Audio: CS35L56 / ALC285 PM, hibernate deadlock, speakers, mic

Scope: read-only research. No sysfs writes, no sudo, no /proc/asound/card1, no lspci or nvidia-smi.
Kernel at time of logs: 7.3.3-1-cachyos (boot 2026-11-14 17:59).

## 1. Kernel PM lifecycle (cs35l56 HDA side-codec)

Source: sound/hda/codecs/side-codecs/cs35l56_hda.c on torvalds/master (fetched 2026-11-14; the fetch returned excerpts, so grep the full file to confirm the items marked "verify").

Proven from the source:
- `cs35l56_hda_pm_ops` is built from:
  - `RUNTIME_PM_OPS(cs35l56_hda_runtime_suspend, cs35l56_hda_runtime_resume, NULL)`
  - `SYSTEM_SLEEP_PM_OPS(cs35l56_hda_system_suspend, cs35l56_hda_system_resume)`
  - `LATE_SYSTEM_SLEEP_PM_OPS(cs35l56_hda_system_suspend_late, ...)`
  - `NOIRQ_SYSTEM_SLEEP_PM_OPS(cs35l56_hda_system_suspend_no_irq, ...)`
- `SYSTEM_SLEEP_PM_OPS` maps freeze/poweroff to the suspend callback and thaw/restore to the resume callback (include/linux/pm.h; general knowledge, verify). The hibernate thaw therefore runs `cs35l56_hda_system_resume`.
- `cs35l56_hda_system_suspend`: sets `suspended`, calls `flush_work(&cs35l56->dsp_work)`, pauses playback, disables the parent IRQ, then `pm_runtime_force_suspend()`.
- `cs35l56_hda_system_resume`: `pm_runtime_force_resume()`, re-enables IRQ, clears `suspended`, and calls `queue_work(system_long_wq, &cs35l56->dsp_work)` when a firmware reload is needed.
- `dsp_work` is queued from bind and from system resume. It is cancelled (`cancel_work_sync`) in unbind and flushed in `cs35l56_hda_wait_dsp_ready`.
- `dsp_work` calls `cs35l56_hda_fw_load` -> `cs35l56_hda_request_firmware_file` -> `firmware_request_nowarn`. Firmware is loaded in the background; this was introduced by the 2024 "Perform firmware download in the background" patch (Simon Trimmer, v2, lkml 2024-06).
- Runtime PM: `cs35l56_hda_runtime_resume` re-runs the DSP if booted and sends `CS35L56_MBOX_CMD_ALLOW_AUTO_HIBERNATE` (amp's own low-power hibernate, a different thing from system hibernation).
- Comment in the source: RESET is shared by all amps and must not be asserted until all instances have done their suspend stage; "Release shared RESET before drivers start resume()". On this machine the log says "Reset GPIO busy, assume shared reset" for amp .1, so only amp .0 owns the reset line.

Not found in the fetched excerpt (verify with grep): freeze/thaw/poweroff/restore explicit callbacks, the string "Hibernate wake failed".

### Proven on this machine (journal, s2idle cycle 18:17)
- `cs35l56-hda.1 cs35l56_hda_system_resume` took 55 ms; `.0` took 9.8 ms.
- `snd_hda_codec_alc269 hdaudioC0D0 hda_codec_pm_resume` took 646 135 us.
- Suspend order: codec, then amp .1 and .0 system_suspend, then suspend_late/no_irq for both. Resume order: amp .0 no_irq/early/system, then codec resume starts, then amp .1 system_resume.

### Hibernate deadlock: mechanism (trace proven by measurement, explanation inferred)
Inferred, consistent with the measured trace (see ../findings/01-hibernate-hang-cs35l56.md):
1. Image creation: devices are suspended, then the image is written, then `dpm_resume` runs thaw callbacks in the image-creating kernel. This happens while unbound workqueues are still frozen.
2. `cs35l56_hda_system_resume` (thaw) queues `dsp_work` on `system_long_wq`.
3. `dsp_work` calls `request_firmware`, which reads `cirrus/cs35l56-b0-...wmfw.zst` from btrfs via `filp_open`. The btrfs read completion work needs the frozen workqueues, so the read never completes and the worker blocks in `io_schedule`.
4. At power-off, `cs35l56_hda_system_suspend` (poweroff) runs `flush_work(&dsp_work)`, waits for a work item that can never finish, and systemd-sleep hangs.

Root cause: firmware file I/O (which needs the filesystem and its workqueues) is run from a work item during the hibernate thaw phase, and the poweroff path waits on it. The 2026 ASoC probe-deadlock series (rf@opensource.cirrus.com, 2026-07-16, patches "ASoC: cs35l56: Fixes for deadlock/hang during component_probe()") is a different code path: ASoC codec, I2C/SPI probe, `init_completion`. It does not touch suspend, resume, or hibernate. Searches found no 2025-2026 HDA patch for the thaw/firmware deadlock.

Name collision: the 2023 "ALSA: hda: cs35l56: Disable low-power hibernation mode" patches concern the amp's own low-power state, not system hibernation.

### Proposed upstream fixes (for Cirrus to choose)
a. Do not queue firmware loading from the `thaw`/`restore` callbacks. Have hibernate restore complete the load synchronously in the resume path, where the filesystem is alive, or add a `pm_hibernation` / `system_state` check that skips the queue.
b. Make the poweroff/freeze path not `flush_work` a firmware load. Cancel without waiting for work that does I/O, or record "load pending" and let runtime resume finish it.
c. Load firmware on first use (runtime resume) rather than during system resume, so the system PM path never depends on filesystem I/O.
Option (c) is the cleanest; it also helps the 645 ms-type latency if the load can be deferred.

## 2. ALC285 codec resume (~646 ms) and the AC power_save=0 workaround

Proven:
- `snd_hda_intel` `power_save=0` and `power_save_controller=Y` (read from /sys/module/snd_hda_intel/parameters). The cachyos udev rule `20-audio-pm.rules` calls `/usr/lib/udev/audio-pm-ctl ac|battery|init`, which sets power_save=0 on AC and restores 10 on battery.
- With power_save=0 the codec is never runtime-suspended, so every s2idle resume runs the full `hda_codec_pm_resume` path.
- Codec resume is 646 ms on this machine (above). The CS35L56 resume is 55 ms, so the amps are not the bottleneck.

Inferred:
- The codec resume replays cached verbs and runs the ALC285 init (`alc_init`/`alc285` specific) plus jack re-detection on all pins. Amps are re-bound via `cs35l56_hda_comp_ops`. Verify with function-graph tracing (not done; read-only constraint).
- The crackle workaround (power_save=0 on AC) targets the codec's power-down/up click. On this machine the amps sit behind the codec, so the click may come from the codec's power state, the amps' own state, or both. Whether it is still needed is unknown; it has to be tested, not assumed.

Test plan (manual, not run yet):
1. Boot with power_save=10 on AC for a day. Listen for crackles at idle and on stream start/stop.
2. If crackles return, try power_save=1 (shortest timeout) and keep power_save_controller=Y.
3. Pipewire/WirePlumber: `session.suspend-timeout-seconds` (default 5 s) closes the ALSA device on idle, which is the more common cause of audible pops than codec runtime PM. A longer timeout on AC would achieve the same effect without power_save=0.
4. Measure resume time with `dmesg`/journal after each change (same method as above).

## 3. Speakers and tuning

Found:
- Kernel commit for `1043:1c63` ("ASUS GU605M") mapping to `ALC285_FIXUP_ASUS_GU605_SPI_2_HEADSET_MIC`, and a separate ALC285 CS35L56 SPI fixup for that ID (search snippet, diff garbled; verify in the tree).
- Linux bugzilla 220152 (GU605CR): ALC285 + two CS35L56, quiet speakers. Notes the GU605M speaker quirk may be needed (bugzilla.kernel.org/show_bug.cgi?id=220152).
- Patchew 2026-01-12 "ALSA: hda/realtek: Add quirk for Asus Zephyrus G14 2025 using CS35L56, fix speakers" (same family, merged in 6.19 cycle).
- Community: swapping in firmware from a different variant (10431b13) gave a small improvement only. Experimental; not recommended.
- EasyEffects Dolby-style presets: anecdotal, minor gains, risk of clipping.
- Local firmware: `/usr/lib/firmware/cirrus/cs35l56-b0-dsp1-misc-10431c63-spkid0*` is the same set that loads on this machine. The `misc` tuning string in the log names an ASUS Windows build path (`C:\Users\...\GU605\240426\init\10431C63_240426_V0_A0-init.bin`). The calibration applied and tuning PID 0x531116 are present, so the ASUS per-unit calibration is in use. I found no separate ASUS Windows "DSP tuning" file that is not already loaded.

Caveat: the codec's autoconfig log line reads `picked fixup  for PCI SSID 1043:1c63` with an empty fixup name. Verify which quirk is actually applied (`/proc/asound/card0/` is safe to read, `grep -i fixup` on the journal). This matters for the headset and speaker routing.

## 4. Mic array and headset jack

- Journal: `Internal Mic=0x12, 0x13`, `Mic=0x19, 0x1b`, `hp_outs=0x21`, `line_outs 0x14/0x17`. Input devices: `HDA Intel PCH Mic` x2, `HDA Intel PCH Headphone`.
- The card is `snd_hda_intel` with the ALC285 codec. The SOF stack did not appear in the matched log lines. The original question assumed SOF topology for the DMIC; verify with `journalctl -k -b | grep -i sof`. If SOF is not loaded, the DMIC path is the HDA path, and the SOF-topology question is moot.
- Known issues: no confirmed headset-mic fix for 1043:1c63 found. A related GA402XY bug (bugzilla 219743) reports the headset mic missing after 6.12.2. Different model; may not apply.
- Not testable read-only (needs a jack plug).

## 5. Draft upstream bug report

To: patches@opensource.cirrus.com
Cc: linux-sound@vger.kernel.org
Subject: [BUG] cs35l56-hda: system hibernate hangs at poweroff: dsp_work firmware load blocks on frozen btrfs workqueues

Hi Cirrus maintainers,

We see a deterministic hibernate hang on a laptop with two CS35L56 amps on SPI (ASUS ROG Zephyrus G16 GU605M, subsystem 1043:1c63, codec ALC285, snd_hda_scodec_cs35l56).

Environment:
- Kernel: 7.3.3-1-cachyos (x86_64), [substitute your exact version]
- Filesystem: btrfs on root, firmware loaded from /usr/lib/firmware/cirrus/
- Firmware: cs35l56-b0-dsp1-misc-10431c63-spkid0 (wmfw + amp1/amp2 bin)
- Shared RESET: amp .1 logs "Reset GPIO busy, assume shared reset"

Sequence:
1. `systemctl hibernate` writes the image.
2. During thaw, `cs35l56_hda_system_resume` returns and queues `dsp_work` on `system_long_wq` (firmware reload is needed).
3. `dsp_work` -> `cs35l56_hda_fw_load` -> `cs35l56_hda_request_firmware_file` -> `firmware_request_nowarn` -> `_request_firmware` -> `fw_get_filesystem_firmware` -> `filp_open` -> `page_get_link` -> `btrfs_read_folio` -> `btrfs_read_extent_buffer`. The read never completes because the btrfs endio workqueues are frozen.
4. At power-off, `cs35l56_hda_system_suspend` calls `flush_work(&cs35l56->dsp_work)` and blocks forever.

Stack traces (from hung-task / sysrq-w):
```
[systemd-sleep] Call Trace:
  __schedule
  schedule
  schedule_timeout / wait_for_completion
  __flush_work
  cs35l56_hda_system_suspend [snd_hda_scodec_cs35l56]
  dpm_run_callback / device_suspend
```
```
[kworker/uXX:Y events_long] Call Trace:
  io_schedule
  ...
  btrfs_read_extent_buffer
  btrfs_read_folio
  page_get_link
  filp_open
  fw_get_filesystem_firmware
  _request_firmware
  firmware_request_nowarn
  cs35l56_hda_request_firmware_file [snd_hda_scodec_cs35l56]
  cs35l56_hda_fw_load [snd_hda_scodec_cs35l56]
  cs35l56_hda_dsp_work [snd_hda_scodec_cs35l56]
  process_one_work
```
[Replace with the exact traces captured by the reporter.]

Workaround: unbinding both amps from /sys/bus/spi/drivers/cs35l56-hda before hibernate avoids the hang. This is confirmed on this machine.

Questions:
1. Should the thaw/restore path queue firmware I/O at all? Could firmware load be deferred to first use (runtime resume) instead of queued from system resume?
2. Should poweroff/freeze wait on dsp_work? A cancel or a "load pending" flag may avoid waiting on I/O that cannot complete during hibernate.

Happy to test patches on the hardware above.

Thanks,
[Name placeholder]
[Affiliation placeholder]

## Open questions
- Exact grep of the full cs35l56_hda.c for PM callbacks, "Hibernate wake failed", and the freeze/poweroff mapping.
- Whether 6.19+ or 7.x has any HDA-side change (git log -- sound/hda/codecs/side-codecs/cs35l56_hda.c, on a local clone).
- Whether the codec resume time is mostly `alc_init` or jack re-detection (ftrace function_graph, needs root).
- Whether the amps lose firmware on s2idle (no RESET pulse on amp .1) and whether that explains the reload.
- Which quirk is actually applied for 1043:1c63 (fixup name empty in the log).
- Whether the DMIC uses SOF or HDA on this machine.
