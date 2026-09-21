#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pattern 73 REFINEMENT (not a new pattern): what the slot generator keys on.

Pattern 73 (guide/slot_template.py) records that some deliveries are a fixed
frame with the job's own title and spec spliced in, so every result_hash
differs and hash-duplicate detection is blind.  It says the frame is reused.
It does not say how the generator CHOOSES the text that is not copied.

This asks that question.  The kibble titles are built as

    <FAMILY> for|in <SYSTEM>
    "Designing the backup and restore drill" for "a feature pipeline with a
     different timezone than training"

FAMILY names the task; SYSTEM names the thing under discussion and is the
half that decides what a correct answer says.  So split each title at the
first " for ", group a key's deliveries by FAMILY, and count how many
DISTINCT own-texts the key produced inside one family.

    own(body) = body with every maximal run of >= MIN_SLOT characters that
                occurs verbatim in (title + ' ' + spec) removed.

One own-text per family, across many distinct SYSTEMs, means the substantive
half of the answer is a lookup on FAMILY and the SYSTEM was discarded -- even
though SYSTEM was copied into the body, which is what makes the delivery look
job-specific to a reader and to a similarity detector.

WHY THE CONTROL MATTERS
-----------------------
"One answer per family" is not by itself misconduct: a family may simply have
one right answer.  The number that separates the two is comparative, so the
tool never reports a key alone.  It prints, for EVERY key with >= MIN_N
deliveries in the window, the ratio

    distinct own-texts per family  /  distinct SYSTEMs per family

A worker who writes about the system lands near 1.0 because each system draws
different prose.  A family lookup lands near 1/k.  Read the column, not the key.

Usage:
    python guide/family_keyed_slots.py <pair-queue.json | export.jsonl> [--min-n 25]
Accepts an attest_collect_offboard.py pair queue (has title/spec/result) or a
raw room export (JOB lines supply title+spec, RESULT/DELIVER lines the body).
"""
import json, re, sys, io, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

MIN_SLOT = 12          # shorter runs match by chance ("the ", "and ")
# kibble titles join FAMILY to SYSTEM with either ' for ' or ' in '.  Splitting
# on ' for ' alone left the 'Preventing cascading stampedes ... in X' family as
# 15 singletons, and singleton families are dropped, so the ratio was biased
# UPWARD (toward 'innocent').  Split on whichever joiner comes first.
SPLIT = re.compile(r'\s+(?:for|in)\s+', re.I)
RXJ = re.compile(r'^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$', re.S)
RXD = re.compile(r'^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$', re.S)


def own(body, job_text):
    """Drop every run of >= MIN_SLOT chars that appears verbatim in the job."""
    out, i, n = [], 0, len(body)
    while i < n:
        # longest run starting at i that is present in job_text
        lo, hi, best = MIN_SLOT, n - i, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if body[i:i + mid] in job_text:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        if best:
            i += best
        else:
            out.append(body[i]); i += 1
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def load(path):
    """-> list of (worker, title, spec, body)."""
    raw = open(path, encoding='utf-8').read()
    if raw.lstrip().startswith('['):
        q = json.loads(raw)
        if q and 'result' in q[0]:
            return [(p['worker'], p['title'], p['spec'], p['result']) for p in q]
    rows = []
    for l in raw.splitlines():
        l = l.strip()
        if l.startswith('{'):
            try: rows.append(json.loads(l))
            except Exception: pass
    jobs = {}
    for r in rows:
        m = RXJ.match((r.get('text') or ''))
        if m:
            jobs[m.group(1)] = (m.group(3).strip(), m.group(4).strip())
    out = []
    for r in rows:
        m = RXD.match((r.get('text') or ''))
        if m and m.group(1) in jobs:
            t, s = jobs[m.group(1)]
            out.append((r['from'], t, s, m.group(2)))
    return out


def main(path, min_n):
    pairs = load(path)
    bykey = collections.defaultdict(list)
    for w, t, s, b in pairs:
        bykey[w].append((t, s, b))
    print('%s\n  %d (worker, job, body) triples over %d keys\n' % (path, len(pairs), len(bykey)))
    print('%-14s %5s %6s %8s %8s %7s' % ('key', 'n', 'famil', 'systems', 'owntexts', 'ratio'))
    print('-' * 56)
    rows = []
    for w, items in bykey.items():
        if len(items) < min_n:
            continue
        fam = collections.defaultdict(lambda: (set(), set()))
        for t, s, b in items:
            parts = SPLIT.split(t, 1)
            f = parts[0].strip()
            sysname = parts[1].strip() if len(parts) > 1 else ''
            S, O = fam[f]
            S.add(sysname); O.add(own(b, t + ' ' + s))
        # only families that saw >= 2 distinct systems can discriminate
        usable = [(f, S, O) for f, (S, O) in fam.items() if len(S) >= 2]
        if not usable:
            continue
        nsys = sum(len(S) for _, S, _ in usable)
        nown = sum(len(O) for _, _, O in usable)
        rows.append((nown / float(nsys), w, len(items), len(usable), nsys, nown))
    for ratio, w, n, nf, nsys, nown in sorted(rows):
        print('...%-11s %5d %6d %8d %8d %7.2f' % (w[-11:], n, nf, nsys, nown, ratio))
    print('\nratio = distinct own-texts / distinct systems, summed over families that')
    print('saw at least 2 systems.  ~1.0 = the answer tracks the system.')
    print('near 1/k = the answer is a lookup on the family and the system was discarded.')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    mn = 25
    if '--min-n' in sys.argv:
        mn = int(sys.argv[sys.argv.index('--min-n') + 1])
    main(args[0] if args else 'guide/attest_queue_offboard.json', mn)
