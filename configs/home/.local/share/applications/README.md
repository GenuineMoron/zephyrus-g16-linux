# Launcher overrides

Per-user copies of system `.desktop` files win over the system ones with the same name.

**Hidden with `NoDisplay=true` (2026-11-15).** These are developer, test or setup tools nobody opens from a launcher:
- `blackmagicraw-speedtest`, `DaVinciControlPanelsSetup`
- `lstopo`, `qv4l2`, `qvidcap`
- `jconsole-java-openjdk`, `jshell-java-openjdk` (Java is a DaVinci Resolve dependency)
- `micro`, `vim`
- `nvidia-settings`
- `org.kde.kdeconnect.nonplasma`, `org.kde.kdeconnect.sms`
- `org.cachyos.scx-manager`

Each override is the system file plus `NoDisplay=true`. Delete it to show the app again.

**`zen.desktop`:** see `zen.desktop.README`.
