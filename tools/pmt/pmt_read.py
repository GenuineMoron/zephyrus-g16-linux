#!/usr/bin/env python3
"""Read-only Intel PMT telemetry decoder.

Decodes /sys/class/intel_pmt/telemN regions using Intel's public XML sample
definitions (github.com/intel/Intel-PMT, xml/MTL/*). Never writes anything.

Samples: sample offset = 8 * group sampleID (bytes); bits lsb..msb of that
little-endian qword. Transformations are the <transform> expressions from
mtl_aggregator_interface.xml, evaluated with a restricted AST evaluator.

Usage (live, needs root for the telem files):
  sudo python3 -I pmt_read.py --dev telem1 telem2 telem3 telem4
  sudo python3 -I pmt_read.py --dev telem1 telem2 --delta 10     # two reads 10 s apart
  sudo python3 -I pmt_read.py --dev telem1 --watch 60 --csv LOG.csv   # append a row every 60 s

Offline (no root, decode a saved dump):
  python3 -I pmt_read.py --file dump.bin --guid 0x130670b2

Dumps for later offline use:
  sudo python3 -I pmt_read.py --dev telem1 --dump-dir DIR
"""
import argparse
import ast
import csv
import datetime
import json
import math
import operator
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

SYSFS = "/sys/class/intel_pmt"
ESU = int(os.environ.get("PMT_ESU", "14"))  # RAPL energy unit exponent (2**-ESU J per count)
XML_ROOT = os.environ.get(
    "PMT_XML_ROOT",
    # Intel's PMT metadata: git clone https://github.com/intel/Intel-PMT tools/pmt/Intel-PMT
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Intel-PMT", "xml"),
)


