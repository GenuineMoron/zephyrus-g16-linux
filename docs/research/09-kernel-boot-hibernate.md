# 09 Kernel, boot, hibernate (summary notes; claims to be verified)
- image_size default = totalram*2/5 (kernel/power/snapshot.c) -> 12.2 GiB here.
- /sys/power/hibernate_compression_threads exists (default 3, CMP_THREADS, clamp ncpu-1); cmdline hibernate_compression_threads=N.
- Compressor lzo default; lz4 selectable at runtime (/sys/module/hibernate/parameters/compressor); recorded in image header.
- zram pages are part of the image (double compression) — test zram-off.
- Cmdline: pcie_aspm=force suspicious (A/B), nowatchdog hides lockups, nvidia-drm.fbdev=1 redundant (default 1).
- Boot: firmware 6.81 s, loader 2.65 s (GRUB_TIMEOUT=1 hidden ~1 s), initrd 2.10 s, userspace 4.11 s; top units grub-btrfs-snapper 1.79 s, asusd 1.28 s, boot-efi.mount 1.25 s, a CIFS network mount 665 ms, tailscaled 621 ms; kernel 17.5 MB, initramfs 25.8 MB.
- Memory: swappiness=100 (one read) [another read showed 150 earlier — verify], page-cluster 0, vfs_cache_pressure 50, dirty 10/3, MGLRU on, zswap off, zram zstd ~31 GiB prio 100. systemd-oomd disabled -> recommend enabling with user-slice ManagedOOM.
- Config present: HIBERNATION, ACPI_DEBUG, PM_TRACE_RTC, PM_DEBUG, PM_SLEEP_DEBUG, KEXEC, CRASH_DUMP, DEBUG_INFO_BTF, PSTORE_RAM=m, INTEL_PMT_CRASHLOG=m, CRYPTO_LZ4=y. Absent: PM_ADVANCED_DEBUG, PSTORE_CONSOLE, PSTORE_PMSG; NO_HZ_IDLE not set (check NO_HZ_FULL).
- Experiment matrix: compression threads 3->8; lz4; zram off; image_size sweep 2/4/8 GiB; GRUB_TIMEOUT=0; drop pcie_aspm=force; enable systemd-oomd.
