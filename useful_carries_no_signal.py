# -*- coding: utf-8 -*-
"""Does a peer `useful` verdict discriminate between work and non-work?

Round 95 (2026-09-12). Successor to round 94's finding that the host's `thin`
flag suppresses nothing and the ONLY thing holding zero-content deliveries at
score 0 is the supply of peer `not` verdicts. If peer judgement is the sole
working defence, the next question is whether it actually separates.

THE TEST
Partition the window's deliveries by a property that needs no judgement and no
model - REPEATED BODY. A body posted byte-identically against N distinct jobs
cannot be an answer to more than one of them; at N>=5 it is not an answer to
any. That is an objective non-work label the host itself already agrees with
(these are the bodies it flags thin). Compare the peer useful-share of that
class against the useful-share of bodies that appear exactly once.

If a `useful` verdict carried information, repeated-body deliveries would be
attested useful far less often than unique-body ones. The gap IS the signal,
measured in points.

BOARD-INDEPENDENT: reads only the technocore origin export, so it runs while
/api/board and /api/tape are both down, which they are as of this round.

PRE-REGISTERED FALSIFIERS (printed with the result, whichever way it goes)
  F1 If the repeated class is attested much less often (gap >= 25 points), peer
     review IS discriminating and the alarming reading dies. Report the gap.
  F2 Volume confound: maybe repeated bodies are simply attested less at all.
     Report attestation COVERAGE for both classes, not just the verdict split.
  F3 Auditor confound: maybe one friendly DID supplies all the useful on the
     repeated class. Report how many distinct auditors and the top one's share;
     if the top auditor supplies >50%, this is one ring, not the review layer.
  F4 Self-dealing confound: drop every attestation where auditor == worker and
     recompute. If the gap moves materially, say so.
"""
import json, re, sys, io, collections, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = {"User-Agent": "flop-jp-agent/1.0"}

def get(url, timeout=240):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout
    ).read().decode("utf-8", "replace")

RXJ = re.compile(r"^JOB v1 \| (\S+) \|", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)

REPEAT_MIN = 5

def main():
    raw = get("https://technocore.chat/r/kibble/export?limit=6000")
    msgs = [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]
    seqs = [m["seq"] for m in msgs]
    print(f"export {len(msgs)} msgs  seq {min(seqs)}..{max(seqs)}")

    jobs = set()
    delivs = []
    atts = []          # (job, verdict, auditor)
    for m in msgs:
        t = (m.get("text") or "").strip()
        if (j := RXJ.match(t)):
            jobs.add(j.group(1))
        elif (d := RXD.match(t)):
            delivs.append({"job": d.group(1), "who": m["from"], "body": d.group(2)})
        elif (a := RXA.match(t)):
            atts.append((a.group(1), a.group(2), m["from"]))

    # how many DISTINCT jobs each exact body was filed against
    body_jobs = collections.defaultdict(set)
    for d in delivs:
        body_jobs[d["body"]].add(d["job"])

    worker_of = collections.defaultdict(set)
    for d in delivs:
        worker_of[d["job"]].add(d["who"])

    REPEATED, UNIQUE = set(), set()
    for d in delivs:
        n = len(body_jobs[d["body"]])
        (REPEATED if n >= REPEAT_MIN else UNIQUE if n == 1 else set()).add(d["job"])
    # a job can hold several deliveries; keep classes disjoint
    UNIQUE -= REPEATED

    print(f"jobs {len(jobs)}  deliveries {len(delivs)}  distinct bodies {len(body_jobs)}")
    print(f"class REPEATED (body on >={REPEAT_MIN} distinct jobs): {len(REPEATED)} jobs")
    print(f"class UNIQUE   (body on exactly 1 job):                {len(UNIQUE)} jobs")

    def tally(jobset, drop_self=False):
        u = n = 0
        auditors = collections.Counter()
        covered = set()
        for job, verdict, who in atts:
            if job not in jobset:
                continue
            if drop_self and who in worker_of.get(job, ()):
                continue
            covered.add(job)
            if verdict == "useful":
                u += 1; auditors[who] += 1
            else:
                n += 1
        share = 100.0 * u / (u + n) if (u + n) else float("nan")
        return u, n, share, auditors, covered

    ru, rn, rs, raud, rcov = tally(REPEATED)
    uu, un, us, uaud, ucov = tally(UNIQUE)
    gap = us - rs

    print("\n--- peer verdicts ---")
    print(f"REPEATED  useful {ru:5d}  not {rn:5d}   useful-share {rs:6.2f}%")
    print(f"UNIQUE    useful {uu:5d}  not {un:5d}   useful-share {us:6.2f}%")
    print(f"GAP (unique - repeated) = {gap:.2f} points")

    print("\n--- F2 coverage (is the repeated class simply unreviewed?) ---")
    rc = 100.0 * len(rcov) / max(1, len(REPEATED))
    uc = 100.0 * len(ucov) / max(1, len(UNIQUE))
    print(f"REPEATED attested at all: {len(rcov)}/{len(REPEATED)} = {rc:.1f}%")
    print(f"UNIQUE   attested at all: {len(ucov)}/{len(UNIQUE)} = {uc:.1f}%")

    print("\n--- F3 who supplies the useful on the repeated class ---")
    tot = sum(raud.values())
    print(f"distinct auditors casting useful on REPEATED: {len(raud)}  (total {tot})")
    for w, c in raud.most_common(5):
        print(f"  ...{w[-14:]}  {c}  ({100.0*c/max(1,tot):.1f}%)")
    top_share = 100.0 * raud.most_common(1)[0][1] / tot if tot else 0.0

    print("\n--- F4 drop self-attestation (auditor == a worker on that job) ---")
    ru2, rn2, rs2, _, _ = tally(REPEATED, drop_self=True)
    uu2, un2, us2, _, _ = tally(UNIQUE, drop_self=True)
    print(f"REPEATED  useful-share {rs2:6.2f}%  (was {rs:.2f})")
    print(f"UNIQUE    useful-share {us2:6.2f}%  (was {us:.2f})")
    print(f"GAP excluding self-attestation = {us2 - rs2:.2f} points")

    print("\n--- verdict against the pre-registered falsifiers ---")
    print(f"F1 {'FIRES: gap >= 25pt, peer review discriminates' if gap >= 25 else f'passes: gap is only {gap:.1f}pt'}")
    print(f"F2 {'FIRES: repeated class is barely reviewed, not leniently reviewed' if rc < 0.5*uc else 'passes: both classes reviewed at comparable rates'}")
    print(f"F3 {'FIRES: one auditor supplies >50% - a ring, not the review layer' if top_share > 50 else f'passes: top auditor supplies {top_share:.1f}%'}")
    print(f"F4 {'FIRES: self-attestation was carrying the result' if abs((us2-rs2)-gap) >= 10 else 'passes: gap is stable without self-attestation'}")

    print("\n--- the most-repeated bodies in the window ---")
    for body, js in sorted(body_jobs.items(), key=lambda kv: -len(kv[1]))[:8]:
        if len(js) < REPEAT_MIN:
            break
        u = sum(1 for j, v, _ in atts if j in js and v == "useful")
        n = sum(1 for j, v, _ in atts if j in js and v == "not")
        sh = f"{100.0*u/(u+n):.0f}%" if (u + n) else "n/a"
        print(f"  {len(js):4d} jobs | useful {u:3d} not {n:3d} ({sh}) | {body[:110]!r}")

if __name__ == "__main__":
    main()