def localname(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def child(node, name):
    for c in node:
        if localname(c.tag) == name:
            return c
    return None


def children(node, name):
    return [c for c in node if localname(c.tag) == name]


def text(node, name, default=None):
    c = child(node, name)
    if c is None or c.text is None:
        return default
    return " ".join(c.text.split())


# ---------------------------------------------------------------- XML loading

def load_guid_map(xml_root):
    """GUID (int) -> XML basedir (relative to xml_root), from pmt.xml."""
    root = ET.parse(os.path.join(xml_root, "pmt.xml")).getroot()
    out = {}
    for m in root.iter("mapping"):
        guid = int(m.get("guid"), 16)
        xs = m.find("xmlset")
        out[guid] = {
            "description": text(m, "description", ""),
            "basedir": xs.findtext("basedir"),
            "prefix": xs.findtext("prefix"),
            "common": xs.findtext("common"),
            "aggregator": xs.findtext("aggregator"),
            "interface": xs.findtext("aggregatorinterface"),
            "size": int(m.get("size")),
        }
    return out


def _strip_entity(xml_bytes):
    # Aggregator files use an external entity (&otherfile;) for the common
    # datatypes file. Drop the DOCTYPE and the include; datatypes are loaded
    # separately from the common file.
    s = xml_bytes.decode("utf-8")
    s = re.sub(r"<!DOCTYPE.*?\]>", "", s, flags=re.S)
    s = re.sub(r"<TELC:DataTypesInclude>\s*&otherfile;\s*</TELC:DataTypesInclude>", "", s)
    return s.encode("utf-8")


def load_definitions(xml_root, entry):
    base = os.path.join(xml_root, entry["basedir"])
    common_p = os.path.join(base, entry["common"])
    agg_p = os.path.join(base, entry["aggregator"])
    ifc_p = os.path.join(base, entry["interface"])

    # datatypes (units, class) from the common file
    datatypes = {}
    croot = ET.parse(common_p).getroot()
    for dt in croot.iter():
        if localname(dt.tag) != "dataType":
            continue
        units = child(dt, "units")
        datatypes[dt.get("datatypeID")] = {
            "dataclass": text(dt, "dataclass", ""),
            "units": text(units, "symbol", "") if units is not None else "",
            "format": text(dt, "format", ""),
        }

    # sample groups and samples (bit layout)
    aroot = ET.fromstring(_strip_entity(open(agg_p, "rb").read()))
    groups = {}  # sampleGroupID -> {"offset":..., "samples": {name: spec}}
    for g in aroot.iter():
        if localname(g.tag) != "SampleGroup":
            continue
        gid = g.get("sampleGroupID")
        off = 8 * int(g.get("sampleID"))
        samples = {}
        for s in children(g, "sample"):
            samples[s.get("name")] = {
                "lsb": int(text(s, "lsb", "0")),
                "msb": int(text(s, "msb", "0")),
                "sampleType": text(s, "sampleType", ""),
                "datatype": s.get("datatypeIDREF"),
                "description": text(s, "description", ""),
            }
        groups[gid] = {"offset": off, "samples": samples}

    # transformations and high-level sample names from the interface file
    iroot = ET.parse(ifc_p).getroot()
    transforms = {}
    for t in iroot.iter():
        if localname(t.tag) != "TransFormation":
            continue
        params = [text(p, "parameterName", "") for p in iter_named(t, "TransFormParameters")]
        transforms[t.get("transformID")] = {
            "params": [p for p in params if p],
            "expr": text(t, "transform", ""),
            "dataclass": text(t, "output_dataclass", ""),
        }
    # output_dataclass/transform text is nested; re-read exactly
    for t in iroot.iter():
        if localname(t.tag) != "TransFormation":
            continue
        tid = t.get("transformID")
        expr = child(t, "transform")
        if expr is not None and expr.text:
            transforms[tid]["expr"] = " ".join(expr.text.split())
        tp = child(t, "TransFormParameters")
        if tp is not None:
            transforms[tid]["params"] = [" ".join((p.text or "").split()) for p in children(tp, "parameterName")]

    high = []
    for s in iroot.iter():
        if localname(s.tag) != "T_AggregatorSample":
            continue
        name = s.get("sampleName")
        inputs = {}
        ti = child(s, "TransFormInputs")
        if ti is not None:
            for inp in children(ti, "TransFormInput"):
                inputs[inp.get("varName")] = (
                    text(inp, "sampleGroupIDREF", ""),
                    text(inp, "sampleIDREF", ""),
                )
        high.append({
            "name": name,
            "sampleGroup": s.get("sampleGroup"),
            "datatype": s.get("datatypeIDREF"),
            "description": text(s, "description", ""),
            "sampleType": text(s, "SampleType", ""),
            "transform": text(s, "transformREF", None),
            "inputs": inputs,
        })

    return {
        "name": text(aroot, "name", entry["prefix"]),
        "description": entry["description"],
        "datatypes": datatypes,
        "groups": groups,
        "transforms": transforms,
        "samples": high,
    }


def iter_named(node, name):
    for n in node.iter():
        if localname(n.tag) == name and n is not node:
            yield n


# ---------------------------------------------------------- restricted evaluator

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_, ast.BitXor: operator.xor,
    ast.RShift: operator.rshift, ast.LShift: operator.lshift, ast.Mod: operator.mod,
}
_UN = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}


def safe_eval(expr, env):
    """Evaluate an arithmetic expression. Names must be in env. Raises ValueError otherwise."""
    tree = ast.parse(expr.replace("$", ""), mode="eval")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise ValueError("unresolved name " + n.id)
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UN:
            return _UN[type(n.op)](ev(n.operand))
        raise ValueError("disallowed syntax")

    return ev(tree)


# ------------------------------------------------------------------ decoding

def read_dev(dev):
    """Return (guid_int, bytes) for a /sys/class/intel_pmt/telemN device."""
    base = os.path.join(SYSFS, dev)
    guid = int(open(os.path.join(base, "guid")).read().strip(), 16)
    data = open(os.path.join(base, "telem"), "rb").read()
    return guid, data


