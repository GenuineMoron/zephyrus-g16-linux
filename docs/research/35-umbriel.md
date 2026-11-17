# 35 Umbriel as a second login session (research, 2026-11-15)

Read-only research. Nothing installed, nothing started, no settings changed.
Not run (read-only scope): lspci, nvidia-smi, vulkaninfo, /sys/class/drm/card0*.

Labels: **PROVEN** = backed by a doc, source, package metadata or issue (link given). **INFERRED** = my reasoning from those, not tested.

Upstream docs are https://docs.noctalia.dev/umbriel/ (sub-pages named inline). The repo docs were read as raw files from https://github.com/noctalia-dev/umbriel (docs/user/*.md, PACKAGING.md, examples/config.toml).

## Bottom line

- Umbriel is a clean, separate session. It is wired for exactly what this laptop's setup needs: a systemd `umbriel.service` that publishes `graphical-session.target`, so `noctalia.service` starts unchanged. **PROVEN**
- GPU isolation maps directly from the niri setup: `[drm] ignored_devices` / `ignored_pci_addresses` keeps the RTX 4070 unopened. **PROVEN** (docs), **INFERRED** that it keeps the dGPU in D3cold.
- Biggest practical risks on this box: 240 Hz idle CPU with blur, VRR/HDR fullscreen edge cases, DPMS-off bugs, and the packaged build lacking the logout fix. The packaged build is also behind the upstream session-exit fix.
- Do not run `start-umbriel` for the smoke test. Use `umbriel -c <test.toml>` directly inside a niri window.

## 1. How Umbriel starts

- Session entry: `umbriel.desktop` in `wayland-sessions`, whose Exec is `start-umbriel`. **PROVEN** (PACKAGING.md, "Installed layout" and "Session integration"). Not installed yet on this machine: `/usr/share/wayland-sessions/` has only `niri.desktop`.
- `start-umbriel` runs `umbriel.service` (`Type=notify`) in the user manager when a systemd user manager is reachable. Otherwise it runs `umbriel` directly. **PROVEN** (PACKAGING.md; docs installation page).
- The service queues `graphical-session.target` and `umbriel-session.target` in its startup transaction. It sends READY only after the graphical env (WAYLAND_DISPLAY etc.) is published to systemd and D-Bus. So services ordered after `graphical-session.target` wait for it. **PROVEN** (PACKAGING.md).
- The local `~/.config/systemd/user/noctalia.service` (WantedBy/PartOf graphical-session.target) should therefore start under Umbriel without changes. **INFERRED** from the above; not tested.
- Login env: `start-umbriel` loads zsh `~/.zprofile`-style login env, not `~/.zshrc`. Values from `environment.d` also apply; `50-gtk-gl-renderer.conf` (GSK_RENDERER=gl) and `60-niri-apps.conf` apply to Umbriel too. **PROVEN** (PACKAGING.md, "Session integration"); the environment.d files are local.
- Umbriel always sets `XDG_CURRENT_DESKTOP`, `XDG_SESSION_TYPE` and `WAYLAND_DISPLAY`; they cannot be overridden in `[environment]`. **PROVEN** (docs configuration page).
- Logs: `$XDG_CACHE_HOME/umbriel/umbriel.log`. **PROVEN**.

**Two local things to fix before using it:**
- `~/.config/systemd/user/swayidle.service` (WantedBy graphical-session.target) runs `niri msg action power-off-monitors` and `niri msg action power-on-monitors`. Under Umbriel those fail, so DPMS-on-idle never happens. The `timeout 300 'noctalia msg session lock'` part is compositor-neutral. **PROVEN** (local file). Plan: make a `umbriel`-only variant (or condition the unit on the niri session) that uses `umbriel msg dpms-off` / `dpms-on`, after checking issue #660 below.
- Upstream says to add noctalia to `[general] autostart`. Do not do that, because `noctalia.service` already starts it. Double instance risk. **INFERRED**.

## 2. Multi-GPU (Intel iGPU + NVIDIA dGPU)

