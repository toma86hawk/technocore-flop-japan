#!/usr/bin/env python3
"""Count the 'ProofHash/Epoch' delivery template on the kibble tape.

Shape:  Deliverable for [<CAT>] '<job title>': Conducted rigorous domain evaluation
        <method phrase>. Specification constraints satisfied: <spec, cut mid-word>...
        Execution invariants and semantic constraints verified with deterministic
        output. <closing assurance>. [ProofHash: <8 hex> - Epoch: <unix seconds>]

Falsification handles: if the marker is one DID it is a single agent, not a fleet;
if ProofHash values repeat it is a constant, not a per-delivery fabrication;
if Epoch tracks the real tape timestamp it is a clock, not a decoration.
"""
import json, re, sys, urllib.request, collections, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PH     = re.compile(r"\[ProofHash:\s*([0-9a-f]{8})\s*-\s*Epoch:\s*(\d{10})\]")
LEAD   = re.compile(r"Deliverable for \[([A-Z]+)\]")
METHOD = re.compile(r"Conducted rigorous domain evaluation ([^.]+)\.")
CUT    = re.compile(r"Specification constraints satisfied: (.*?)\.\.\.")

with urllib.request.urlopen("https://flop-kibble.onrender.com/api/tape?limit=1500", timeout=300) as r:
    d = json.loads(r.read().decode())
msgs = d.get("messages", [])
seqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
print("window: msgs", len(msgs), "seq", min(seqs), "-", max(seqs))
results = [m for m in msgs if m.get("kind") == "result"]
print("results in window:", len(results))

hits = []
for m in results:
    t = m.get("text") or m.get("body") or ""
    g = PH.search(t)
    if g:
        hits.append((m, g.group(1), int(g.group(2)), t))

print("\n=== ProofHash/Epoch template ===")
print("deliveries carrying it:", len(hits),
      "(%.1f%% of results)" % (100.0 * len(hits) / max(1, len(results))))
dids = collections.Counter((h[0].get("did") or h[0].get("from")) for h in hits)
print("distinct DIDs:", len(dids))
for k, n in dids.most_common():
    print("   ", (k or "?")[-14:], n)

ph = [h[1] for h in hits]
print("ProofHash values:", len(set(ph)), "distinct of", len(ph))
dupe = [k for k, n in collections.Counter(ph).items() if n > 1]
print("repeated ProofHash:", dupe or "none")

print("\nepoch vs the tape's own timestamp:")
drifts = []
for m, p, e, t in hits:
    try:
        real = datetime.datetime.fromisoformat(m["ts"].replace("Z", "+00:00")).timestamp()
        drifts.append(e - real)
    except Exception:
        pass
if drifts:
    drifts.sort()
    print("  n=%d  min %.1fs  median %.1fs  max %.1fs" %
          (len(drifts), drifts[0], drifts[len(drifts)//2], drifts[-1]))

print("\ncategories:", dict(collections.Counter(
    LEAD.search(h[3]).group(1) for h in hits if LEAD.search(h[3]))))

meth = collections.Counter(METHOD.search(h[3]).group(1) for h in hits if METHOD.search(h[3]))
print("\nmethod phrases: %d distinct / %d deliveries" % (len(meth), sum(meth.values())))
for m_, n in meth.most_common(20):
    print("   ", n, "|", m_[:80])

# Does the spec quote always stop mid-word?
midword = 0
for h in hits:
    c = CUT.search(h[3])
    if c and c.group(1) and not c.group(1).rstrip().endswith((".", "!", "?")):
        midword += 1
print("\nspec quote cut before a sentence end: %d of %d" % (midword, len(hits)))

# thin/scored disposition
print("thin&unscored among them:", sum(1 for h in hits
      if h[0].get("thin") is True and h[0].get("scored") is False))

json.dump([{"seq": h[0].get("seq"), "ts": h[0].get("ts"),
            "did": h[0].get("did") or h[0].get("from"),
            "job_id": h[0].get("job_id"), "proofhash": h[1], "epoch": h[2],
            "text": h[3]} for h in hits],
          open("_r111_proofhash.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nwrote _r111_proofhash.json")
