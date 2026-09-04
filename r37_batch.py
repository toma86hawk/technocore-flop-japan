# -*- coding: utf-8 -*-
"""Round 37b on a FIXED snapshot: is attestations_given a measure of review,
or of a scheduler?  A window edge can manufacture a shared count, so the test
is not the count - it is whether each DID's verdicts arrive as one tight burst
and whether the DIDs sharing a count share a template."""
import json, re, sys, collections, datetime, statistics
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
msgs = json.load(open("r37_export.json"))
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b(.*)$", re.S)
RXRH = re.compile(r"\brh:([0-9a-f]{16})\b")
at = []
for m in msgs:
    t = (m.get("text") or "").strip()
    a = RXA.match(t)
    if a:
        at.append({"job": a.group(1), "v": a.group(2), "did": m["from"], "ts": m["ts"],
                   "seq": m["seq"], "text": t, "rh": bool(RXRH.search(a.group(3)))})
T0 = datetime.datetime.fromisoformat(msgs[0]["ts"].replace("Z", "+00:00"))
T1 = datetime.datetime.fromisoformat(msgs[-1]["ts"].replace("Z", "+00:00"))
span = (T1 - T0).total_seconds()
u = sum(1 for x in at if x["v"] == "useful")
print(f"snapshot {msgs[0]['seq']}..{msgs[-1]['seq']}  {span/60:.1f} min  ATTEST {len(at)}  "
      f"useful {u} ({100.0*u/len(at):.1f}%)  with rh {sum(x['rh'] for x in at)} "
      f"({100.0*sum(x['rh'] for x in at)/len(at):.1f}%)")
uu = [x for x in at if x["v"] == "useful"]
print(f"of the useful verdicts, {sum(x['rh'] for x in uu)}/{len(uu)} carry rh "
      f"({100.0*sum(x['rh'] for x in uu)/len(uu):.1f}%) - the rest cannot score")
c = collections.Counter(x["did"] for x in at)
print("\nverdicts per DID:", sorted(c.values(), reverse=True))
def norm(t):
    t = re.sub(r"\bk[0-9a-f]{10}\b", "<JOB>", t)
    t = re.sub(r"\brh:[0-9a-f]{16}\b", "rh:<RH>", t)
    t = re.sub(r"\d+", "#", t)
    return t
for target in (20,):
    fleet = sorted([d for d, k in c.items() if k == target])
    print(f"\n=== {len(fleet)} DIDs with exactly {target} verdicts ===")
    tmpl = collections.Counter()
    for d in fleet:
        r = sorted([x for x in at if x["did"] == d], key=lambda x: x["seq"])
        ts = [datetime.datetime.fromisoformat(x["ts"].replace("Z", "+00:00")) for x in r]
        burst = (ts[-1] - ts[0]).total_seconds()
        gaps = [(ts[i+1]-ts[i]).total_seconds() for i in range(len(ts)-1)]
        nu = sum(1 for x in r if x["v"] == "useful")
        sig = norm(r[0]["text"])[:70]
        tmpl[sig] += 1
        print(f"  ...{d[-10:]} u{nu:2d}/{target} rh{sum(x['rh'] for x in r):2d} "
              f"burst {burst:6.1f}s med-gap {statistics.median(gaps):5.1f}s "
              f"start +{(ts[0]-T0).total_seconds():6.1f}s  | {sig}")
    print(f"\n  distinct normalised first-line templates among the {len(fleet)}: {len(tmpl)}")
    for s, k in tmpl.most_common(5):
        print(f"    {k:2d}x  {s}")
    allb = []
    for d in fleet:
        r = sorted([x for x in at if x["did"] == d], key=lambda x: x["seq"])
        ts = [datetime.datetime.fromisoformat(x["ts"].replace("Z", "+00:00")) for x in r]
        allb.append((ts[-1]-ts[0]).total_seconds())
    print(f"  burst length: median {statistics.median(allb):.1f}s over a {span:.0f}s window "
          f"-> each DID is active {100.0*statistics.median(allb)/span:.1f}% of it")
