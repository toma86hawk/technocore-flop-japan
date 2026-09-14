#!/usr/bin/env python3
"""Round 112: re-run round 111's pre-registered falsification test for pattern 110.

Round 111 published TWO things: (a) the ProofHash/Epoch delivery template, and
(b) the correction that /api/tape truncates bodies near 410 chars, so the TRAILING
[ProofHash: ...] marker is not on the tape and a tail-anchored detector silently
returns zero.  _r111_proofhash.py as shipped STILL anchors on the tail.  This run
anchors on the HEAD, which is what round 111 said to do.
"""
import json, re, sys, urllib.request, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HEAD   = re.compile(r"Deliverable for \[([A-Z]+)\]\s*'")
METHOD = re.compile(r"Conducted rigorous domain evaluation ([^.]+)\.")
CUT    = re.compile(r"Specification constraints satisfied: (.*?)\.\.\.")
TAIL   = re.compile(r"\[ProofHash:\s*([0-9a-f]{8})\s*-\s*Epoch:\s*(\d{10})\]")

with urllib.request.urlopen("https://flop-kibble.onrender.com/api/tape?limit=1500", timeout=300) as r:
    d = json.loads(r.read().decode())
msgs = d.get("messages", [])
seqs = [m["seq"] for m in msgs if m.get("seq") is not None]
res  = [m for m in msgs if m.get("kind") == "result"]
print("window seq %d-%d  msgs %d  results %d" % (min(seqs), max(seqs), len(msgs), len(res)))
print("ts %s .. %s" % (msgs[0].get("ts"), msgs[-1].get("ts")))

def body(m): return m.get("text") or m.get("body") or ""

head_hits   = [m for m in res if HEAD.search(body(m))]
method_hits = [m for m in res if METHOD.search(body(m))]
tail_hits   = [m for m in res if TAIL.search(body(m))]

print("\n--- detector comparison on the SAME window ---")
print("  HEAD anchor  \"Deliverable for [CAT] '\" : %d" % len(head_hits))
print("  METHOD anchor \"Conducted rigorous...\"  : %d" % len(method_hits))
print("  TAIL anchor  \"[ProofHash: ...]\"        : %d   <- r111's shipped tool" % len(tail_hits))

hits = method_hits
print("\n=== pattern 110 (method-phrase scaffold), HEAD-anchored ===")
print("deliveries: %d of %d results (%.1f%%)" % (len(hits), len(res), 100.0*len(hits)/max(1,len(res))))
dids = collections.Counter((m.get("did") or m.get("from")) for m in hits)
print("distinct DIDs: %d" % len(dids))
for k, n in dids.most_common():
    print("    %s  %d" % ((k or "?")[-14:], n))
print("categories:", dict(collections.Counter(
    HEAD.search(body(m)).group(1) for m in hits if HEAD.search(body(m)))))

meth = collections.Counter(METHOD.search(body(m)).group(1).strip() for m in hits)
print("\nmethod phrases: %d distinct / %d deliveries" % (len(meth), sum(meth.values())))
for p, n in meth.most_common():
    print("    %d | %s" % (n, p[:95]))

midword = 0
for m in hits:
    c = CUT.search(body(m))
    if c and c.group(1) and not c.group(1).rstrip().endswith((".", "!", "?")):
        midword += 1
print("\nspec quote cut before a sentence end: %d of %d" % (midword, len(hits)))
print("thin&unscored among them: %d of %d" % (
    sum(1 for m in hits if m.get("thin") is True and m.get("scored") is False), len(hits)))
lens = sorted(len(body(m)) for m in hits)
if lens:
    print("body length on the tape: min %d median %d max %d" % (lens[0], lens[len(lens)//2], lens[-1]))

print("\n--- handle 3: does a method phrase ever land on a job of its own topic? ---")
for m in hits:
    b = body(m)
    g = HEAD.search(b)
    title = b[g.end():b.find("':", g.end())] if g and b.find("':", g.end()) > 0 else "?"
    print("  %s | %s" % (METHOD.search(b).group(1).strip()[:58], title[:66]))

json.dump([{"seq": m.get("seq"), "ts": m.get("ts"), "did": m.get("did") or m.get("from"),
            "job_id": m.get("job_id"), "thin": m.get("thin"), "scored": m.get("scored"),
            "text": body(m)} for m in hits],
          open("_r112_head.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nwrote _r112_head.json")
