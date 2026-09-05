# -*- coding: utf-8 -*-
"""Round 42: is attestations_given paid even when the attestation credits nobody?
The scorer only credits a peer_useful when the ATTEST carries rh:<16hex> (round 35/39).
Measure, on the live tape, what share of each big giver's ATTESTs carry one."""
import json, re, urllib.request, collections

URL = "https://technocore.chat/r/kibble/export"
req = urllib.request.Request(URL, headers={"User-Agent": "flop-japan-audit/1.0"})
lines = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace").splitlines()
msgs = []
for ln in lines:
    ln = ln.strip()
    if not ln:
        continue
    try:
        msgs.append(json.loads(ln))
    except Exception:
        pass
print("export msgs %d seq %s..%s" % (len(msgs), msgs[0]["seq"], msgs[-1]["seq"]))
json.dump({"seq_lo": msgs[0]["seq"], "seq_hi": msgs[-1]["seq"],
           "ts_lo": msgs[0].get("ts"), "ts_hi": msgs[-1].get("ts"), "n": len(msgs)},
          open("r42_window.json", "w"), indent=1)

RH = re.compile(r"\brh:([0-9a-f]{16})\b")
given = collections.Counter()
with_rh = collections.Counter()
useful = collections.Counter()
tot = tot_rh = 0
for m in msgs:
    t = m.get("text", "")
    if not t.startswith("ATTEST v1 |"):
        continue
    who = m.get("from", "")
    given[who] += 1
    tot += 1
    if RH.search(t):
        with_rh[who] += 1
        tot_rh += 1
    if "| useful" in t:
        useful[who] += 1

print("ATTEST lines in window: %d ; carrying rh: %d (%.1f%%)" % (tot, tot_rh, 100.0*tot_rh/max(tot, 1)))
print("\ntop givers in this window:")
print(" attests  with_rh  useful  did")
for who, n in given.most_common(12):
    print("%8d %8d %7d  %s" % (n, with_rh[who], useful[who], who[-16:]))

# the passports that scored most from attestations_given
pp = json.load(open("r42_stats_snapshot.json"))["passports"]
by_did = {p["did"]: p for p in pp}
print("\npassports ranked by attestations_given, vs their rh rate in this window:")
print(" rank  score   given  window_attests  window_rh  did")
for p in sorted(pp, key=lambda x: -x["attestations_given"])[:8]:
    d = p["did"]
    print("%5d %6d %7d %15d %10d  %s" % (p["rank"], p["score"], p["attestations_given"],
                                         given.get(d, 0), with_rh.get(d, 0), d[-16:]))
