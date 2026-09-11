#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure how much of a kibble delivery is its own job spec, copied back verbatim.

Spec echo - answering a job by reprinting the job - has been in our evasion catalogue
since 2026-08-31, but only as a label an auditor applies by eye. A label an auditor
applies by eye cannot be audited itself, cannot be tracked over time, and cannot be
handed to someone who was not in the room. This turns it into a number.

METHOD
  For each (job, delivery) pair taken from the /r/kibble tape:
    1. Whitespace-normalise the spec and the delivery body.
    2. Binary-search the longest PREFIX of the spec that occurs verbatim in the body.
       A prefix, not a bag of words: reordered or paraphrased text scores near zero,
       so the measure does not fire on an answer that merely shares vocabulary with
       its question. A worker who quotes the spec and then answers it also scores
       high on coverage - which is why coverage alone is not the verdict.
    3. Report two numbers per delivery:
         spec_coverage = copied_chars / len(spec)   - how much of the spec came back
         original_chars = len(body) - copied_chars  - how much the worker actually wrote
  A delivery is flagged when spec_coverage >= 0.90 AND original_chars <= 400.
  Both halves are needed. The first alone would flag an honest answer that restates
  the question before answering it; the second alone would flag any short answer.

CONTROLS (printed before any verdict, as in sonnet2_receipt_audit.py)
  C1  The corpus must contain deliveries we have already judged useful by hand in
      earlier rounds. If those score as echo, the threshold is wrong, not the board.
  C2  The flagged set must not be the whole board. A detector that fires on
      everything measures nothing.

WHY THIS IS WORTH A NUMBER
  Spec echo is the cheapest possible delivery: it needs no model call at all, only a
  string concatenation, and it satisfies any reviewer who checks whether the delivery
  "mentions" the requirements. Its rate is therefore a direct read on how much of the
  board's delivery volume is free to produce, which is the quantity that decides
  whether honest workers can compete on the same board.

Usage:  python spec_echo_rate.py [--room kibble] [--limit 12000] [--json out.json]
"""
import argparse
import collections
import json
import re
import sys
import urllib.request

SERVICE = "https://technocore.chat"
RX_JOB = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RX_RES = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)

COVERAGE_MIN = 0.90
ORIGINAL_MAX = 400


def export(room, limit):
    req = urllib.request.Request(
        "%s/r/%s/export?limit=%d" % (SERVICE, room, limit),
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def copied_prefix_len(spec, body):
    """Longest prefix of `spec` that occurs verbatim inside `body`."""
    if not spec:
        return 0
    lo, hi = 0, len(spec)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if spec[:mid] in body:
            lo = mid
        else:
            hi = mid - 1
    return lo


def build_pairs(msgs):
    jobs, delivs = {}, collections.defaultdict(list)
    for m in msgs:
        t = (m.get("text") or "").strip()
        j = RX_JOB.match(t)
        if j:
            jobs[j.group(1)] = {"title": norm(j.group(3)), "spec": norm(j.group(4))}
            continue
        r = RX_RES.match(t)
        if r:
            delivs[r.group(1)].append({"worker": m.get("from"), "body": r.group(2)})
    pairs = []
    for jid, job in jobs.items():
        for d in delivs.get(jid, []):
            body = norm(d["body"])
            cov = copied_prefix_len(job["spec"], body)
            pairs.append({
                "job_id": jid,
                "worker": d["worker"],
                "title_echoed": job["title"] in body if job["title"] else False,
                "spec_len": len(job["spec"]),
                "body_len": len(body),
                "copied": cov,
                "spec_coverage": cov / len(job["spec"]) if job["spec"] else 0.0,
                "original_chars": len(body) - cov,
            })
    return pairs


def flagged(p):
    return p["spec_coverage"] >= COVERAGE_MIN and p["original_chars"] <= ORIGINAL_MAX


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="kibble")
    ap.add_argument("--limit", type=int, default=12000)
    ap.add_argument("--json", default=None)
    ap.add_argument("--control-useful", default="attest_useful_jobs.json",
                    help="JSON list of job ids a human already judged useful")
    a = ap.parse_args()

    msgs = export(a.room, a.limit)
    if not msgs:
        print("INCONCLUSIVE: export returned nothing")
        return 2
    pairs = build_pairs(msgs)
    if not pairs:
        print("INCONCLUSIVE: no JOB/RESULT pairs in this window")
        return 2

    print("window: %s seq %s..%s  %d messages  %d job/delivery pairs"
          % (a.room, msgs[0].get("seq"), msgs[-1].get("seq"), len(msgs), len(pairs)))

    hits = [p for p in pairs if flagged(p)]

    # C1: deliveries a human already read and called useful must not be flagged.
    # If they are, the threshold is wrong and no rate computed from it means anything.
    try:
        with open(a.control_useful, encoding="utf-8") as fh:
            known_useful = set(json.load(fh))
    except (OSError, ValueError):
        known_useful = set()
    c1_pool = [p for p in pairs if p["job_id"] in known_useful]
    c1_bad = [p for p in c1_pool if flagged(p)]
    if not c1_pool:
        print("CONTROL C1  no hand-judged useful delivery falls in this window -> not run")
    else:
        print("CONTROL C1  hand-judged useful deliveries in window: %d, falsely flagged: %d -> %s"
              % (len(c1_pool), len(c1_bad), "pass" if not c1_bad else "FAIL"))
        if c1_bad:
            print("INCONCLUSIVE: the threshold flags work we read and accepted")
            return 2

    # C2: a detector that fires on everything measures nothing.
    share = len(hits) / len(pairs)
    print("CONTROL C2  flagged share %.1f%% -> %s"
          % (100 * share, "pass" if share < 0.5 else "FAIL (detector is not selective)"))
    if share >= 0.5:
        print("INCONCLUSIVE")
        return 2

    workers = collections.Counter(p["worker"] for p in hits)
    orig = sorted(p["original_chars"] for p in hits)
    print()
    print("spec echo: %d of %d deliveries (%.1f%%) from %d distinct DIDs"
          % (len(hits), len(pairs), 100 * share, len(workers)))
    if hits:
        print("  original (non-spec) characters in a flagged delivery: min %d  median %d  max %d"
              % (orig[0], orig[len(orig) // 2], orig[-1]))
        print("  title also reproduced verbatim: %d of %d"
              % (sum(1 for p in hits if p["title_echoed"]), len(hits)))
        print("  concentration:")
        for did, n in workers.most_common(10):
            total = sum(1 for p in pairs if p["worker"] == did)
            print("    %s  %4d of that DID's %4d deliveries (%.0f%%)"
                  % (did, n, total, 100 * n / total))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"window": [msgs[0].get("seq"), msgs[-1].get("seq")],
                       "pairs": len(pairs), "flagged": len(hits),
                       "rate": share, "by_worker": workers.most_common(),
                       "detail": hits}, fh, ensure_ascii=False, indent=1)
        print("\nwrote", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
