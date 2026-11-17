// SPDX-License-Identifier: GPL-2.0
/*
 * hibtrace - TEMPORARY hibernate diagnostics (2026-11-14).
 *
 * Loaded only while a hibernate test runs. It
 *  1. prints a line when each listed kernel/NVIDIA function is entered ("HT >")
 *     and when it returns ("HT <"), so the log shows the exact step reached;
 *  2. arms a watchdog when hibernation starts: if hibernation is still running
 *     after watchdog_secs, it prints every blocked task's stack and every CPU's
 *     backtrace, then panics - the panic saves the log to firmware storage
 *     (EFI pstore) and the kernel restarts by itself (sysctl kernel.panic=N);
 *  (A CMOS-clock step marker was tried and removed: it made the clock jump
 *   89 years on resume. Never write the RTC from here.)
 */
#include <linux/module.h>
#include <linux/kprobes.h>
#include <linux/hrtimer.h>
#include <linux/suspend.h>
#include <linux/sysrq.h>
#include <linux/sched.h>
#include <linux/ktime.h>

static int watchdog_secs = 120;
module_param(watchdog_secs, int, 0644);
MODULE_PARM_DESC(watchdog_secs, "panic (with stacks) if hibernation is still running after this many seconds; 0 = off");

static int last_stage;		/* read back after a restore; 0 = none */
module_param(last_stage, int, 0444);

struct traced_fn {
	const char *name;
	int stage_in, stage_out;	/* unused (old CMOS marker) */
};

/* Stage numbers are unused (the CMOS marker was removed). */
static const struct traced_fn traced[] = {
	/* core hibernation path */
	{ "hibernation_snapshot" },
	{ "swsusp_write",		 1,  2 },	/* writing image / image written */
	{ "hibernation_platform_enter",	 3,  0 },	/* platform (S4) power-down begins */
	{ "dpm_suspend_start",		 4,  5 },	/* device power-off callbacks */
	{ "dpm_suspend_end",		 6,  7 },	/* late + noirq power-off */
	{ "acpi_pm_prepare",		 8,  9 },	/* ACPI _PTS */
	{ "syscore_suspend",		10, 11 },	/* interrupts off */
	{ "acpi_hibernation_enter",	12,  0 },	/* handed to firmware for S4 */
	{ "kernel_power_off",		13,  0 },	/* shutdown-mode power-off begins */
	{ "device_shutdown",		14, 15 },
	{ "machine_power_off",		16,  0 },	/* handed to firmware for S5 */
	{ "acpi_power_off" },
	{ "kthread_stop" },
	/* NVIDIA core (nvidia.ko) */
	{ "nv_pm_notifier" }, { "nv_set_system_power_state" }, { "nv_power_management" },
	{ "rm_power_management" }, { "nv_pmops_freeze" }, { "nv_pmops_thaw" },
	{ "nv_pmops_poweroff",		17, 18 },
	{ "nv_pci_shutdown",		19,  0 },
	{ "nv_pci_remove_helper" }, { "nv_linux_stop_open_q" }, { "nvidia_modeset_remove" },
	{ "nv_linux_remove_device_locked" }, { "rm_notify_gpu_removal" },
	{ "rm_check_for_gpu_surprise_removal" }, { "nv_procfs_remove_gpu" },
	{ "nv_clk_clear_handles" }, { "nv_stop_device" },
	{ "rm_cleanup_dynamic_power_management" }, { "nv_linux_remove_minor_locked" },
	{ "nv_acpi_unregister_notifier" }, { "rm_disable_gpu_state_persistence" },
	{ "nv_shutdown_adapter" }, { "rm_shutdown_adapter" }, { "nv_dev_free_stacks" },
	/* NVIDIA modeset / DRM */
	{ "nvkms_remove" }, { "nvKmsKapiRemove" }, { "nvkms_suspend" }, { "nvKmsSuspend" },
	{ "nvShutDownApiHeads" }, { "nvSuspendDevEvo" },
	{ "nv_drm_remove" }, { "nv_drm_remove_devices" }, { "nv_drm_dev_unload" },
};
#define NTRACED ARRAY_SIZE(traced)
#define KTHREAD_STOP_IDX 12

struct ht_probe {
	struct kretprobe rp;
	struct kprobe kp;	/* fallback when a return probe is not allowed */
	const struct traced_fn *fn;
	int kind;		/* 0 none, 1 entry+return, 2 entry only */
};
static struct ht_probe probes[NTRACED];

static struct hrtimer wd_timer;
static ktime_t hib_start;
static bool hib_active;

/*
 * The CMOS year marker was REMOVED (2026-11-14): Linux reads the RTC when it
 * comes back from hibernation and adds 100 years to two-digit years < 70 on
 * top of the firmware century byte, so "2011" became 2111 and the system clock
 * jumped 89 years. pm_trace avoids this by flagging the RTC as unusable; we
 * simply do not touch the RTC any more.
 */
static void mark_stage(int stage) { }

