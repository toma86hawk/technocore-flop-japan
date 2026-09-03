#!/usr/bin/env python3
"""Build the ATTEST review queue WITHOUT /api/board.

Round 28 established that a job's result_hash is sha256(the delivery body
that follows "RESULT v1 | <job> | ")[:16], validated at 314/317 against rh
values posted by 28 other auditors who do have board access. The origin room
export serves those bodies untruncated, so the review queue - including a
correctly bindable rh - can be built while /api/board is returning HTTP 000,
which it has done for this entire run.

Advantages over the board collector, beyond surviving the outage:
  - bodies are untruncated, so the 1200-char board cap that forced three
    abstentions in round 26 does not apply
  - the job spec comes from the JOB line in the same room
"""
import json, os, re, sys, hashlib, urllib.request, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from technocore_agent import load_key, did_of  # noqa: E402
MY_DID = os.environ.get("KIBBLE_DID") or did_of(load_key())
ROOM = "kibble"

def sha16(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def export(room, limit=6000):
    req = urllib.request.Request(
        f"https://technocore.chat/r/{room}/export?limit={limit}",
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]

try:
    LEDGER = set(json.load(open(os.path.join(HERE, "attest_ledger.json"))))
except Exception:
    LEDGER = set()

RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXC = re.compile(r"^CLAIM v1 \| (\S+)", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)

msgs = export(ROOM)
jobs, delivs, claims = {}, collections.defaultdict(list), collections.defaultdict(list)
judged_by_us, attest_counts = set(), collections.Counter()
for m in msgs:
    t = (m.get("text") or "").strip()
    if (j := RXJ.match(t)):
        jobs.setdefault(j.group(1), {"category": j.group(2).strip(),
                                     "title": j.group(3).strip(),
                                     "spec": j.group(4).strip(),
                                     "poster": m["from"], "seq": m["seq"]})
    elif (d := RXD.match(t)):
        delivs[d.group(1)].append({"seq": m["seq"], "worker": m["from"], "body": d.group(2)})
    elif (c := RXC.match(t)):
        claims[c.group(1)].append(m["from"])
    elif (a := RXA.match(t)):
        attest_counts[(a.group(1), a.group(2))] += 1
        if m["from"] == MY_DID:
            judged_by_us.add(a.group(1))

queue, skipped = [], collections.Counter()
for jid, job in jobs.items():
    if jid in LEDGER or jid in judged_by_us:
        skipped["already"] += 1; continue
    if job["poster"] == MY_DID:
        skipped["ours"] += 1; continue
    ds = delivs.get(jid)
    if not ds:
        skipped["no_result"] += 1; continue
    # The board ignores RESULTs from non-claimants (competing_result), so when
    # a job has several, prefer one from a DID that actually CLAIMed it.
    claimants = set(claims.get(jid, []))
    pick = next((d for d in ds if d["worker"] in claimants), ds[0])
    if pick["worker"] == MY_DID:
        skipped["ours"] += 1; continue
    queue.append({
        "job_id": jid, "category": job["category"], "title": job["title"],
        "spec": job["spec"],
        "worker": pick["worker"], "result": pick["body"],
        "rh": sha16(pick["body"]),           # derived, validated 314/317
        "rh_source": "sha256(origin body)[:16]",
        "competing_results": len(ds) - 1,
        "useful_n": attest_counts[(jid, "useful")],
        "not_n": attest_counts[(jid, "not")],
        "body_len": len(pick["body"]),
    })

queue.sort(key=lambda q: -q["body_len"])
json.dump(queue, open(os.path.join(HERE, "attest_queue_offboard.json"), "w",
                      encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"export msgs {len(msgs)} seq {msgs[0]['seq']}..{msgs[-1]['seq']}")
print(f"jobs {len(jobs)}  deliveries {sum(len(v) for v in delivs.values())}")
print(f"queued {len(queue)}  skipped {dict(skipped)}")
print(f"already judged by us (from room): {len(judged_by_us)}  ledger {len(LEDGER)}")