- Umbriel discovers DRM devices itself. There is no documented `WLR_DRM_DEVICES` for Umbriel. The docs only state that `WLR_BACKENDS` with exclusions supports only drm/libinput. **PROVEN** (configuration page, `[drm]` section). Issue #666 shows `WLR_RENDER_DRM_DEVICE` being used by a user, but it is not a documented Umbriel option. **PROVEN** that it exists in the issue report; treat as unsupported.
- The documented way to keep a GPU closed is:
  ```toml
  [drm]
  ignored_pci_addresses = ["0000:01:00.0"]
  ignored_devices = ["/dev/dri/by-path/pci-0000:01:00.0-card"]
  ```
  Restart required. Startup fails if no allowed GPU initializes. Exclusions apply to native sessions only. **PROVEN** (configuration page). The PCI address `0000:01:00.0` is taken from the local niri config, not from sysfs.
- Add the render node too: `/dev/dri/by-path/pci-0000:01:00.0-render`. The docs say `ignored_devices` accepts card or render-node paths. **PROVEN** (docs). Niri only lists the card; the render node is what Vulkan games open, so exclude it too if the dGPU must stay truly idle. **INFERRED** on the effect.
- Parity with niri: niri already ignores the card, so HDMI and the NVIDIA-wired USB-C port are dead in both sessions. Dropping the ignore would be needed for external displays on NVIDIA; that undoes the runtime-suspend fix. **PROVEN** (config) / **INFERRED** on the tradeoff.
- Games on the dGPU: Vulkan apps open the NVIDIA render node and present through PRIME to the Intel scanout. The niri setup already does this without an NVIDIA card in the compositor. Umbriel's behaviour here is **INFERRED**, untested. Watch for issue #666 type failures (EGLImage / FBO on the iGPU-driven panel). That issue is an NVIDIA-primary case, so the exclude-NVIDIA config avoids it. **PROVEN** (issue #666, config avoids that path).
- Per-session note: the greeter's `WLR_DRM_DEVICES=/dev/dri/intel-igpu` is set only for the greeter process. The Umbriel session will not inherit it. **INFERRED** (greetd runs a fresh session command). Umbriel must get its own `[drm]` block in the per-user config.

## 3. Proposed config for this laptop (not written)

Full draft lives in the note below; the blocks here are what matters.

Outputs (`[output.eDP-1]`; the docs use the connector name, confirm with `umbriel outputs` in the test session):
```toml
[output.eDP-1]
mode = "2560x1600@240"
scale = 1.5                 # niri: scale 1.5
vrr = "fullscreen"          # niri: on-demand; see risks #699 #749 #779
hdr = "auto"                # docs: HDR for fullscreen with HDR metadata
bit_depth = 8               # try 10 later; #408 was a black screen on the HDR/XR30 path
color_profile = "<local-copy>/GU605MI_8086_834C41A3_CMDEF.icm"
sdr_gamut = "native"        # "srgb" maps untagged SDR into the panel gamut; needs color_profile
sdr_white = 203
direct_scanout = true
```
- `hdr`, `vrr`, `bit_depth`, `color_profile`, `sdr_gamut`, `sdr_white`: all **PROVEN** in outputs docs. The ICC path is accepted as an absolute path; a changed mtime triggers reload. The ICC is only a characterization; lcms2 is a listed runtime dep (`pacman -Si` Depends On includes lcms2). **PROVEN**.
- The ICC file itself: I did not open it. Its name suggests an ASUS factory profile for the Intel display path. **INFERRED**.

Input (mirrors niri `input.kdl`):
```toml
[input.keyboard]
numlock_toggle = true      # niri numlock; see #788 numlock bug
[input.touchpad]
tap = true
natural_scroll = true
scroll_factor = 0.4        # niri scroll-factor 0.4
disable_while_typing = true
disable_on_external_mouse = true
[input.focus]
follows_mouse = "sloppy"   # niri focus-follows-mouse; see #368 (steals focus during scroll)
[input.cursor]
theme = "capitaine-cursors"
size = 24
```
Keys and defaults: **PROVEN** (input docs and example). Niri's `workspace-auto-back-and-forth` has no documented Umbriel key. **INFERRED** that it is absent.

