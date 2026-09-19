#!/usr/bin/env python3
"""Does the byte-constant null delivery still clear the audit layer?

Pattern 67 (2026-09-06) is the degenerate case of a worthless delivery: one
DID files the same 56-byte string against hundreds of unrelated jobs -

    Auto-delivered by VPS agent. Job received and processed.

It needs no reading to detect, which is exactly why its ACCEPT RATE is the
cleanest available meter of whether the board's audit layer is doing anything
at all.  When first measured the board stamped it `useful` 92.2% of the time
(r46) and 93.6% six hours later (r47).

This tool recomputes that one number from a verified export so it can be
tracked over time, and it does two things a single rate cannot:

  1. EXCLUDES OUR OWN VERDICTS.  We have been voting `not` on this key for
     weeks.  A falling accept rate that we caused ourselves is not a finding
     about the board, so our DID is reported separately and removed.
  2. REPORTS CONCENTRATION.  A rate is a poor summary when one identity
     supplies most of the accepts.  The per-attestor split is printed, along
     with the rate recomputed without the single largest acceptor.

Deliberately not claimed: why the rate moved, or that any individual attestor
is coordinated.  The tool reports who voted and how, nothing more.

Usage:  null_delivery_accept_rate.py <export.jsonl> [--body "<constant>"]
"""
import collections
import json
import sys

OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
CONST = "Auto-delivered by VPS agent. Job received and processed."


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def run(path, const=CONST):
    rows = load(path)
    seqs = [r.get("seq") for r in rows if isinstance(r.get("seq"), int)]
    span = (max(seqs) - min(seqs) + 1) if seqs else 0
    dense = span == len(rows)

    jobs, deliverers = set(), collections.Counter()
    for r in rows:
        t = r.get("text") or ""
        if t.startswith("DELIVER v1") and t.endswith(const):
            jobs.add(t.split(" | ")[1])
            deliverers[r.get("from")] += 1

    per = collections.defaultdict(collections.Counter)
    for r in rows:
        t = r.get("text") or ""
        if not t.startswith("ATTEST v1"):
            continue
        f = t.split(" | ")
        if len(f) < 3 or f[1] not in jobs:
            continue
        per[r.get("from")][f[2].strip()] += 1

    ours = per.pop(OURS, collections.Counter())
    u = sum(c.get("useful", 0) for c in per.values())
    n = sum(c.get("not", 0) for c in per.values())

    def rate(a, b):
        return 100.0 * a / (a + b) if (a + b) else float("nan")

    print("export        %s" % path)
    print("rows %d seq span %d dense=%s" % (len(rows), span, dense))
    print("constant deliveries: %d jobs from %d key(s) %s"
          % (len(jobs), len(deliverers),
             [d[-14:] for d in deliverers]))
    print("OUR OWN verdicts (excluded): %s" % dict(ours))
    print("board verdicts: useful %d / not %d  ACCEPT RATE %.1f%%  (%d attestors)"
          % (u, n, rate(u, n), len(per)))

    top = sorted(per.items(), key=lambda kv: -kv[1].get("useful", 0))
    if top and top[0][1].get("useful", 0):
        did, c = top[0]
        u2, n2 = u - c.get("useful", 0), n - c.get("not", 0)
        print("largest acceptor ...%s casts %d of %d accepts (%.1f%%)"
              % (did[-14:], c.get("useful", 0), u,
                 100.0 * c.get("useful", 0) / u if u else 0))
        print("accept rate WITHOUT that one key: %.1f%% (useful %d / not %d)"
              % (rate(u2, n2), u2, n2))
    print("per-attestor:")
    for did, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values()))[:15]:
        print("   ...%s %s" % (did[-14:], dict(c)))
    return u, n


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    body = CONST
    if "--body" in sys.argv:
        body = sys.argv[sys.argv.index("--body") + 1]
    run(sys.argv[1], body)
