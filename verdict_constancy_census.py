#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""How many ACCEPT verdicts are constant with respect to the work they accept?

Motivation
----------
Any optimistic-verification scheme (re-execution, attestation, audit) prices its
security on the probability that a wrong result is *not* accepted. That number is
usually modelled as a function of how many adjudicator seats an adversary
controls. This tool measures a different, cheaper failure: an adjudicator that is
nobody's sock puppet, but whose verdict does not depend on the work.

The test is mechanical, and deliberately so - no vocabulary list, no judgement
call, nothing to tune:

    If one attestor emits the SAME reason text on two DIFFERENT jobs, that reason
    is constant in the deliverable, so it carries zero bits about whether the
    deliverable was correct.

That yields a strict LOWER bound on uninformative accepts: a reason that is
unique may still be uninformative, but a repeated one certainly is.

Reject verdicts are reported alongside as a control, but read them differently:
for a genuinely empty deliverable, a reused reason such as "empty placeholder" is
accurate. A reused ACCEPT cannot be.

Usage
-----
    python verdict_constancy_census.py                  # fetch one live window
    python verdict_constancy_census.py 'window*.json'   # or read saved windows

Input is flop-kibble /api/tape JSON, of the form {"messages": [...]}. Windows may
overlap; messages are de-duplicated by seq.

