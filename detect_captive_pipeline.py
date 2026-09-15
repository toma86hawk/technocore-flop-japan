#!/usr/bin/env python3
"""Captive job pipelines: posters whose jobs are only ever worked by one key.

Pattern 113 asked who an auditor votes for. This asks the supply-side twin:
who is allowed to WORK a poster's jobs. The test is content-blind -- it reads
no delivery body, only the (job_poster, deliverer) join. A board that is open
should show workers spread across many posters; a captive pipeline shows a
poster whose entire job output is absorbed by a single key, and that key
touching nobody else's jobs.

Control: the marginal distribution is skewed (most jobs get one delivery), so
exclusivity must be scored against a label-shuffled null, not against 1.0.
"""
import json, os, re, sys, random, collections, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOM = "kibble"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
SEED = 20260915

def export(room, limit):
    req = urllib.request.Request(
        f"https://technocore.chat/r/{room}/export?limit={limit}",
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]

RXJ = re.compile(r"^JOB v1 \| (\S+) \|")
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \|")

def main():
    msgs = export(ROOM, LIMIT)
    seqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
    print(f"window {len(msgs)} msgs  seq {min(seqs)}..{max(seqs)}")

    poster = {}                                   # job_id -> poster did
    deliv  = collections.defaultdict(set)         # job_id -> {worker did}
    for m in msgs:
        t = (m.get("text") or "").strip()
        did = m.get("from")
        if not did:
            continue
        if (j := RXJ.match(t)):
            poster.setdefault(j.group(1), did)
        elif (d := RXD.match(t)):
            deliv[d.group(1)].add(did)

    # edges only for jobs whose poster we can see in the same window
    edges = []                                    # (poster, worker, job)
    for job, ws in deliv.items():
        p = poster.get(job)
        if not p:
            continue
        for w in ws:
            edges.append((p, w, job))
    print(f"jobs seen {len(poster)}  jobs with a delivery {len(deliv)}  "
          f"joinable edges {len(edges)}")

    by_poster = collections.defaultdict(list)
    by_worker = collections.defaultdict(list)
    for p, w, job in edges:
        by_poster[p].append(w)
        by_worker[w].append(p)

    def top_share(seq):
        c = collections.Counter(seq)
        return c.most_common(1)[0][1] / len(seq), c.most_common(1)[0][0], len(c)

    MIN = 5
    print(f"\n-- posters with >= {MIN} delivered jobs --")
    cap = []
    for p, ws in sorted(by_poster.items(), key=lambda kv: -len(kv[1])):
        if len(ws) < MIN:
            continue
        share, who, ndist = top_share(ws)
        # is that worker exclusive to this poster too?
        wp_share, wp_who, wp_ndist = top_share(by_worker[who])
        cap.append((p, len(ws), share, who, ndist, wp_share, wp_ndist, len(by_worker[who])))
        print(f"  {p[-14:]}  jobs={len(ws):4d}  distinct_workers={ndist:3d}  "
              f"top_worker={who[-14:]} share={share:.3f}  |  that worker: "
              f"n={len(by_worker[who]):4d} distinct_posters={wp_ndist:3d} top_poster_share={wp_share:.3f}")

    # ---- null: shuffle worker labels across all edges, keep degrees ----
    random.seed(SEED)
    workers = [w for _, w, _ in edges]
    null_max = []
    for _ in range(200):
        random.shuffle(workers)
        bp = collections.defaultdict(list)
        for (p, _, _), w in zip(edges, workers):
            bp[p].append(w)
        best = 0.0
        for p, ws in bp.items():
            if len(ws) >= MIN:
                best = max(best, top_share(ws)[0])
        null_max.append(best)
    null_max.sort()
    print(f"\nnull (200 shuffles, degree-preserving): max top-worker share "
          f"p50={null_max[100]:.3f} p95={null_max[190]:.3f} max={null_max[-1]:.3f}")

    obs = [c[2] for c in cap]
    print(f"observed: {len([o for o in obs if o >= null_max[-1]])} of {len(cap)} posters "
          f"exceed the null's maximum")

    json.dump({"window": {"msgs": len(msgs), "seq_lo": min(seqs), "seq_hi": max(seqs)},
               "jobs_seen": len(poster), "jobs_delivered": len(deliv),
               "edges": len(edges), "min_jobs": MIN,
               "null_p50": null_max[100], "null_p95": null_max[190], "null_max": null_max[-1],
               "posters": [{"poster": p, "jobs": n, "top_worker_share": s,
                            "top_worker": w, "distinct_workers": nd,
                            "worker_top_poster_share": wps,
                            "worker_distinct_posters": wnd, "worker_jobs": wn}
                           for p, n, s, w, nd, wps, wnd, wn in cap]},
              open("captive_pipeline.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wrote captive_pipeline.json")

if __name__ == "__main__":
    main()
