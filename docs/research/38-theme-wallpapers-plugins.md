# 38: Theme, daily photo wallpapers, keyboard colour, Noctalia plugins (2026-11-15)

Goal: a clean, macOS-grade desktop on Umbriel + Noctalia 5.4.1, based on a r/Noctalia
screenshot I liked (vertical left bar, rounded screen frame, sage palette from
the wallpaper, Nautilus themed to match). The anime art and the launcher illustration
were dropped, and so were the poster's desktop widget wall, 28-app dock and cursor trail.

## Look
| Piece | Setting |
|---|---|
| Bar | Left, 42 px, solid, capsules (`surface_container`), no shadow/blur. Top: launcher (CachyOS logo, colourised), workspaces (pills), CPU. Centre: clock `{:%H\n%M}`. Bottom: tray, wallpaper, clipboard, notifications, control centre, battery, session |
| Screen | `shell.screen_corners` on, `corner_radius_scale = 1.5` |
| Windows (Umbriel) | `corner_radius = 14`, `border_width = 1` (accent from Noctalia's umbriel template), shadow softness 24 / y 6 / `#00000066`, `layout.gap = 8`, no blur |
| Colours | `theme.source = "wallpaper"`, `m3-tonal-spot`, dark. Templates: gtk3, gtk4 (adw-gtk3-dark), kcolorscheme, alacritty, umbriel, plus a user template for the keyboard |
| Terminal | Alacritty opacity 0.8 → 1.0: photos behind translucent text hurt readability |
| VRR | `vrr = "disabled"` until umbriel#809 is fixed. It never enabled, and after HDR switches it stuck ON, which disabled PSR |

The config is in [configs/home/.local/state/noctalia/look-excerpt.toml](../../configs/home/.local/state/noctalia/look-excerpt.toml) and [configs/home/.config/umbriel/config.toml](../../configs/home/.config/umbriel/config.toml).

## Daily photo wallpaper ([wallpaper-feed](../../configs/home/.local/bin/wallpaper-feed))
- **Sources:** Bing photo of the day (`HPImageArchive.aspx?format=js&n=8&uhd=1`, `urlbase + _UHD.jpg`) and Windows Spotlight (`fd.api.iris.microsoft.com/v4/api/selection?placement=88000820&bcnt=1`). Both are editor-curated real photography at 3840x2160; a 16:10 crop at 2560x1600 needs no upscaling. Unsplash was rejected: its API guidelines forbid wallpaper apps.
- **Library:** keeps the newest 30 photos, with credits in `~/Pictures/Wallpapers/.credits.tsv`.
- **Rotation:** once a day (hourly was too often). The same job sets the newest unseen photo via `noctalia msg wallpaper-set`. Noctalia's own rotation timer stays off.
- **Scheduling:** a systemd user timer, daily, `RandomizedDelaySec=2h`, `Persistent=true`. Exit code 75 (offline) is retried 10 min later. Metered connections are skipped. One run costs about 0.4 s of CPU.
- **Bar button:** left click opens the picker, right click picks a random photo, scroll steps next/previous.

## Keyboard colour and folder icons ([theme-accent-sync](../../configs/home/.local/bin/theme-accent-sync))
- A Noctalia user template (`accent`) renders `colors.primary` into `~/.config/noctalia/generated/accent.txt`. Its post-hook runs `theme-accent-sync`, which only acts when the colour changes. Each run takes about 0.1 s.
- Icons: Adwaita plus MoreWaita (AUR, PKGBUILD reviewed: upstream maintainer, pinned commit, copies files only). The overlay theme `Adwaita-Accent` (`~/.local/share/icons`) holds 196 Adwaita/MoreWaita place icons recoloured from Adwaita blue to the accent hue (HLS: keep lightness, saturation scaled to the accent). It is swapped in atomically and its mtime bumped so GTK reloads, and it inherits MoreWaita and Adwaita for everything else. `gsettings icon-theme 'Adwaita-Accent'`.
- Dark-mode primaries are pastel, and LEDs show low saturation as white. The script keeps the hue and clamps saturation to 0.45–0.75, at full value. Example: the sage `#bbcf81` becomes a soft lime `#daff6f`.
- Brightness stays with the Fn keys and idle dimming.

## Plugins (code read before enabling)
| Plugin | Decision | Notes |
|---|---|---|
| noctalia/umbriel-companion 1.2.4 (official) | Enabled | 1.4.0 needs plugin API 54 (Noctalia 5.5) |
| mgeldi/pixel-shift 1.2.1 | **Removed 2026-11-15 (the moving bar was distracting)**; grim uninstalled | OLED burn-in care for the static bar: captures only the bar strip every 10 min (`grim`, installed), moves 1 px every 4 min. Fullscreen detection knows only Hyprland/Sway; an Umbriel contribution is possible |
| icefish/phone-connect 0.2.2 | Enabled, Control Centre tile | KDE Connect (already running). Pair the phone in the KDE Connect app. Chosen over demencia89/androidconnect (needs adb, scrcpy, ffmpeg) |
| rylos/tailnet 2.2.1 | Enabled, Control Centre tile, `poll_interval = 60` (default 5 s) | `tailscale set --operator=$USER` was set so up/down and exit-node switching work without sudo |
| jrohland/claudecode 1.1.3 | **Rejected** | When the Claude Code OAuth token expires, its script refreshes the token itself (`platform.claude.com/v1/oauth/token`) and writes new tokens into `~/.claude/.credentials.json`. That can log the CLI out, and it puts a third-party script on the credentials. Use Claude Code's `/usage` instead |
| noctalia/bitwarden (official) | Deferred | Not needed yet. |
| cleboost/asus-fans-controller-ec | **Rejected** | Writes EC fan registers as root via a third-party tool |
| Battery-limit plugins | Not needed | They duplicate asusd's charge limit |
| ROG/G-Helper | **Build our own** | No existing plugin is G-Helper-grade |

Noctalia froze its UI for 32 s while installing plugins: `poll source 13IpcPollSource dispatch took 32072.5ms`, a git export on the main loop. Worth reporting upstream. Enabling several plugins in quick succession also lost all but the first; enable them one at a time.

Control Centre shortcuts: wifi, bluetooth, `rylos/tailnet:toggle`, `icefish/phone-connect:tile`, nightlight, notification.

## Umbriel source analysis (umbriel#809/#810)
- **#810 EBUSY:** one commit per frame, sent the instant the flip lands. The kernel EBUSY most likely comes from the disabled cursor plane's previous `flip_done`. Each failure becomes a fixed 16 ms retry (`kFrameRetryDelayMs`), about 4 lost refreshes at 240 Hz.
  - Fix A: exponential backoff from 1 ms.
  - Fix B: a `max_render_time`-style delay (a feature, so scope it with the maintainers first).
  - Verify with `drm.debug=0x10`, grepping for "busy with a previous commit".
- **#809 VRR:** the adaptive-sync commit lacks `allow_reconfiguration`, so wlroots sends it without ALLOW_MODESET and i915 returns EINVAL. The refusal is never remembered, and 12 callers re-trigger it on focus and title changes. HDR modesets also turn VRR on, and turning it off then fails, so it stays stuck ON.
  - Fix: a `VrrTransition` helper that remembers refusals per output until a mode or config change, and doesn't stage VRR into HDR modesets.
  - Follow-up posted on #809.

## Greeter sync and greeter → desktop handoff (2026-11-15)
- **Why the greeter didn't follow the wallpaper:** Auto-Sync was off, and every sync needed an admin password (polkit `auth_admin`).
- **Fix (upstream's design):**
  - `sudo noctalia-greeter passwordless-sync enable <user>`: a narrow polkit rule that covers only the constrained `noctalia-greeter-apply-appearance --sync` action, and only from an active local session.
  - `[shell.greeter_sync] auto_sync = true`: syncs wallpaper, palette, font and corners on every change.
  - Also, `greeter.toml` still had `[session] default = "Niri"`; it is now `"Umbriel"`.
- **Handoff timeline** (login at 35.05 s):

  | Stage | Time |
  |---|---|
  | Greeter exits | 35.09 |
  | User manager + Umbriel start: **black** | 0.72 s |
  | Umbriel's first frame (backdrop colour) | 35.81 |
  | Noctalia init before creating the wallpaper | 0.52 s |
  | 3840x2160 JPEG decode | 0.18 s |
  | Wallpaper visible | ~36.65 |

- **Done:**
  - wallpapers are stored centre-cropped at 2560x1600, Lanczos, q92 (library 39 → 15 MB, decode about half);
  - `wallpaper.transition_on_startup = true` and `transition_duration = 1000` (fade instead of pop).
- **Upstream ideas:** the black gap is the greeter releasing the screen before the session exists. Possible fixes are for the greeter compositor to leave its last frame on the CRTC for the session's live-mode takeover, or for Noctalia to create the wallpaper surface before its other init.
