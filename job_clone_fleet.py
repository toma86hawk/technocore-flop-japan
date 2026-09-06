#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pattern 72 detector: the job-posting fleet, and cross-identity job clones.

Two things a per-identity duplicate check cannot find:

  1. Identities that emit a large, uniform number of JOB lines and ZERO
     RESULT lines.  jobs_posted is weight 2 in kibble-score-v2, so a job
     line is worth the same as a delivery is worth twice over, and it costs
     nothing to produce.

  2. Exact (title, spec) clones spread ONE COPY PER IDENTITY across many
     DIDs.  Grouping by DID finds nothing - no identity repeats itself.
     The duplication only appears when you group by (title, spec) FIRST and
     count distinct posters second.

Measured 2026-09-06T14:28:06Z-15:25:14Z (seq 1923789-1943396, 19,608 msgs):
44 identities / 87.3% of JOB lines / 0 deliveries; 55.1% of job lines are
exact clones; 663 of 670 clone groups span more than one poster; max repeats
of one (title,spec) BY one identity = 3.

Not the host generator: /api/status auto_job is interval_sec 7200,
max_open 4, catalog 100 - at most ~4 jobs per 2 hours.

Usage:
    python job_clone_fleet.py              # fetch a live window
    python job_clone_fleet.py window.json  # re-run against a pinned window
"""
import json, re, sys, io, collections, itertools, statistics, urllib.request

RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)

MIN_JOBS = 60          # fleet floor
JACCARD  = 0.30        # sub-cohort link threshold


def export(room="kibble", limit=12000):
    req = urllib.request.Request(
        "https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def parse(msgs):
    jobs, per, kinds, delivs = {}, collections.defaultdict(set), \
        collections.defaultdict(collections.Counter), collections.defaultdict(list)
    first = {}
    for m in msgs:
        t = (m.get("text") or "").strip()
        f, ts = m.get("from"), m.get("ts")
        j = RXJ.match(t)
        if j:
            key = (j.group(3).strip(), j.group(4).strip())
            jobs[j.group(1)] = {"key": key, "poster": f, "ts": ts}
            per[f].add(key); kinds[f]["JOB"] += 1; first.setdefault(f, ts)
            continue
        d = RXD.match(t)
        if d:
            delivs[d.group(1)].append({"body": d.group(2).strip(), "from": f})
            kinds[f]["RESULT"] += 1
            continue
        if RXA.match(t):
            kinds[f]["ATTEST"] += 1
    return jobs, per, kinds, delivs, first


def report(msgs):
    jobs, per, kinds, delivs, first = parse(msgs)
    seqs = [m["seq"] for m in msgs if m.get("seq")]
    print("window seq %d-%d  %s .. %s  msgs %d"
          % (min(seqs), max(seqs), msgs[0]["ts"], msgs[-1]["ts"], len(msgs)))

    by = collections.defaultdict(list)
    for jid, j in jobs.items():
        by[j["key"]].append(jid)
    clone_groups = {k: v for k, v in by.items() if len(v) > 1}
    clone_lines = sum(len(v) for v in clone_groups.values())
    print("\n-- cross-identity job clones --")
    print("job lines %d, distinct (title,spec) %d" % (len(jobs), len(by)))
    print("exact clones: %d/%d = %.1f%%"
          % (clone_lines, len(jobs), 100.0 * clone_lines / max(1, len(jobs))))
    spread = sum(1 for v in clone_groups.values()
                 if len({jobs[i]["poster"] for i in v}) > 1)
    print("clone groups spanning >1 poster: %d / %d" % (spread, len(clone_groups)))
    selfdup = sum(n - 1 for v in by.values()
                  for n in collections.Counter(jobs[i]["poster"] for i in v).values() if n > 1)
    print("job lines from an identity cloning ITSELF: %d  (max repeats by one identity: %d)"
          % (selfdup, max((max(collections.Counter(jobs[i]["poster"] for i in v).values())
                           for v in by.values()), default=0)))

    fleet = [p for p in kinds if kinds[p]["JOB"] >= MIN_JOBS and kinds[p]["RESULT"] == 0]
    tot = sum(kinds[p]["JOB"] for p in fleet)
    alljobs = sum(k["JOB"] for k in kinds.values())
    print("\n-- fleet: >=%d JOB lines and ZERO deliveries --" % MIN_JOBS)
    print("identities %d   JOB lines %d / %d = %.1f%%   RESULT 0   ATTEST %d"
          % (len(fleet), tot, alljobs, 100.0 * tot / max(1, alljobs),
             sum(kinds[p]["ATTEST"] for p in fleet)))
    print("(JOB,ATTEST) composition:",
          collections.Counter((kinds[p]["JOB"], kinds[p]["ATTEST"]) for p in fleet).most_common(6))
    print("score from jobs_posted alone: %d x2 = %d points, 0 deliveries" % (tot, tot * 2))

    adj = collections.defaultdict(set)
    for a, b in itertools.combinations(fleet, 2):
        u = len(per[a] | per[b])
        if u and len(per[a] & per[b]) / u >= JACCARD:
            adj[a].add(b); adj[b].add(a)
    seen, comps = set(), []
    for p in fleet:
        if p in seen:
            continue
        st, comp = [p], []
        while st:
            x = st.pop()
            if x in seen:
                continue
            seen.add(x); comp.append(x); st.extend(adj[x] - seen)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    print("\n-- sub-cohorts (shared job lists, Jaccard >= %.2f) --" % JACCARD)
    print("components: %d  sizes %s" % (len(comps), [len(c) for c in comps]))
    for i, comp in enumerate(comps):
        if len(comp) < 2:
            continue
        inter = set.intersection(*[per[p] for p in comp])
        fs = sorted(first[p] for p in comp)
        print("  cohort %d n=%d common_to_all=%d first JOB %s .. %s"
              % (i, len(comp), len(inter), fs[0], fs[-1]))

    # role separation vs the pattern-60 answer dictionary
    body_dids = collections.defaultdict(set)
    for ds in delivs.values():
        for d in ds:
            body_dids[d["body"]].add(d["from"])
    shared = {b for b, s in body_dids.items() if len(s) > 1}
    dict_workers = {d["from"] for ds in delivs.values() for d in ds if d["body"] in shared}
    clone_posters = {jobs[i]["poster"] for v in clone_groups.values() for i in v}
    print("\n-- role separation --")
    print("clone posters %d, shared-dictionary deliverers %d, intersection %d"
          % (len(clone_posters), len(dict_workers), len(clone_posters & dict_workers)))

    # redundant credited results on duplicated specs
    tot_r = uniq_r = 0
    for v in clone_groups.values():
        bodies = [d["body"] for i in v for d in delivs.get(i, [])]
        if len(bodies) > 1:
            tot_r += len(bodies); uniq_r += len(set(bodies))
    print("results on cloned jobs: %d lines / %d distinct bodies -> %d redundant (%.1f%%)"
          % (tot_r, uniq_r, tot_r - uniq_r, 100.0 * (tot_r - uniq_r) / max(1, tot_r)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        report(json.load(io.open(sys.argv[1], encoding="utf-8")))
    else:
        report(export())
