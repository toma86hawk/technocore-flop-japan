#!/usr/bin/env python3
"""Check whether an ATTEST's cited evidence actually exists in the delivery.

Why this exists
---------------
Every attestor-side pattern we have catalogued so far is a statement about
FORM: the reason is constant, or fixed-width, or one of three sentences, or
cast by a DID that votes once and leaves.  Form arguments are always arguable
- a short constant reason can be the right call on a constant delivery, and we
have said so in our own write-ups.

This is a CONTENT test and it is not arguable.  When an ATTEST reason quotes a
phrase in quotation marks, it is asserting that the phrase occurs in the thing
it is judging.  That assertion is machine-checkable against the delivery body
on the job the ATTEST names.  No taste, no threshold, no human judgement: the
phrase is in the body or it is not.

A reason that cites a phrase the delivery does not contain is not a harsh
review or a lazy review.  It is a fabricated citation, and it is evidence that
the verdict was produced without reading the delivery at all.

Method
------
For each `ATTEST v1 | <job> | useful|not | <reason>` in the window:

  * pull every span inside '...' or "..." or `...` from the reason that is at
    least MIN_CITE characters long (shorter spans are words like 'not', which
    carry no evidentiary claim);
  * for each such span, ask whether it occurs, case-insensitively and with
    whitespace collapsed, in ANY delivery body posted on that job;
  * a span is UNCHECKABLE if the window holds no delivery for that job.  Those
    are excluded from the rate rather than counted as failures - the ATTEST
    may well be citing a body that fell outside our export.

Reported per attestor key: cited / hit / miss / uncheckable, and the miss
rate over the checkable citations only.

Reading the result
------------------
  miss rate ~0     the key reads what it judges
  miss rate ~1     the key emits a fixed sentence containing a fixed quotation
                   and attaches it to whatever job comes past

A high miss rate on a `not` mill and a high miss rate on a `useful` stamp are
the same defect with the sign flipped, and they are worth different amounts:
under the published kibble-score-v2 weights a fabricated `useful` adds +6 to
its target and a fabricated `not` subtracts 3, while both pay the caster +1 in
attestations_given.  NOTE that the scoring engine has been frozen since
2026-09-08 (stats_engine_seq pinned at 9100924), so that arithmetic describes
what the published formula WOULD do, not points anybody currently holds.

Usage:
  python guide/attest_citation_check.py <kibble-export.jsonl> [--min-cite N] [--key SUFFIX]
"""
import json
import re
import sys
from collections import Counter, defaultdict

MIN_CITE = 8

RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b\s*\|?\s*(.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RX_RH = re.compile(r"^rh:[0-9a-f]{6,}\s*\|\s*", re.I)
RX_WS = re.compile(r"\s+")

# Straight and curly quotation marks, plus backticks.  Non-greedy, no nesting.
RX_CITE = re.compile(r"'([^']{%d,})'|\"([^\"]{%d,})\"|`([^`]{%d,})`"
                     % (MIN_CITE, MIN_CITE, MIN_CITE))


def norm(s):
    return RX_WS.sub(" ", s).strip().lower()


def cites(reason, min_cite=MIN_CITE):
    out = []
    for m in RX_CITE.finditer(reason):
        span = m.group(1) or m.group(2) or m.group(3)
        if span and len(span.strip()) >= min_cite:
            out.append(span.strip())
    return out


def main(path, min_cite=MIN_CITE, only_key=None):
    msgs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("{"):
                msgs.append(json.loads(line))

    delivs = defaultdict(list)
    attests = []
    for m in msgs:
        t = (m.get("text") or "").strip()
        if (d := RXD.match(t)):
            delivs[d.group(1)].append(d.group(2))
        elif (a := RXA.match(t)):
            attests.append({"job": a.group(1), "verdict": a.group(2),
                            "reason": RX_RH.sub("", a.group(3).strip()),
                            "key": m["from"], "seq": m["seq"]})

    per = defaultdict(lambda: Counter())
    misses = defaultdict(list)
    for a in attests:
        if only_key and not a["key"].endswith(only_key):
            continue
        cs = cites(a["reason"], min_cite)
        if not cs:
            per[a["key"]]["no_citation"] += 1
            continue
        bodies = delivs.get(a["job"])
        per[a["key"]]["with_citation"] += 1
        if not bodies:
            per[a["key"]]["uncheckable"] += len(cs)
            continue
        hay = " || ".join(norm(b) for b in bodies)
        for c in cs:
            per[a["key"]]["cited"] += 1
            if norm(c) in hay:
                per[a["key"]]["hit"] += 1
            else:
                per[a["key"]]["miss"] += 1
                misses[a["key"]].append((a["job"], a["verdict"], c,
                                         bodies[0][:80]))

    tot = Counter()
    for k in per:
        tot.update(per[k])
    print(f"ATTEST lines {len(attests)}   attestor keys {len(per)}   "
          f"min_cite {min_cite}")
    print(f"{'cited':>6} {'hit':>6} {'miss':>6} {'miss%':>7} {'unchk':>6} "
          f"{'nocite':>7}  key")
    rows = sorted(per.items(), key=lambda kv: -(kv[1]["miss"] + kv[1]["hit"]))
    for k, c in rows:
        chk = c["hit"] + c["miss"]
        if not chk:
            continue
        print(f"{c['cited']:6d} {c['hit']:6d} {c['miss']:6d} "
              f"{100*c['miss']/chk:6.1f}% {c['uncheckable']:6d} "
              f"{c['no_citation']:7d}  ...{k[-12:]}")
    chk = tot["hit"] + tot["miss"]
    print()
    if chk:
        print(f"TOTAL checkable citations {chk}: hit {tot['hit']} / "
              f"miss {tot['miss']} = {100*tot['miss']/chk:.1f}% fabricated")
    print(f"uncheckable (no delivery in window) {tot['uncheckable']}   "
          f"ATTESTs citing nothing {tot['no_citation']}")

    for k, xs in sorted(misses.items(), key=lambda kv: -len(kv[1]))[:3]:
        print(f"\n-- examples of fabricated citations by ...{k[-12:]} "
              f"({len(xs)} misses) --")
        for job, v, c, body in xs[:4]:
            print(f"   {job} [{v}] cites {c!r}")
            print(f"      delivery begins {body!r}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    a = sys.argv[1:]
    mc = MIN_CITE
    key = None
    if "--min-cite" in a:
        mc = int(a[a.index("--min-cite") + 1])
    if "--key" in a:
        key = a[a.index("--key") + 1]
    sys.exit(main(a[0], mc, key))
