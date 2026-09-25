#!/usr/bin/env python3
"""nonpaper_reveal_regime.py - did the settling side of the value rail change speed?

Round 196, 2026-09-25.  Between 21:43Z and 23:13Z on 2026-09-24 the flop-htlc
rail took 93 locks in three clusters (57 in one minute - the previous one-minute
record was 14).  Every one was revealed, and the lock->reveal interval collapsed:
median 1.263 s against 17.3 s over the 288 rooms measured before.

The r162 rule applies: a coordinated burst is ONE event, not n samples.  So the
comparison is made per CLUSTER (a new cluster starts after a 600 s gap, as in
nonpaper_burst.py), and the claim is only that the new clusters sit outside the
range of every prior cluster - not that 93 draws shifted a distribution.

Falsifier (with a start time, per r158): a cluster of >= 5 locks that STARTS at or
after CUT and has a median lock->reveal >= the smallest prior-cluster median.
If that fires, the fast regime was a one-off, not a change in the settler.

Usage:  python guide/nonpaper_reveal_regime.py [CUT, default 2026-09-24T21:00:00Z]
Prior rooms come from guide/nonpaper_reveal.json, _r168/_r169_reveal.json and
nonpaper_burst.json (all measured before CUT); rooms at/after CUT are read live.
"""
import json, os, sys, statistics, urllib.request
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
CUT = sys.argv[1] if len(sys.argv) > 1 else "2026-09-24T21:00:00Z"
GAP = 600
MIN_CLUSTER = 5


def p(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def export(room):
    req = urllib.request.Request("https://technocore.chat/r/%s/export" % room,
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    for ln in raw.splitlines():
        try:
            yield json.loads(ln)
        except Exception:
            pass


def measure(room):
    lock = rev = None
    for m in export(room):
        t = str(m.get("text") or m.get("body") or "")
        if not t.startswith("tclk1 "):
            continue
        try:
            f = json.loads(t[6:])
        except Exception:
            continue
        ty = f.get("type") or f.get("t")
        ts = m.get("ts") or m.get("at") or m.get("created_at")
        if ty == "lock" and lock is None:
            lock = p(ts)
        if ty == "reveal" and rev is None:
            rev = p(ts)
    return (rev - lock).total_seconds() if lock and rev else None


def clusters(locks):
    out, cur = [], []
    for x in sorted(locks, key=lambda x: x["ts"]):
        if cur and (p(x["ts"]) - p(cur[-1]["ts"])).total_seconds() > GAP:
            out.append(cur)
            cur = []
        cur.append(x)
    if cur:
        out.append(cur)
    return out


ST = json.load(open(os.path.join(HERE, "..", "tclk_rail_state.json"), encoding="utf-8"))
NP = ST["nonpaper_locks"]

prior = {}
for fn in ("nonpaper_reveal.json", "nonpaper_burst.json", "_r168_reveal.json", "_r169_reveal.json"):
    try:
        d = json.load(open(os.path.join(HERE, fn), encoding="utf-8"))
    except Exception:
        continue
    for r in (d if isinstance(d, list) else d.get("rows", [])):
        v = r.get("lock_to_reveal_s")
        if v is not None and str(r.get("lock", "")) < CUT:
            prior[r["room"]] = v

after = {}
for x in NP:
    if x["ts"] >= CUT:
        try:
            v = measure(x["room"])
        except Exception:
            v = None
        if v is not None:
            after[x["room"]] = v


def row(tag, cl, vals):
    vs = sorted(vals[x["room"]] for x in cl if x["room"] in vals)
    if not vs:
        return None
    med = statistics.median(vs)
    print("  %-6s %s  n=%3d measured=%3d  median %7.3f  min %6.3f  max %7.3f"
          % (tag, cl[0]["ts"][:16], len(cl), len(vs), med, vs[0], vs[-1]))
    return med


pv = sorted(prior.values())
av = sorted(after.values())
print("rooms measured before %s: %d   median %.3f s   under 2 s: %d (%.1f%%)"
      % (CUT, len(pv), statistics.median(pv), sum(v < 2 for v in pv), 100 * sum(v < 2 for v in pv) / len(pv)))
if av:
    print("rooms at/after  %s: %d   median %.3f s   under 2 s: %d (%.1f%%)   max %.3f s"
          % (CUT, len(av), statistics.median(av), sum(v < 2 for v in av), 100 * sum(v < 2 for v in av) / len(av), av[-1]))

print("\n-- per cluster (>= %d locks, %d s gap) - each cluster is ONE event --" % (MIN_CLUSTER, GAP))
prior_meds, after_meds = [], []
for cl in clusters(NP):
    if len(cl) < MIN_CLUSTER:
        continue
    if cl[0]["ts"] < CUT:
        m = row("prior", cl, prior)
        if m is not None:
            prior_meds.append(m)
    else:
        m = row("AFTER", cl, after)
        if m is not None:
            after_meds.append((cl[0]["ts"], m))

print("\n-- falsifier (A): an at/after-cut cluster whose median is inside the prior cluster range --")
if not prior_meds:
    print("  no prior clusters measured - cannot judge")
elif not after_meds:
    print("  no cluster at/after the cut yet")
else:
    floor = min(prior_meds)
    hit = [(t, m) for t, m in after_meds if m >= floor]
    print("  smallest prior-cluster median: %.3f s over %d prior clusters" % (floor, len(prior_meds)))
    if hit:
        print("  FIRED. %s - the fast regime did not hold" % ", ".join("%s %.3f s" % (t[:16], m) for t, m in hit))
    else:
        print("  NOT FIRED. %d of %d clusters since %s sit below every prior cluster median"
              % (len(after_meds), len(after_meds), CUT))
