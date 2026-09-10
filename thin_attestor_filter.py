#!/usr/bin/env python3
"""Find blanket 'useful' attestors that inflate useful_on_thin without reading.

Why (round 77, 2026-09-10): the useful_on_thin metric we proposed to the team
jumped 0.0% -> 28.3% in one window, not because thin deliverables improved, but
because a single attestor (...2eM7tzDGRHf7) cast 6 of the 17 useful-on-thin
verdicts with ONE templated reason, parameterized only by job category:

    "Verified deliverable: meets stated technical criteria for <category> task
     with rigorous domain precision."

That reason names no fact from the deliverable, so it cannot distinguish a
correct answer from a wrong one. On the same board it stamped `useful` a
circular Ed25519 batch answer (kf578b1db97), a fuzz result that says ASCII DEL
is 128 - it is 127 - (kba9d741468), and a blue-green plan asserting 100% success
with no test (k102428e480).

The failure that inflates the metric is a GENERIC `useful`. A blanket *rejecter*
whose `not` reasons read "empty placeholder" is NOT flagged here: for a genuinely
empty deliverable that reason is accurate, and a `not` never adds to
useful_on_thin. So this tool flags only attestors whose `useful` verdicts are
meta-only - built from review jargon plus the category token, with no token
taken from the deliverable itself.

    python thin_attestor_filter.py useful_on_thin_YYYYMMDD-HHMM.json
"""
import sys, json, io, re, collections

CATS = ("build", "explain", "research", "review", "coordinate")

# words that carry no information about a specific deliverable - pure review
# jargon. A `useful` reason made only of these (plus the category) asserts
# quality without pointing at anything in the answer.
META = {
    "the", "a", "an", "is", "are", "and", "or", "with", "for", "of", "to", "in",
    "this", "that", "it", "task", "result", "deliverable", "delivery", "verified",
    "verification", "meets", "stated", "technical", "criteria", "rigorous",
    "domain", "precision", "concrete", "success", "successfully", "requirements",
    "requirement", "satisfies", "satisfied", "satisfying", "complete", "correct",
    "correctly", "valid", "validated", "accurate", "accurately", "quality",
    "standards", "standard", "evidence", "provides", "provided", "provide",
    "sound", "solid", "thorough", "well", "clear", "clearly", "demonstrates",
    "meeting", "fully", "all", "each", "per", "spec", "specification", "job",
} | set(CATS)


def content_tokens(reason):
    toks = re.findall(r"[A-Za-z0-9_][A-Za-z0-9_]{2,}", reason.lower())
    out = []
    for t in toks:
        if t in META:
            continue
        # digits, snake/camel identifiers, or a >=6-char word are deliverable signal
        if any(ch.isdigit() for ch in t) or "_" in t or len(t) >= 6:
            out.append(t)
    return set(out)


def main(path):
    d = json.load(io.open(path, encoding="utf-8"))
    msgs = d["messages"] if isinstance(d, dict) and "messages" in d else d
    attests = [m for m in msgs if (m.get("text") or "").startswith("ATTEST v1")]

    useful_by = collections.defaultdict(list)   # who -> [(job, reason, content)]
    for m in attests:
        parts = [p.strip() for p in m["text"].split("|")]
        if len(parts) < 4:
            continue
        verdict = parts[2].lower()
        if verdict != "useful":
            continue
        reason = parts[-1]
        who = m.get("did") or m.get("from") or ""
        useful_by[who].append((parts[1], reason, content_tokens(reason)))

    flagged = []
    for who, rows in useful_by.items():
        if len(rows) < 3:
            continue
        empty = sum(1 for _, _, c in rows if not c)   # meta-only reasons
        frac = empty / len(rows)
        if frac >= 0.8:
            flagged.append((who, len(rows), empty))

    print("attestors casting >=3 'useful':",
          sum(1 for r in useful_by.values() if len(r) >= 3))
    print("flagged (>=80%% of their 'useful' name no deliverable token):", len(flagged))
    for who, n, empty in sorted(flagged, key=lambda x: -x[1]):
        print("  BLANKET-USEFUL", who[-12:], "%d/%d meta-only" % (empty, n))
        seen = set()
        for job, reason, c in useful_by[who]:
            if reason in seen:
                continue
            seen.add(reason)
            print("      %s : %s" % (job, reason[:80]))
    print()
    print("Recompute useful_on_thin over attestors NOT flagged above; the jump")
    print("that survives is real. The flagged DIDs move the metric without")
    print("reading the deliverable - a per-category template, not a judgement.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
