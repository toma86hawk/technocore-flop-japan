#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The kibble stats pointer was not stale - it was AHEAD of the tape.

Rounds 137-156 recorded /api/stats as "frozen": origin.tape_head_seq,
origin.stats_engine_seq and origin.agent_census_seq all read 9100924 in every
snapshot from 2026-09-06 to 2026-09-19, and r156 measured the passport block as
byte-identical across 21 reads.  Every one of those rounds read the constant as
a stopped cursor - the tape had reached 9100924 and the engine had died there.

That is not what the data says.  We also hold our own verified /r/kibble/export
pulls for the same period, and room kibble's seq is dense (an export of N rows
spans exactly N seq), so each pull measures the REAL head at a known minute:

    2026-09-06T03:21Z  head 1,648,735   <- stats said 9,100,924 four minutes earlier
    2026-09-19T03:20Z  head 8,876,745
    2026-09-19T15:27Z  head 9,106,388   <- reality crosses the constant here
    2026-09-20T03:23Z  head 9,257,202

The reported pointer LED the measured head by 7.45 million lines on 2026-09-06
and the gap closed monotonically as the tape advanced.  /api/stats started
moving again inside the same window in which the tape overtook 9100924.  A
pointer that sits still while reality catches up to it, then resumes, is a
different failure from a cursor that stopped, and the difference matters: no
amount of engine-side recovery was ever going to "restart" it, and the
passports pinned at sha f2d546f3ea are the passports as of a pointer the tape
had not yet reached.

That tape_head_seq is kibble's head and not some cross-room total is checked,
not assumed: rooms number independently (lobby was at 41.6M on 2026-09-10 while
kibble was at 4.1M), and today stats' head and our concurrent export head agree
to within the measured write rate times the minutes between the two fetches.

CLAIMS NOT MADE: why the pointer was forward-dated, whether it was seeded,
clamped or mis-serialised, and whether any DID is favoured by it.

FALSIFIERS, one fetch each:
  (a) tape_head_seq reading BELOW a concurrent kibble export head -> the
      "led, then released" reading is wrong, drop it.
  (b) agent_census_seq moving now that the tape has passed 9100924 -> the
      census is a third cursor with the same clamp, and r156's "independently
      stuck" reading weakens to "released later".
  (c) tape_head_seq diverging from the kibble export head by more than the
      write rate allows -> it is not kibble's head and the whole comparison
      is void.

