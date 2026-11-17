#!/usr/bin/env python3
"""ec-map: decode the ASUS embedded-controller RAM using the ACPI field map in dsdt.dsl.

Read-only. Steps:
  1. Parse every `OperationRegion (NAME, SystemMemory, base, len)` and the `Field (NAME, ...)`
     blocks that use it from the decompiled DSDT (and SSDTs in the same folder). Offset(),
     unnamed (padding) fields and multi-bit fields are handled with ACPI bit-stream rules.
  2. Read the region with os.pread() on /dev/mem (needs root). Nothing is ever written.
  3. Print every named field with its value, and (with --refs) the ACPI methods that use it.

Usage:
  sudo python3 -I ec-map.py                      one snapshot of ERAM
  sudo python3 -I ec-map.py -n 4 -i 10           4 samples 10 s apart, changed fields flagged
  sudo python3 -I ec-map.py --region ERM3        another region (ERM2/ERM3 are also SystemMemory)
  python3 -I ec-map.py --parse-only --refs       field table + DSDT users, no /dev/mem access
  python3 -I ec-map.py --parse-only --refs --only VGAT,VIUF,MBCT
"""

import argparse
import glob
import os
import pwd
import re
import sys
import time
from collections import OrderedDict

DEFAULT_DIR = os.path.join(
    pwd.getpwnam(os.environ.get("SUDO_USER", os.environ.get("USER", "root"))).pw_dir,
    ".local/src/acpi-tables",
)

# Meanings, from the DSDT methods that read or write each field (see the research note 22).
# flag: "s" = signed value, "bit" = single bit flag. Only fields with a verified or strongly
# inferred meaning are annotated; everything else prints without a label.
ANNOT = OrderedDict([
    # verified against sysfs / live values (see research note 22)
    ("VGAT", ("", "dGPU power flag, 1 while NVIDIA is on (set _ON, cleared _OFF in ssdt15)")),
    ("VIUF", ("", "dGPU 'VGA in use'; ssdt15 _OFF skips rail-off when 1")),
    ("GC6S", ("", "GC6 state bit (declared, no ACPI reader)")),
    ("LIDS", ("", "lid CLOSED=1 (_LID returns the inverse)")),
    ("ACIN", ("", "AC adapter present (_PSR returns this)")),
    ("NOAC", ("", "inverse of ACIN (_PSR, _Q3F)")),
    ("CTMP", ("", "main thermal zone, deg C (_TZ.THRM = acpitz)")),
    ("CLOT", ("", "thermal sensor, deg C (_TMP at dsdt:76757; sensor identity unknown)")),
    ("VLTT", ("", "thermal sensor, deg C (_TMP at dsdt:76884; sensor identity unknown)")),
    ("VRTT", ("", "deg C, read by NVIDIA NPCF (ssdt24:2153); reads 0 with dGPU off")),
    ("FRMS", ("", "CPU fan tach (WMNB 0x110013): RPM ~= 2140890 / value")),
    ("FRS2", ("", "GPU fan tach (WMNB 0x110014): RPM ~= 2140890 / value")),
    ("FRS3", ("", "mid fan tach (WMNB 0x110031): RPM ~= 2140890 / value")),
    ("MBVT", ("", "battery voltage, mV (UPBS)")),
    ("MBCT", ("s", "battery current, mA, signed (UPBS); >0 charge, <0 discharge")),
    ("RCAP", ("", "remaining capacity, mWh (sysfs charge_now)")),
    ("MBCP", ("", "full-charge capacity, mWh (sysfs charge_full)")),
    ("MDCP", ("", "design capacity, mWh (sysfs charge_full_design)")),
    ("MBDV", ("", "design voltage, mV (UPBI)")),
    ("RSOC", ("", "state of charge, % (drives _QB6 dynamic-boost switch)")),
    ("BHCH", ("", "charge limit %; 0x50 = 80 (_QDB writes; UPBS checks)")),
    ("BHPE", ("", "battery-health pending flag (UPBS)")),
    ("CYCL", ("", "battery cycle count (sysfs cycle_count shows 0 instead)")),
    ("BTMP", ("", "battery temp, 0.1 K (inferred; no ACPI reader)")),
    ("PL01", ("", "PL1 watts, written by WMNB 0x1200A3 (= ppt_pl1_spl)")),
    ("PL02", ("", "PL2 watts, written by WMNB 0x1200A0 (sysfs reads 135)")),
    ("TTT1", ("", "fan/thermal threshold, read by SFMN (120)")),
    ("TTT2", ("", "fan/thermal threshold, read by SFMN (80)")),
    ("TPFG", ("", "touchpad-toggle flag (_Q22, SKEY)")),
    ("MBDN", ("", "battery model string, ASCII (starts GU60558)")),
    ("ECMJ", ("", "EC firmware major (inferred from name)")),
    ("ECMN", ("", "EC firmware minor (inferred from name)")),
    ("DVMJ", ("", "version major (inferred from name)")),
    ("DVMN", ("", "version minor (inferred from name)")),
    ("NDF9", ("", "NVIDIA dynamic-boost value written by _QB6")),
    ("DB2F", ("", "dynamic-boost flag (_QA8)")),
    ("FGA9", ("", "dGPU bus-check flag (_QA9)")),
    ("CHKR", ("", "EC signature 0xAA55")),
    ("DBEA", ("", "remaining-capacity low byte, written by UPBS at <=5 % (empty alarm)")),
    ("DBEB", ("", "remaining-capacity high byte, written by UPBS at <=5 %")),
    ("SMAD", ("", "EC SMBus mailbox (not read by ACPI)")),
    ("SMCD", ("", "EC SMBus mailbox (not read by ACPI)")),
    ("SMD0", ("", "EC SMBus mailbox data (not read by ACPI)")),
    ("SMST", ("", "EC SMBus mailbox status (not read by ACPI)")),
    ("SMAA", ("", "EC SMBus mailbox address (not read by ACPI)")),
    ("SMAR", ("", "EC SMBus mailbox register (not read by ACPI)")),
    ("UFON", ("", "set by _Q3F (AC change)")),
    ("TRSC", ("", "AC-change handled flag (_Q3F)")),
])