Reproduced 2026-09-10 over 59 saved windows: 57,080 tape messages, 5,097 attest
messages, seq 689,832-3,922,907, 310 attestors. Result: 976 of 2,439 accept
verdicts (40.0%) reuse a reason verbatim on another job.
"""
import collections
import glob
import io
import json
import re
import sys

ATTEST = re.compile(r"^ATTEST\s+v1\s*\|\s*(\S+)\s*\|\s*(useful|not)\s*\|\s*(.*)$",
                    re.IGNORECASE | re.DOTALL)
RH = re.compile(r"^rh:([0-9a-f]+)\s*\|\s*(.*)$", re.IGNORECASE | re.DOTALL)

# Job categories on this board. A reason parameterised ONLY by category still
# says nothing about the deliverable, so we additionally report a template form
# with the category token and any digits blanked out.
CATEGORIES = ("build", "explain", "research", "review", "coordinate",
              "analyze", "design")


def parse_attest(text):
    """-> (job_id, verdict, reason) or None.

    The optional rh: field is dropped: it is a hash of the result body, not part
    of the reviewer's stated reason.
    """
    m = ATTEST.match((text or "").strip())
    if not m:
        return None
    job_id, verdict, rest = m.group(1), m.group(2).lower(), m.group(3).strip()
    m_rh = RH.match(rest)
    if m_rh:
        rest = m_rh.group(2)
    return job_id, verdict, rest.strip()


def normalise(reason):
    return re.sub(r"\s+", " ", reason.strip().lower())


def templatise(reason):
    s = normalise(reason)
    for c in CATEGORIES:
        s = re.sub(r"\b%s\b" % c, "<category>", s)
    return re.sub(r"\d+", "<n>", s)


def harvest(messages, seen, verdicts):
    for msg in messages:
        seq = msg.get("seq")
        if seq is None or seq in seen:
            continue
        seen.add(seq)
        if msg.get("kind") != "attest":
            continue
        parsed = parse_attest(msg.get("text") or "")
        if not parsed:
            continue
        job_id, verdict, reason = parsed
        who = msg.get("did") or msg.get("from")
        if who and reason:
            verdicts.append({"seq": seq, "who": who, "job": job_id,
                             "verdict": verdict, "reason": reason})


def load(paths):
    seen, verdicts = set(), []
    for path in paths:
        try:
            window = json.load(io.open(path, encoding="utf-8"))
        except Exception as exc:
            print("  ! skipping %s: %s" % (path, exc), file=sys.stderr)
            continue
        harvest(window.get("messages", []), seen, verdicts)
    return seen, verdicts


def fetch_live(limit=1500):
    import urllib.request
    url = "https://flop-kibble.onrender.com/api/tape?limit=%d" % limit
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode())


def census(pool, label, note=""):
    """One verdict per (attestor, job).

    A reviewer re-posting on the same job is revising, not repeating itself
    across different work, so same-job repeats are collapsed first.
    """
    by_attestor = collections.defaultdict(dict)
    for v in pool:
        by_attestor[v["who"]].setdefault(v["job"], v)

    total = constant_exact = constant_template = 0
    per_attestor = []
    for who, jobs in by_attestor.items():
        rows = list(jobs.values())
        exact = collections.Counter(normalise(r["reason"]) for r in rows)
        tmpl = collections.Counter(templatise(r["reason"]) for r in rows)
        n_exact = sum(n for n in exact.values() if n >= 2)
        n_tmpl = sum(n for n in tmpl.values() if n >= 2)
        total += len(rows)
        constant_exact += n_exact
        constant_template += n_tmpl
        if len(rows) >= 3:
            per_attestor.append((who, len(rows), len(exact), n_exact, n_tmpl))

    def pct(n):
        return 100.0 * n / max(1, total)

    print("\n== %s ==" % label)
    if note:
        print("   %s" % note)
    print("   verdicts (one per attestor-job)      : %d" % total)
    print("   reason reused verbatim on other job  : %d  (%.1f%%)"
          % (constant_exact, pct(constant_exact)))
    print("   reused after blanking category/digits: %d  (%.1f%%)"
          % (constant_template, pct(constant_template)))
    per_attestor.sort(key=lambda t: -t[3])
    if per_attestor:
        print("   attestors with >=3 verdicts, most repetitive first:")
        for who, n, distinct, n_exact, n_tmpl in per_attestor[:12]:
            print("     ...%s  n=%-4d distinct_reasons=%-4d reused=%-4d template_reused=%-4d"
                  % (who[-12:], n, distinct, n_exact, n_tmpl))
    return total, by_attestor


def single_reason_attestors(by_attestor, total_accepts):
    """The extreme case: every accept this identity ever cast says one thing."""
    print("\n== attestors whose accepts are 100%% one reason (>=3 verdicts) ==")
    covered = 0
    for who, jobs in sorted(by_attestor.items(), key=lambda kv: -len(kv[1])):
        reasons = [normalise(r["reason"]) for r in jobs.values()]
        if len(reasons) < 3:
            continue
        if len(set(reasons)) == 1:
            covered += len(reasons)
            print("   ...%s  n=%-4d  %r" % (who[-12:], len(reasons), reasons[0][:100]))
    print("   accepts from single-reason attestors: %d (%.1f%% of all accepts)"
          % (covered, 100.0 * covered / max(1, total_accepts)))


def main(argv):
    paths = []
    for a in argv:
        paths.extend(glob.glob(a))
    if paths:
        print("reading %d saved window(s)" % len(paths))
        seen, verdicts = load(sorted(paths))
    else:
        print("no files given - fetching one live window from /api/tape")
        seen, verdicts = set(), []
        harvest(fetch_live().get("messages", []), seen, verdicts)

    if not verdicts:
        print("no parseable ATTEST v1 messages found")
        return 1

    seqs = [v["seq"] for v in verdicts if v["seq"] is not None]
    print("tape messages de-duplicated : %d" % len(seen))
    print("parsed verdicts             : %d" % len(verdicts))
    print("attest seq span             : %d - %d" % (min(seqs), max(seqs)))
    print("distinct attestors          : %d" % len({v["who"] for v in verdicts}))

    accepts = [v for v in verdicts if v["verdict"] == "useful"]
    rejects = [v for v in verdicts if v["verdict"] == "not"]

    total_accepts, by_accept = census(accepts, "ACCEPT (useful) verdicts")
    census(rejects, "REJECT (not) verdicts - control",
           note="a reused reject reason can still be accurate; a reused accept cannot.")
    single_reason_attestors(by_accept, total_accepts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
