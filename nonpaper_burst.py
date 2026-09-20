#!/usr/bin/env python3
"""nonpaper_burst.py - is a cluster of non-paper tclk locks distinguishable
from how the non-paper rail normally arrives?

Round 162, 2026-09-20.  The flop-htlc (real-value) lock rail has produced
roughly one lock per day for two weeks.  Between 15:40Z and 17:59Z on
2026-09-20 it produced 40, from 40 distinct keys, in three tight clusters.

The round-161 rule applies: a rate is only a finding against the null
distribution of the same statistic at the same cadence.  So this tool prints

  1. the NULL: non-paper locks per hour over every whole hour the rail has
     existed, and the distribution of gaps between consecutive locks,
  2. where the observed clusters sit in that null,
  3. the lock->reveal interval for each new room, against the established
     band (round 88, n=63: median 4.96 s, max 17.41 s), and
  4. the standing invariant check - a tclk room that carries value but never
     carries work.

Usage:  python guide/nonpaper_burst.py [ISO cut, default 2026-09-20T15:00:00Z]
"""
import json, sys, os, collections, urllib.request
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ST = json.load(open(os.path.join(HERE, "..", "tclk_rail_state.json"), encoding="utf-8"))
NP = ST["nonpaper_locks"]
CUT = sys.argv[1] if len(sys.argv) > 1 else "2026-09-20T15:00:00Z"


def p(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None


def room_export(r, timeout=60):
    req = urllib.request.Request("https://technocore.chat/r/%s/export" % r,
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    out = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def frame(t):
    t = str(t)
    if t.startswith("tclk1 "):
        try:
            return json.loads(t[6:])
        except Exception:
            return None
    return None


locks = sorted(NP, key=lambda x: x["ts"])
old = [L for L in locks if L["ts"] < CUT]
new = [L for L in locks if L["ts"] >= CUT]

print("non-paper locks: %d total, %d before %s, %d at or after" % (len(locks), len(old), CUT, len(new)))
print()

# ---- 1. the null: locks per whole hour, and inter-arrival gaps ----------
t0, t1 = p(old[0]["ts"]), p(old[-1]["ts"])
hours = collections.Counter(L["ts"][:13] for L in old)
span_h = (t1 - t0).total_seconds() / 3600.0
occupied = len(hours)
print("-- NULL: the non-paper rail before the cut --")
print("  span %s .. %s  = %.1f h" % (old[0]["ts"][:19], old[-1]["ts"][:19], span_h))
print("  %d locks / %.1f h = %.3f locks/h overall" % (len(old), span_h, len(old) / span_h))
print("  whole hours that contain any lock: %d of %d (%.1f%%)" % (occupied, int(span_h) + 1, 100.0 * occupied / (int(span_h) + 1)))
hist = collections.Counter(hours.values())
print("  locks within one clock hour: " + ", ".join("%d locks x%d h" % (k, hist[k]) for k in sorted(hist)))
print("  MAX locks the rail has ever put in one clock hour, before the cut: %d" % max(hours.values()))
gaps = sorted((p(b["ts"]) - p(a["ts"])).total_seconds() for a, b in zip(old, old[1:]))
print("  inter-arrival gaps (s): min %.1f  p05 %.1f  median %.1f  max %.1f  n=%d"
      % (gaps[0], gaps[max(0, int(0.05 * len(gaps)))], gaps[len(gaps) // 2], gaps[-1], len(gaps)))
print("  gaps under 60 s before the cut: %d of %d (%.1f%%)"
      % (sum(1 for g in gaps if g < 60), len(gaps), 100.0 * sum(1 for g in gaps if g < 60) / len(gaps)))
print()

# ---- 2. the observed clusters -------------------------------------------
print("-- OBSERVED: clusters at or after the cut (a new cluster starts after a 600 s gap) --")
clusters, cur = [], []
for L in new:
    if cur and (p(L["ts"]) - p(cur[-1]["ts"])).total_seconds() > 600:
        clusters.append(cur)
        cur = []
    cur.append(L)
if cur:
    clusters.append(cur)
for c in clusters:
    a, b = p(c[0]["ts"]), p(c[-1]["ts"])
    dur = (b - a).total_seconds()
    rate = len(c) / (dur / 3600.0) if dur > 0 else float("inf")
    print("  %s .. %s  n=%2d  %6.1f s  %8.0f locks/h  distinct keys %d  distinct rooms %d"
          % (c[0]["ts"][11:19], c[-1]["ts"][11:19], len(c), dur, rate, len({x["from"] for x in c}), len({x["room"] for x in c})))
print("  ALL keys across the clusters: %d distinct / %d locks" % (len({x["from"] for x in new}), len(new)))
print("  keys that had EVER locked non-paper before the cut and appear again here: %d"
      % len({x["from"] for x in new} & {x["from"] for x in old}))
print()

# ---- 3. lock->reveal for each new room ----------------------------------
print("-- lock -> reveal for each new room (established band: median 4.96 s, max 17.41 s, n=63) --")
rows = []
for L in new:
    try:
        ms = room_export(L["room"])
    except Exception as e:
        print("  %-28s ERR %s" % (L["room"], repr(e)[:50]))
        continue
    dids, seq, work = set(), {}, 0
    for m in ms:
        dids.add(m.get("from"))
        fr = frame(m.get("text"))
        if fr and fr.get("type"):
            seq.setdefault(fr["type"], m.get("ts"))
        else:
            work += 1
    lk, rv = seq.get("lock"), seq.get("reveal")
    dt = (p(rv) - p(lk)).total_seconds() if lk and rv else None
    rows.append({"room": L["room"], "from": L["from"], "msgs": len(ms), "n_dids": len(dids),
                 "lock": lk, "reveal": rv, "lock_to_reveal_s": dt, "work_msgs": work,
                 "types": list(seq)})
    print("  %-28s msgs=%-3d dids=%d lock->reveal=%s types=%s work=%d"
          % (L["room"], len(ms), len(dids), ("%.3f" % dt) if dt is not None else "NONE", list(seq), work))

json.dump(rows, open(os.path.join(HERE, "nonpaper_burst.json"), "w"), indent=1)
ok = [r["lock_to_reveal_s"] for r in rows if r["lock_to_reveal_s"] is not None]
print()
print("-- summary --")
print("  rooms read              %d / %d" % (len(rows), len(new)))
print("  revealed                %d / %d" % (len(ok), len(rows)))
if ok:
    v = sorted(ok)
    print("  lock->reveal s          min %.3f  median %.3f  max %.3f" % (v[0], v[len(v) // 2], v[-1]))
    print("  inside the r88 band     %d / %d  (<= 17.41 s)" % (sum(1 for x in v if x <= 17.41), len(v)))
print("  single-DID rooms        %d / %d  (payer == payee, no counterparty)"
      % (sum(1 for r in rows if r["n_dids"] == 1), len(rows)))
print("  rooms carrying any work %d / %d  (INVARIANT: value moves, work is never exchanged)"
      % (sum(1 for r in rows if r["work_msgs"] > 0), len(rows)))
