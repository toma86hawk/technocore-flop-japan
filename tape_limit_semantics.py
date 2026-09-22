# -*- coding: utf-8 -*-
"""What does /api/tape?limit=N actually return?

measure_useful_on_thin.py has called /api/tape?limit=1500 every three hours since
2026-08-31 and treated the answer as "the current window" - 138 published points
rest on that reading.  A limit=20 probe came back as seq 1..20, i.e. the OLDEST
rows on the tape, which is not what a window means.  So the reading has to be
tested rather than assumed.

For each limit this records: rows returned, min/max seq, and whether the seqs are
contiguous.  A "most recent N" endpoint gives contiguous seqs at the top of the
range; a "first N" endpoint gives contiguous seqs starting at 1.

One request at a time, spaced, per the rate-limit rule.  Output is flushed after
every probe so a run that has to be interrupted still leaves its evidence.
"""
import json, urllib.request, time, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
BASE = "https://flop-kibble.onrender.com/api/tape?limit=%d"
LIMITS = [int(x) for x in sys.argv[1:]] or [20, 200, 1000, 1500]


def probe(n, tries=2, timeout=75):
    for t in range(tries):
        try:
            with urllib.request.urlopen(BASE % n, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            print("   limit=%d try %d failed: %s" % (n, t + 1, str(e)[:60]), flush=True)
            time.sleep(6)
    return None


out = []
for n in LIMITS:
    d = probe(n)
    if d is None:
        out.append({"limit": n, "error": "unreachable after retries"})
        print(json.dumps(out[-1]), flush=True)
        continue
    msgs = d.get("messages", [])
    seqs = sorted(m["seq"] for m in msgs if m.get("seq") is not None)
    if not seqs:
        out.append({"limit": n, "rows": len(msgs), "error": "no seqs"})
        print(json.dumps(out[-1]), flush=True)
        continue
    span = seqs[-1] - seqs[0] + 1
    rec = {
        "limit": n,
        "rows": len(msgs),
        "seq_lo": seqs[0],
        "seq_hi": seqs[-1],
        "span": span,
        "contiguous": len(seqs) == span,
        "gaps": span - len(seqs),
    }
    out.append(rec)
    print(json.dumps(rec), flush=True)
    time.sleep(6)

json.dump(out, open(r"C:\Users\Administrator\flop\guide\_r175_tape_limits.json",
                    "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nwrote guide/_r175_tape_limits.json", flush=True)
