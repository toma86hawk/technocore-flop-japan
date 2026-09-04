#!/usr/bin/env python3
"""r35: settle `useful_without_rh` (open since 2026-08-31).
Classify every ATTEST in the window by its rh field, then check the engine's
attestations_given for the attestors of each class."""
import json, collections, re, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

msgs = json.load(open("r35_export.json"))
att = [m for m in msgs if (m.get("text") or "").startswith("ATTEST v1")]
RH = re.compile(r"\brh:([0-9a-fA-F]+)")

cls = collections.Counter()
per_did = collections.defaultdict(collections.Counter)
for m in att:
    g = RH.search(m["text"])
    if not g:
        k = "absent"
    elif len(g.group(1)) == 16:
        k = "16hex"
    else:
        k = "short:%d" % len(g.group(1))
    cls[k] += 1
    per_did[m["from"]][k] += 1

n = len(att)
print("ATTEST lines in window:", n)
for k, c in cls.most_common():
    print("   rh %-9s %4d  (%.1f%%)" % (k, c, 100.0 * c / n))
bad = n - cls["16hex"]
print("   -> uncreditable by shape: %d / %d = %.1f%%" % (bad, n, 100.0 * bad / n))

pop = {r["did"]: r for r in json.load(open("r35_rh_population.json"))}
print("\nattestors >=8 attests, cross-checked against /api/score attestations_given:")
print("%-16s %5s %6s %6s %7s %7s" % ("did-tail", "att", "16hex", "absent", "short", "given"))
for d, r in sorted(pop.items(), key=lambda kv: -kv[1]["att"]):
    c = per_did[d]
    short = sum(v for k, v in c.items() if k.startswith("short"))
    print("%-16s %5d %6d %6d %7d %7s" % (d[-14:], r["att"], c["16hex"], c["absent"], short, r["given"]))

grp = {"all-16hex": [], "no-16hex": []}
for d, r in pop.items():
    c = per_did[d]
    (grp["all-16hex"] if c["16hex"] == r["att"] else grp["no-16hex"]).append(r["given"] or 0)
print("\nattestors whose window lines are ALL 16-hex : n=%d, given==0 in %d"
      % (len(grp["all-16hex"]), sum(1 for g in grp["all-16hex"] if g == 0)))
print("attestors with ANY non-16-hex line          : n=%d, given==0 in %d"
      % (len(grp["no-16hex"]), sum(1 for g in grp["no-16hex"] if g == 0)))
