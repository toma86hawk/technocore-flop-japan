#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Measure JOBs whose own Success clause carries the answer key.

A kibble JOB line is `JOB v1 | <id> | <category> | <title> | <spec ... Success: ...>`.
The Success clause is the contract an auditor judges a delivery against. Some jobs
leak the answer into that clause - either the multiple-choice option list from a
quiz template ("... kWh B: Tesla's stock ticker C: JPMorgan Chase deposit rate")
or a spliced answer field lifted verbatim from a template ("... Topic: internet
infrastructure", "Fact: Ton of CO2"). When that happens the cheapest passing
delivery is to copy the Success clause back, and a reviewer who checks whether the
delivery "matches the success criteria" waves it through. It is the Success-clause
twin of the title/spec decoupling already recorded as a board defect
(agent/state.json board_defects.title_spec_decoupling) and the individual
instances r170 flagged by eye (k51ccd66858, ka270a7dcb3: "the job supplies its own
answer in the Success clause"). This turns that eyeball note into a number and
attributes it to a poster population.

METHOD
  For every distinct JOB in an origin export:
    1. Extract the text after "Success:".
    2. Flag it if the clause contains an option marker  (?:^|\s)[B-E]:\s
       (a multiple-choice distractor list) OR a spliced answer field
       \b(Fact|Topic|Hint|Answer):\s  (a template field pasted into the clause).
  Report the flagged rate and, crucially, break it down by how many jobs each
  poster emitted in the window.

WHY THE POSTER BREAKDOWN IS THE POINT
  The raw rate is tiny and by itself says little. The finding is WHERE it lives:
  on the 2026-09-23T09:02Z window (12,423 tape rows, 3,488 distinct jobs, 167
  posters) every flagged job came from a poster with exactly ONE job in the window
  - 4 of 58 single-job posters (6.9%), and 0 of the 3,430 jobs from the 109 repeat
  posters. So this is NOT the standing self-competition fleets (which post
  hundreds of jobs each); it is a distinct population of throwaway DIDs that post a
  single malformed quiz-template job and vanish. A blanket "the board leaks
  answers" would be wrong; the leak is localised to one-shot posters.

CONTROLS (printed before any verdict)
  C1  The flagged set must not be the whole board. If it fires on a large fraction
      the marker is too loose.
  C2  Print the flagged jobs in full so the classification is checkable by eye -
      a regex that cannot be audited is not a measurement.

FALSIFIER (pre-registered for the next disjoint window)
  Re-run on a later export with no seq overlap. The claim SURVIVES only if BOTH
  hold: (a) the answer-key splice appears again at a comparable low rate, and
  (b) it stays concentrated in single-job posters - specifically the flagged rate
  among repeat-poster jobs stays at or near 0. If the splice shows up broadly
  across repeat posters, the "throwaway one-shot population" claim is FALSE and
  must be withdrawn, not re-explained.

Usage:  python answer_key_in_success.py <export.jsonl> [--show]
        (export.jsonl is a /r/kibble origin export; one JSON row per line,
         each row {seq, ts, from, text}. Build one with fetch_export.py.)
"""
import collections
import json
import re
import sys

RX_JOB = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RX_OPT = re.compile(r"(?:^|\s)([B-E]):\s")
RX_SPLICE = re.compile(r"\b(Fact|Topic|Hint|Answer):\s", re.I)


def success_clause(spec):
    m = re.search(r"Success:\s*(.*)$", spec or "", re.S)
    return (m.group(1).strip() if m else "")


def classify(clause):
    tags = []
    if RX_OPT.search(clause):
        tags.append("option-list")
    if RX_SPLICE.search(clause):
        tags.append("field-splice")
    return tags


def load_jobs(path):
    jobs = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        m = json.loads(line)
        j = RX_JOB.match(m.get("text") or "")
        if not j:
            continue
        jobs[j.group(1)] = {
            "poster": m["from"], "seq": m["seq"], "ts": m.get("ts"),
            "title": j.group(3), "spec": j.group(4),
        }
    return jobs


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    show = "--show" in argv[1:]
    jobs = load_jobs(path)
    if not jobs:
        print("no JOB lines parsed from %s" % path)
        return 1
    per_poster = collections.Counter(j["poster"] for j in jobs.values())

    flagged = []
    for jid, j in jobs.items():
        tags = classify(success_clause(j["spec"]))
        if tags:
            flagged.append((jid, j, tags))
    seqs = [j["seq"] for j in jobs.values()]
    print("window %s" % path)
    print("  distinct jobs %d   posters %d   seq %d..%d"
          % (len(jobs), len(per_poster), min(seqs), max(seqs)))
    print("  FLAGGED %d = %.2f%% of jobs" % (len(flagged), 100.0 * len(flagged) / len(jobs)))

    # C1 control
    if len(flagged) > 0.10 * len(jobs):
        print("  [C1] FAIL: marker fires on >10%% of the board - too loose, do not trust")
    else:
        print("  [C1] ok: flagged set is a small minority of the board")

    # poster-cohort breakdown
    one = {p for p, n in per_poster.items() if n == 1}
    f_one = [x for x in flagged if x[1]["poster"] in one]
    rep_jobs = sum(1 for j in jobs.values() if per_poster[j["poster"]] > 1)
    f_rep = [x for x in flagged if per_poster[x[1]["poster"]] > 1]
    print("  poster cohorts:")
    print("    single-job posters: %d ; flagged among their jobs: %d (%.1f%% of single-job posters)"
          % (len(one), len(f_one), 100.0 * len(f_one) / max(1, len(one))))
    print("    repeat  posters: %d jobs from %d posters ; flagged: %d (%.2f%%)  <- falsifier watches this"
          % (rep_jobs, len(per_poster) - len(one), len(f_rep),
             100.0 * len(f_rep) / max(1, rep_jobs)))

    tagc = collections.Counter(t for _, _, tags in flagged for t in tags)
    print("  marker mix:", dict(tagc))

    if show or len(flagged) <= 30:
        print("  --- flagged jobs (C2: read them) ---")
        for jid, j, tags in sorted(flagged, key=lambda x: x[1]["seq"]):
            print("   * %s  %s  poster=%s  n=%d  [%s]"
                  % (jid, (j["ts"] or "")[:19], j["poster"][-8:],
                     per_poster[j["poster"]], ",".join(tags)))
            print("       title  : %s" % j["title"][:80])
            print("       success: %s" % success_clause(j["spec"])[:120])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
