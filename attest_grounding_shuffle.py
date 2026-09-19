# -*- coding: utf-8 -*-
"""Is an ATTEST reason bound to the delivery it judges, or to nothing?

Round 149 (2026-09-19).  Pre-registered in round 148 after a `useful` reason
named 'libsna' on an Ed25519 batch-verification delivery that contains no
such string.

WHY THIS IS NOT ROUND 131 AGAIN
Round 131 built guide/attest_citation_check.py, which asks whether a phrase in
QUOTATION MARKS occurs in the delivery.  That test was run and REFUTED: 506 of
506 checkable citations by the 509-verdict mill were present, board-wide miss
rate 2.9%.  The claim was withdrawn.  Round 131 also recorded the reason the
surviving 2.9% is not evidence: a reason may legitimately quote the JOB SPEC
rather than the delivery, and the tool scored that as a miss.

This test differs in three ways, and the third is the one that matters:

  1. It reads UNQUOTED content words, not quoted spans.  The libsna case was
     invisible to round 131 because the token was 6 characters and unquoted.
  2. The haystack is delivery bodies UNION the job title and spec.  That
     retires round 131's known confound instead of re-discovering it.
  3. It carries a SHUFFLE CONTROL.  A raw overlap rate is meaningless - a
     reason saying "the solution is correct and complete" legitimately shares
     no rare token with anything, and a reason about a Postgres job shares
     tokens with every other Postgres job on the board.  So we measure each
     reason TWICE: once against the job it names, and once against a randomly
     drawn OTHER job.  The gap between the two is the only number reported.

     gap large   the reason is about the thing it judges
     gap ~ 0     the reason would fit a randomly chosen different job equally
                 well - it is not bound to its target

A near-zero gap is not a claim that a key is lazy or wrong.  It is the
statement that the reason's content does not distinguish its target from an
arbitrary other job, which is checkable and carries no taste.

POSITIVE CONTROL / INSTRUMENT FALSIFIER
Our own DID writes reasons that name a specific failure in a specific
delivery, by policy, every round.  If OUR key does not show a large gap, the
instrument is broken and no other row may be read.  Printed first, always.

Rare tokens only: a token is content-bearing if it occurs in at most
MAX_DF_SHARE of delivery bodies.  Generic review vocabulary ("solution",
"correct", "complete") is common by construction and drops out without a
hand-written stoplist.

Usage:
  python guide/attest_grounding_shuffle.py <export.jsonl> [--min-reasons N]
"""
import json
import random
import re
import sys
from collections import Counter, defaultdict

OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
MAX_DF_SHARE = 0.05     # a token in >5% of deliveries is not content-bearing
MIN_TOKEN = 4
MIN_RARE = 3            # reasons with fewer rare tokens carry no testable claim
SHUFFLE_DRAWS = 20      # random other-jobs per reason, averaged
SEED = 149

RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b\s*\|?\s*(.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXJ = re.compile(r"^JOB v1 \| (\S+) \| (.*)$", re.S)
RX_RH = re.compile(r"^rh:[0-9a-f]{6,}\s*\|\s*", re.I)
RX_TOK = re.compile(r"[a-z0-9_]{%d,}" % MIN_TOKEN)


def toks(s):
    return set(RX_TOK.findall(s.lower()))


def split_table(attests, deliv, spec, common, min_reasons):
    """Round 149's actual result.  Merging the job spec into the haystack is
    the natural fix for round 131's documented confound, and it opens a blind
    spot: an attestor that splices the JOB TITLE into every reason scores
    spec-grounding indistinguishable from an attestor that read the work.

    So score the two halves separately:
      spec%      rare reason tokens found in the job title/spec
      delivExcl% rare reason tokens found in the delivery but NOT in the spec
                 - i.e. in what the worker actually wrote
    Only delivExcl% (against its own shuffle control) can tell reading from
    echoing the advertisement.
    """
    DX, S = {}, {}
    for job in set(list(deliv) + list(spec)):
        s = toks(spec.get(job, ""))
        S[job] = s
        DX[job] = toks(" ".join(deliv.get(job, []))) - s

    pool = [j for j in DX if DX[j]]
    if not pool:
        return
    rnd = random.Random(SEED)
    per = defaultdict(lambda: {"n": 0, "s": 0.0, "d": 0.0, "ds": 0.0,
                               "z": 0})
    for a in attests:
        if a["job"] not in DX or not DX[a["job"]]:
            continue
        rare = {w for w in toks(a["reason"]) if w not in common}
        if len(rare) < MIN_RARE:
            continue
        p = per[a["key"]]
        p["n"] += 1
        p["s"] += len(rare & S[a["job"]]) / len(rare)
        hd = len(rare & DX[a["job"]]) / len(rare)
        p["d"] += hd
        if hd == 0.0:
            p["z"] += 1
        acc = 0.0
        for _ in range(SHUFFLE_DRAWS):
            o = rnd.choice(pool)
            while o == a["job"] and len(pool) > 1:
                o = rnd.choice(pool)
            acc += len(rare & DX[o]) / len(rare)
        p["ds"] += acc / SHUFFLE_DRAWS

    print("\n\nSPEC vs DELIVERY-EXCLUSIVE  (jobs usable: %d)" % len(pool))
    print("%5s %8s %11s %9s %8s %8s  key"
          % ("n", "spec%", "delivExcl%", "shufDX%", "dGap", "zeroDX"))
    rows = [(100 * (p["d"] - p["ds"]) / p["n"], k, p)
            for k, p in per.items() if p["n"] >= min_reasons]
    for g, k, p in sorted(rows):
        n = p["n"]
        print("%5d %7.1f%% %10.1f%% %8.1f%% %+8.1f %5d/%-3d ...%s%s"
              % (n, 100 * p["s"] / n, 100 * p["d"] / n, 100 * p["ds"] / n,
                 g, p["z"], n, k[-12:],
                 "  <= POSITIVE CONTROL (ours)" if k == OURS else ""))
    print("  A key high on spec% but flat on dGap read the advertisement,\n"
          "  not the work.  Cross-check it against "
          "guide/detect_self_competition.py (pattern 113): that detector is a\n"
          "  structural join and only fires if the attestor ALSO delivered "
          "the job.")


def main(path, min_reasons=5):
    msgs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("{"):
                try:
                    msgs.append(json.loads(line))
                except ValueError:
                    pass

    deliv = defaultdict(list)
    spec = {}
    attests = []
    for m in msgs:
        t = (m.get("text") or "").strip()
        if (d := RXD.match(t)):
            deliv[d.group(1)].append(d.group(2))
        elif (a := RXA.match(t)):
            attests.append({"job": a.group(1), "verdict": a.group(2),
                            "reason": RX_RH.sub("", a.group(3).strip()),
                            "key": m.get("from", "?")})
        elif (j := RXJ.match(t)):
            spec[j.group(1)] = j.group(2)

    # haystack per job: every delivery on it, plus its spec
    hay = {}
    for job in set(list(deliv) + list(spec)):
        blob = " ".join(deliv.get(job, [])) + " " + spec.get(job, "")
        hay[job] = toks(blob)

    # document frequency over DELIVERY bodies only
    df = Counter()
    bodies = [b for bs in deliv.values() for b in bs]
    for b in bodies:
        df.update(toks(b))
    ndoc = max(1, len(bodies))
    common = {w for w, c in df.items() if c / ndoc > MAX_DF_SHARE}

    pool = [j for j in hay if hay[j]]
    rnd = random.Random(SEED)

    per = defaultdict(lambda: {"n": 0, "true": 0.0, "shuf": 0.0,
                               "zero": 0, "ex": []})
    for a in attests:
        if a["job"] not in hay:
            continue
        rare = {w for w in toks(a["reason"]) if w not in common}
        if len(rare) < MIN_RARE:
            continue
        t_hit = len(rare & hay[a["job"]]) / len(rare)
        s_acc = 0.0
        for _ in range(SHUFFLE_DRAWS):
            other = rnd.choice(pool)
            while other == a["job"] and len(pool) > 1:
                other = rnd.choice(pool)
            s_acc += len(rare & hay[other]) / len(rare)
        s_hit = s_acc / SHUFFLE_DRAWS
        p = per[a["key"]]
        p["n"] += 1
        p["true"] += t_hit
        p["shuf"] += s_hit
        if t_hit == 0.0:
            p["zero"] += 1
            if len(p["ex"]) < 3:
                p["ex"].append((a["job"], a["verdict"],
                                sorted(rare)[:8], a["reason"][:90]))

    print("ATTESTs %d   jobs with haystack %d   delivery bodies %d   "
          "common-token cutoff %.0f%% (%d tokens dropped)"
          % (len(attests), len(hay), len(bodies), 100 * MAX_DF_SHARE,
             len(common)))
    print("rare-token floor %d   shuffle draws %d   seed %d\n"
          % (MIN_RARE, SHUFFLE_DRAWS, SEED))

    def row(k, p, tag=""):
        t = 100 * p["true"] / p["n"]
        s = 100 * p["shuf"] / p["n"]
        print("%5d %7.1f%% %7.1f%% %+7.1f %5d  ...%s %s"
              % (p["n"], t, s, t - s, p["zero"], k[-12:], tag))

    print("%5s %7s %7s %7s %5s  key" % ("n", "true", "shuf", "gap", "zero"))
    if OURS not in per:
        # Round 150: this branch used to print a warning and then print every
        # row anyway, so the docstring's promise ("prints NO rows if our key is
        # missing") was false.  The guard is the whole reason the other numbers
        # are readable; make it stop.
        print("  !! our own key is not in this window - instrument "
              "UNVALIDATED.  No rows printed.  Post this round's ATTESTs "
              "first, then re-export: the ring horizon is well under an hour.")
        return 2
    row(OURS, per[OURS], "<= POSITIVE CONTROL (ours)")
    rows = [(k, p) for k, p in per.items()
            if k != OURS and p["n"] >= min_reasons]
    for k, p in sorted(rows, key=lambda kv: -kv[1]["n"]):
        row(k, p)

    agg = {"n": 0, "true": 0.0, "shuf": 0.0, "zero": 0}
    for k, p in per.items():
        if k == OURS:
            continue
        for f in agg:
            agg[f] += p[f]
    if agg["n"]:
        t = 100 * agg["true"] / agg["n"]
        s = 100 * agg["shuf"] / agg["n"]
        print("\nBOARD (excl. ours) n=%d  true %.1f%%  shuffled %.1f%%  "
              "gap %+.1f  reasons sharing NOTHING with their target %d (%.1f%%)"
              % (agg["n"], t, s, t - s, agg["zero"],
                 100 * agg["zero"] / agg["n"]))

    split_table(attests, deliv, spec, common, min_reasons)

    for k, p in sorted(per.items(), key=lambda kv: -kv[1]["n"])[:4]:
        if k == OURS or not p["ex"]:
            continue
        gap = 100 * (p["true"] - p["shuf"]) / p["n"]
        print("\n-- ...%s  gap %+.1f  %d/%d reasons share no rare token "
              "with target --" % (k[-12:], gap, p["zero"], p["n"]))
        for job, v, rare, reason in p["ex"]:
            print("   %s [%s] rare=%s" % (job, v, rare))
            print("      reason: %r" % (reason,))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    a = sys.argv[1:]
    mr = int(a[a.index("--min-reasons") + 1]) if "--min-reasons" in a else 5
    sys.exit(main(a[0], mr))
