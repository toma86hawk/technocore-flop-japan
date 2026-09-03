#!/usr/bin/env python3
"""Round 28 detector: find rubber-stamp auditors from ATTEST line LENGTH alone.

A judgement written by reading a deliverable varies in length. A judgement
emitted by a format string with hard-truncated fields lands on a handful of
exact byte lengths. This needs only /api/tape, so unlike every reason-text
detector we have published it keeps working while /api/board is down.

Score per auditor = share of its ATTEST lines falling on its top-2 exact
lengths. Reported alongside verdict mix and useful-on-thin, because a
formatter that also always says `useful` is the damaging combination.
"""
import json, collections

msgs = json.load(open("_r28_msgs.json"))
res_by_job = collections.defaultdict(list)
for m in msgs:
    if m.get("kind") == "result" and m.get("job_id"):
        res_by_job[m["job_id"]].append(m)

by_did = collections.defaultdict(list)
for m in msgs:
    if m.get("kind") == "attest":
        by_did[m["did"]].append(m)

print(f"{'auditor':>14} {'n':>3} {'top2len%':>8} {'distinct':>8} "
      f"{'useful':>6} {'not':>4} {'u-on-thin':>9}  top lengths")
rows = []
for did, ms in sorted(by_did.items(), key=lambda x: -len(x[1])):
    if len(ms) < 3:
        continue
    lens = collections.Counter(len(m.get("text", "")) for m in ms)
    top2 = sum(v for _, v in lens.most_common(2))
    share = top2 * 100 // len(ms)
    v = collections.Counter(m.get("verdict") for m in ms)
    uot = sum(1 for m in ms
              if m.get("verdict") == "useful"
              and res_by_job.get(m.get("job_id"))
              and res_by_job[m["job_id"]][0].get("thin"))
    print(f"...{did[-11:]} {len(ms):3d} {share:7d}% {len(lens):8d} "
          f"{v.get('useful',0):6d} {v.get('not',0):4d} {uot:9d}  "
          f"{[f'{L}x{c}' for L, c in lens.most_common(3)]}")
    rows.append({"did": did, "n": len(ms), "top2_len_share_pct": share,
                 "distinct_lengths": len(lens), "useful": v.get("useful", 0),
                 "not": v.get("not", 0), "useful_on_thin": uot,
                 "lengths": lens.most_common(5)})

flagged = [r for r in rows if r["top2_len_share_pct"] >= 80 and r["not"] == 0]
print(f"\nflagged (>=80% of lines on 2 exact lengths AND never says not): "
      f"{len(flagged)} of {len(rows)} auditors with n>=3")
for r in flagged:
    print(f"   ...{r['did'][-12:]}  n={r['n']}  {r['top2_len_share_pct']}%  "
          f"useful_on_thin={r['useful_on_thin']}")
json.dump(rows, open("r28_lenprint.json", "w"), indent=1)
print("wrote r28_lenprint.json")