Layout and look (from `layout.kdl`, `rules.kdl`, `misc.kdl`):
```toml
[layout]
mode = "scrolling"
gap = 16                   # niri gaps 16; Umbriel default 8
extent_presets = [0.333, 0.5, 0.667]
[layout.scrolling]
default_extent_fraction = 0.5
[appearance]
corner_radius = 20         # niri geometry-corner-radius 20
[appearance.title_bar]
mode = "off"               # niri prefer-no-csd look (key name from example; default not stated)
[appearance.blur]          # Umbriel adds blur; niri has none, so disable it (see risks)
```
Layout keys: **PROVEN** (layout docs). `corner_radius` is a global appearance key (window rules doc). Blur: the example's first `[[window_rule]] blur = true` should be removed or set false to match niri and save iGPU/CPU. Window-rule blur fact: **PROVEN** (example + issue #473).

Window rules (from `rules.kdl`):
```toml
[[window_rule]]
match.title = "^notificationtoasts_.+_desktop"
default_position = { x = 0, y = 0, anchor = "bottom_right" }
default_focused = false
default_pinned = true

[[window_rule]]
match.app_id = "^(zen|firefox)$"
match.title = "^Picture-in-Picture$"
default_floating = true
default_maximize = false

[[window_rule]]
match.app_id = "^steam_app_"
vrr = "always"             # niri: VRR for Steam games only

[[window_rule]]
match.app_id = "(?i)bitwarden"   # regex flavour unknown; use "^[Bb]itwarden" if (?i) fails
block_capture = true       # niri block-out-from screencast
```
- `block_capture`: **PROVEN** (window-rules doc). The `(?i)` flag is **INFERRED** to be a risk: the regex engine is unverified.
- Steam main window: niri floats all Steam windows except `^[Ss]team$`. Umbriel regex negative match is unverified, so this rule is **INFERRED** and may need a title-specific rule.

Autostart and env:
```toml
[general]
autostart = ["/usr/lib/mate-polkit/polkit-mate-authentication-agent-1"]   # niri spawn
xwayland = true            # default; needed for Steam/Proton
[environment]
# niri misc.kdl env block, minus what Umbriel forbids (XDG_CURRENT_DESKTOP, XDG_SESSION_TYPE).
# Most of it is already in environment.d, so this can stay empty.
```
Autostart and xwayland: **PROVEN** (example config comment: "XWayland support is enabled by default"). Polkit agent: the niri config uses it, and Umbriel's `autostart` is the equivalent.

Keybinds (`[keybinds]` replaces the whole default set, so list every bind needed). Mapped from `keybinds.kdl`:

