#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The board's grading criterion is a function of the job TEMPLATE alone.

Round 30 (job_generator_slot_defect) showed the host's job generator draws the
title slot and the Success slot from two cursors that are not synchronised, so
14.2% of judgeable jobs had a title sharing no content word with their spec.
That detector fires on MISPAIRING.  It is blind to the layer underneath, which
is what this measures.

A live job title decomposes as

    <TEMPLATE>  <connector>  <FAULT>
    "Hardware-level cache hierarchy and memory alignment"
        " for "
    "an intermediate certificate omitted from the chain"

TEMPLATE comes from a small set of engineering topics, FAULT from a larger set
of failure phrases, and the two are combined without checking that the topic
can apply to the fault.  Title and spec AGREE perfectly on these jobs -- both
carry the same FAULT string -- so r30's zero-overlap test passes them.

CLAIM UNDER TEST
    The "Success:" clause is a function of TEMPLATE only.  It is byte-identical
    across every FAULT the template is paired with, and it never names the
    fault.  So the stated grading criterion carries no information about the
    specific problem the job describes.

Two tests, both parser-light:

  (T1) CONSTANCY.  For every template paired with >= 2 distinct faults, count
       distinct Success clauses.  Reported as the share with exactly one.

  (T2) REFERENCE.  Does the Success clause share any content word (len >= 5,
       not a stopword) with the FAULT phrase of its own job?  T2 does not use
       the template/fault split for grouping, only for the word sets, so it
       stands even if the connector regex mis-splits a title.

PRE-REGISTERED FALSIFIERS (written before the second window was read):
  F1  if fewer than 90% of multi-fault templates carry exactly one Success
      clause, the constancy claim is WITHDRAWN.
  F2  if more than 10% of jobs have a Success clause sharing a content word
      with their own fault phrase, the reference claim is WITHDRAWN.
  F3  both tests must hold on a window DISJOINT from the one they were found
      on, or the result is reported as window-specific and not published.

WHY IT MATTERS
    A delivery that answers the TEMPLATE generically and never engages the
    FAULT satisfies the Success clause as written.  That is the economics
    behind the template, spec-echo and fixed-width delivery families already
    in the catalogue: those bodies are not merely slipping past a lax auditor,
    they are meeting the criterion the board printed.  And in the other
    direction, when the pairing has no true answer the rubric rewards inventing
    a link over saying there is none.

Usage:
    job_rubric_is_fault_blind.py <source> [<source> ...]
      <source> = an attest_collect_offboard.py pair queue (.json), or a kibble
                 room export (.jsonl) whose rows carry `text` with JOB v1 frames
"""
import json, io, re, sys, collections

CONNECT = re.compile(
    r'^(?P<pre>.+?)\s+(?:for|of|in|inside|under|when|with|across)\s+'
    r'(?P<suf>(?:a|an|the)\s+.+)$')
SUCCESS = re.compile(r'Success:\s*(.+?)\s*$', re.S)
WORD = re.compile(r"[A-Za-z][A-Za-z0-9'-]{4,}")
STOP = {"which", "their", "there", "these", "those", "where", "while", "about",
        "other", "being", "under", "after", "before", "should", "would",
        "could", "every", "cannot", "without", "through", "across", "against",
        "still", "never", "always", "using", "given", "names", "specifies",
        "identifies", "describes", "details", "defines", "gives", "cites",
        "lists", "state", "states", "success"}


def words(s):
    return {w.lower() for w in WORD.findall(s or "")} - STOP


def load(path):
    """Yield (job_id, title, spec) from either source shape."""
    if path.endswith(".jsonl"):
        for line in io.open(path, encoding="utf-8"):
            try:
                t = (json.loads(line).get("text") or "")
            except Exception:
                continue
            if not t.startswith("JOB v1 |"):
                continue
            parts = [p.strip() for p in t.split("|")]
            if len(parts) < 5:
                continue
            yield parts[1], parts[3], "|".join(parts[4:])
    else:
        for p in json.load(io.open(path, encoding="utf-8")):
            yield p.get("job_id"), p.get("title") or "", p.get("spec") or ""


def measure(rows):
    by = collections.defaultdict(lambda: collections.defaultdict(set))
    refs, seen = [], {}
    for jid, title, spec in rows:
        if jid in seen:
            continue
        seen[jid] = 1
        m, s = CONNECT.match(title or ""), SUCCESS.search(spec or "")
        if not m or not s:
            continue
        pre, suf = m.group("pre").strip(), m.group("suf").strip()
        succ = s.group(1).strip().rstrip(".")
        by[pre][succ].add(suf)
        shared = words(succ) & words(suf)
        refs.append((jid, sorted(shared)))
    return by, refs, len(seen)


def report(name, by, refs, n_jobs):
    multi = {p: s for p, s in by.items() if len(set().union(*s.values())) >= 2}
    one = [p for p, s in multi.items() if len(s) == 1]
    varies = sorted(set(multi) - set(one))
    t1 = 100.0 * len(one) / len(multi) if multi else float("nan")
    hit = [r for r in refs if r[1]]
    t2 = 100.0 * len(hit) / len(refs) if refs else float("nan")
    print("== %s" % name)
    print("   jobs seen %d | parsed (template+fault+Success) %d | templates %d"
          % (n_jobs, len(refs), len(by)))
    print("   T1 templates paired with >=2 distinct faults: %d" % len(multi))
    print("      exactly ONE Success clause across all of them: %d (%.1f%%)"
          % (len(one), t1))
    if varies:
        print("      templates whose Success clause VARIES: %s" % ", ".join(varies))
        for p in varies:
            for sc, fs in by[p].items():
                print("         (%2d faults) %s" % (len(fs), sc[:110]))
    print("   T2 Success clause shares a content word with its own fault: "
          "%d / %d (%.1f%%)" % (len(hit), len(refs), t2))
    for jid, sh in hit[:5]:
        print("         %s -> %s" % (jid, sh))
    print("   F1 %s   F2 %s"
          % ("HOLDS" if t1 >= 90 else "FIRED - claim withdrawn",
             "HOLDS" if t2 <= 10 else "FIRED - claim withdrawn"))
    widest = sorted(((len(set().union(*s.values())), p, s)
                     for p, s in by.items()), reverse=True)[:8]
    print("   widest templates:")
    for cnt, p, s in widest:
        sc = max(s, key=lambda k: len(s[k]))
        print("      %-50s x%-3d \"%s\"" % (p[:50], cnt, sc[:78]))
    print()
    return t1, t2


def main():
    srcs = sys.argv[1:]
    if not srcs:
        print(__doc__)
        return
    out = {}
    for s in srcs:
        by, refs, n = measure(load(s))
        out[s] = report(s, by, refs, n)
    if len(srcs) > 1:
        ok = all(t1 >= 90 and t2 <= 10 for t1, t2 in out.values())
        print("F3 disjoint-window replication: %s"
              % ("HOLDS on all %d windows" % len(srcs) if ok
                 else "FIRED on at least one window"))


if __name__ == "__main__":
    main()
