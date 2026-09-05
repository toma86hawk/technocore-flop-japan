# -*- coding: utf-8 -*-
"""useful-on-thin with the round-39 correction: report both the all-useful column
and the creditable column (verdicts carrying a 16-hex rh, the only ones the engine scores)."""
import json, sys, re, collections, glob
sys.stdout.reconfigure(encoding="utf-8")
f = sorted(glob.glob("useful_on_thin_20260905-21*.json"))[-1]
d = json.load(open(f, encoding="utf-8")); msgs = d.get("messages", [])
print("file", f, "msgs", len(msgs))
results = [m for m in msgs if m.get("kind") == "result"]
thin_jobs = {m.get("job_id") for m in results if m.get("thin") is True and m.get("scored") is False}
att = [m for m in msgs if m.get("kind") == "attest"]
useful = [m for m in att if str(m.get("verdict", "")).lower() == "useful"]
def rh_of(m):
    t = m.get("text") or ""
    g = re.search(r"rh:([0-9a-f]+)", t)
    return g.group(1) if g else ""
cred = [m for m in useful if re.fullmatch(r"[0-9a-f]{16}", rh_of(m))]
uot = [m for m in useful if m.get("job_id") in thin_jobs]
cred_uot = [m for m in cred if m.get("job_id") in thin_jobs]
print("results %d thin_unscored_jobs %d" % (len(results), len(thin_jobs)))
print("useful %d  -> on thin %d  = %.1f%%" % (len(useful), len(uot), 100.0*len(uot)/max(1,len(useful))))
print("creditable useful %d (%.1f%% of useful) -> on thin %d = %.1f%%"
      % (len(cred), 100.0*len(cred)/max(1,len(useful)), len(cred_uot), 100.0*len(cred_uot)/max(1,len(cred))))
