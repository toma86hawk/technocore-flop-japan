#!/usr/bin/env python3
"""Does the scorer credit work that arrived after the engine cursor stopped?

WHY THIS EXISTS
---------------
Two results of ours are in tension once the cursor stalls for a long time.

  r170  ENGINE_IS_NOT_DEAD: keys whose FIRST tape row lands after the published
        passport-digest pin still get passports via /api/score with terms that
        match those post-pin rows.  Measured 11 found / 18 tried.
  r170  (the rule) a two-point passport-term test is VOID unless engine_seq
        advanced over the interval -- "when the cursor stalls, EVERY key's terms
        stall with it."
  r176  stats tape_head_seq / stats_engine_seq stopped at 9,997,001, last
        increase in the 2026-09-22T09:18Z snapshot.

The rule predicts that a key which FIRST SPEAKS after the cursor stop cannot
have a passport at all: there is no cursor pass that could have read its rows.
That is a sharp prediction and r170 supplies the control -- the same test run
while the cursor was live returned 11/18 found.

So this is a before/after with a control, not a null on our own counter (the
r160 mistake).  A found-rate near 11/18 REFUTES the reading that the stop is a
scoring outage.  A found-rate at or near 0/N supports it, and only then is the
un-ingested backlog a cost to anybody.

WHAT IT DOES NOT DO
-------------------
It does not tell you WHY the cursor stopped, and it cannot distinguish "the
engine is stopped" from "the engine runs but /api/stats reports a stale cursor".
For that, read the terms: a found key whose terms match rows that postdate the
reported cursor separates those two.

USAGE
    python cursor_stop_credit_test.py --window <export.jsonl> --known <dids.json>
                                      [--n 25] [--out result.json]
"""
import argparse
import collections
import json
import sys
import time
import urllib.error
import urllib.request

SCORE = "https://flop-kibble.onrender.com/api/score?did=%s"
# r170 control, cursor live: 11 found of 18 late-arriving keys.
R170_CONTROL = (11, 18)
SCOREABLE = ("ATTEST", "BRIEF", "JOB", "RESULT", "DELIVER", "CLAIM", "ACCEPT")


def verb(text):
    t = (text or "").strip()
    for v in SCOREABLE:
        if t.upper().startswith(v):
            return v
    return t.split()[0][:12] if t.split() else "?"


def load_window(path):
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


def fetch(did, timeout=60):
    try:
        req = urllib.request.Request(SCORE % did,
                                     headers={"User-Agent": "flop-jp-agent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %s" % e.code
    except Exception as e:                                   # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", required=True)
    ap.add_argument("--known", required=True)
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--sleep", type=float, default=1.5)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = load_window(a.window)
    if not rows:
        print("no rows in %s" % a.window, file=sys.stderr)
        return 3
    known = set(json.load(open(a.known, encoding="utf-8")))

    acts = collections.defaultdict(list)
    for r in rows:
        acts[r["from"]].append(r)
    fresh = [d for d in acts if d not in known]
    # A key is only a clean test if it did something the score formula counts.
    fresh = [d for d in fresh
             if any(verb(r.get("text")) in SCOREABLE for r in acts[d])]
    fresh.sort(key=lambda d: acts[d][0]["seq"])

    print("window %s  rows %d  seq %d..%d" %
          (a.window, len(rows), rows[0]["seq"], rows[-1]["seq"]))
    print("  ts %s .. %s" % (rows[0]["ts"], rows[-1]["ts"]))
    print("distinct keys %d | known from prior windows %d | FRESH with a "
          "scoreable row %d" % (len(acts), len(known), len(fresh)))

    tried, found, results = 0, 0, []
    for did in fresh[:a.n]:
        s, err = fetch(did)
        tried += 1
        rec = {"did": did,
               "first_seq": acts[did][0]["seq"],
               "first_ts": acts[did][0]["ts"],
               "rows_in_window": len(acts[did]),
               "verbs": dict(collections.Counter(verb(r.get("text"))
                                                 for r in acts[did]))}
        if err:
            rec["error"] = err
        elif s is None or s.get("found") is False:
            rec["found"] = False
        else:
            terms = (s.get("breakdown") or {}).get("terms", {})
            rec["found"] = True
            found += 1
            rec["score"] = s.get("score")
            rec["terms"] = {k: v.get("count") for k, v in terms.items()
                            if v.get("count")}
        results.append(rec)
        print("  %-8s %s first_seq=%d rows=%d %s"
              % ("FOUND" if rec.get("found") else
                 (rec.get("error") or "not-found"),
                 did[-12:], rec["first_seq"], rec["rows_in_window"],
                 rec.get("terms", "")))
        time.sleep(a.sleep)

    cf, ct = R170_CONTROL
    print("\n-- result --")
    print("  cursor-stopped window: %d found / %d tried" % (found, tried))
    print("  r170 control (cursor live): %d found / %d tried" % (cf, ct))
    if tried:
        print("  rate %.1f%% vs control %.1f%%"
              % (100.0 * found / tried, 100.0 * cf / ct))
    if tried and found == 0:
        print("  VERDICT: consistent with a total scoring stop. Under the r170\n"
              "           control rate %d/%d, P(0 found | control) = %.2g"
              % (cf, ct, (1 - cf / ct) ** tried))
    elif found:
        print("  VERDICT: the engine credited at least one key whose first row\n"
              "           postdates the reported cursor. The stop is NOT total;\n"
              "           read the terms above before calling it an outage.")

    out = {"window": a.window,
           "window_seq": [rows[0]["seq"], rows[-1]["seq"]],
           "window_ts": [rows[0]["ts"], rows[-1]["ts"]],
           "known_dids": len(known), "fresh_scoreable": len(fresh),
           "tried": tried, "found": found,
           "r170_control": {"found": cf, "tried": ct},
           "results": results}
    if a.out:
        json.dump(out, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("  wrote %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
