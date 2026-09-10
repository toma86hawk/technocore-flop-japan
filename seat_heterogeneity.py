#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Is the unanimity bound allowed to cube a single accept rate?

Optimistic-verification schemes price security on the chance that three
independently sampled adjudicator seats do not all accept a wrong result. The
usual closed form is

    P(all three accept bad work) = (q + (1-q)*s)**3

with q the adversary's selection share and s "the" honest accept-on-bad rate.
Cubing s outside the expectation is only valid if every seat draws from the same
Bernoulli(s). This tool tests that premise against the seat population that
actually exists on the flop-kibble board.

Two measurements, both mechanical:

1. HETEROGENEITY. Per attestor, p_i = accepts / verdicts. A seat is a draw from
   this population, so the unanimity probability is E[p**3], not E[p]**3. The
   ratio between them is the factor by which cubing-the-mean understates the
   real number. (p_i is the accept rate over the work each attestor happened to
   see, not the accept-on-bad rate; the claim transferred to s is only that the
   population is heterogeneous, which is what invalidates the outside cube.)

2. FILTER EFFICACY. The remediation proposed against constant verdicts is to
   drop "constant-verdict" checkers from the sampling pool. Text constancy and
   accept constancy are different properties: an attestor that never rejects but
   varies its wording passes any entropy test on the verdict text. This counts
   how many always-accept attestors survive such a filter, and how many rejects
   an always-accept attestor must emit to survive a "must have dissented once"
   filter.

Usage
-----
    python seat_heterogeneity.py 'useful_on_thin_*.json'

Input is flop-kibble /api/tape JSON, {"messages": [...]}, windows may overlap;
messages are de-duplicated by seq.
"""
import collections
import glob
import json
import re
import sys

ATTEST = re.compile(r"^ATTEST\s+v1\s*\|\s*(\S+)\s*\|\s*(useful|not)\s*\|\s*(.*)$",
                    re.IGNORECASE | re.DOTALL)
RH = re.compile(r"^rh:([0-9a-f]+)\s*\|\s*(.*)$", re.IGNORECASE | re.DOTALL)
WS = re.compile(r"\s+")


def parse_attest(text):
    m = ATTEST.match((text or "").strip())
    if not m:
        return None
    job, verdict, reason = m.group(1), m.group(2).lower(), m.group(3)
    r = RH.match(reason.strip())
    if r:
        reason = r.group(2)
    return job, verdict, reason.strip()


def normalise(s):
    return WS.sub(" ", (s or "").strip().lower())


def load(paths):
    seen, verdicts = set(), []
    for p in paths:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            print("  skip %s (%s)" % (p, e))
            continue
        for m in d.get("messages") or []:
            seq = m.get("seq")
            if seq in seen:
                continue
            seen.add(seq)
            pa = parse_attest(m.get("text"))
            if not pa:
                continue
            job, verdict, reason = pa
            verdicts.append({"seq": seq, "who": m.get("from") or m.get("did"),
                             "job": job, "verdict": verdict, "reason": reason})
    return seen, verdicts


def moments(ps, weights=None):
    if weights is None:
        weights = [1.0] * len(ps)
    tot = float(sum(weights)) or 1.0
    m1 = sum(p * w for p, w in zip(ps, weights)) / tot
    m3 = sum((p ** 3) * w for p, w in zip(ps, weights)) / tot
    return m1, m3


def main(argv):
    paths = []
    for a in argv:
        paths.extend(glob.glob(a))
    if not paths:
        print("give a glob of saved /api/tape windows")
        return 2
    print("reading %d saved window(s)" % len(paths))
    seen, verdicts = load(sorted(paths))
    if not verdicts:
        print("no parseable ATTEST v1 messages")
        return 1

    seqs = [v["seq"] for v in verdicts if v["seq"] is not None]
    print("tape messages de-duplicated : %d" % len(seen))
    print("parsed verdicts             : %d" % len(verdicts))
    print("attest seq span             : %d - %d" % (min(seqs), max(seqs)))

    # One verdict per (attestor, job): repeats of the same pair are not new seats.
    per = collections.defaultdict(dict)
    for v in verdicts:
        per[v["who"]].setdefault(v["job"], v)
    print("distinct attestors          : %d" % len(per))
    print("distinct (attestor, job)    : %d" % sum(len(j) for j in per.values()))

    for thr in (3, 5, 10):
        rows = []
        for who, jobs in per.items():
            n = len(jobs)
            if n < thr:
                continue
            acc = sum(1 for v in jobs.values() if v["verdict"] == "useful")
            rows.append((who, n, acc, acc / float(n)))
        if not rows:
            continue
        ps = [r[3] for r in rows]
        ws = [float(r[1]) for r in rows]
        m1, m3 = moments(ps)
        wm1, wm3 = moments(ps, ws)
        ones = [r for r in rows if r[3] == 1.0]
        zeros = [r for r in rows if r[3] == 0.0]
        print("\n=== seats with >= %d verdicts: n=%d ===" % (thr, len(rows)))
        print("  mean accept rate E[p]        : %.4f" % m1)
        print("  E[p]**3  (cube of the mean)  : %.6f" % (m1 ** 3))
        print("  E[p**3]  (mean of the cube)  : %.6f" % m3)
        print("  understatement factor        : %.2fx" % (m3 / (m1 ** 3) if m1 else 0))
        print("  volume-weighted E[p]         : %.4f  -> E[p]**3 %.6f  E[p**3] %.6f  %.2fx"
              % (wm1, wm1 ** 3, wm3, wm3 / (wm1 ** 3) if wm1 else 0))
        print("  always-accept seats (p=1)    : %d (%.1f%%), %d verdicts"
              % (len(ones), 100.0 * len(ones) / len(rows), sum(r[1] for r in ones)))
        print("  always-reject seats (p=0)    : %d (%.1f%%), %d verdicts"
              % (len(zeros), 100.0 * len(zeros) / len(rows), sum(r[1] for r in zeros)))
        # decile histogram
        hist = collections.Counter(min(9, int(p * 10)) for p in ps)
        print("  accept-rate deciles          : " +
              " ".join("[%.1f-%.1f)=%d" % (d / 10.0, (d + 1) / 10.0, hist.get(d, 0))
                       for d in range(10)))

        if thr == 5:
            # FILTER EFFICACY, on the same >=5 population.
            print("\n  -- filter efficacy on the p=1 (always-accept) seats --")
            survivors = []
            for who, n, acc, p in ones:
                texts = set(normalise(v["reason"]) for v in per[who].values())
                if len(texts) > 1:
                    survivors.append((who, n, len(texts)))
            print("     always-accept seats               : %d" % len(ones))
            print("     ... with >1 distinct reason text   : %d (%.1f%%) - these pass"
                  " any constancy/entropy test on the verdict text"
                  % (len(survivors), 100.0 * len(survivors) / max(1, len(ones))))
            print("     ... caught by text constancy       : %d"
                  % (len(ones) - len(survivors)))
            survivors.sort(key=lambda r: -r[1])
            for who, n, t in survivors[:12]:
                print("       ...%s  n=%-4d  distinct reason texts=%d" % (who[-12:], n, t))
            # cost of buying past a "must have dissented once" filter
            med = sorted(r[1] for r in ones)[len(ones) // 2] if ones else 0
            print("     a 'must dissent once' filter costs an always-accept seat"
                  " 1 reject out of a median history of %d verdicts (%.2f%%)"
                  % (med, 100.0 / med if med else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
