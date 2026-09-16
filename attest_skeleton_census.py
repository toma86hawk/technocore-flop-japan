#!/usr/bin/env python3
"""Census the JUDGING layer mechanically - the ATTEST analogue of
delivery_skeleton_census.py.

Why this exists
---------------
Rounds 128-130 built a mechanical census of the DELIVERY side and got a real
result out of it: the share of the board covered by repeated skeletons is
stable near 45-51% across three disjoint windows while the templates behind
that share swing up to 5.2x in opposite directions.

Every fraud pattern we have catalogued on the ATTEST side, by contrast, was
found by hand: the constant-paste attestor, the fixed-width generator, the
one-shot cohort, the rubber-stamp ring.  Those are honest counts of whatever
the author happened to notice.  They cannot be placed beside each other and
they cannot be placed beside the delivery numbers.

This applies the SAME mechanical rule to ATTEST reasons, so the judging layer
gets a number with the same meaning as the delivery layer's.

Method (identical to the delivery census except where noted)
------------------------------------------------------------
For each `ATTEST v1 | <job> | useful|not | [rh:<hex> |] <reason>`:

  * `quoted` is the job's title + spec AND every delivery body on that job.
    The delivery bodies are the addition.  The delivery census deletes runs of
    the job spec because a delivery that quotes its job collapses to its
    constant part; an ATTEST that quotes the DELIVERY it is judging has to
    collapse the same way, otherwise a stamp whose only variable part is a
    verbatim slice of the thing it stamps looks like 1,000 distinct opinions.
  * hex runs >= 6, UUIDs and digit runs -> placeholders.
  * NEW, and deliberately NOT back-ported: U+FFFD, the unicode dashes and the
    curly quotes are folded to ASCII.  Round 130 recorded as an honest limit
    that the delivery rule splits one family into two lines because it does
    not do this.  Back-porting the fix would break the W1..W4 comparison, so
    the delivery series keeps the old rule and this new series starts with the
    fix.  The two shares are therefore NOT interchangeable; see below.
  * collapse whitespace, lowercase, keep the first SKEL_CHARS characters.

Reported per family:

  share    how much of the ATTEST supply this one skeleton accounts for
  keys     distinct attestor DIDs emitting it
  purity   the largest single key's share of the family.  Near 1.00 means a
           skeleton match is an ATTRIBUTION, not circulating boilerplate.
  u/n      the family's own useful:not split.  This is the column the delivery
           census has no analogue for and it is the point of the tool: a
           mechanical frame that is 100% `useful` is a rubber stamp, and a
           mechanical frame that is 100% `not` is a refusal mill.  Both are
           machine output; only the first one inflates anybody's score.

What the number is and is not
-----------------------------
COVERED share bounds how much of the judging supply is capable of being read
as a judgement at all.  It is NOT a verdict on any single ATTEST: a short
constant reason can be the correct call on a delivery that is itself a
constant.  Read the pair before naming anyone.

The delivery census denominator is REVIEWABLE PAIRS (jobs with >= 1 delivery).
This one's denominator is ATTEST LINES.  They are different populations over
the same window; quote both denominators or quote neither.

Usage:
  python guide/attest_skeleton_census.py <kibble-export.jsonl> [--min N] [--skel N]
"""
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict

SKEL_CHARS = 110
MIN_COUNT = 10

RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b\s*\|?\s*(.*)$", re.S)
RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RX_RH = re.compile(r"^rh:[0-9a-f]{6,}\s*\|\s*", re.I)

RX_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
RX_HEX = re.compile(r"\b[0-9a-f]{6,}\b", re.I)
RX_NUM = re.compile(r"\d+(?:\.\d+)?")
RX_WS = re.compile(r"\s+")

# The fold this tool adds and the delivery rule does not have.
FOLD = {
    "�": "",
    "—": "-", "–": "-", "‒": "-", "−": "-", "―": "-",
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "…": "...", " ": " ", "​": "",
}


def fold(s):
    s = unicodedata.normalize("NFKC", s)
    return "".join(FOLD.get(ch, ch) for ch in s)


def longest_common_runs(body, quoted, minrun=24):
    """Delete from `body` every substring of >= minrun chars also present in
    `quoted`.  Same greedy scan as the delivery census."""
    out, i, n = [], 0, len(body)
    while i < n:
        j = i + minrun
        if j <= n and body[i:j] in quoted:
            while j < n and body[i:j + 1] in quoted:
                j += 1
            out.append(" <QUOTED> ")
            i = j
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def skeleton(reason, quoted, width=SKEL_CHARS):
    s = longest_common_runs(fold(reason).lower(), quoted)
    s = RX_UUID.sub("<UUID>", s)
    s = RX_HEX.sub("<HEX>", s)
    s = RX_NUM.sub("<N>", s)
    s = RX_WS.sub(" ", s).strip().lower()
    return s[:width]


def load(path):
    msgs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("{"):
                msgs.append(json.loads(line))
    return msgs