OPREG_RE = re.compile(
    r"OperationRegion\s*\(\s*(\w+)\s*,\s*SystemMemory\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*,\s*(0x[0-9A-Fa-f]+|\d+)\s*\)"
)
FIELD_HDR_RE = re.compile(r"\bField\s*\(\s*(\w+)\s*,")
TOKEN_RE = re.compile(
    r"(?P<off>Offset\s*\(\s*(?P<ov>0x[0-9A-Fa-f]+|\d+)\s*\))"
    r"|(?P<acc>AccessAs\s*\([^()]*\))"
    r"|(?P<conn>Connection\s*\((?:[^()]|\([^()]*\))*\))"
    r"|(?P<fld>(?P<name>[A-Za-z_]\w*|)\s*,\s*(?P<bits>\d+))"
)
DECL_RE = re.compile(r"^\s*(Method|Device|Scope|Processor|PowerResource|ThermalZone)\s*\(\s*([\\^\w.]+)")
COMMENT_RE = re.compile(r"//.*$")


def num(s):
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def parse_dsdt(path):
    """Return (regions, fields). regions: {name: (base, length)}.
    fields: list of dict(region, name, bitpos, width, line, scope) for every Field block."""
    with open(path, "r", errors="replace") as fh:
        lines = fh.readlines()

    regions = {}
    for ln in lines:
        m = OPREG_RE.search(ln)
        if m:
            regions.setdefault(m.group(1), (num(m.group(2)), num(m.group(3))))

    fields = []
    i = 0
    n = len(lines)
    while i < n:
        m = FIELD_HDR_RE.search(lines[i])
        if not m or lines[i].lstrip().startswith("//"):
            i += 1
            continue
        region = m.group(1)
        start_line = i + 1
        # find the opening brace (may be on the same or following line)
        j = i
        while "{" not in COMMENT_RE.sub("", lines[j]):
            j += 1
        depth = 0
        body = []
        k = j
        done = False
        while k < n and not done:
            text = COMMENT_RE.sub("", lines[k])
            for ch in text:
                if ch == "{":
                    depth += 1
                    if depth == 1:
                        continue
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        done = True
                        break
                if depth >= 1:
                    body.append(ch)
            body.append("\n")
            k += 1
        bodytext = "".join(body)
        if region in regions:
            bitpos = 0
            for t in TOKEN_RE.finditer(bodytext):
                if t.group("off"):
                    bitpos = num(t.group("ov")) * 8
                elif t.group("fld"):
                    name = t.group("name") or None
                    width = int(t.group("bits"))
                    fields.append(dict(region=region, name=name, bitpos=bitpos, width=width,
                                       line=start_line))
                    bitpos += width
                # AccessAs / Connection do not move the bit position
        i = k
    return regions, fields


