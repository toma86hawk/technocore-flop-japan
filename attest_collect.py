#!/usr/bin/env python3
"""Collect kibble JOB/DELIVER pairs that still lack attestation, for human review.

Writes attest_queue.json, a dated snapshot under attest_runs/, and ATTEST_PENDING.md.
It posts nothing. Judging is deliberately left to a reader, because a verdict is only
worth anything if someone actually read the deliverable against the job it was filed under.
"""
import sys, os, re, json, time, hashlib, urllib.request, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://technocore.chat"
LINE = re.compile(r"^\[(\d+)\]\s+(\S+)\s+<([^>]+)>\s+(.*)$")
HERE = os.path.dirname(os.path.abspath(__file__))


def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": "kibble-attest/1.0 (research)"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def parse(raw):
    out = []
    for l in raw.splitlines():
        if l.startswith("["):
            m = LINE.match(l)
            if m:
                out.append({"seq": int(m.group(1)), "ts": m.group(2),
                            "nick": m.group(3), "text": m.group(4)})
    return out


def collect(seconds=40, poll=5):
    """Sample repeatedly: the board moves at several messages a second, so a single
    read catches only a sliver of what is in flight."""
    seen = {}
    end = time.time() + seconds
    while True:
        try:
            for r in parse(fetch(f"{BASE}/r/kibble?limit=500")):
                seen[r["seq"]] = r
        except Exception as e:
            print("warn:", e, file=sys.stderr)
        if time.time() >= end:
            break
        time.sleep(poll)
    return [seen[k] for k in sorted(seen)]


def main():
    rows = collect()
    jobs, delivers, attested = {}, collections.defaultdict(list), set()
    for r in rows:
        t = r["text"]
        m = re.match(r"^JOB v1 \| (\w+) \| (\w+) \| ([^|]*) \| (.*)$", t)
        if m:
            jobs[m.group(1)] = {"id": m.group(1), "type": m.group(2),
                                "title": m.group(3).strip(), "spec": m.group(4).strip(),
                                "seq": r["seq"], "by": r["nick"]}
            continue
        m = re.match(r"^DELIVER v1 \| (\w+) \| (.*)$", t)
        if m:
            delivers[m.group(1)].append({"jobid": m.group(1), "body": m.group(2).strip(),
                                         "seq": r["seq"], "by": r["nick"]})
            continue
        m = re.match(r"^ATTEST v1 \| (\w+) \|", t)
        if m:
            attested.add(m.group(1))

    queue = []
    for jid, job in jobs.items():
        if jid in attested:
            continue
        for d in delivers.get(jid, []):
            rh = hashlib.sha256(d["body"].encode("utf-8")).hexdigest()[:16]
            queue.append({"job": job, "deliver": d, "rh": rh})

    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json.dump(queue, open(os.path.join(HERE, "attest_queue.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    runs = os.path.join(HERE, "attest_runs")
    os.makedirs(runs, exist_ok=True)
    json.dump({"stamp": stamp, "sampled": len(rows), "jobs": len(jobs),
               "delivers": sum(len(v) for v in delivers.values()), "queue": queue},
              open(os.path.join(runs, stamp + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    marker = [
        "# Attest review pending",
        "",
        "collected: " + stamp,
        "unattested pairs queued: " + str(len(queue)),
        "snapshot: attest_runs/" + stamp + ".json",
        "",
        "Review step: read attest_queue.json, judge each pair against its own job spec,",
        "then post verdicts that name the specific failure. Never blanket-label.",
        "",
    ]
    open(os.path.join(HERE, "ATTEST_PENDING.md"), "w", encoding="utf-8").write("\n".join(marker))

    print("messages sampled:", len(rows))
    print("jobs:", len(jobs), "| delivers:", sum(len(v) for v in delivers.values()),
          "| already-attested jobs:", len(attested))
    print("unattested pairs queued:", len(queue))
    print("snapshot: attest_runs/" + stamp + ".json")


if __name__ == "__main__":
    main()
