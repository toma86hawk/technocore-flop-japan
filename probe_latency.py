#!/usr/bin/env python3
"""probe_latency.py - can a reply-latency floor recover the `probe v1` experiment?

Round 65 showed the labelled experiment saturated: from 2026-09-08T12:17:43Z every arm
answers at ~100%, including the null control that says it expects no reply, so the arm
contrast the design depends on is gone. That result says the instrument broke. It does
not say what to do with the data already on the wire.

This script asks a narrower question the team can act on without redesigning anything:
the announced rule counts any answer inside 120s. If the saturating responders answer
mechanically fast and genuine readers do not, then a latency FLOOR - ignore replies that
arrive sooner than L seconds - is a purely retrospective filter that can be applied to
data already collected.

It reports:
  * the latency distribution per responder key, so a fleet clustered at the floor is visible
  * arm rates before and after the saturation boundary at several floors L
  * which floor, if any, restores a difference between the arms after the boundary

Input is probe_fold.json as written by probe_fold.py (public reads, no key needed).
Usage: python probe_latency.py [boundary_iso]
"""
import json, sys, collections, statistics
from datetime import datetime

BOUNDARY = sys.argv[1] if len(sys.argv) > 1 else "2026-09-08T12:17:43+00:00"
FLOORS = [0, 1, 2, 3, 5, 10, 20, 30, 60]
ARMS = ["null", "ask", "offer", "addressed"]


def ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def load():
    data = json.load(open("probe_fold.json"))
    rows = []
    for d in data:
        by_id = {p["id"]: p for p in d["probes"]}
        for pid, r in d["res"].items():
            p = by_id.get(pid)
            if not p:
                continue
            rows.append({"room": d["room"], "id": pid, "arm": r["arm"],
                         "ts": ts(p["ts"]), "hits": r["hits"]})
    rows.sort(key=lambda r: r["ts"])
    return rows


def rates(rows, floor):
    a = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        a[r["arm"]][0] += 1
        if any(h["dt"] >= floor for h in r["hits"]):
            a[r["arm"]][1] += 1
    return a


def line(label, a):
    out = []
    for arm in ARMS:
        if arm in a:
            n, k = a[arm]
            out.append(("%s %d/%d=%.0f%%" % (arm, k, n, k / n * 100.0)).rjust(20))
    return "%-9s%s" % (label, "".join(out))


def main():
    rows = load()
    if not rows:
        print("probe_fold.json has no probes")
        return
    b = ts(BOUNDARY)
    pre = [r for r in rows if r["ts"] < b]
    post = [r for r in rows if r["ts"] >= b]
    print("probes %d  window %s .. %s" % (len(rows), rows[0]["ts"], rows[-1]["ts"]))
    print("boundary %s -> pre %d / post %d probes" % (b, len(pre), len(post)))

    lat = collections.defaultdict(list)
    for r in rows:
        for h in r["hits"]:
            lat[h["from"]].append(h["dt"])
    print("\nreply latency per responder (seconds after the probe)")
    print("%-26s%7s%8s%8s%8s%8s" % ("responder", "n", "min", "med", "max", "<=5s"))
    for did, v in sorted(lat.items(), key=lambda kv: -len(kv[1])):
        v = sorted(v)
        fast = sum(1 for x in v if x <= 5.0)
        print("%-26s%7d%8.1f%8.1f%8.1f%7.0f%%" %
              (did[8:32], len(v), v[0], statistics.median(v), v[-1], fast / len(v) * 100.0))

    for name, part in (("PRE", pre), ("POST", post)):
        if not part:
            continue
        print("\n%s-boundary arm rates at each latency floor" % name)
        for L in FLOORS:
            a = rates(part, L)
            spread = 0.0
            vals = [a[x][1] / a[x][0] for x in a if a[x][0]]
            if len(vals) > 1:
                spread = (max(vals) - min(vals)) * 100.0
            print("%s   spread %.0fpt" % (line("floor %ds" % L, a), spread))

    print("\nreading: a floor only helps if POST spread grows back toward PRE spread.")
    print("if every floor leaves POST flat, the saturating replies are not merely fast -")
    print("they are indistinguishable from genuine ones on timing alone, and the arm")
    print("labels cannot be recovered from the collected data at all.")


if __name__ == "__main__":
    main()
