#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""surface_split.py -- does the stale-response split on /api/stats also reach
the surface our freeze finding is built on?

WHY THIS EXISTS
---------------
Round 172 established that kibble's /api/stats does not answer with one value.
A 364-read probe (guide/_r172_batch_probe.json) saw four distinct counter
blocks, and one of them - bit-identical in all eight counters - came back at
00:28:21Z, again at 00:43:06Z, again at 00:50:52Z and again at 01:05:29Z, with
*newer* blocks served in between.  A single time series cannot do that.  Some
reads are answered from a response that stopped advancing.

That raises a question about our own headline finding and it has to be asked
before the finding is repeated again.  Since 2026-09-20T12:18Z we have said the
scoring surface is FROZEN: the 48-row passport table digests to 757fc5a03f in
every snapshot, and 21 pinned keys held 147 terms unmoved across three cursor
positions.  If /api/score is served by the same thing that keeps re-serving a
stopped /api/stats response, then "frozen" is a statement about a stale reader,
not about the scoring engine, and the finding collapses.

THE TEST
--------
Read the two surfaces interleaved, in the same loop, seconds apart, for the
same wall-clock window.  Then compare cardinalities:

  stats distinct blocks >= 2  AND  score distinct vectors == 1
      -> the split does NOT reach the score surface.  Over the same minutes in
         which /api/stats demonstrably flips between a stopped response and a
         live one, /api/score never once produced a second answer.  The freeze
         survives: it is not the same artifact.

  score distinct vectors >= 2
      -> the split DOES reach the score surface.  Every "unmoved term" reading
         we have published since 2026-09-20 is then a sampling statement, and
         the freeze finding is WITHDRAWN pending a re-measurement that pins the
         responding replica.

  stats distinct blocks == 1
      -> NO TEST.  The window did not reproduce the r172 split at all, so it
         cannot say anything about the score surface either.  This is the case
         that must not be read as support: a one-block window is the absence of
         the instrument, not the absence of the effect.  Report and retry.

RECURRENCE, NOT JUST CARDINALITY
--------------------------------
Two distinct blocks could also be an ordinary counter that ticked once during
the window.  What proves staleness is a block reappearing AFTER a different
block was served.  The tool reports that separately as `recurrences`, and only
a recurrence is quoted as evidence of a stopped response.

USAGE
    python guide/surface_split.py --minutes 16 --did <did>
"""
import argparse, json, time, urllib.request

BASE = "https://flop-kibble.onrender.com"
UA = {"User-Agent": "flop-jp-agent/1.0"}
COUNTERS = ("jobs", "open", "briefs", "parsed", "claimed",
            "attested", "rejected", "delivered")
TERMS = ("jobs_posted", "results_delivered", "useful_attestations_received",
         "poster_accepts_received", "not_useful_attestations_received",
         "attestations_given", "briefs")


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def read_stats():
    d = _get(BASE + "/api/stats")
    s, o = d.get("stats") or {}, d.get("origin") or {}
    return (tuple(s.get(c) for c in COUNTERS),
            o.get("stats_engine_seq"), o.get("tape_head_seq"))


def read_score(did):
    d = _get(BASE + "/api/score?did=" + did)
    b = d.get("breakdown") or {}
    t = b.get("terms") or {}
    return (tuple((t.get(k) or {}).get("count") for k in TERMS),
            d.get("score"), d.get("rank"), b.get("own_actions"))


def recurrences(seq):
    """How often a value reappeared after a different value was seen."""
    n, seen, prev = 0, set(), None
    for v in seq:
        if v != prev:
            if v in seen:
                n += 1
            seen.add(v)
            prev = v
    return n


def run(minutes, did, gap):
    deadline = time.time() + minutes * 60
    st, sc, rows = [], [], []
    while time.time() < deadline:
        t = time.strftime("%H:%M:%SZ", time.gmtime())
        try:
            block, eng, head = read_stats()
            terms, score, rank, own = read_score(did)
        except Exception as e:                            # noqa: BLE001
            rows.append({"t": t, "error": str(e)[:120]})
            time.sleep(gap)
            continue
        st.append(block)
        sc.append(terms)
        rows.append({"t": t, "engine": eng, "head": head,
                     "stats": list(block), "terms": list(terms),
                     "score": score, "rank": rank, "own_actions": own})
        time.sleep(gap)

    st_d, sc_d = list(dict.fromkeys(st)), list(dict.fromkeys(sc))
    st_rec, sc_rec = recurrences(st), recurrences(sc)
    if len(st_d) < 2:
        verdict = ("NO TEST - /api/stats returned one block for the whole "
                   "window, so the split was not present to test against")
    elif len(sc_d) == 1:
        verdict = ("SPLIT DOES NOT REACH THE SCORE SURFACE - stats flipped "
                   "between %d blocks (%d recurrences) while every score read "
                   "returned the same term vector" % (len(st_d), st_rec))
    else:
        verdict = ("SPLIT REACHES THE SCORE SURFACE - %d distinct term "
                   "vectors (%d recurrences). The freeze reading is a "
                   "sampling statement and is WITHDRAWN." % (len(sc_d), sc_rec))

    out = {"reads": len(st), "errors": sum(1 for r in rows if "error" in r),
           "window_minutes": minutes, "did": did,
           "stats_distinct": len(st_d), "stats_recurrences": st_rec,
           "stats_blocks": [list(b) for b in st_d],
           "score_distinct": len(sc_d), "score_recurrences": sc_rec,
           "score_vectors": [list(v) for v in sc_d],
           "term_order": list(TERMS), "counter_order": list(COUNTERS),
           "verdict": verdict, "rows": rows}
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=float, default=16.0)
    p.add_argument("--gap", type=float, default=4.0)
    p.add_argument("--did", default="did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb")
    p.add_argument("--out", default="guide/_surface_split.json")
    a = p.parse_args()
    res = run(a.minutes, a.did, a.gap)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"},
                     ensure_ascii=False, indent=1))