def decode(defs, data):
    """Return list of dicts: name, group, raw(value), value, units, sampleType, description, ok."""
    rows = []

    def read_field(gidref, sidref):
        """Return (raw, spec) for group/sample reference, or (None, None)."""
        gg = defs["groups"].get(gidref)
        if gg is None or sidref not in gg["samples"]:
            return None, None
        ss = gg["samples"][sidref]
        if gg["offset"] + 8 > len(data):
            return None, ss
        qq = int.from_bytes(data[gg["offset"]:gg["offset"] + 8], "little")
        return (qq >> ss["lsb"]) & ((1 << (ss["msb"] - ss["lsb"] + 1)) - 1), ss

    name_index = {}
    for gid, g in defs["groups"].items():
        for sname in g["samples"]:
            name_index.setdefault(sname, (gid, sname))

    for hs in defs["samples"]:
        # primary source: the parameter_0 input, else the group/sample named like the sample
        inputs = hs["inputs"]
        if inputs:
            primary = inputs.get("parameter_0") or next(iter(inputs.values()))
        else:
            primary = None
        if primary is None:
            continue
        gkey, skey = primary
        row_spec = defs["groups"].get(gkey, {}).get("samples", {}).get(skey)
        if row_spec is None:
            continue
        dt = defs["datatypes"].get(hs["datatype"] or row_spec["datatype"], {})
        row = {
            "name": hs["name"],
            "group": gkey,
            "sampleType": hs["sampleType"] or row_spec["sampleType"],
            "units": dt.get("units", ""),
            "description": hs["description"] or row_spec["description"],
            "ok": True,
            "raw": None,
            "value": None,
            "note": "",
        }
        raw, _ = read_field(gkey, skey)
        if raw is None:
            row["ok"] = False
            row["note"] = "outside region"
            rows.append(row)
            continue
        row["raw"] = raw
        row["value"] = raw
        row["width"] = row_spec["msb"] - row_spec["lsb"] + 1
        tid = hs["transform"]
        if tid == "energy_J":
            # XML says raw / 2**20 J. Measured against RAPL package-0 the counter runs in
            # the RAPL energy unit (2**-ESU J, ESU=14 on this part). Use ESU, see notes.
            row["value"] = raw * 2.0 ** -ESU
            row["units"] = "J"
            row["note"] = "2^-%d J/count (XML /2^20 disagrees with RAPL)" % ESU
        elif tid == "vr_energy":
            # XML expr raw/16384 gives J (2^-14) although the datatype says 10nJ.
            row["value"] = raw / 16384.0
            row["units"] = "J"
            row["note"] = "raw/16384 J (XML label says 10nJ)"
        elif tid == "xtal_time":
            # XML expression yields picoseconds; the counter is 38.4 MHz xtal ticks.
            row["value"] = raw / 38.4e6
            row["units"] = "s"
            row["note"] = "raw/38.4MHz (XML expr gives ps)"
        elif tid and tid in defs["transforms"]:
            tr = defs["transforms"][tid]
            env = {}
            ok = True
            for var in tr["params"]:
                pname = var.lstrip("$")
                ref = inputs.get(pname)
                if ref is None:
                    ok = False
                    break
                v, _ = read_field(*ref)
                if v is None:
                    ok = False
                    break
                env[pname] = v
            # PACKAGE_CSTATE_*_REFCNT style constants: resolve from a same-named sample
            # (or the DIE_ twin) in this definition, read raw.
            if ok:
                for name in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", tr["expr"]):
                    if name in env or name in ("e", "E") or name.startswith("PARAM"):
                        continue
                    if not re.match(r"^[A-Z][A-Z0-9_]+$", name):
                        continue
                    cand = [name, name.replace("PACKAGE_", "DIE_"), name.replace("DIE_", "PACKAGE_")]
                    got = None
                    for c in cand:
                        if c in name_index:
                            got = name_index[c]
                            break
                    if got is None:
                        ok = False
                        break
                    v, _ = read_field(*got)
                    if v is None:
                        ok = False
                        break
                    env[name] = v
            if ok:
                try:
                    row["value"] = safe_eval(tr["expr"], env)
                    if tr["dataclass"] == "float":
                        row["value"] = float(row["value"])
                    consts = sorted(k for k in env if k not in tr["params"])
                    if consts:
                        row["note"] = "constants from " + ",".join(consts)
                except (ValueError, ZeroDivisionError, SyntaxError) as e:
                    row["note"] = "transform not evaluated (%s)" % e
            else:
                row["note"] = "unresolved input/constant: " + tr["expr"].strip()
        rows.append(row)
    return rows