| niri bind | Umbriel action |
|---|---|
| Mod+Return | `spawn alacritty` (repeat=false) |
| Mod+Space / Mod+CTRL+Return | `spawn noctalia msg panel-toggle launcher` |
| Mod (alone) | launcher (Umbriel default; keep) |
| Mod+S / Mod+Shift+S | `spawn noctalia msg panel-toggle control-center` / `settings-toggle` |
| Mod+V | `spawn noctalia msg panel-toggle clipboard` |
| Mod+CTRL+Space | `spawn noctalia msg panel-toggle launcher /emo` (replaces Umbriel's scratchpad-restore) |
| Mod+B / Mod+E | `spawn zen-browser` / `spawn nautilus` |
| Mod+ALT+L | `spawn noctalia msg session lock` |
| Mod+Shift+Q | `spawn noctalia msg panel-toggle session` |
| Alt+Tab | `spawn noctalia msg window-switcher hold` (Noctalia doc) |
| Mod+Escape | `shortcuts-inhibit-toggle` (niri emergency escape; Umbriel default quits) |
| CTRL+ALT+Delete | `session-quit` |
| Mod+Q | `window-close` |
| Mod+H/J/K/L and arrows | `window-focus-left/down/up/right` |
| Mod+CTRL+H/J/K/L and arrows | `column-move-left/right`, `window-move-up/down` |
| Mod+Comma / Mod+Period | `window-consume-left` / `window-consume-right` (semantics differ from niri) |
| Mod+R / Mod+Shift+R | `window-cycle-primary-extent` / `-back` |
| Mod+Minus / Mod+Equal | `window-modify-primary-extent -0.10 / +0.10` |
| Mod+Shift+Minus / Mod+Shift+Equal | `window-modify-secondary-extent -0.10 / +0.10` |
| Mod+F | `window-toggle-maximize` (niri maximize-column analogue) |
| Mod+Shift+F | `window-toggle-fullscreen` |
| Mod+M | `window-toggle-maximize-to-edges` |
| Mod+T / Mod+Shift+V | `window-toggle-floating` / `window-focus-switch-floating` |
| Mod+W | `column-toggle-tabbed` |
| Mod+O | `overview-toggle` (repeat=false) |
| Mod+1..9 | `workspace-switch N` |
| Mod+Shift+1..9 | `window-move-to-workspace N` (niri used Mod+CTRL+N) |
| Mod+Tab | `workspace-previous` (niri focus-workspace-previous) |
| Mod+WheelUp / Mod+WheelDown | `window-focus-left` / `-right` (Umbriel example) |
| Mod+Shift+P | `spawn umbriel msg dpms-off` (see risk #660; test first) |
| Media / brightness XF86 keys | `spawn noctalia msg volume-up` etc., `allow_when_locked = true` (as niri and the Umbriel example) |
| Shift+Print | `spawn noctalia msg screenshot-annotate` |
| Print / CTRL+Print / ALT+Print | no Umbriel screenshot action documented. Needs grim/slurp via spawn; **INFERRED** that wlr-screencopy works (docs name it for Sunshine). |

Dropped: `focus-monitor-*` and `move-column-to-monitor-*` (one output, so moot), `Mod+Ctrl+Shift+R` and `Mod+Ctrl+R` height resets (no height in scrolling layout), Mod+C/Mod+CTRL+C centre (no documented action; **INFERRED**).

## 4. Known bugs and risks for this laptop

Numbers are issue numbers on noctalia-dev/umbriel (https://github.com/noctalia-dev/umbriel/issues/N).

**Packaging and session**
- The CachyOS build `0.1.0.r1459.2952bbc-1` is behind upstream commit 4227845, which fixes #627 (logout via Noctalia leaves `umbriel.service` running, next login is a blank-screen loop). GitHub compare: 2952bbc is behind 4227845 by 24 commits. **PROVEN**. Consequence: wait for a newer package or build from source before relying on logout. Also check #77 (no compositor PID, Noctalia logout cannot kill the compositor); closed, but verify on the test build.
- Packaged deps (`pacman -Si`): wlroots0.20.1+, xdg-desktop-portal-umbriel, xorg-xwayland, lcms2. **PROVEN**.

**Idle power and CPU (matters for the battery work)**
- #473: idle CPU 9% without blur, 17–20% with blur, at 165 Hz; scales with refresh. **PROVEN** for 165 Hz. At 240 Hz **INFERRED** ~1.5x.
- #507: ~80% of one core while locked on a hybrid Intel/NVIDIA box with a 144 Hz output on the dGPU. This panel is on the Intel iGPU and the dGPU is excluded, so probably not the same path. **INFERRED** low risk; test it with `loginctl lock-session`.
- #381 (hibernate artifacts) was closed as a missing wallpaper service, not a compositor fault. **PROVEN**. The local cs35l56 hibernate hook is outside the compositor. **INFERRED** no conflict.
- #292 (s2idle resume) was closed as stale firmware. **PROVEN**.

**Display**
- #408: HDR=auto fullscreen gives a black screen on Intel Arc (Xe driver), with direct scanout off and an XR30 switch. Closed upstream as a kernel regression. **PROVEN**. Relevant: this iGPU runs i915, not xe, so the exact path is different, but the XR30 path is the same risk. Start with bit_depth=8.
- #699: VRR stays on after leaving fullscreen with `vrr = "fullscreen"`. Open. **PROVEN**. #779: VRR choppiness after workspace switch with a deadlock. Open. #749: cursor movement breaks VRR in fullscreen. Open. These hit the vrr="fullscreen" choice directly. Fallback: `vrr = "disabled"`.
- #660: `dpms-off` does not keep displays off, and `dpms-on` is needed (multi-output). Open. **PROVEN**. #234: no signal after power-cycle, needs dpms-off then dpms-on. Open. The local swayidle DPMS and the Mod+Shift+P bind depend on this.
- #218: DP Alt Mode MST swapchain failures (not this topology). Open.

**Steam and games**
- #361: full-screen Steam game pauses or drops connectivity when focus leaves it (laptop, Umbriel 0.1.0). Open, 12 comments. Hyprland 0.57 fixed the same symptom. **PROVEN** on the issue.
- #612, #468, #557: Steam Big Picture focus and freeze problems. Open. **PROVEN**.
- #426: Xwayland windows (Steam client, Settings) exist but are never rendered. Open. Relevant to the niri Steam black-window fix (`-cef-disable-gpu`). **PROVEN**.
- #422: sdl-freerdp never goes fullscreen under Xwayland. Open.

**Input and focus**
- #368 and #538: follows_mouse steals focus during layout scroll. Open. **PROVEN**. Consider `follows_mouse = "off"` if it bites.
- #788: NumLock randomly disables. Open. **PROVEN**.
- #767: phantom HID key makes a spawn bind repeat forever (brightness storm). Open. Relevant to the brightness keys.

**Protocols and clients**
- #278: screencast bakes the cursor when PAINT_CURSORS is absent. Open. **PROVEN**.
- #792: dmabuf broken with mpv. Open.
- Wine/Proton floating windows resize after first present (#785). Open.

**Colour**
- `[output]` ICC characterization is documented, but issue #308 ("Make use of the color pipeline") is still open. **PROVEN**. Expect the ICC to be a partial feature; verify with `umbriel color`.

**Security**
- Input capture and XTest need permission prompts (security doc). Harmless here. **PROVEN**.

## 5. Smoke test nested inside niri (do not disturb niri)

Preconditions and cautions:
- Do NOT use `start-umbriel`. It starts `umbriel.service` and publishes `WAYLAND_DISPLAY` and `graphical-session.target` to the systemd user manager, overwriting niri's env and pulling in `noctalia.service`. **PROVEN** (PACKAGING.md) / **INFERRED** on the nested side.
- Nested mode uses Alt as `Mod`. Niri owns Alt+Tab and Alt+Print. Avoid those keys inside the test. **PROVEN** (keybinds doc: "Mod is Alt when Umbriel runs nested").
- Nested umbriel uses the direct launch path, not systemd-run or the user manager. **PROVEN** (PACKAGING.md: "for nested launches... the direct launch path").

Steps (after installing the package; it was not installed during this research):
1. Baseline: `systemctl --user show-environment | sort > $SCRATCH/env-before.txt`; `pgrep -a noctalia`; `niri msg outputs`.
2. Test config at `~/.config/umbriel/test.toml`: `[general] xwayland = false`, `autostart = []`, `[drm]` section absent (nested does not open DRM), `[output."<nested name>"]` as needed. Validate with `umbriel config validate -c ~/.config/umbriel/test.toml`. **PROVEN** (config validate docs).
3. Start in a floating niri terminal (Mod+T): `WAYLAND_DISPLAY` unchanged; run `umbriel -c ~/.config/umbriel/test.toml`. Do not set `WLR_DRM_DEVICES`.
4. From a second terminal, use the test socket only: `umbriel msg` picks `$XDG_RUNTIME_DIR/umbriel-$WAYLAND_DISPLAY.sock`; confirm it is the nested one with `umbriel outputs`. **PROVEN** (IPC doc).
5. Confirm the nested compositor opens no NVIDIA node: `ls -l /proc/<umbriel-pid>/fd | grep -E 'dri|nvidia'`. Expect nothing on NVIDIA. **INFERRED** on the nested backend (wlroots Wayland backend should not open DRM).
6. Re-run `systemctl --user show-environment | sort` and diff against baseline. No change expected. **INFERRED**.
7. Keep Noctalia out of the nested test (no autostart, no `noctalia.service` run). Two Noctalia instances would fight over IPC.
8. Exit with the nested window's close bind, then `pgrep -a umbriel` to confirm it is gone. The #627 logout bug does not apply to a direct launch. **INFERRED**.

## Sources

- https://docs.noctalia.dev/umbriel/ (installation, configuration, outputs, input, keybinds, ipc, streaming pages)
- https://docs.noctalia.dev/noctalia/compositor-settings/umbriel
- https://github.com/noctalia-dev/umbriel: PACKAGING.md, examples/config.toml, docs/user/window-rules.md, layout.md, security.md
- Issues cited above (noctalia-dev/umbriel)
- Local: ~/.config/niri/config.kdl and cfg/*.kdl; /etc/greetd/config.toml; /usr/share/wayland-sessions/niri.desktop; ~/.config/systemd/user/noctalia.service and swayidle.service; ~/.config/environment.d/*.conf; `pacman -Si umbriel xdg-desktop-portal-umbriel`
