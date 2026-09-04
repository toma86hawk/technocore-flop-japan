# -*- coding: utf-8 -*-
"""r32: exact measurement of the kibble board's title/body slot desync.

Templated jobs draw the SUBJECT for the title and the SUBJECT for the body
(the field carrying the Success clause) from independent random draws. This
matches each job to its template family with a regex pair and compares the two
subject slots literally -- no fuzzy topic overlap, so a mismatch is a mismatch.

Also counts DEGENERATE comparisons: templates that drew the SAME token into both
sides of an A-vs-B slot, producing jobs like "Compare Zig and Zig".

Usage: python r32_slot_mismatch.py [board.json]
"""
import json, re, sys
from collections import Counter

# (family, title regex, body regex).  Group 1 (and 2) = the subject slot(s).
FAMILIES = [
    ("gets-wrong",   r"^One thing (.+?) gets wrong",
                     r"^Name one design choice in (.+?) that is widely considered"),
    ("compare-task", r"^Compare (.+?) vs (.+?) for ",
                     r"^Compare (.+?) and (.+?) for the task of "),
    ("one-line",     r"^(.+?) vs (.+?): one-line difference",
                     r"^State the single most important difference between (.+?) and (.+?) in one line"),
    ("key-diff",     r"^(.+?) vs (.+?) for .+?: key difference",
                     r"^Compare (.+?) and (.+?) for "),
    ("one-sentence", r"^What is (.+?) in one sentence",
                     r"^Define (.+?) in a single sentence"),
    ("replaced",     r"^What replaced (.+?)\?",
                     r"^Name what (?:system|technology) or pattern has effectively replaced (.+?) in "),
    ("list3",        r"^List 3 real-world (?:applications|uses) of (.+?)$",
                     r"^Name 3 deployed systems or real-world use cases of (.+?)\."),
    ("maintained",   r"^Is (.+?) still maintained",
                     r"^Check (.+?)'s GitHub"),
    ("failure-modes",r"^Failure modes of (.+?) under (.+?):",
                     r"^Analyze failure modes that (.+?) exhibits under (.+?)\."),
    ("scaling",      r"^Scaling (.+?) from (.+?): what breaks first",
                     r"^Analyze how (.+?) behaves when scaling from (.+?)\."),
    ("latency",      r"^Latency bounds for (.+?) under (.+?)$",
                     r"latency for (.+?) under (.+?)\."),
    ("problem-solve",r"^What problem does (.+?) solve\?",
                     r"^Name the specific problem (.+?) was designed to solve"),
    ("how-works",    r"^Explain how (.+?) works in 200 words",
                     r"^Explain how (.+?) works in under 200 words"),
    ("security",     r"^Audit the security model of (.+?):",
                     r"^Audit the security model of (.+?)\."),
    ("sybil",        r"^Sybil resistance in (.+?): why (.+?) fails",
                     r"^Analyze Sybil resistance in the context of (.+?)\. Explain why (.+?) is insufficient"),
    ("rejects",      r"^Why (.+?) rejects mutable shared state",
                     r"^Explain why (.+?) explicitly rejects the common pattern of (.+?)\."),
    ("coordinates",  r"^Coordinates of (.+?) in (.+?)$",
                     r"^Provide the latitude and longitude of (.+?) in (.+?) to four decimal"),
    ("readme",       r"^Evaluate (.+?) README vs reality",
                     r"^Read (.+?)'s README"),
    ("uses-instead", r"^Why\s+(.+?) uses (.+?) instead of (.+?)$",
                     r"^Explain why (.+?) adopted (.+?) rather than the alternative (.+?)\."),
    ("explain-diff", r"^(.+?) vs (.+?): core difference",
                     r"^Explain the core difference between (.+?) and (.+?) in one sentence"),
    ("review-sol",   r"^Evaluate (.+?) for (.+?): correctness",
                     r"^Review (.+?) as a solution for (.+?)\."),
]

def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().rstrip(".:").lower())

def main(path):
    d = json.load(open(path, encoding="utf-8"))
    jobs = d["jobs"] if isinstance(d, dict) else d
    matched = mism = 0
    per_family = Counter(); per_family_mm = Counter()
    degenerate = []; examples = []; mm_posters = Counter(); matched_posters = Counter()

    for j in jobs:
        title, body = j.get("title") or "", j.get("body") or ""
        for fam, tre, bre in FAMILIES:
            mt = re.search(tre, title, re.I)
            mb = re.search(bre, body, re.I)
            if not (mt and mb):
                continue
            t_slots = [norm(g) for g in mt.groups()]
            b_slots = [norm(g) for g in mb.groups()]
            matched += 1; per_family[fam] += 1
            matched_posters[j.get("poster_did", "")] += 1
            # degenerate: one side drew the same token twice
            for where, slots in (("title", t_slots), ("body", b_slots)):
                if len(slots) >= 2 and slots[0] == slots[1]:
                    degenerate.append((j["job_id"], fam, where, slots[0]))
            if t_slots[0] != b_slots[0]:
                mism += 1; per_family_mm[fam] += 1
                mm_posters[j.get("poster_did", "")] += 1
                if len(examples) < 12:
                    examples.append((j["job_id"], fam, t_slots[0], b_slots[0]))
            break

    print("board jobs: %d   matched to a template family: %d" % (len(jobs), matched))
    print("title subject != body subject: %d / %d = %.1f%%" % (mism, matched, 100.0*mism/max(matched,1)))
    print()
    print("by family (mismatched / matched):")
    for fam, n in per_family.most_common():
        print("   %-14s %2d / %2d" % (fam, per_family_mm[fam], n))
    print()
    print("degenerate draws (same token in both sides of one A-vs-B slot): %d" % len(degenerate))
    for r in degenerate:
        print("   %s  %-13s %s slot: %r vs %r" % (r[0], r[1], r[2], r[3], r[3]))
    print()
    print("posters of mismatched jobs (mismatched / matched posted):")
    for did, c in mm_posters.most_common(5):
        print("   ...%s  %2d / %2d" % (did[-20:], c, matched_posters[did]))
    print()
    print("examples (job, family, title subject, body subject):")
    for e in examples:
        print("   %s %-13s title=%-22r body=%r" % e)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "board_r32.json")
