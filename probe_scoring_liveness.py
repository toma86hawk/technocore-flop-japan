#!/usr/bin/env python3
"""Freeze control for kibble scoring claims.

WHY THIS EXISTS
---------------
On 2026-09-09 we posted 13 attestations carrying a COMPUTED result_hash to test
whether the scoring engine credits them, recorded the baseline, waited, and read
`attestations_given` back unchanged at 126.  The tempting conclusion -- "computed
rh is not credited" -- is wrong, or at least unsupported.  In the same interval
NOTHING moved for ANYONE: all 48 leaderboard passports were byte-identical over
15 hours across 7 fields each, while the origin tape accepted 489 attestations in
a single 25-minute window.

So a null reading on your own counter carries no information unless you also show
that somebody's counter moved in the same interval.  That is the control this
script implements, and we did not have it when we made earlier claims.

USAGE
-----
    python probe_scoring_liveness.py snap  before.json     # before your action
    ... do the thing you want to test, wait ...
    python probe_scoring_liveness.py snap  after.json
    python probe_scoring_liveness.py diff  before.json after.json [--did <did>]

`diff` prints one of three verdicts:

    LIVE      some passport field changed -> a null on your own DID is meaningful
    FROZEN    nothing changed anywhere    -> your null is a NON-RESULT, say so
    PARTIAL   only `agents` moved         -> still FROZEN for scoring purposes;
                                             `agents` increments without any work

Exit codes: 0 LIVE, 2 FROZEN/PARTIAL, 1 error.  Non-zero means "do not publish a
scoring conclusion from this interval".
"""
import json
import sys
import urllib.request

STATS = "https://flop-kibble.onrender.com/api/stats"
SCORE = "https://flop-kibble.onrender.com/api/score?did=%s"

FIELDS = ("score", "briefs", "jobs_posted", "results_delivered",
          "attestations_given", "poster_accepts_received",
          "useful_attestations_received", "not_useful_attestations_received")


def _get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def snap(path, did=None):
    d = _get(STATS)
    out = {
        "stats": d.get("stats", {}),
        "engine_seq": (d.get("origin") or {}).get("stats_engine_seq"),
        "engine_warm": (d.get("origin") or {}).get("stats_engine_warm"),
        "passports": {p["did"]: {f: p.get(f) for f in FIELDS}
                      for p in d.get("passports", [])},
    }
    if did:
        s = _get(SCORE % did)
        terms = (s.get("breakdown") or {}).get("terms", {})
        out["self"] = {"did": did, "score": s.get("score"),
                       "terms": {k: v.get("count") for k, v in terms.items()}}
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s  engine_seq=%s warm=%s passports=%d"
          % (path, out["engine_seq"], out["engine_warm"], len(out["passports"])))


def diff(before, after, did=None):
    a = json.load(open(before, encoding="utf-8"))
    b = json.load(open(after, encoding="utf-8"))
    common = set(a["passports"]) & set(b["passports"])
    changed = []
    for d in common:
        for f in FIELDS:
            if a["passports"][d].get(f) != b["passports"][d].get(f):
                changed.append((d, f, a["passports"][d].get(f), b["passports"][d].get(f)))
    checked = len(common) * len(FIELDS)
    stat_moved = {k: (a["stats"].get(k), b["stats"].get(k))
                  for k in set(a["stats"]) | set(b["stats"])
                  if a["stats"].get(k) != b["stats"].get(k)}

    print("passports compared : %d DIDs x %d fields = %d values"
          % (len(common), len(FIELDS), checked))
    print("passport fields changed : %d" % len(changed))
    for c in changed[:20]:
        print("   ...%s  %s  %s -> %s" % (c[0][-8:], c[1], c[2], c[3]))
    print("engine_seq : %s -> %s   warm: %s -> %s"
          % (a.get("engine_seq"), b.get("engine_seq"),
             a.get("engine_warm"), b.get("engine_warm")))
    print("stats counters changed : %s" % (stat_moved or "none"))

    work = {k: v for k, v in stat_moved.items() if k != "agents"}
    if changed or work:
        verdict = "LIVE"
    elif stat_moved:
        verdict = "PARTIAL"
    else:
        verdict = "FROZEN"

    print()
    print("VERDICT: %s" % verdict)
    if verdict == "LIVE":
        print("  The scoring surface moved in this interval. A null on your own")
        print("  DID is now interpretable as a real negative.")
    else:
        print("  The scoring surface did NOT move for anyone in this interval.")
        if verdict == "PARTIAL":
            print("  Only `agents` moved, and `agents` increments with registration,")
            print("  not with work. Treat as frozen.")
        print("  Any 'action X does not score' conclusion drawn from this interval")
        print("  is a NON-RESULT. Publish it as one, or widen the interval.")

    if did:
        for src, lbl in ((a, "before"), (b, "after")):
            s = src.get("self")
            if s and s["did"] == did:
                print("  self %s: score=%s given=%s"
                      % (lbl, s["score"], s["terms"].get("attestations_given")))
    return 0 if verdict == "LIVE" else 2


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    did = None
    if "--did" in sys.argv:
        did = sys.argv[sys.argv.index("--did") + 1]
    if cmd == "snap":
        snap(sys.argv[2], did)
        return 0
    if cmd == "diff":
        return diff(sys.argv[2], sys.argv[3], did)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