def bit_range(bitpos, width):
    lo, hi = bitpos, bitpos + width - 1
    return lo, hi


def get_bits(data, bitpos, width):
    v = 0
    for i in range(width):
        b = bitpos + i
        if (data[b >> 3] >> (b & 7)) & 1:
            v |= 1 << i
    return v


def read_region(base, length):
    fd = os.open("/dev/mem", os.O_RDONLY)
    try:
        data = os.pread(fd, length, base)
    finally:
        os.close(fd)
    if len(data) != length:
        raise OSError("short read from /dev/mem: %d of %d bytes" % (len(data), length))
    return data


def scan_refs(dsdt_dir, names):
    """Map field name -> list of 'file:line:method' where the name is used outside Field blocks."""
    refs = {nm: [] for nm in names}
    if not names:
        return refs
    pat = re.compile(r"\b(" + "|".join(re.escape(x) for x in names) + r")\b")
    files = [os.path.join(dsdt_dir, "dsdt.dsl")] + sorted(glob.glob(os.path.join(dsdt_dir, "ssdt*.dsl")))
    for path in files:
        if not os.path.exists(path):
            continue
        base = os.path.basename(path)
        stack = []  # (name, depth)
        depth = 0
        pending = None
        in_field = 0  # >0 while inside a Field(...) { } block
        fdepth = None
        with open(path, "r", errors="replace") as fh:
            for lineno, raw in enumerate(fh, 1):
                line = COMMENT_RE.sub("", raw)
                if in_field == 0 and FIELD_HDR_RE.search(line):
                    fdepth = depth
                    in_field = 1
                    # the Field body is consumed; its declarations are not references
                    # (we still track braces below)
                d = DECL_RE.match(line)
                if d:
                    pending = d.group(2)
                # strip braces while counting so braces inside fields are handled
                if in_field:
                    for ch in line:
                        if ch == "{":
                            depth += 1
                        elif ch == "}":
                            depth -= 1
                            if fdepth is not None and depth <= fdepth:
                                in_field = 0
                                fdepth = None
                    continue
                for ch in line:
                    if ch == "{":
                        depth += 1
                        if pending:
                            stack.append((pending, depth))
                            pending = None
                    elif ch == "}":
                        if stack and stack[-1][1] == depth:
                            stack.pop()
                        depth -= 1
                for m in pat.finditer(line):
                    nm = m.group(1)
                    scope = stack[-1][0] if stack else "<top>"
                    if len(refs[nm]) < 400:
                        refs[nm].append("%s:%d:%s" % (base, lineno, scope))
    return refs


def fmt_refs(lst, maxn=4):
    if not lst:
        return "-"
    seen = OrderedDict()
    for r in lst:
        f, ln, sc = r.split(":", 2)
        seen.setdefault(sc, []).append("%s:%s" % (f.replace(".dsl", ""), ln))
    parts = []
    for sc, locs in list(seen.items())[:maxn]:
        parts.append("%s(%s)" % (sc, locs[0]))
    more = len(seen) - maxn
    if more > 0:
        parts.append("+%d more" % more)
    return " ".join(parts)