/* ---- tracing ---- */
static void ht_entry_common(struct ht_probe *p, struct pt_regs *regs)
{
	if (p->fn == &traced[KTHREAD_STOP_IDX]) {	/* kthread_stop(task) */
		struct task_struct *t = (struct task_struct *)regs->di;

		pr_emerg("HT > kthread_stop(%s/%d%s) by %s/%d\n",
			 t ? t->comm : "?", t ? t->pid : -1,
			 t && (READ_ONCE(t->__state) & TASK_FROZEN) ? " FROZEN" : "",
			 current->comm, current->pid);
		return;
	}
	pr_emerg("HT > %s [%s/%d cpu%d]\n", p->fn->name, current->comm, current->pid,
		 raw_smp_processor_id());
	mark_stage(p->fn->stage_in);
}

static int ht_rp_entry(struct kretprobe_instance *ri, struct pt_regs *regs)
{
	ht_entry_common(container_of(get_kretprobe(ri), struct ht_probe, rp), regs);
	return 0;
}

static int ht_rp_ret(struct kretprobe_instance *ri, struct pt_regs *regs)
{
	struct ht_probe *p = container_of(get_kretprobe(ri), struct ht_probe, rp);

	pr_emerg("HT < %s = %lx [%s/%d]\n", p->fn->name, regs_return_value(regs),
		 current->comm, current->pid);
	mark_stage(p->fn->stage_out);
	return 0;
}

static int ht_kp_pre(struct kprobe *kp, struct pt_regs *regs)
{
	ht_entry_common(container_of(kp, struct ht_probe, kp), regs);
	return 0;
}

/* ---- watchdog ---- */
static enum hrtimer_restart ht_watchdog(struct hrtimer *t)
{
	pr_emerg("HT WATCHDOG: hibernation still running %lld s after it started - dumping state\n",
		 ktime_ms_delta(ktime_get(), hib_start) / 1000);
	mark_stage(99);
	pr_emerg("HT WATCHDOG: blocked (D-state) tasks:\n");
	handle_sysrq('w');
	pr_emerg("HT WATCHDOG: all CPU backtraces:\n");
	handle_sysrq('l');
	panic("hibtrace: hibernation stuck");
	return HRTIMER_NORESTART;
}

static int ht_pm_notify(struct notifier_block *nb, unsigned long ev, void *unused)
{
	switch (ev) {
	case PM_HIBERNATION_PREPARE:
		hib_start = ktime_get();
		hib_active = true;
		pr_emerg("HT: hibernation starting (watchdog %d s)\n", watchdog_secs);
		if (watchdog_secs > 0)
			hrtimer_start(&wd_timer, ktime_set(watchdog_secs, 0), HRTIMER_MODE_REL);
		break;
	case PM_POST_HIBERNATION:
		hrtimer_cancel(&wd_timer);
		hib_active = false;
		pr_emerg("HT: hibernation finished, %lld ms after it started (monotonic)\n",
			 ktime_ms_delta(ktime_get(), hib_start));
		break;
	}
	return NOTIFY_DONE;
}

static struct notifier_block ht_nb = {
	.notifier_call = ht_pm_notify,
	.priority = INT_MAX,	/* first in, so the watchdog covers everyone */
};

static int __init ht_init(void)
{
	int i, full = 0, entry_only = 0, missing = 0;

	for (i = 0; i < NTRACED; i++) {
		struct ht_probe *p = &probes[i];

		p->fn = &traced[i];
		p->rp.kp.symbol_name = p->fn->name;
		p->rp.entry_handler = ht_rp_entry;
		p->rp.handler = ht_rp_ret;
		p->rp.maxactive = 64;
		if (register_kretprobe(&p->rp) == 0) {
			p->kind = 1;
			full++;
			continue;
		}
		p->kp.symbol_name = p->fn->name;
		p->kp.pre_handler = ht_kp_pre;
		if (register_kprobe(&p->kp) == 0) {
			p->kind = 2;
			entry_only++;
		} else {
			missing++;
			pr_info("hibtrace: cannot trace %s\n", p->fn->name);
		}
	}

	hrtimer_setup(&wd_timer, ht_watchdog, CLOCK_MONOTONIC, HRTIMER_MODE_REL);
	register_pm_notifier(&ht_nb);

	pr_emerg("HT: loaded - %d functions traced (+%d entry-only, %d unavailable), watchdog %d s\n",
		 full, entry_only, missing, watchdog_secs);
	return 0;
}

static void __exit ht_exit(void)
{
	int i;

	unregister_pm_notifier(&ht_nb);
	hrtimer_cancel(&wd_timer);
	for (i = 0; i < NTRACED; i++) {
		if (probes[i].kind == 1)
			unregister_kretprobe(&probes[i].rp);
		else if (probes[i].kind == 2)
			unregister_kprobe(&probes[i].kp);
	}
	pr_info("hibtrace: unloaded\n");
}

module_init(ht_init);
module_exit(ht_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary hibernate tracing and watchdog");
