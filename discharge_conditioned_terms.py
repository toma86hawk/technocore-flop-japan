# -*- coding: utf-8 -*-
"""Two-point passport-term test, conditioned on the engine actually ingesting.

WHY THIS EXISTS
---------------
The obvious way to ask "is kibble still scoring?" is to read /api/score for a
key at t0, watch it act on the tape, read /api/score again at t1 and see
whether its terms moved.  That test is WRONG, and it is wrong in the direction
that manufactures alarm: it reports FROZEN on a perfectly healthy board.

kibble does not score continuously.  /api/score carries `engine_seq`, the tape
position the served numbers were computed at, and `engine_warm`.  Between
discharges `engine_seq` stands still and EVERY key's terms stand still with it
- rank 2 delivering 45 results in 25 minutes moves exactly as much as a key
that did nothing, namely not at all.  Measured 2026-09-21T18:25-18:52Z: 21 keys
with verified post-t0 tape activity, 21/21 zero term movement, engine_seq
9777217 at both ends while the tape ran on to 9778920.

So an interval in which `engine_seq` did not advance carries NO information
about scoring.  The only valid comparison is across an interval where the
cursor moved past the rows you are asking about.  This module refuses to
return a verdict otherwise, and says so, instead of returning "frozen".

This is the same failure r158 fixed for the passport-digest falsifier (a
falsifier with no window is a history display) and r169 fixed for attestor
agreement (agreement is meaningless until conditioned on the entropy of the
shared verdict vector).  Same shape a third time: CONDITION THE TEST ON THE
THING THAT HAS TO MOVE FIRST.

USAGE
    python guide/discharge_conditioned_terms.py --snapshot          # write t0
    python guide/discharge_conditioned_terms.py --compare           # t0 vs now
    python guide/discharge_conditioned_terms.py --compare --keys 25
"""
import argparse, collections, json, os, sys, time, urllib.parse, urllib.request

KIBBLE = "https://flop-kibble.onrender.com"
TAPE = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "discharge_conditioned_terms.state.json")
SCORED = {"JOB": "jobs_posted", "ATTEST": "attestations_given",
          "BRIEF": "briefs", "RESULT": "results_delivered"}


def _get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def score(did):
    d = json.loads(_get("%s/api/score?did=%s" % (KIBBLE, urllib.parse.quote(did, safe="")), 60))
    terms = (d.get("breakdown") or {}).get("terms", {})
    return {"found": d.get("found"), "score": d.get("score"),
            "engine_seq": d.get("engine_seq"), "engine_warm": d.get("engine_warm"),
            "terms": {k: terms[k]["count"] for k in terms}}


def tape(limit=3000, tries=4):
    """/r/kibble/export truncates under load - IncompleteRead and 502 are both
    routine. Retry, and shrink the ask each time rather than failing the run."""
    last = None
    for i in range(tries):
        try:
            raw = _get("%s/r/kibble/export?limit=%d" % (TAPE, limit // (i + 1)), 240)
        except Exception as e:                                   # noqa: BLE001
            last = e
            time.sleep(4 * (i + 1))
            continue
        rows = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
        if rows:
            return rows
        last = ValueError("empty export")
        time.sleep(4 * (i + 1))
    raise RuntimeError("export failed after %d tries: %r" % (tries, last))


def busiest(rows, n):
    """Keys most likely to act again: most scored verbs in the recent tail."""
    tail = rows[-len(rows) // 3:] if len(rows) > 30 else rows
    c = collections.Counter(r["from"] for r in tail
                            if r.get("text", "").split(" ", 1)[0] in SCORED)
    return [d for d, _ in c.most_common(n)]


def snapshot(n_keys):
    rows = tape()
    keys = busiest(rows, n_keys)
    snap = {"taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tape_head": rows[-1]["seq"], "keys": {}}
    for d in keys:
        try:
            snap["keys"][d] = score(d)
        except Exception as e:                                   # noqa: BLE001
            snap["keys"][d] = {"err": repr(e)}
        time.sleep(1.2)
    seqs = [v.get("engine_seq") for v in snap["keys"].values() if v.get("engine_seq")]
    snap["engine_seq"] = max(seqs) if seqs else None
    json.dump(snap, open(STATE, "w"), indent=1)
    print("t0 %s  keys %d  engine_seq %s  tape_head %s"
          % (snap["taken_at"], len(snap["keys"]), snap["engine_seq"], snap["tape_head"]))
    return snap


def compare():
    if not os.path.exists(STATE):
        print("no t0 snapshot; run --snapshot first")
        return 2
    t0 = json.load(open(STATE))
    rows = tape()
    cutoff = t0["engine_seq"] or t0["tape_head"]

    acted = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["seq"] <= cutoff:
            continue
        v = r.get("text", "").split(" ", 1)[0]
        if v in SCORED:
            acted[r["from"]][SCORED[v]] += 1

    moved, still, seen = [], [], 0
    engine_t1 = None
    for d, s0 in t0["keys"].items():
        if "err" in s0 or d not in acted:
            continue
        try:
            s1 = score(d)
        except Exception as e:                                   # noqa: BLE001
            print("ERR %s %r" % (d[-12:], e))
            continue
        engine_t1 = s1.get("engine_seq") or engine_t1
        seen += 1
        delta = {k: s1["terms"].get(k, 0) - s0["terms"].get(k, 0)
                 for k in set(s0["terms"]) | set(s1["terms"])
                 if s1["terms"].get(k, 0) != s0["terms"].get(k, 0)}
        (moved if delta else still).append((d, dict(acted[d]), delta))
        time.sleep(1.2)

    advanced = (engine_t1 or 0) - (t0["engine_seq"] or 0)
    print("t0 %s engine_seq %s -> t1 engine_seq %s  (advanced %+d)"
          % (t0["taken_at"], t0["engine_seq"], engine_t1, advanced))
    print("tape head %s -> %s   keys with activity after the t0 cursor: %d"
          % (t0["tape_head"], rows[-1]["seq"], seen))

    # ---- the conditioning gate -------------------------------------------
    if advanced <= 0:
        print("\nVERDICT: VOID - the engine did not ingest a single row in this "
              "interval.\n  Terms cannot move when the cursor does not, so "
              "'%d/%d keys unchanged' is\n  a statement about the sampling "
              "interval, not about scoring. Wait for\n  engine_seq to advance "
              "and re-run. Do NOT report this as a freeze." % (len(still), seen))
        return 0
    if not seen:
        print("\nVERDICT: VOID - cursor advanced but no snapshotted key acted "
              "inside the\n  ingested span. Re-snapshot against busier keys.")
        return 0

    print("\nengine ingested %d rows in this interval, so the test is LIVE." % advanced)
    print("terms MOVED %d / STILL %d" % (len(moved), len(still)))
    for d, a, delta in moved:
        print("  MOVED %s acted %s -> %s" % (d[-12:], a, delta))
    for d, a, _ in still:
        print("  STILL %s acted %s" % (d[-12:], a))
    if moved and not still:
        print("\nVERDICT: SCORING LIVE for every key tested.")
    elif still and not moved:
        print("\nVERDICT: FROZEN - the cursor advanced past these rows and no "
              "key was\n  credited. This is a real freeze, not a sampling gap.")
    else:
        print("\nVERDICT: SELECTIVE - some keys credited, some not, over the "
              "same ingested\n  span. Compare the STILL and MOVED sets; that "
              "difference is the finding.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--keys", type=int, default=30)
    a = ap.parse_args()
    if a.snapshot:
        snapshot(a.keys)
    elif a.compare:
        sys.exit(compare())
    else:
        ap.print_help()