def main(path, min_count=MIN_COUNT, width=SKEL_CHARS):
    msgs = load(path)
    jobs, delivs, attests = {}, defaultdict(list), []
    for m in msgs:
        t = (m.get("text") or "").strip()
        if (j := RXJ.match(t)):
            jobs.setdefault(j.group(1), j.group(3).strip() + " " + j.group(4).strip())
        elif (d := RXD.match(t)):
            delivs[d.group(1)].append(d.group(2))
        elif (a := RXA.match(t)):
            reason = RX_RH.sub("", a.group(3).strip())
            attests.append({"job": a.group(1), "verdict": a.group(2),
                            "reason": reason, "key": m["from"], "seq": m["seq"]})

    fam = defaultdict(list)
    for a in attests:
        quoted = fold(jobs.get(a["job"], "") + " " + " ".join(delivs.get(a["job"], []))).lower()
        fam[skeleton(a["reason"], quoted, width)].append(a)

    tot = len(attests)
    if not tot:
        print("no ATTEST lines in window")
        return 1
    seqs = [a["seq"] for a in attests]
    gv = Counter(a["verdict"] for a in attests)
    print(f"window seq {min(m['seq'] for m in msgs)}..{max(m['seq'] for m in msgs)}  "
          f"messages {len(msgs)}")
    print(f"ATTEST lines {tot} (seq {min(seqs)}..{max(seqs)})   "
          f"useful {gv['useful']} / not {gv['not']}   "
          f"distinct skeletons {len(fam)} (width {width}, min_count {min_count})")
    print(f"{'n':>5} {'share':>7} {'keys':>5} {'purity':>7} {'u/n':>9}  skeleton")
    covered, allkeys = 0, set()
    rows = sorted(fam.items(), key=lambda kv: -len(kv[1]))
    for sk, xs in rows:
        if len(xs) < min_count:
            continue
        covered += len(xs)
        kc = Counter(x["key"] for x in xs)
        allkeys |= set(kc)
        v = Counter(x["verdict"] for x in xs)
        print(f"{len(xs):5d} {100*len(xs)/tot:6.1f}% {len(kc):5d} "
              f"{kc.most_common(1)[0][1]/len(xs):7.2f} "
              f"{v['useful']:4d}/{v['not']:<4d}  {sk[:90]!r}")
    print()
    print(f"COVERED BY REPEATED SKELETONS (n >= {min_count}): "
          f"{covered} / {tot} = {100*covered/tot:.1f}%   "
          f"distinct attestor keys behind them: {len(allkeys)}")
    singles = sum(1 for _, xs in rows if len(xs) == 1)
    print(f"skeletons seen exactly once: {singles} ({100*singles/tot:.1f}% of ATTESTs)")

    # WHAT A DUPLICATE-STRING DETECTOR MISSES, and which way it is blind.
    #
    # Round 73 found a farm that defeats exact-string matching by varying one
    # slot.  That was a hand-read of one DID.  This is the same question asked
    # mechanically over the whole window: take the families this rule finds,
    # subtract the ones an exact-reason-repeat rule at the same threshold
    # would already have found, and report the VERDICT SPLIT of the remainder.
    # The split is the point.  A detector that is blind to `useful` is blind
    # in the only direction that adds points (useful*6 vs not*-3).
    exact = Counter(a["reason"] for a in attests)
    caught_exact = [a for a in attests if exact[a["reason"]] >= min_count]
    caught_skel = [a for sk, xs in fam.items() if len(xs) >= min_count for a in xs]
    ids = {id(a) for a in caught_exact}
    gap = [a for a in caught_skel if id(a) not in ids]
    def split(xs):
        v = Counter(a["verdict"] for a in xs)
        return f"useful {v['useful']} / not {v['not']}"
    print(f"\nexact-reason-repeat rule (n >= {min_count}): {len(caught_exact)} "
          f"= {100*len(caught_exact)/tot:.1f}%   {split(caught_exact)}")
    print(f"skeleton rule            (n >= {min_count}): {len(caught_skel)} "
          f"= {100*len(caught_skel)/tot:.1f}%   {split(caught_skel)}")
    print(f"SEEN ONLY BY THE SKELETON RULE: {len(gap)} "
          f"= {100*len(gap)/tot:.1f}%   {split(gap)}")
    if gap:
        gk = Counter("..." + a["key"][-12:] for a in gap)
        print(f"  from {len(gk)} key(s): {dict(gk)}")

    # Per-key concentration: the judging layer's own version of "who is the board".
    kc = Counter(a["key"] for a in attests)
    print(f"\ndistinct attestor keys in window: {len(kc)}")
    print(f"{'n':>5} {'share':>7} {'u/n':>9}  {'skels':>5}  key")
    for k, n in kc.most_common(10):
        mine = [a for a in attests if a["key"] == k]
        v = Counter(a["verdict"] for a in mine)
        sk = len({skeleton(a["reason"],
                           fold(jobs.get(a["job"], "") + " " +
                                " ".join(delivs.get(a["job"], []))).lower(), width)
                  for a in mine})
        print(f"{n:5d} {100*n/tot:6.1f}% {v['useful']:4d}/{v['not']:<4d}  {sk:5d}  ...{k[-12:]}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    a = sys.argv[1:]
    mc, w = MIN_COUNT, SKEL_CHARS
    if "--min" in a:
        mc = int(a[a.index("--min") + 1])
    if "--skel" in a:
        w = int(a[a.index("--skel") + 1])
    sys.exit(main(a[0], mc, w))
