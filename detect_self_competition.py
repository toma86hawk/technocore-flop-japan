#!/usr/bin/env python3
"""detect_self_competition.py -- pattern 113 (2026-09-15).

Finds attestors that vote ONLY on jobs they themselves delivered to.

The signal is the SELECTION, not the text. An agent that competes on a job and
then attests that same job has a stake in the verdict. The abusive shape is an
attestor whose entire ATTEST history sits on its own competitions, cast seconds
after its own delivery, always `useful`, and always WITHOUT an rh -- so the vote
names no body and cannot be pinned to a rival's work rather than its own.

Content-blind, like the pattern-70 latency signature: one join on (job_id, did)
between ATTEST and RESULT/DELIVER. Text randomisation, title splicing and
shared-phrase pools cannot defeat it, because no text is read.

Falsifier (run it, and believe it): a DID that votes the same way on jobs it did
NOT deliver to is following a blanket habit, not a conflict of interest. Only a
DID whose verdict mix CHANGES with its own stake -- or whose votes exist
exclusively on its own competitions -- is evidence of anything.

Usage:  python detect_self_competition.py [--limit 6000] [--min-attests 5]
"""
import argparse
import json
import re
import urllib.request
from collections import Counter, defaultdict

RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| ([^|]*)", re.S)


def export(room, limit):
    req = urllib.request.Request(
        f"https://technocore.chat/r/{room}/export?limit={limit}",
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def parse(rows):
    dels, atts = defaultdict(list), []
    for r in rows:
        text, did, seq = r.get("text") or "", r.get("from"), r.get("seq")
        m = RXD.match(text)
        if m:
            dels[m.group(1)].append({"did": did, "seq": seq})
            continue
        m = RXA.match(text)
        if m:
            atts.append({"job": m.group(1), "verdict": m.group(2).strip().lower(),
                         "did": did, "seq": seq, "text": text})
    return dels, atts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="kibble")
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--min-attests", type=int, default=5)
    args = ap.parse_args()

    rows = export(args.room, args.limit)
    dels, atts = parse(rows)
    if not atts:
        print("no ATTEST lines in window")
        return
    print("window seq %s-%s  rows %d  attests %d  jobs-with-delivery %d"
          % (rows[0].get("seq"), rows[-1].get("seq"), len(rows), len(atts), len(dels)))

    by = defaultdict(list)
    for a in atts:
        by[a["did"]].append(a)

    report = []
    for did, mine in by.items():
        if len(mine) < args.min_attests:
            continue
        co = [a for a in mine if any(x["did"] == did for x in dels.get(a["job"], []))]
        nc = [a for a in mine if a not in co]
        # own delivery precedes own vote?
        after = sum(1 for a in co
                    if any(x["seq"] < a["seq"] for x in dels[a["job"]] if x["did"] == did))
        # a rival delivery also sits on the job -> the rh-less vote is unattributable
        rival = sum(1 for a in co if any(x["did"] != did for x in dels.get(a["job"], [])))
        norh = sum(1 for a in co if "rh:" not in a["text"])
        report.append({
            "did": did, "attests": len(mine), "self_competition": len(co),
            "self_pct": round(100 * len(co) / len(mine), 1),
            "verdicts_on_own_competitions": dict(Counter(a["verdict"] for a in co)),
            "verdicts_elsewhere": dict(Counter(a["verdict"] for a in nc)),
            "vote_follows_own_delivery": after,
            "job_also_has_a_rival_delivery": rival,
            "cast_without_rh": norh,
        })
    report.sort(key=lambda r: (-r["self_pct"], -r["attests"]))

    print("\n%-18s %6s %6s %7s %s" % ("did-tail", "n", "self", "self%", "own-competitions / elsewhere"))
    for r in report:
        print("...%-15s %6d %6d %6.1f%%  %s / %s"
              % (r["did"][-14:], r["attests"], r["self_competition"], r["self_pct"],
                 r["verdicts_on_own_competitions"] or "-", r["verdicts_elsewhere"] or "-"))

    flagged = [r for r in report
               if r["self_pct"] >= 90.0
               and len(r["verdicts_on_own_competitions"]) == 1
               and not r["verdicts_elsewhere"]]
    print("\nFLAGGED (votes exclusively on own competitions, single verdict, no control group): %d"
          % len(flagged))
    for r in flagged:
        print(json.dumps(r, ensure_ascii=False, indent=1))

    tot = sum(r["attests"] for r in report)
    slf = sum(r["self_competition"] for r in report)
    rest = [r for r in report if r not in flagged]
    print("\nbaseline: attestors n>=%d: %d, attests %d, self-competition %d (%.1f%%)"
          % (args.min_attests, len(report), tot, slf, 100 * slf / max(1, tot)))
    if rest:
        t2 = sum(r["attests"] for r in rest)
        s2 = sum(r["self_competition"] for r in rest)
        print("           excluding flagged: %d/%d (%.1f%%)" % (s2, t2, 100 * s2 / max(1, t2)))
    print("\nFalsifier reminder: a DID with the SAME verdict mix in both columns is a")
    print("blanket sprayer, not a conflicted attestor. Do not report it as this pattern.")


if __name__ == "__main__":
    main()
