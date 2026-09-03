"""r27 / pattern 49: pseudo-proof markers that are just a clock.

Several workers append authority markers to deliverables:
  [ProofHash: <8 hex> - Epoch: <unix>]      and      Ref:<jobsuffix>-<unix>
They look like a commitment. This decodes the Epoch and compares it to the
message's own post time. If Epoch == post time, the marker binds nothing: it is
a timestamp wearing the costume of a proof, and it cannot be checked against anything.
Second question: is the marker confined to one DID, or is one generator behind several?

usage: python r27_selfdating.py <tape_window.json>
"""
import json,re,sys,collections,datetime

W=sys.argv[1] if len(sys.argv)>1 else None
msgs=json.load(open(W))["messages"]

PROOF=re.compile(r"\[ProofHash:\s*([0-9a-f]{6,})\s*-\s*Epoch:\s*(\d{10})\]")
REF  =re.compile(r"Ref:([0-9a-f]{4,})-(\d{10})")

def ts_of(m):
    t=m.get("ts") or m.get("time") or ""
    try: return datetime.datetime.fromisoformat(t.replace("Z","+00:00")).timestamp()
    except Exception: return None

hits=[]
for m in msgs:
    if m.get("kind")!="result": continue
    txt=m.get("text") or ""
    for rx,name in ((PROOF,"ProofHash"),(REF,"Ref")):
        for h,e in rx.findall(txt):
            hits.append((name,m.get("seq"),(m.get("did") or m.get("from") or ""),
                         m.get("job_id"),h,int(e),ts_of(m)))

print(f"window results: {sum(1 for m in msgs if m.get('kind')=='result')}, marker-bearing: {len(hits)}")
dids=collections.Counter(h[2] for h in hits)
print(f"distinct DIDs emitting a marker: {len(dids)}")
for d,c in dids.most_common(): print(f"   ...{d[-12:]}  {c}")

print("\nEpoch vs the message's own post time:")
deltas=[]
for name,seq,did,job,h,e,t in sorted(hits,key=lambda x:x[5]):
    d = None if t is None else e-t
    if d is not None: deltas.append(d)
    print(f"  {name:9s} seq {seq} ...{did[-12:]} {job} h={h} "
          f"epoch={datetime.datetime.utcfromtimestamp(e).isoformat()}Z "
          f"delta_vs_post={'n/a' if d is None else f'{d:+.0f}s'}")
if deltas:
    print(f"\n  delta range {min(deltas):+.0f}s .. {max(deltas):+.0f}s over {len(deltas)} markers")
    print("  => the 'proof' is the post clock; it commits to no input and no output.")

if hits:
    span=max(h[5] for h in hits)-min(h[5] for h in hits)
    print(f"\nall markers in window span {span}s of wall clock across {len(dids)} DIDs")
    hexes=[h[4] for h in hits]
    print(f"distinct hashes {len(set(hexes))} / {len(hexes)} -> "
          f"{'unique per post (no reuse to catch)' if len(set(hexes))==len(hexes) else 'REUSED'}")
