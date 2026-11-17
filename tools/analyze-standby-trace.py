#!/usr/bin/env python3
"""Summarise a standby (s2idle) trace recorded with tools/trace-standby.sh.

Input: the text from `trace-cmd report -i trace.dat`.
Output: phase timeline, slowest device PM callbacks per direction, every ACPI
(BIOS AML) Sleep() with the task that ran it, and the longest function_graph
calls if a graph was recorded.

usage: trace-cmd report -i trace.dat > report.txt
       tools/analyze-standby-trace.py report.txt
"""
import re
import sys
from collections import defaultdict

TS = r'\s(\d+\.\d+):\s'
re_phase = re.compile(TS + r'suspend_resume:\s+(\S+)\[\d+\]\s+(begin|end)')
re_dev_start = re.compile(TS + r'device_pm_callback_start:\s+(.*?), parent: (\S+), ?(.*?)\[(\w+)\]')
re_dev_end = re.compile(TS + r'device_pm_callback_end:\s+(.*?), err=(-?\d+)')
re_acpi = re.compile(r'^\s*(\S+)\s+\[\d+\].*' + TS + r'acpisleep:.*ms=(\d+)')
re_fexit = re.compile(TS + r'funcgraph_exit:\s+[$@*#!+ ]?\s*([\d.]+) us\s+\|(\s*)\}')
re_fentry = re.compile(TS + r'funcgraph_entry:\s+\|(\s*)(\S+)\(\) \{')

def main(path):
    phases = []
    starts = {}
    durs = []
    acpi = []
    stack = defaultdict(list)          # per-CPU-task function_graph stacks
    longcalls = []
    for line in open(path, errors='replace'):
        m = re_phase.search(line)
        if m:
            phases.append((float(m.group(1)), m.group(2), m.group(3)))
            continue
        m = re_dev_start.search(line)
        if m:
            words = m.group(4).split()
            stage = next((w for w in words if w in ('late', 'early', 'noirq')), '')
            starts[m.group(2)] = (float(m.group(1)), (m.group(5) + ' ' + stage).strip())
            continue
        m = re_dev_end.search(line)
        if m:
            key = m.group(2)
            if key in starts:
                t0, ev = starts.pop(key)
                durs.append((float(m.group(1)) - t0, ev, key))
            continue
        m = re_acpi.search(line)
        if m:
            acpi.append((float(m.group(2)), int(m.group(3)), m.group(1)))
            continue
        task = line.split('[', 1)[0].strip()
        m = re_fentry.search(line)
        if m:
            stack[task].append((len(m.group(2)), m.group(3)))
            continue
        m = re_fexit.search(line)
        if m and stack[task]:
            depth = len(m.group(3))
            while stack[task] and stack[task][-1][0] > depth:
                stack[task].pop()
            if stack[task]:
                _, fn = stack[task].pop()
                us = float(m.group(2))
                if us >= 50000:
                    longcalls.append((us / 1000, fn, depth, task))

    print('## Phases (seconds from first event)')
    if phases:
        t0 = phases[0][0]
        open_ = {}
        for t, name, be in phases:
            if be == 'begin':
                open_[name] = t
            elif name in open_:
                print(f'  {open_[name] - t0:9.3f}  {name:<24} {1000 * (t - open_.pop(name)):9.1f} ms')
    print()
    for direction, kind in (('suspend (going to sleep)', ('suspend', 'prepare')),
                            ('resume (waking up)', ('resume', 'complete'))):
        sel = sorted((d for d in durs if d[1].split()[0] in kind), reverse=True)[:12]
        print(f'## Slowest device callbacks: {direction}')
        for d, ev, dev in sel:
            print(f'  {1000 * d:8.1f} ms  {ev:<14} {dev}')
        print()
    print('## BIOS (ACPI AML) Sleep() calls')
    if acpi:
        marks = [(t, n) for t, n, be in phases if n in ('machine_suspend',) and be == 'end'] or [(acpi[-1][0] + 1, '')]
        wake = marks[0][0]
        for label, sel in (('before/while suspending', [a for a in acpi if a[0] < wake]),
                           ('while resuming', [a for a in acpi if a[0] >= wake])):
            print(f'  {label}: {len(sel)} calls, {sum(a[1] for a in sel)} ms')
            for t, ms, task in sel:
                print(f'      +{t - phases[0][0]:8.3f}s  Sleep({ms:>4} ms)  by {task}')
    else:
        print('  (no kprobes:acpisleep events recorded)')
    if longcalls:
        print()
        print('## Function-graph calls longer than 50 ms (outermost first)')
        for ms, fn, depth, task in sorted(longcalls, key=lambda x: (-x[0]))[:25]:
            print(f'  {ms:9.1f} ms  depth {depth:<3} {fn}  [{task}]')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
