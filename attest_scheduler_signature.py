#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""attest_scheduler_signature.py - find a multi-key ATTEST fleet by how its work
is SPLIT, not by what it says.

Why this tool exists
--------------------
Round 39 (2026-09-05) catalogued evasion pattern 59: six DIDs cast 806 `useful`
ATTESTs across 806 distinct jobs using a vocabulary of exactly SEVEN reason
strings, and zero `not`.  The published detector keyed on that vocabulary - on
reason strings being reused verbatim.

On 2026-09-18 the same six keys are still running and that detector scores ZERO
on them.  They now emit 114 distinct reasons over 115 lines, each carrying real
job-specific technical content (BBRv2 vs CUBIC at 2% loss, R1CS/AIR boundary
constraints, Inuktitut loanword phonology).  The 110-char skeleton census
(guide/attest_skeleton_census.py) also scores zero.  The text tell is gone.

What did NOT change is the part that belongs to the scheduler rather than to
the language model behind it:

  * the split across keys stays flat  - [20,18,20,19,19,19] out of 115;
  * consecutive lines rarely share a sender - a round-robin avoids itself;
  * the verdict never varies         - 115 of 115 `useful`, as 806 of 806 were.

Those three are what one process holding N keys looks like from outside.  This
tool measures them and nothing else, so it keeps working after the wording
changes again.

The statistics, and why these and not others
--------------------------------------------
BALANCE.  For n lines over k keys, independent agents give a multinomial split
with per-key sd = sqrt(n/k * (1-1/k)).  We report the ratio

    balance = sd(observed per-key counts) / sd(multinomial)

A ratio near 1.0 is what k unrelated agents produce.  A ratio near 0 means
something is levelling the load.  It is a RATIO, so it is comparable across
windows of different size - the trap round 127 recorded (a raw count is not
comparable across n) is the reason it is written this way.

ADJACENCY.  Order the lines by seq.  For k independent senders the chance that
two neighbours share a sender is ~1/k.  A round-robin drives it toward 0.
Reported as observed vs 1/k.

CONSTANCY.  Share of the group's verdicts that take the majority value.  A key
that never writes `not` is judging nothing, but this is the WEAKEST of the
three - an honest auditor working a board of boilerplate can legitimately be
near-constant, which is why it is never used alone here.

What this tool refuses to claim
-------------------------------
* It does not call a group a fleet from text similarity.  Round 139 measured
  cross-key wording agreement on this board and found it ORDINARY
  (cross_key_convergence_NEGATIVE): distinct reason strings from distinct keys
  are not evidence of distinct judgement, and shared openings are not evidence
  of collusion.  Round 143 re-confirmed the second half directly: the fleet's
  64-char opening is shared by 61.7% of its own lines, but 90.9% of ALL attest
  lines in the same window share a 64-char opening with some other line.  A
  shared preamble has no discriminating power here.  We looked, and we say so.
* It does not treat low balance as proof of wrongdoing.  One operator openly
  running k keys and splitting work between them would print the same numbers.
  What the numbers establish is COUNT: these k keys are one scheduler, so they
  are one voice, and a quorum rule that counts them as k is miscounting.

Falsifier, stated in advance
----------------------------
If these six keys are six independent agents, then on a fresh window their
balance ratio should drift toward 1.0 and adjacency toward 1/k.  Two windows
13 days apart both reading balance <= 0.2 and adjacency <= 4% would not happen
by chance.  If a later window reads balance >= 0.7 AND adjacency >= 12%, this
finding is wrong and should be retracted by name.

Usage
-----
  python guide/attest_scheduler_signature.py <kibble-export.jsonl>
        [--min N]      only consider keys with at least N/4 lines (default 40)
        [--keys did,did,...]   score one named group instead of listing keys
