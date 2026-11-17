Same model here (GU605MI). One concrete cause of high idle power on this machine, measured with turbostat and Intel PMT telemetry:

- The package almost never reaches PC10: the OS requests it ~81% of the time and it is achieved ~0.3%. The PCH LTR sits at ~51 µs, coming from the xHCI, which is below the C10 threshold.
- The xHCI is held up by the two ASUS USB HID devices: 0b05:19b6 (N-KEY keyboard) and 0b05:193b (Slash). They never runtime-suspend, because asusd keeps their `/dev/hidraw*` nodes open (`hidraw_open()` → `hid_hw_power(PM_HINT_FULLON)`). In addition, USB devices default to `power/control=on`.
- With asusd built from OpenGamingCollective/asusctl PR #404 (opens hidraw per write; test report: https://github.com/OpenGamingCollective/asusctl/pull/404#issuecomment-6890492623) and `power/control=auto` on both devices, PC10 goes from 0.4% to ~65% with the screen off. Platform power drops by ~0.8 W.

Two other things that helped on this model:
- `GSK_RENDERER=gl`: GTK 4.16+ creates a Vulkan instance per app launch, which wakes an RTD3-suspended NVIDIA GPU for ~2.6 s.
- Turning the keyboard backlight off after 60 s idle saves ~0.5 W, as Armoury Crate does on Windows.

Screen-on idle still rarely reaches PC10, but that is not asusd or the display: PSR self-refresh is active 80–95% of the time and DC6 is entered normally. PMT telemetry puts 94% of the blocked package C-state requests on `TNTE_CDIE`, meaning the next timer event is too close. The cause is ordinary software wake-ups (browser, VPN daemon and so on), not this hardware.
