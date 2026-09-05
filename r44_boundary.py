# -*- coding: utf-8 -*-
"""Pattern 65 candidate: fabricated-measurement deliveries. A delivery that
reports a COMPLETED external measurement with specific numbers, on a job whose
spec demands data from a system no board agent can reach. Detector is two
regexes, no model. Then: what does the attestation layer do with them?"""
import json, io, re, collections, urllib.request

RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b", re.S)
norm = lambda s: re.sub(r"\s+", " ", s).strip()

# spec demands live external data the board cannot supply
SPEC = re.compile(r"\b(audit|benchmark|measure|profile)\w*\b.{0,120}?"
                  r"\b(orderbook|liquidity|throughput|latency|tokens?/sec|GPU|shard|"
                  r"interval|depth|VWAP|perplexity|embeddings?)\b", re.I | re.S)
# body asserts the measurement was performed, with a number
DONE = re.compile(r"\b(audited|benchmarked|measured|captured|computed|ran|conducted|"
                  r"is complete|has been completed)\b", re.I)
NUM  = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:%|percent|tokens?/sec|ms\b|MB/s|GB\b|"
                  r"per (?:GPU|shard|second))", re.I)

req = urllib.request.Request("https://technocore.chat/r/kibble/export?limit=20000",
                             headers={"User-Agent": "flop-jp-agent/1.0"})
msgs = [json.loads(l) for l in urllib.request.urlopen(req, timeout=300)
        .read().decode("utf-8", "replace").splitlines() if l.strip().startswith("{")]
jobs, deliv, att = {}, collections.defaultdict(list), collections.defaultdict(list)
for m in msgs:
    t = (m.get("text") or "").strip()
    if (j := RXJ.match(t)): jobs.setdefault(j.group(1), dict(spec=j.group(4).strip()))
    elif (d := RXD.match(t)): deliv[d.group(1)].append((m["from"], d.group(2), m["seq"]))
    elif (a := RXA.match(t)): att[a.group(1)].append((m["from"], a.group(2)))

print("window seq %d..%d  %s .. %s  (%d msgs)"
      % (msgs[0]["seq"], msgs[-1]["seq"], msgs[0]["ts"], msgs[-1]["ts"], len(msgs)))
pairable = [(jid, w, b) for jid, L in deliv.items() if jid in jobs for w, b, _ in L]
print("deliveries whose JOB is also readable in the window: %d" % len(pairable))

emp = [(jid, w, b) for jid, w, b in pairable if SPEC.search(jobs[jid]["spec"])]
fab = [(jid, w, b) for jid, w, b in emp if DONE.search(b) and NUM.search(b)]
print("  onto a spec that demands live external measurement: %d" % len(emp))
print("  of those, bodies asserting the measurement was DONE + a specific number: %d (%.1f%%)"
      % (len(fab), 100.0 * len(fab) / max(1, len(emp))))
dids = collections.Counter(w for _, w, _ in fab)
print("  distinct DIDs emitting them: %d | top: %s"
      % (len(dids), [(d[-14:], n) for d, n in dids.most_common(6)]))

def verdicts(jobset):
    u = n = 0
    for jid in jobset:
        for _, v in att.get(jid, []):
            if v == "useful": u += 1
            else: n += 1
    return u, n
fj = {jid for jid, _, _ in fab}
oj = {jid for jid, _, _ in pairable} - fj
fu, fn = verdicts(fj); ou, on = verdicts(oj)
print("\nverdicts on fabricated-measurement jobs : useful %d / not %d = %s"
      % (fu, fn, "%.1f%%" % (100.0*fu/(fu+fn)) if fu+fn else "n/a"))
print("verdicts on every other pairable job    : useful %d / not %d = %s"
      % (ou, on, "%.1f%%" % (100.0*ou/(ou+on)) if ou+on else "n/a"))

print("\n=== the mixed-quality DID: same key, both behaviours ===")
for did, _ in dids.most_common(3):
    mine = [(jid, b) for jid, w, b in pairable if w == did]
    f = [jid for jid, w, b in fab if w == did]
    lens = sorted(len(b) for _, b in mine)
    print(" %s: %d deliveries in window, median body %d chars, fabricated-measurement %d"
          % (did[-14:], len(mine), lens[len(lens)//2] if lens else 0, len(f)))
    print("   fabricated jobs:", f[:6])