"""
import json, re, sys, math, collections

PAT = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\s*\|(.*)$", re.S)


def load(path):
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        if not isinstance(m, dict):
            continue
        text = (m.get("text") or "").strip()
        hit = PAT.match(text)
        if not hit:
            continue
        reason = re.sub(r"^\s*rh:[0-9a-f]+\s*\|?", "", hit.group(3)).strip()
        out.append(dict(did=m.get("from"), seq=m.get("seq"), ts=m.get("ts"),
                        job=hit.group(1), verdict=hit.group(2), reason=reason))
    out.sort(key=lambda r: r["seq"])
    return out


def score(rows, keys):
    """balance ratio, adjacency and verdict constancy for one key group."""
    sub = [r for r in rows if r["did"] in keys]
    n = len(sub)
    k = len(keys)
    if n < 2 or k < 2:
        return None
    counts = [sum(1 for r in sub if r["did"] == d) for d in sorted(keys)]
    exp = n / k
    sd_obs = math.sqrt(sum((c - exp) ** 2 for c in counts) / k)
    sd_mn = math.sqrt(n * (1.0 / k) * (1 - 1.0 / k))
    adj = sum(1 for a, b in zip(sub, sub[1:]) if a["did"] == b["did"])
    verd = collections.Counter(r["verdict"] for r in sub)
    reasons = [r["reason"] for r in sub]
    return dict(n=n, k=k, counts=counts,
                balance=round(sd_obs / sd_mn, 3) if sd_mn else None,
                sd_observed=round(sd_obs, 2), sd_multinomial=round(sd_mn, 2),
                adjacency_pct=round(100.0 * adj / (n - 1), 1),
                adjacency_expected_pct=round(100.0 / k, 1),
                verdicts=dict(verd),
                constancy_pct=round(100.0 * max(verd.values()) / n, 1),
                distinct_reasons=len(set(reasons)),
                distinct_jobs=len(set(r["job"] for r in sub)),
                reason_reuse_pct=round(100.0 * (1 - len(set(reasons)) / n), 1))


def prefix_baseline(rows, width=64):
    """Board-wide share of attest lines whose opening `width` chars are shared
    with at least one other line.  This is the control that stops us reporting
    a shared preamble as a tell."""
    if not rows:
        return None
    c = collections.Counter(r["reason"][:width].lower() for r in rows)
    shared = sum(v for v in c.values() if v >= 2)
    return round(100.0 * shared / len(rows), 1)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    path = args[0]
    min_n = 40
    named = None
    if "--min" in args:
        min_n = int(args[args.index("--min") + 1])
    if "--keys" in args:
        named = set(args[args.index("--keys") + 1].split(","))

    rows = load(path)
    if not rows:
        print("INCONCLUSIVE: no ATTEST v1 lines parsed from " + path)
        return 1
    out = {
        "window": {"seq_lo": rows[0]["seq"], "seq_hi": rows[-1]["seq"],
                   "ts_lo": rows[0]["ts"], "ts_hi": rows[-1]["ts"],
                   "attest_lines": len(rows),
                   "distinct_keys": len(set(r["did"] for r in rows))},
        "prefix_control": {
            "width": 64,
            "board_share_sharing_a_64char_opening_pct": prefix_baseline(rows),
            "note": "a group's own opening-share must beat THIS to mean anything",
        },
    }
    if named:
        g = score(rows, named)
        if g is None:
            print("INCONCLUSIVE: named group has fewer than 2 lines in this window")
            return 1
        own = [r for r in rows if r["did"] in named]
        g["own_prefix64_share_pct"] = prefix_baseline(own)
        out["named_group"] = g
    else:
        bykey = collections.Counter(r["did"] for r in rows)
        prof = []
        for d, n in bykey.most_common():
            if n < max(1, min_n // 4):
                continue
            sub = [r for r in rows if r["did"] == d]
            v = collections.Counter(r["verdict"] for r in sub)
            prof.append({"did": d, "n": n,
                         "distinct_reasons": len(set(r["reason"] for r in sub)),
                         "verdicts": dict(v),
                         "constancy_pct": round(100.0 * max(v.values()) / n, 1)})
        out["per_key"] = prof
        out["hint"] = ("re-run with --keys a,b,c to score a candidate group; "
                       "membership is a judgement, the statistics are not")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
