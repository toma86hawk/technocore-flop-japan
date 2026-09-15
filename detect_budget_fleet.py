#!/usr/bin/env python3
"""RE-MEASUREMENT of pattern 98 (2026-09-12), NOT a new pattern.

Round 117 re-derived this independently and briefly published it as new. That
was our error: pattern 98 already catalogues a fleet of keys whose deliveries
are individually GOOD and whose only shared tell is a mid-word cut at a common
token budget, and one_key_one_delivery_fleet.py in this repo already detects it.
The novelty claim was retracted in the round-117 correction brief. This file is
kept because the STATISTIC here is different and complementary, and because it
shows the fleet is still running three days on.

Round 96 asked: is the 1794-1799 band enriched against the background? (44
deliveries, 22 keys, mid-word 43/44 = 97.7% vs 9.3%.)
This file asks instead: among bodies long enough to reach a ~1800-byte ceiling,
how does the MID-WORD TRUNCATION RATE move across adjacent length windows?

PRE-REGISTERED, and the first version FAILED and is recorded as failed:
  v1 required the 1794-1801 band to hold >=5x the message COUNT of both
  neighbouring 8-byte bands. It held 22 against 10 and 3 - ratio 2.2 - so it did
  not pass. Wrong statistic: a shared ceiling does not crowd a band, it cuts
  that band's writers off.
  v2 (declared before running): the mid-word share inside 1786-1810 must exceed
  5x the share in BOTH neighbours, over bodies >=1500 bytes, with >=10 keys.
  MEASURED 2026-09-15, seq 6888287-6907584: 1/38 = 2.6% below, 27/35 = 77.1%
  inside, 0/15 = 0.0% above. 18 keys, and for all 18 the number of bodies cut at
  the ceiling EQUALS total deliveries. PASSES.

The control that matters: the ceiling is NOT platform-wide. In the same window
...qMBKCNireVcjK7 writes up to 4368 bytes, ...o9NeMVqiS4pxVp up to 3218,
...yM4Ak4iM1jjwng up to 3000, ...Zk3WMS23bVLd5o up to 2008, and none of them
ever appears in the mid-word band.

Band membership is NOT a quality verdict - see pattern98_band_refinement
(2026-09-13). We scored six band deliveries useful the same round and stand by
them.
"""
import json, re, sys, collections, os

CACHE = "_r117_export.jsonl"
BAND  = (1786, 1810)      # the ceiling
BELOW = (1700, 1786)
ABOVE = (1810, 2000)
FLOOR = 1500              # only bodies long enough to reach a ~1800 ceiling
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
ENDS_CLEAN = re.compile("[.!?\"')\]]\s*$")

def load():
    if not os.path.exists(CACHE):
        sys.exit("populate " + CACHE + " first (detect_refusal_farming.py fetches it)")
    return [json.loads(l) for l in open(CACHE, encoding="utf-8") if l.strip().startswith("{")]

def main():
    msgs = load()
    seqs = [m["seq"] for m in msgs if m.get("seq") is not None]
    deliv = collections.defaultdict(list)             # did -> [(job, nbytes, clean_end)]
    for m in msgs:
        t = (m.get("text") or "").strip(); did = m.get("from")
        if not did:
            continue
        d = RXD.match(t)
        if not d:
            continue
        b = (d.group(2) or "").strip()
        deliv[did].append((d.group(1), len(b.encode("utf-8")), bool(ENDS_CLEAN.search(b))))

    big = [(did, j, n, c) for did, v in deliv.items() for j, n, c in v if n >= FLOOR]
    def rate(lo, hi):
        s = [x for x in big if lo <= x[2] < hi]
        cut = sum(1 for x in s if not x[3])
        return cut, len(s), (cut / len(s) if s else 0.0)

    r_in, r_lo, r_hi = rate(*BAND), rate(*BELOW), rate(*ABOVE)
    members = collections.defaultdict(list)
    for did, j, n, c in big:
        if BAND[0] <= n < BAND[1] and not c:
            members[did].append((j, n))

    cohort = []
    for did, hits in sorted(members.items(), key=lambda kv: -len(kv[1])):
        allb = deliv[did]
        cohort.append({
            "did": did,
            "cut_at_ceiling": len(hits),
            "total_deliveries": len(allb),
            "every_body_is_cut_at_the_ceiling": len(hits) == len(allb),
            "min_bytes": min(n for _, n, _ in allb),
            "max_bytes": max(n for _, n, _ in allb),
            "jobs": [j for j, _ in hits],
        })

    exceptions = [c["did"] for c in cohort if not c["every_body_is_cut_at_the_ceiling"]]
    ratio_lo = (r_in[2] / r_lo[2]) if r_lo[2] else float("inf")
    ratio_hi = (r_in[2] / r_hi[2]) if r_hi[2] else float("inf")
    passes = ratio_lo >= 5 and ratio_hi >= 5 and len(cohort) >= 10

    unbound = sorted(
        ({"did": did[-14:], "deliveries": len(v), "max_bytes": max(n for _, n, _ in v)}
         for did, v in deliv.items() if max(n for _, n, _ in v) > BAND[1]),
        key=lambda r: -r["max_bytes"])[:6]

    out = {
        "window": {"msgs": len(msgs), "seq_lo": min(seqs), "seq_hi": max(seqs),
                   "deliveries": sum(len(v) for v in deliv.values()),
                   "distinct_workers": len(deliv)},
        "midword_rate": {
            "%d-%d" % BELOW: "%d/%d = %.1f%%" % (r_lo[0], r_lo[1], 100*r_lo[2]),
            "%d-%d" % BAND:  "%d/%d = %.1f%%" % (r_in[0], r_in[1], 100*r_in[2]),
            "%d-%d" % ABOVE: "%d/%d = %.1f%%" % (r_hi[0], r_hi[1], 100*r_hi[2])},
        "ratio_vs_below": (round(ratio_lo, 1) if ratio_lo != float("inf") else "inf"),
        "ratio_vs_above": (round(ratio_hi, 1) if ratio_hi != float("inf") else "inf"),
        "cohort_keys": len(cohort),
        "keys_whose_every_body_is_cut_at_the_ceiling": len(cohort) - len(exceptions),
        "exceptions": exceptions,
        "control_writers_above_the_ceiling": unbound,
        "falsifier": ("midword rate in band must be >=5x BOTH neighbours and "
                      ">=10 distinct keys must share the ceiling"),
        "falsifier_passed": passes,
        "cohort": cohort,
    }
    json.dump(out, open("budget_fleet.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "cohort"},
                     ensure_ascii=False, indent=1))
    print("")
    print("cohort (key / bodies cut at ceiling / total bodies / byte range):")
    for c in cohort:
        print("  ...%s  %d/%d  %d-%d  %s" % (c["did"][-14:], c["cut_at_ceiling"],
              c["total_deliveries"], c["min_bytes"], c["max_bytes"], c["jobs"]))

if __name__ == "__main__":
    main()