def raw_qwords(data):
    n = len(data) // 8
    return [int.from_bytes(data[i * 8:i * 8 + 8], "little") for i in range(n)]


# ---------------------------------------------------------------- reporting

def fmt_val(v):
    if isinstance(v, float):
        return "%.4g" % v
    return str(v)


def print_table(rows, prev=None, dt=None):
    prevmap = {r["name"]: r for r in prev} if prev else {}
    print("%-44s %-10s %-14s %-10s %s" % ("sample", "type", "value", "units", "delta/s  note"))
    for r in rows:
        line = "%-44s %-10s %-14s %-10s" % (r["name"][:44], r["sampleType"][:10], fmt_val(r["value"]), r["units"][:10])
        if prevmap and r["name"] in prevmap and r["sampleType"] == "Counter" and r["ok"] and dt:
            p = prevmap[r["name"]]
            if r["raw"] is not None and p["raw"] is not None and r["raw"] is not None:
                # wrap-aware raw delta; value scale from the (linear) transform
                dr = (r["raw"] - p["raw"]) % (1 << r["width"])
                scale = (r["value"] / r["raw"]) if r["raw"] else 0.0
                line += " %s/s" % ("%.4g" % (dr * scale / dt))
        if r["note"]:
            line += "  [" + r["note"] + "]"
        print(line)


ONLY = None  # compiled --only regex, set in main()


