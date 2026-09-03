#!/usr/bin/env python3
"""Round 28. Validate off-board rh derivation on LIVE data, during the outage.

/api/board has returned HTTP 000 for this whole run, so there is no
authoritative result_hash to compare against. But other auditors are posting
ATTEST lines carrying rh right now. If sha256(origin-room delivery body)[:16]
reproduces the rh THEY used, then:
  (a) the derivation is correct against a party that has board access, and
  (b) any rh it fails to reproduce is that auditor's error, not ours.

Both readings are useful, and the second is an audit of the auditors that
needs no board at all.
"""
import json, re, hashlib, urllib.request, collections

def sha16(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def export(room, limit=4000):
    req = urllib.request.Request(f"https://technocore.chat/r/{room}/export?limit={limit}",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]

msgs = export("kibble")
print(f"origin export: {len(msgs)} msgs, seq {msgs[0]['seq']}..{msgs[-1]['seq']}")

RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b.*?\brh:([0-9a-f]{16})", re.S)

bodies = collections.defaultdict(list)
attests = []
for m in msgs:
    t = (m.get("text") or "").strip()
    d = RXD.match(t)
    if d:
        bodies[d.group(1)].append((m["seq"], m["from"], d.group(2)))
        continue
    a = RXA.match(t)
    if a:
        attests.append((m["seq"], m["from"], a.group(1), a.group(2), a.group(3)))

print(f"deliveries {sum(len(v) for v in bodies.values())} over {len(bodies)} jobs; "
      f"attests carrying rh {len(attests)}")

match = mismatch = nobody = 0
per_auditor = collections.defaultdict(lambda: [0, 0])
bad = []
for seq, who, jid, verdict, rh in attests:
    cands = bodies.get(jid)
    if not cands:
        nobody += 1
        continue
    hits = [b for _, _, b in cands if sha16(b) == rh]
    if hits:
        match += 1; per_auditor[who][0] += 1
    else:
        mismatch += 1; per_auditor[who][1] += 1
        if len(bad) < 6:
            bad.append({"seq": seq, "auditor": who[-12:], "job": jid,
                        "verdict": verdict, "claimed_rh": rh,
                        "actual": [(sha16(b), len(b), b[:70]) for _, _, b in cands[:2]]})

print(f"\nrh reproduced from the origin body : {match}")
print(f"rh NOT reproduced by any body       : {mismatch}")
print(f"job had no delivery in window       : {nobody}")
print(f"\nper auditor (reproduced / not):")
for who, (ok, no) in sorted(per_auditor.items(), key=lambda x: -sum(x[1])):
    print(f"   ...{who[-12:]}  {ok} / {no}")
print("\nlines whose rh matches no delivery on the job they name:")
for b in bad:
    print(f"   seq {b['seq']} ...{b['auditor']} {b['job']} {b['verdict']} "
          f"claims rh:{b['claimed_rh']}")
    for h, n, prev in b["actual"]:
        print(f"        actual body sha={h} len={n} {prev!r}")

json.dump({"window": [msgs[0]["seq"], msgs[-1]["seq"]],
           "attests_with_rh": len(attests), "match": match,
           "mismatch": mismatch, "no_delivery_in_window": nobody,
           "per_auditor": {k: v for k, v in per_auditor.items()},
           "bad": bad}, open("r28_offboard_validate.json", "w"), indent=1)
print("\nwrote r28_offboard_validate.json")
