# 39: ROG control on Noctalia: architecture (2026-11-15)

Goal: G-Helper-grade control of the G16 on Linux that is clean, near-zero cost when idle, published for other ROG owners, and built in the right place so no work is wasted.

## Options weighed
| Option | Verdict |
|---|---|
| Contribute to G-Helper | No: C#/WinForms, `net10.0-windows`, talks to `\\.\ATKACPI`. The author points Linux users to asusctl |
| Linux G-Helper ports (g-helper-linux C#/setuid helper; rog-helper Rust plus its own daemon; Ayuz Rust/GTK4) | No: they bypass asusd or add a daemon |
| rog-control-center (asusctl's Rust/Slint GUI) | Good for configuration, but in the tray it measured 6.5 wake-ups/s, 28 MB, 50 threads. **Autostart hidden 2026-11-15** |
| Existing Noctalia plugins | asus-gpu-mode (baizhu945): good mode logic, but runs the deprecated supergfxctl CLI. asus-fan: `sh -c asusctl` every 2.5 s. asus-fans-controller-ec: root EC writes. None worth extending |
| **Thin Noctalia plugin on asusd D-Bus + upstream asusd additions** | **Chosen** |

## Facts the design rests on (verified on this laptop)
- **asusd** `xyz.ljones.Asusd`, ObjectManager at `/`. One `GetManagedObjects` returns everything (6 KB, 26 ms, dGPU stays in D3cold). Change notification is `PropertiesChanged`, driven by inotify on sysfs. asusd itself makes 0 wake-ups/s when idle.
  - `/xyz/ljones` `xyz.ljones.Platform`:
    - `PlatformProfile` (0 Balanced, 1 Performance, 2 Quiet), plus `PlatformProfileOnAc` and `PlatformProfileOnBattery`.
    - `ChargeControlEndThreshold`, `OneShotFullCharge()`, `NextPlatformProfile()`, `EnablePptGroup`.
  - `/xyz/ljones` `xyz.ljones.FanCurves`: methods only, no change signals.
  - `/xyz/ljones/asus_armoury/<attr>` `xyz.ljones.AsusArmoury`: attributes such as ppt_pl1_spl, ppt_pl2_sppt, panel_overdrive, dgpu_disable, gpu_mux_mode, nv_dynamic_boost and nv_temp_target. Each has a writable `CurrentValue`, plus `Min`/`Max`/`Possible`.
  - `/xyz/ljones/aura/19b6_2_6` `xyz.ljones.Aura` (keyboard) and `/xyz/ljones/aura/193b_4_8` `xyz.ljones.Slash`.
- **supergfxctl** `org.supergfxctl.Daemon` `/org/supergfxctl/Gfx` is deprecated upstream in favour of asusd attributes plus **Cardwire** (OGC). supergfxd polls every 1 s (about 4.5 wake-ups/s). It stays until the plugin covers GPU mode.
- **Noctalia plugin API (5.4.1, API ≤ 43):**
  - No D-Bus binding. Plugins get `runAsync`, `runStream` (long-lived line stream), `readFile`, `state.watch` and IPC.
  - Limits: 4 streams and 8 async commands per entry, and callbacks have a 25 ms CPU budget.
  - Panel `update()` ticks every 1 s, only while the panel is open.
  - The cheapest live path is one `gdbus monitor --system --dest xyz.ljones.Asusd` stream (works without root).
- **Reads that don't wake the GPU:** `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status` and the hwmon `asus` fans and coretemp, all user-readable.

## Plan
1. **`GenuineMoron/rog-control`** (Luau, noctalia-dev/community-plugins). It covers:
   - performance profile;
   - charge limit 80/100 plus one-off full charge;
   - GPU mode (from asusd's paired attributes) and dGPU sleep/wake state, optionally with the latest `gpu-wake` log entry;
   - panel overdrive;
   - fans and temperatures (panel open only);
   - fan-curve editor;
   - keyboard Aura and Slash;
   - shortcuts for next profile and the charge-limit toggle.

   Optional: 60 Hz plus overdrive off on battery (via wlr-output-management; coordinate with the umbriel-displays plugin). Credit baizhu945's GPU-mode action matrix.
2. **Upstream to OGC asusctl** (Rust/zbus; design talk on Discord first; AI assistance must be disclosed):
   - read/write PPT and fan tuning for any profile × power-source combination;
   - fan-curve properties with change signals;
   - a `pending_reboot` property and a single GPU-mode property;
   - help land #404 (hidraw autosuspend) and the D-Bus reference docs (#452).
3. **No new daemon.** Once the plugin covers its features, retire supergfxd.

## v0.1.0 built (2026-11-15): [GenuineMoron/noctalia-rog-control](https://github.com/GenuineMoron/noctalia-rog-control) (moved to its own public repo 2026-11-15)
- **Language:** Luau, the only language Noctalia plugins run in; plugin_api 43, so it works on Noctalia 5.4.1. The work happens in asusd (Rust), which is already event-driven.
- **Entries:** service, bar widget, panel (420 px wide, height fits its content), Control Center tile (`mode`), and a shared `lib/model.luau`.
- **Verified on this laptop:**
  - streams `gdbus monitor --system --dest xyz.ljones.Asusd` and `--dest org.supergfxctl.Daemon`;
  - the panel shows live state (plugged in, 80%, held at limit; Standard, GPU asleep; overdrive on; keyboard Medium/Static following the theme; fans 1700–3800 rpm, CPU 40 °C);
  - IPC `next-profile` stepped Balanced → Turbo → Silent → Balanced, with `PlatformProfileOnAc` following each step;
  - `noctalia plugins lint`: 0 errors, 0 warnings.
- **Keyboard colour:** "follow the theme" moved into the plugin (Lighting → Match theme colour). `theme-accent-sync` now only recolours folder icons.
- **Gotchas:**
  - `noctalia.runAsync` with a plain string does not go through a shell; use `{ "sh", "-c", ... }`.
  - Manifest changes need a plugin disable/enable.
  - supergfxd's stream must start once its first query answers.
- **Store submission:** [noctalia-dev/community-plugins#1453](https://github.com/noctalia-dev/community-plugins/pull/1453), ready for review 2026-11-15, AI assistance disclosed. `thumbnail.webp` made with the official generator. Both CI checks pass: `validate` (manifest) and `enforce` (PR template).
  - Gotcha: the template check matches checklist lines word for word. One reworded line (a slip in the first PR body) failed it. Copy the checklist verbatim from `.github/PULL_REQUEST_TEMPLATE.md` on `main`, and test the body locally with `missing_requirements(body, require_completed=True)` from `.github/workflows/scripts/enforce-pr-template.py`.
- **Next:**
  - fan-curve editor and power limits (needs the asusd additions listed above);
  - auto 60 Hz plus overdrive off on battery (optional).

## Charge limit: one owner, UPower (2026-11-15)
- **Problem:** asusd wrote 80% straight to the battery driver while UPower's `ChargeThresholdEnabled` stayed false. Noctalia's Control Center Power tab therefore flagged it "Set by another tool" and locked its toggle (`power_tab.cpp`: UPower disabled + restrictive threshold = ExternallyManaged).
- **Test:** toggling UPower `EnableChargeThreshold(b)` moved sysfs, asusd's live `ChargeControlEndThreshold` **and** `/etc/asusd/asusd.ron` along with it (80 ↔ 100). asusd follows UPower, so there's no tug-of-war, and asusd re-applies the same value at boot.
- **Now:** UPower owns the limit (polkit `enable-charging-limit` allows the active session; no prompt). Noctalia's Power tab shows "Stops at 80% · Use charge thresholds" as a working toggle.
- **ROG Control:** its toggle calls UPower, and a third `gdbus monitor` stream (UPower battery object, filtered to threshold changes) keeps it in sync. "Charge to 100% once" stays on asusd. The plugin's percentage setting is removed: UPower's configured limit (hwdb `CHARGE_LIMIT`, default 75,80; this battery has only an end threshold) sets the number. Change it with a local hwdb rule if ever wanted.
- Battery health per Noctalia: 85% of design capacity.

## Umbriel fixes, live (test build f55de43d)
- **VRR:** with `vrr = "fullscreen"` (runtime override), an HDR clip logged exactly one "backend rejected enabling VRR without a modeset" warning and 0 EINVAL. VRR stayed off, and PSR1 was enabled after exit. Before the fix: 1,029 failed commits in 33 min, and VRR stuck on.
- **EBUSY:** 3 in 21 min (all at login), against 10–15/min while browsing before. Likely cause: the VRR retry storm (commits on every focus/title change) collided with frame commits. Collecting more data with VRR enabled at runtime.