def snapshot(region_name, base, length, fields, data):
    rows = []
    for f in fields:
        if f["name"] is None:
            continue
        v = get_bits(data, f["bitpos"], f["width"])
        rows.append((f, v))
    return rows


def render(region_name, base, length, rows, prev_vals, refs, show_refs):
    lines = []
    hdr = "%-7s %-8s %3s  %-10s %-8s" % ("field", "byte.bit", "w", "value", "hex")
    if show_refs:
        hdr += "  used-by (DSDT)"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for f, v in rows:
        lo, hi = bit_range(f["bitpos"], f["width"])
        byte = f["bitpos"] // 8
        bitlo = f["bitpos"] % 8
        where = "%02X.%d" % (byte, bitlo)
        width_txt = "%d" % f["width"]
        vtxt = "%d" % v
        htxt = "0x%0*X" % ((f["width"] + 3) // 4, v)
        flag = ""
        if prev_vals is not None and prev_vals.get(f["name"]) not in (None, v):
            flag = " *"
        note = ""
        if f["name"] in ANNOT:
            note = ANNOT[f["name"]][1]
        line = "%-7s %-8s %3s  %-10s %-8s%s" % (
            f["name"], where, width_txt, vtxt + flag, htxt, ("  " + note) if note else "")
        if show_refs:
            line += "  " + fmt_refs(refs.get(f["name"], []))
        lines.append(line)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsdt", default=os.path.join(DEFAULT_DIR, "dsdt.dsl"))
    ap.add_argument("--region", default="ERAM", help="OperationRegion name (default ERAM)")
    ap.add_argument("-n", "--samples", type=int, default=1, help="number of snapshots")
    ap.add_argument("-i", "--interval", type=float, default=10.0, help="seconds between samples")
    ap.add_argument("--refs", action="store_true", help="show DSDT methods that use each field")
    ap.add_argument("--only", help="comma list of field names to show")
    ap.add_argument("--parse-only", action="store_true", help="do not read /dev/mem")
    ap.add_argument("--json", metavar="FILE", help="also write the last snapshot as JSON")
    args = ap.parse_args()

    regions, fields = parse_dsdt(args.dsdt)
    if args.region not in regions:
        sys.exit("region %s not found in %s" % (args.region, args.dsdt))
    base, length = regions[args.region]
    fields = [f for f in fields if f["region"] == args.region]
    named = [f for f in fields if f["name"]]
    if args.only:
        want = set(x.strip() for x in args.only.split(","))
        named = [f for f in named if f["name"] in want]

    total_bits = max((f["bitpos"] + f["width"] for f in fields), default=0)
    print("region %s  base 0x%X  length %d bytes; %d named fields, %d Field entries, "
          "max bit %d (%d bytes)" % (args.region, base, length, len(named), len(fields),
                                     total_bits, (total_bits + 7) // 8), file=sys.stderr)
    if total_bits > length * 8:
        sys.exit("field map exceeds region length")

    refs = scan_refs(os.path.dirname(os.path.abspath(args.dsdt)), [f["name"] for f in named]) \
        if args.refs else {}

    if args.parse_only:
        print(render(args.region, base, length, [(f, 0) for f in named], None, refs, args.refs))
        return

    prev = None
    last_rows = None
    for s in range(args.samples):
        try:
            data = read_region(base, length)
        except PermissionError:
            sys.exit("cannot open /dev/mem: run with sudo (sudo python3 -I ec-map.py)")
        rows = snapshot(args.region, base, length, named, data)
        stamp = time.strftime("%H:%M:%S")
        print("\n== sample %d/%d at %s  (%s @ 0x%X) ==" % (s + 1, args.samples, stamp, args.region, base))
        print(render(args.region, base, length, rows, prev, refs, args.refs))
        prev = {f["name"]: v for f, v in rows}
        last_rows = rows
        if s + 1 < args.samples:
            time.sleep(args.interval)
    if args.json and last_rows is not None:
        import json
        with open(args.json, "w") as fh:
            json.dump({f["name"]: v for f, v in last_rows}, fh, indent=1)


if __name__ == "__main__":
    main()
