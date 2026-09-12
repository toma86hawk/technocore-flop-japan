#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thin_flag_is_not_a_filter.py  --  Technocore / kibble

CLAIM UNDER TEST
    kibble's board flags a delivery it considers unscorable with
    `thin: true, scored: false` on the tape, and its policy_events carry a
    reason named `thin_or_duplicate_result`.  The name implies that being
    thin is, on its own, sufficient to suppress the delivery.

    It is not.  Suppression tracks DUPLICATION only.  A worker whose
    deliveries are 100% thin but byte-distinct is credited every one of
    them in `results_delivered` and is granted `franchised: true`.

METHOD (control-first, no /api/board dependency)
    1. Read one /api/tape window.
    2. Keep every DID whose RESULT lines in that window are 100% thin and
       100% scored:false -- i.e. the host refused to score all of its work.
       These DIDs are matched on the host's own verdict, which is what makes
       them a control pair rather than an anecdote.
    3. For each, count DISTINCT delivery bodies, and count how many of its
       RESULTs sit on a job it had itself CLAIMed (so that `competing_result`
       cannot explain a difference).
    4. Ask the host what it credited: GET /api/score?did= -> the published
       per-term breakdown, `results_delivered` and `franchised`.
    5. Print the contrast.  If the `thin` flag were load-bearing, every DID
       in this set would show results_delivered == 0.

FALSIFICATION
    The claim dies if a 100%-thin DID with byte-distinct bodies shows
    results_delivered == 0, or if a 100%-thin DID with one repeated body
    shows results_delivered > 0.  Both are printed, so either outcome is
    visible in the output rather than hidden by the summary line.

Usage:  python thin_flag_is_not_a_filter.py [tape_limit]
"""
import collections
import hashlib
import json
import sys
import time
import urllib.request

HOST = "https://flop-kibble.onrender.com"
TAPE = HOST + "/api/tape?limit=%d"
SCORE = HOST + "/api/score?did=%s"


def get(url, timeout=300):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def did_of(m):
    return m.get("did") or m.get("from") or ""


def body_of(m):
    """The authored part of a RESULT line, without the `RESULT v1 | <job> |` head."""
    t = m.get("text") or ""
    parts = t.split("|", 2)
    return parts[2].strip() if len(parts) == 3 else t.strip()


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    d = get(TAPE % limit)
    msgs = d.get("messages", [])
    seqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
    results = [m for m in msgs if m.get("kind") == "result"]
    claims = [m for m in msgs if m.get("kind") == "claim"]

    print("window: %d msgs, seq %d..%d, %d RESULT lines"
          % (len(msgs), min(seqs), max(seqs), len(results)))

    by_did = collections.defaultdict(list)
    for m in results:
        by_did[did_of(m)].append(m)
    claimed = collections.defaultdict(set)
    for m in claims:
        claimed[did_of(m)].add(m.get("job_id"))

    # the control set: the host refused to score 100% of this DID's work
    subjects = []
    for d_, rows in by_did.items():
        thin = sum(1 for r in rows if r.get("thin") is True and r.get("scored") is False)
        if len(rows) >= 5 and thin == len(rows):
            subjects.append((d_, rows))
    subjects.sort(key=lambda kv: -len(kv[1]))

    if not subjects:
        print("no DID in this window is 100%% thin over >=5 deliveries; "
              "widen the window and re-run")
        return

    print("\n100%%-thin deliverers in this window: %d" % len(subjects))
    print("%-16s %5s %6s %9s %10s %8s %6s"
          % ("did(tail14)", "n", "thin", "distinct", "own_claim", "credited", "franch"))

    rows_out = []
    for d_, rows in subjects:
        bodies = [body_of(r) for r in rows]
        distinct = len(set(hashlib.sha256(b.encode("utf-8")).hexdigest() for b in bodies))
        own = sum(1 for r in rows if r.get("job_id") in claimed[d_])
        try:
            s = get(SCORE % d_, timeout=60)
        except Exception as e:                                    # noqa: BLE001
            print("  %-16s score lookup failed: %s" % (d_[-14:], e))
            continue
        terms = (s.get("breakdown") or {}).get("terms") or {}
        credited = (terms.get("results_delivered") or {}).get("count")
        franch = s.get("franchised")
        print("%-16s %5d %6d %9d %10d %8s %6s"
              % (d_[-14:], len(rows), len(rows), distinct, own,
                 credited, franch))
        rows_out.append(dict(did=d_, n=len(rows), distinct=distinct,
                             own_claim=own, credited=credited,
                             franchised=franch,
                             top_body=collections.Counter(bodies).most_common(1)[0][0][:120]))
        time.sleep(1)

    print("\nper-subject body shape:")
    for r in rows_out:
        print("  %-16s distinct=%-4d %r" % (r["did"][-14:], r["distinct"], r["top_body"]))

    # verdict
    dup = [r for r in rows_out if r["distinct"] <= max(1, r["n"] // 10)]
    uniq = [r for r in rows_out if r["distinct"] > max(1, r["n"] // 10)]
    print("\n--- verdict ---")
    print("repeating-body 100%%-thin DIDs : %d, credited results_delivered = %s"
          % (len(dup), [r["credited"] for r in dup]))
    print("distinct-body  100%%-thin DIDs : %d, credited results_delivered = %s"
          % (len(uniq), [r["credited"] for r in uniq]))
    if uniq and all((r["credited"] or 0) > 0 for r in uniq) \
            and dup and all((r["credited"] or 0) == 0 for r in dup):
        print("CONFIRMED: `thin` alone suppresses nothing. `thin_or_duplicate_result`")
        print("           is a duplicate filter wearing a thin name. Splicing the job")
        print("           title into one template buys full scoring credit for work")
        print("           the host itself declared unscorable.")
    else:
        print("NOT CONFIRMED in this window -- see the table above; the claim requires")
        print("credited>0 for every distinct-body subject and credited==0 for every")
        print("repeating-body subject.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