def snapshot(devs, defs_by_guid):
    out = {}
    for dev in devs:
        guid, data = read_dev(dev)
        defs = defs_by_guid.get(guid)
        rows = decode(defs, data) if defs else None
        if rows is not None and ONLY is not None:
            rows = [r for r in rows if ONLY.search(r["name"])]
        out[dev] = {"guid": guid, "data": data, "rows": rows}
    return out


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dev", nargs="*", default=[], help="telemN names under /sys/class/intel_pmt")
    ap.add_argument("--file", help="decode a saved raw region instead of sysfs")
    ap.add_argument("--guid", help="GUID for --file (hex, e.g. 0x130670b2)")
    ap.add_argument("--xml-root", default=XML_ROOT)
    ap.add_argument("--delta", type=float, metavar="SEC", help="take a second read after SEC seconds and show rates")
    ap.add_argument("--watch", type=float, metavar="SEC", help="loop forever, one read every SEC seconds")
    ap.add_argument("--csv", metavar="PATH", help="with --watch: append one row per read (cumulative raw + decoded)")
    ap.add_argument("--dump-dir", metavar="DIR", help="save raw region bytes to DIR (for offline decode)")
    ap.add_argument("--json", action="store_true", help="print decoded values as JSON (single read)")
    ap.add_argument("--list", action="store_true", help="list devices, GUIDs, sizes and whether XML exists")
    ap.add_argument("--only", metavar="REGEX", help="keep only sample names matching REGEX (CSV, JSON and tables)")
    args = ap.parse_args()
    global ONLY
    if args.only:
        ONLY = re.compile(args.only)

    gmap = load_guid_map(args.xml_root)

    if args.list:
        for t in sorted(os.listdir(SYSFS), key=lambda s: int(re.sub(r"\D", "", s) or 0)):
            guid = int(open(os.path.join(SYSFS, t, "guid")).read().strip(), 16)
            size = open(os.path.join(SYSFS, t, "size")).read().strip()
            off = open(os.path.join(SYSFS, t, "offset")).read().strip()
            known = gmap.get(guid)
            print("%-8s guid=0x%x size=%-5s off=%-5s xml=%s" % (
                t, guid, size, off, (known["basedir"] + " " + known["description"][:50]) if known else "none"))
        return

    defs_cache = {}

    def defs_for(guid):
        if guid not in defs_cache:
            e = gmap.get(guid)
            defs_cache[guid] = load_definitions(args.xml_root, e) if e else None
        return defs_cache[guid]

    if args.file:
        if not args.guid:
            ap.error("--file needs --guid")
        guid = int(args.guid, 16)
        data = open(args.file, "rb").read()
        d = defs_for(guid)
        if d is None:
            print("no public XML for guid 0x%08x; raw qwords:" % guid)
            for i, q in enumerate(raw_qwords(data)):
                if q:
                    print("  qword[%3d] (+0x%03x) = 0x%016x" % (i, i * 8, q))
            return
        rows = decode(d, data)
        if ONLY is not None:
            rows = [r for r in rows if ONLY.search(r["name"])]
        if args.json:
            print(json.dumps(rows, indent=1, default=str))
        else:
            print("# %s (%s)" % (d["description"], args.file))
            print_table(rows)
        return

    if not args.dev:
        ap.error("give --dev telemN ... or --file")

    if args.dump_dir:
        os.makedirs(args.dump_dir, exist_ok=True)
        if os.environ.get("SUDO_UID"):
            os.chown(args.dump_dir, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
        stamp = time.strftime("%Y%m%dT%H%M%S")
        for dev in args.dev:
            guid, data = read_dev(dev)
            p = os.path.join(args.dump_dir, "%s_0x%08x_%s.bin" % (dev, guid, stamp))
            with open(p, "wb") as f:
                f.write(data)
            if os.environ.get("SUDO_UID"):
                os.chown(p, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
            print("saved", p, len(data), "bytes")

    def one_read():
        defs_map = {g: defs_for(g) for g in gmap}  # XML parse happens before the timestamp
        t = time.time()
        snap = snapshot(args.dev, defs_map)
        return t, snap

    def report(t, snap, prev=None, dt=None):
        for dev in args.dev:
            s = snap[dev]
            print("== %s guid=0x%x  %s" % (dev, s["guid"], time.strftime("%H:%M:%S", time.localtime(t))))
            if s["rows"] is None:
                qs = raw_qwords(s["data"])
                nz = [(i, q) for i, q in enumerate(qs) if q]
                print("   no public XML. %d nonzero qwords of %d" % (len(nz), len(qs)))
                for i, q in nz[:40]:
                    pq = None
                    if prev and prev[dev]["rows"] is None:
                        pq = raw_qwords(prev[dev]["data"])[i]
                    dlt = "" if pq is None else "  delta=%d" % (q - pq)
                    print("   qword[%3d] +0x%03x = 0x%016x (%d)%s" % (i, i * 8, q, q, dlt))
                continue
            pr = prev[dev]["rows"] if prev and prev[dev]["rows"] else None
            print_table(s["rows"], pr, dt)
            print()

    if args.watch:
        # one CSV per device (columns differ per GUID): LOG.csv -> LOG-telemN.csv
        writers = {}
        handles = []
        if args.csv:
            base, ext = os.path.splitext(args.csv)
            for dev in args.dev:
                path = "%s-%s%s" % (base, dev, ext or ".csv")
                new = not os.path.exists(path)
                fh = open(path, "a", newline="")
                if os.environ.get("SUDO_UID") and new:
                    os.chown(path, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
                handles.append(fh)
                writers[dev] = (csv.writer(fh), new)
        try:
            while True:
                t, snap = one_read()
                if writers:
                    for dev in args.dev:
                        s = snap[dev]
                        if s["rows"] is None:
                            continue
                        w, new = writers[dev]
                        if new:
                            w.writerow(["time", "dev"] + [r["name"] for r in s["rows"]])
                            writers[dev] = (w, False)
                        w.writerow([datetime.datetime.fromtimestamp(t).isoformat(timespec="seconds"), dev] +
                                   [r["raw"] for r in s["rows"]])
                    for fh in handles:
                        fh.flush()
                else:
                    report(t, snap)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            pass
        finally:
            for fh in handles:
                fh.close()
        return

    t1, s1 = one_read()
    if args.json and not args.delta:
        out = {d: s1[d]["rows"] for d in args.dev if s1[d]["rows"] is not None}
        print(json.dumps(out, indent=1, default=str))
        return
    if args.delta:
        report(t1, s1)
        time.sleep(args.delta)
        t2, s2 = one_read()
        print("---- second read, dt=%.2f s" % (t2 - t1))
        report(t2, s2, prev=s1, dt=t2 - t1)
    else:
        report(t1, s1)


if __name__ == "__main__":
    main()
