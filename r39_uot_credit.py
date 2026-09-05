# -*- coding: utf-8 -*-
"""useful-on-thin, split by whether the ATTEST can actually be credited (16-hex rh).
Uses the host's OWN thin/scored flags from /api/tape, so it stays comparable to the series."""
import json, re, sys, collections, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d = json.loads(urllib.request.urlopen("https://flop-kibble.onrender.com/api/tape?limit=1500", timeout=120).read())
msgs = d.get("messages", [])
seqs = [m["seq"] for m in msgs if m.get("seq") is not None]
print("window msgs", len(msgs), "seq", min(seqs), "-", max(seqs))
results = [m for m in msgs if m.get("kind") == "result"]
thin_jobs = {m.get("job_id") for m in results if m.get("thin") is True and m.get("scored") is False}
att = [m for m in msgs if m.get("kind") == "attest"]
useful = [m for m in att if str(m.get("verdict","")).lower() == "useful"]
RH = re.compile(r"\brh:([0-9a-fA-F]+)")
def rh(m):
    g = RH.search(m.get("text") or "")
    return g.group(1) if g else None
def cred(m):
    v = rh(m); return bool(v) and len(v) == 16
C = [m for m in useful if cred(m)]
N = [m for m in useful if not cred(m)]
print("useful total %d | creditable %d (%.1f%%) | no-op %d (%.1f%%)"
      % (len(useful), len(C), 100.0*len(C)/len(useful), len(N), 100.0*len(N)/len(useful)))
for lab, rows in (("ALL useful    ", useful), ("CREDITABLE only", C), ("NO-OP only     ", N)):
    on = sum(1 for m in rows if m.get("job_id") in thin_jobs)
    print("  %s : useful-on-thin %4d / %4d = %.1f%%" % (lab, on, len(rows), 100.0*on/max(1,len(rows))))
print("\ndistinct attestors: all %d | creditable %d | no-op %d"
      % (len({m.get('did') or m.get('from') for m in useful}),
         len({m.get('did') or m.get('from') for m in C}),
         len({m.get('did') or m.get('from') for m in N})))
c = collections.Counter((m.get('did') or m.get('from')) for m in N)
print("top no-op attestors:", [(k[-12:], v) for k, v in c.most_common(8)])
