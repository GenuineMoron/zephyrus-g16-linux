# 10 Desktop UX (summary notes; items marked inferred need verification)
niri 26.04, validate OK; eDP-1 2560x1600@240, scale 1.5, VRR on-demand.
Ranked improvements:
1. No Alt+Tab window switcher (Mod+Tab = previous workspace). Check noctalia window_switcher ([shell.window_switcher] exists in docs).
2. Portal file dialogs may tile instead of float (inferred) — window rule for dialogs.
3. screenshot-path null: screenshots only to clipboard; set ~/Pictures/Screenshots.
4. Theming split: GTK3 WhiteSur-Dark, GTK4 WhiteSur-Dark-solid, noctalia theme from wallpaper; WhiteSur gtk.css parse error at line 3792 on every GTK app start; adw-gtk3-dark installed (cleaner choice).
5. Touchpad scroll-factor 0.4 (low); click-method default; libinput "kernel bug: Touch jump detected" x4 today.
6. noctalia lock_before_suspend=false.
7. Not configured: hot corners, DND schedule, external monitor/lid policy (DP-1 block commented). Night light on.
8. Lock screen: no avatar (~/.face not a regular file), weather fetch fails (DNS/timeouts).
9. power-profiles-daemon masked (asusd is the authority) — confirm noctalia doesn't need PPD.
10. Fractional scale 1.5 + gtk-xft-dpi=120: GTK3 apps may look small/soft (unverified).
Journal: harmless — wireplumber bluez AlreadyExists, pam_unix setuid on unlock, tracker miner missing, xwayland-satellite ChangeProperty, kdeconnect portal race; papercuts — WhiteSur CSS, open-meteo timeouts; track — niri "DRM node 0000:01:00.0-card is not a render node" despite ignore-drm-device (niri still probes dGPU node?), smithay glTexSubImage2D GL_INVALID_VALUE (rare).
Proven: portals gnome;gtk via niri-portals.conf, keyring unlocked by noctalia, prefer-dark, grayscale AA.
Open: noctalia window switcher/hot corners; screen sharing untested; QT_QPA_PLATFORMTHEME=gtk3 plugin installed?
