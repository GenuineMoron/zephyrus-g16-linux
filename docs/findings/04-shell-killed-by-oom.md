# 04: One app running out of memory took down the shell and the lock screen

**Status:** fixed (2026-11-14).

## What happened

1. A test program ran away and used all RAM and swap. The kernel's OOM killer killed it.
2. The program had been started from a terminal, and that terminal had been launched from noctalia. Every process noctalia launched lived in noctalia's own systemd scope (`app-niri-…-<pid>.scope`). systemd's default `OOMPolicy=stop` therefore stopped the whole scope: **noctalia, its lock screen, and every app launched from it**.
3. The session was locked. When the lock client dies, niri shows a solid **red** screen by design: the session is still locked, but nothing can unlock it.
4. Pressing the power button suspended and resumed the laptop. Each resume briefly showed a text console, because NVIDIA's `chvt 63` services were still active then (see [02](02-standby-nvidia-wakes-idle-gpu.md)). The only way out was holding power.

This is also a plausible explanation for an earlier "noctalia sometimes isn't running" mystery.

## Fix

**Noctalia now runs as a systemd user service** ([configs/home/.config/systemd/user/noctalia.service](../../configs/home/.config/systemd/user/noctalia.service)):
- `WantedBy`/`PartOf` `graphical-session.target` (niri-session provides it);
- `Slice=session.slice`;
- `Restart=always`, `RestartSec=200ms`;
- `OOMPolicy=continue`.

**Each launched app gets its own unit.** Setting `launch_apps_as_systemd_services = true` in `[shell]` of `~/.local/state/noctalia/settings.toml` makes dock and launcher apps run as `app-<id>@<random>.service`. Noctalia only honours this when it runs under the systemd user manager.

**The app environment matches what the compositor gives its children.** Apps started by systemd get their environment from the user manager, so [configs/home/.config/environment.d/60-session-apps.conf](../../configs/home/.config/environment.d/60-session-apps.conf) sets the same values the compositor sets (originally niri's `environment {}` and `cursor {}`; Umbriel since 2026-11-15):
- `QT_QPA_PLATFORM`;
- `ELECTRON_OZONE_PLATFORM_HINT`;
- the cursor theme and size.

**The lock screen comes back after a crash.** If noctalia dies while locked, the session stays locked. [noctalia-relock-if-locked](../../configs/home/.local/bin/noctalia-relock-if-locked) runs after every start. If logind's `LockedHint` is set, it asks noctalia to lock again, retrying every 0.3 s until noctalia logs "session is locked". The compositor logs that it replaced the dead lock (niri: `locking session (replacing existing dead lock)`).

**Autostart no longer spawns noctalia.** Remove noctalia from niri's `spawn-at-startup`.

## Verified

| Test | Result |
|---|---|
| Lock, then `kill -9` noctalia | red briefly; noctalia restarted and the lock screen came back by itself; unlock worked |
| Dock-launched Nautilus and Spotify | ran in their own `app-…@….service` units, with the right cursor and Wayland settings |
