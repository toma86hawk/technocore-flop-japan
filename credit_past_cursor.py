#!/usr/bin/env python3
"""Within-key before/after: does the engine credit rows posted AFTER the cursor
that /api/stats reports as its own position?

WHY THE OBVIOUS TEST DOES NOT WORK
----------------------------------
The tempting test is r170's shape: find keys with no prior history and see
whether they have a passport.  We ran it at r179 and it failed its own audit.
Of 13 credited keys that were absent from TEN sampled tape windows, 7 had term
counts EXCEEDING their in-window rows -- prior history our sampling never saw.
The tape takes ~48k rows per 3 h and an export window holds ~12k, so "absent
from our samples" is not "new".  And for the 6 that looked clean, jobs_posted=1
against one in-window JOB is equally well explained by "a prior JOB is counted
and the in-window JOB is not" -- which is the hypothesis under test.  Newness
cannot be established from sampled windows, so this tool does not try.

WHAT THIS DOES INSTEAD
----------------------
It reads the SAME key twice around a window in which it demonstrably acted.

  T0: snapshot /api/score terms for N active keys, plus the reported cursor.
  ... wait ...
  T1: pull a fresh export, find tracked keys that emitted NEW scoreable rows
      strictly after the T0 export head, re-read /api/score, and diff.

If a key's counted term rises while stats_engine_seq is unmoved, the engine
credited rows the reported cursor has not reached.  No newness assumption, and
no null on our own counter (the r160 trap): the control is the key's own
earlier reading, and the cursor is re-read at both ends.

USAGE
    python credit_past_cursor.py t0 --window <export.jsonl> --out t0.json [--n 40]
    python credit_past_cursor.py t1 --state t0.json --window <fresh.jsonl>
"""
import argparse
import collections
import json
import sys
import time
import urllib.error
import urllib.request

SCORE = "https://flop-kibble.onrender.com/api/score?did=%s"
STATS = "https://flop-kibble.onrender.com/api/stats"
COUNTED = {"JOB": "jobs_posted", "RESULT": "results_delivered",
           "DELIVER": "results_delivered", "ATTEST": "attestations_given",
           "BRIEF": "briefs"}


def verb(text):
    t = (text or "").strip().upper()
    for v in COUNTED:
        if t.startswith(v):
            return v
    return None


def get(url, timeout=90, tries=4):
    """GET with backoff.

    r178 burned a round by reading a single transient 502 from this host as a
    result and writing it up as a cause.  An intermittent failure is not an
    observation about the service until it repeats, so retry before believing
    it, and raise only when every attempt failed.
    """
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            url, headers={"User-Agent": "flop-jp-agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:                               # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
    raise last


def cursor():
    d = get(STATS)
    o = d.get("origin") or {}
    return {"stats_engine_seq": o.get("stats_engine_seq"),
            "tape_head_seq": o.get("tape_head_seq"),
            "stats": d.get("stats", {})}


def load(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r.get("seq"), int) and r.get("from"):
                rows.append(r)
    rows.sort(key=lambda r: r["seq"])
    return rows


def terms_of(did):
    try:
        s = get(SCORE % did, timeout=60)
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %s" % e.code}
    except Exception as e:                                   # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, e)}
    if s.get("found") is False:
        return {"found": False}
    t = (s.get("breakdown") or {}).get("terms", {})
    return {"found": True, "score": s.get("score"),
            "terms": {k: v.get("count") for k, v in t.items()}}


def cmd_t0(a):
    rows = load(a.window)
    acts = collections.defaultdict(list)
    for r in rows:
        if verb(r.get("text")):
            acts[r["from"]].append(r)
    # Prefer keys that acted more than once: they are likeliest to act again.
    cand = sorted(acts, key=lambda d: -len(acts[d]))[:a.n]
    cur = cursor()
    print("T0 export head %d (%s)  reported cursor engine=%s head=%s"
          % (rows[-1]["seq"], rows[-1]["ts"],
             cur["stats_engine_seq"], cur["tape_head_seq"]))
    snap = {}
    for did in cand:
        snap[did] = terms_of(did)
        time.sleep(a.sleep)
    got = sum(1 for v in snap.values() if v.get("found"))
    print("snapshotted %d keys, %d with a passport" % (len(snap), got))
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "export_head": rows[-1]["seq"], "cursor": cur, "snap": snap},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s" % a.out)
    return 0


def cmd_t1(a):
    st = json.load(open(a.state, encoding="utf-8"))
    rows = load(a.window)
    head0 = st["export_head"]
    new = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["seq"] > head0:
            v = verb(r.get("text"))
            if v and r["from"] in st["snap"]:
                new[r["from"]][COUNTED[v]] += 1
    cur = cursor()
    print("T1 export head %d (%s)  reported cursor engine=%s head=%s"
          % (rows[-1]["seq"], rows[-1]["ts"],
             cur["stats_engine_seq"], cur["tape_head_seq"]))
    print("cursor moved since T0: %s"
          % (cur["stats_engine_seq"] != st["cursor"]["stats_engine_seq"]))
    print("gap covered by fresh export: %s"
          % ("YES" if rows[0]["seq"] <= head0 + 1 else
             "NO - hole between seq %d and %d" % (head0, rows[0]["seq"])))
    print("tracked keys with NEW scoreable rows after seq %d: %d"
          % (head0, len(new)))
    credited, tested, detail = 0, 0, []
    for did, adds in sorted(new.items(), key=lambda kv: -sum(kv[1].values())):
        before = st["snap"][did]
        after = terms_of(did)
        time.sleep(a.sleep)
        if not (before.get("found") and after.get("found")):
            continue
        tested += 1
        b, af = before.get("terms", {}), after.get("terms", {})
        moved = {k: (b.get(k), af.get(k)) for k in set(b) | set(af)
                 if b.get(k) != af.get(k)}
        if moved:
            credited += 1
        detail.append({"did": did, "new_rows": dict(adds), "moved": moved})
        print("  %s new=%s  moved=%s" % (did[-12:], dict(adds), moved or "-"))
    print("")
    print("-- result --")
    print("  keys re-read that acted after the T0 head: %d" % tested)
    print("  keys whose credited terms MOVED:           %d" % credited)
    if tested and credited:
        print("  VERDICT: the engine credited rows beyond the cursor that "
              "/api/stats\n           reports. The reported cursor does not "
              "bound what /api/score counts.")
    elif tested:
        print("  VERDICT: no term moved on any key that acted. Consistent with "
              "a real\n           scoring stop across this window.")
    else:
        print("  VERDICT: INCONCLUSIVE - no tracked key acted again in time.")
    json.dump({"t0": st["at"],
               "t1": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "cursor_t0": st["cursor"], "cursor_t1": cur,
               "tested": tested, "credited": credited, "detail": detail},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  wrote %s" % a.out)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p0 = sub.add_parser("t0")
    p0.add_argument("--window", required=True)
    p0.add_argument("--out", required=True)
    p0.add_argument("--n", type=int, default=40)
    p0.add_argument("--sleep", type=float, default=1.2)
    p1 = sub.add_parser("t1")
    p1.add_argument("--state", required=True)
    p1.add_argument("--window", required=True)
    p1.add_argument("--sleep", type=float, default=1.2)
    p1.add_argument("--out", default="guide/_r179_credit_t1.json")
    a = ap.parse_args()
    return cmd_t0(a) if a.cmd == "t0" else cmd_t1(a)


if __name__ == "__main__":
    sys.exit(main())
