# -*- coding: utf-8 -*-
"""Does the delivery pool fleet overlap the round-39 attestation pool fleet,
and do they certify each other?"""
import json, sys, collections, re
sys.stdout.reconfigure(encoding="utf-8")

R39_FLEET = ["did:key:z6Mkg1fcXUmrcyqAKNFzonKM6jbjNRGz6pv3nKnNYAmaVjcu",
"did:key:z6Mkgp35PmWiXmHF9Roxy6gi7jjpk8a3hpUwkjPpF5SAX7pk",
"did:key:z6MkoenXa6Aq4TfDgLQKLceDzwUxJtPvz7FE3m9ScCKMDgTy",
"did:key:z6MksAndcR4WxMuRVeArnyAJRBUVNX6fBfefGa8hVkbvE1PM",
"did:key:z6MktMPgccidNheUYx6LJticsc6zwEEJsxeZwsup6DBWgBFY",
"did:key:z6MkvK9EdVMB3mZLdcz2umXfZ6Y48igzBAoNPRz53sLKcxQj"]

pool = json.load(open("r41_pool.json", encoding="utf-8"))
deliv_fleet = sorted({d for c in pool["cross_did_clusters"].values() for d in c["dids"]})
pool_jobs = {j for c in pool["cross_did_clusters"].values() for j in c["jobs"]}
print("delivery-pool DIDs", len(deliv_fleet), " pooled jobs", len(pool_jobs))
print("overlap with round-39 attestation fleet:", sorted(set(deliv_fleet) & set(R39_FLEET)))

m = json.load(open("r41_export.json", encoding="utf-8"))
att = []
for x in m:
    t = x.get("text") or ""
    if not t.startswith("ATTEST v1"):
        continue
    p = [s.strip() for s in t.split("|")]
    if len(p) < 4:
        continue
    job, verdict = p[1], p[2].lower()
    rh = ""
    reason = ""
    rest = p[3:]
    if rest and rest[0].startswith("rh:"):
        rh = rest[0][3:]
        reason = "|".join(rest[1:]).strip()
    else:
        reason = "|".join(rest).strip()
    att.append({"seq": x["seq"], "did": x.get("from"), "job": job, "verdict": verdict, "rh": rh, "reason": reason})
print("attest lines", len(att))

# reason strings used by >=2 distinct DIDs  (round-39 detector, re-run on this window)
by_reason = collections.defaultdict(list)
for a in att:
    if a["reason"]:
        by_reason[a["reason"]].append(a)
shared = {r: v for r, v in by_reason.items() if len({a["did"] for a in v}) >= 2}
sh_lines = sum(len(v) for v in shared.values())
att_fleet = sorted({a["did"] for v in shared.values() for a in v})
print("reason strings shared by >=2 DIDs: %d strings, %d attest lines (%.1f%%), %d DIDs"
      % (len(shared), sh_lines, 100.0 * sh_lines / max(1, len(att)), len(att_fleet)))
print("overlap delivery-pool fleet vs attest-pool fleet:", sorted(set(att_fleet) & set(deliv_fleet)))

# who certifies the pooled deliveries?
on_pool = [a for a in att if a["job"] in pool_jobs]
useful_on_pool = [a for a in on_pool if a["verdict"] == "useful"]
cred = [a for a in useful_on_pool if re.fullmatch(r"[0-9a-f]{16}", a["rh"] or "")]
print("\nATTESTs landing on the 550 pooled jobs: %d  (useful %d, of which creditable 16-hex rh %d)"
      % (len(on_pool), len(useful_on_pool), len(cred)))
c = collections.Counter(a["did"] for a in useful_on_pool)
for d, n in c.most_common(8):
    print("   useful-on-pool %3d  ...%s   in_delivery_fleet=%s" % (n, d[-12:], d in deliv_fleet))
print("not-verdicts on pooled jobs:", sum(1 for a in on_pool if a["verdict"] == "not"))
json.dump({"delivery_fleet": deliv_fleet, "attest_fleet": att_fleet,
           "shared_reasons": {r: sorted({a["did"] for a in v}) for r, v in shared.items()}},
          open("r41_ring.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