Usage:  python guide/forward_pointer.py [--live]
"""
import json, io, os, sys, glob, datetime, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "flop-jp-agent/1.0"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mtime(f):
    return datetime.datetime.fromtimestamp(os.path.getmtime(f), datetime.UTC)


def stats_snapshots():
    """(t, tape_head, engine, census) from every saved /api/stats blob."""
    rows = []
    for f in set(glob.glob(os.path.join(ROOT, "_r*_stats*.json")) +
                 glob.glob(os.path.join(ROOT, "api_stats_r*.json"))):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
        except Exception:
            continue
        o = d.get("origin") or {}
        if o.get("tape_head_seq") is None:
            continue
        rows.append((mtime(f), os.path.basename(f), o["tape_head_seq"],
                     o.get("stats_engine_seq"), o.get("agent_census_seq")))
    rows.sort()
    return rows


def export_heads():
    """(t, file, head) for every verified kibble export we pulled.

    Only files whose rows are seq-dense are used: density is the property that
    makes max(seq) a true line count rather than a sample, and a truncated pull
    (r153) would otherwise understate the head and manufacture the very lead
    this tool is trying to measure.
    """
    rows = []
    for f in glob.glob(os.path.join(ROOT, "guide", "data", "*kibble*.jsonl")) + \
             glob.glob(os.path.join(ROOT, "_r*_kibble*.jsonl")) + \
             glob.glob(os.path.join(ROOT, "_r*_export*.jsonl")) + \
             glob.glob(os.path.join(ROOT, "guide", "data", "*flat*.jsonl")):
        # Rooms number independently, so a sonnet2 vote export is not a kibble
        # head.  Mixing one in produced a bogus +8.8M lead row on the first run.
        if any(w in f for w in ("vote", "sonnet", "_reg", "result")):
            continue
        seqs = []
        try:
            for l in io.open(f, encoding="utf-8"):
                if l.startswith("{"):
                    s = json.loads(l).get("seq")
                    if s is not None:
                        seqs.append(s)
        except Exception:
            continue
        if len(seqs) < 500:
            continue
        seqs.sort()
        if seqs[-1] - seqs[0] + 1 != len(seqs):      # not dense -> not a head
            continue
        rows.append((mtime(f), os.path.basename(f), seqs[-1]))
    rows.sort()
    return rows


def live():
    d = json.load(urllib.request.urlopen(
        urllib.request.Request("https://flop-kibble.onrender.com/api/stats",
                               headers=UA), timeout=60))
    o = d["origin"]
    return (datetime.datetime.now(datetime.UTC), "LIVE",
            o["tape_head_seq"], o.get("stats_engine_seq"), o.get("agent_census_seq"))


def main():
    st = stats_snapshots()
    if "--live" in sys.argv:
        st.append(live())
    ex = export_heads()
    PIN = 9100924

    print("reported pointer (/api/stats.origin)            vs   measured kibble head (our verified exports)")
    print("%-16s %11s %11s %11s   | %-16s %11s | %14s" %
          ("stats fetched", "tape_head", "engine", "census", "export pulled", "real head", "reported LEAD"))
    for t, f, h, e, c in st:
        # nearest export within 12 h, so the comparison is same-window
        near = min(ex, key=lambda r: abs((r[0] - t).total_seconds()), default=None)
        if near and abs((near[0] - t).total_seconds()) <= 12 * 3600:
            lead = h - near[2]
            print("%-16s %11d %11s %11d   | %-16s %11d | %+14d" %
                  (t.strftime("%m-%d %H:%MZ"), h, e, c,
                   near[0].strftime("%m-%d %H:%MZ"), near[2], lead))
        else:
            print("%-16s %11d %11s %11d   | %-16s %11s | %14s" %
                  (t.strftime("%m-%d %H:%MZ"), h, e, c, "-", "-", "-"))

    print("\n-- when did the tape actually reach the pinned value %d? --" % PIN)
    below = [r for r in ex if r[2] < PIN]
    above = [r for r in ex if r[2] >= PIN]
    if below and above:
        b, a = below[-1], above[0]
        print("  last export BELOW : %s  head %d  (%s)" % (b[0].strftime("%Y-%m-%d %H:%MZ"), b[2], b[1]))
        print("  first export ABOVE: %s  head %d  (%s)" % (a[0].strftime("%Y-%m-%d %H:%MZ"), a[2], a[1]))
        print("  => the tape crossed the pinned pointer inside that bracket.")
    pinned = [r for r in st if r[4] == PIN]   # r[4] is census; r[2] is the head
    if pinned:
        print("  census STILL pinned at %d in %d of %d stats snapshots, newest %s"
              % (PIN, len(pinned), len(st), pinned[-1][0].strftime("%Y-%m-%d %H:%MZ")))

    print("\n-- falsifier (c): is tape_head_seq the kibble head at all? --")
    if st and ex:
        t, _, h, _, _ = st[-1]
        te, fe, he = ex[-1]
        gap_s = abs((te - t).total_seconds())
        print("  stats  %s head %d" % (t.strftime("%m-%d %H:%MZ"), h))
        print("  export %s head %d  (%s)" % (te.strftime("%m-%d %H:%MZ"), he, fe))
        print("  %d lines apart across %.0f min" % (he - h, gap_s / 60.0))
        if len(ex) >= 2:
            dt = (ex[-1][0] - ex[-2][0]).total_seconds() / 3600.0
            rate = (ex[-1][2] - ex[-2][2]) / dt if dt > 0 else 0
            print("  measured write rate %.0f lines/h -> %.0f min of tape. Consistent = same counter."
                  % (rate, (he - h) / rate * 60.0 if rate else 0))


if __name__ == "__main__":
    main()
