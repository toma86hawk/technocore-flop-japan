#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Did /api/tape stop being a tail read?

Every useful_on_thin point since 2026-08-31 was computed from /api/tape?limit=1500
and read as "the current window".  r175 verified that reading over 137 archived
responses: seq_hi advanced in 136 of 136 consecutive steps, so it WAS a tail read.
r175 also saw limit=20 come back as seq 1..20 and left "small and large limits
differ" open.

At 2026-09-22T12:5xZ a limit=1500 call came back as seq 400..1393 - the OLDEST
rows - which is not a limit effect, because 1500 is the limit that had been a
tail read in all 136 archived steps.  So the question is not small-vs-large, it
is before-vs-after.

This prints, for each probe: rows, seq_lo, seq_hi, and seq_hi as a fraction of
the tape head taken from /api/stats in the same run.  A tail read has that
fraction at ~1.0.  A head-of-space read has it at ~0.0.
"""
import json, urllib.request, time, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
TAPE = "https://flop-kibble.onrender.com/api/tape?limit=%d"
STATS = "https://flop-kibble.onrender.com/api/stats"


def get(url, timeout=90):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def head():
    try:
        d = get(STATS)
        return (d.get("origin") or {}).get("tape_head_seq")
    except Exception as e:
        print("  stats failed: %s" % str(e)[:60])
        return None


def probe(n):
    try:
        d = get(TAPE % n)
    except Exception as e:
        print("  limit=%-5d FAILED %s" % (n, str(e)[:60]))
        return None
    ms = d.get("messages", [])
    seqs = sorted(m["seq"] for m in ms if m.get("seq") is not None)
    if not seqs:
        print("  limit=%-5d rows=%d no seqs" % (n, len(ms)))
        return None
    return {"limit": n, "rows": len(ms), "seq_lo": seqs[0], "seq_hi": seqs[-1],
            "span": seqs[-1] - seqs[0] + 1, "gaps": seqs[-1] - seqs[0] + 1 - len(seqs)}


def main():
    limits = [int(x) for x in sys.argv[1:]] or [1500, 1500, 1000, 1500]
    h = head()
    print("tape_head_seq from /api/stats: %s\n" % h)
    out = []
    for n in limits:
        r = probe(n)
        if r:
            r["head"] = h
            r["seq_hi_over_head"] = round(r["seq_hi"] / h, 6) if h else None
            print("  limit=%-5d rows=%-5d seq %d..%d  span %d gaps %d  seq_hi/head=%s"
                  % (n, r["rows"], r["seq_lo"], r["seq_hi"], r["span"], r["gaps"],
                     r["seq_hi_over_head"]))
            out.append(r)
        time.sleep(8)
    if out:
        frac = [r["seq_hi_over_head"] for r in out if r["seq_hi_over_head"] is not None]
        if frac:
            print("\nverdict: %s"
                  % ("TAIL READ (seq_hi within 1%% of head)" if min(frac) > 0.99
                     else "HEAD-OF-SPACE READ - the endpoint is returning the oldest rows"
                          if max(frac) < 0.01 else "MIXED / inconclusive"))
    json.dump(out, open(r"C:\Users\Administrator\flop\guide\data\tape_order_flip.json",
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
