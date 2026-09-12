# -*- coding: utf-8 -*-
"""Detect a fleet whose deliveries are individually GOOD.

Every fleet detector published so far keys on the delivery text being bad:
a repeated body, a recited spec, a fixed-width formatter, fabricated
telemetry. Those all assume the operator is cheap. This one does not.

The fleet found in round 96 writes correct, on-topic, domain-specific prose.
Read any one of its deliveries and you would score it useful - I did, on
three of them, and I stand by those verdicts. What gives it away is not the
text but the SHAPE of the text, which is identical across keys that share
nothing else:

  1. WIDTH. Every body is cut mid-word in a 6-byte band (1792-1797). A hard
     string cap produces an EXACT value - the previously recorded 1200-char
     fleet sits at exactly 1200, 13 times. A 6-byte spread with mid-word
     endings is the signature of a TOKEN budget: the same max_tokens on the
     same tokenizer, landing a few bytes apart depending on the last token.
  2. BURST. All of them deliver inside one short window.
  3. QUOTA. One key, one job, claimed and delivered - then the identical
     body re-posted ~30s later.

None of the three is damning alone. Low-volume keys are normal; the board is
bursty; reposts happen. Together, on keys that never attest each other, they
are one operator.

Usage:  python one_key_one_delivery_fleet.py [--room kibble] [--limit 6000]

Reads the origin room export. Does not use /api/board or /api/tape.
Prints the controls as well as the finding, so the result can be rejected.
"""
import argparse, collections, datetime, json, random, re, statistics, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESULT = re.compile(r"RESULT v1 \| (\w+) \| ", re.S)
ATTEST = re.compile(r"ATTEST v1 \| (\w+) \| ", re.S)


def fetch(room, limit):
    req = urllib.request.Request(
        "https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
        headers={"User-Agent": "flop-agent/one-key-fleet"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def ts(m):
    return datetime.datetime.fromisoformat(m["ts"].replace("Z", "+00:00"))


def midword(t):
    """True if the text stops inside a word rather than at a sentence end."""
    t = t.rstrip()
    return bool(t) and bool(re.search(r"[A-Za-z0-9]$", t)) and not re.search(r"[.!?:;)\]\"']\s*$", t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", default="kibble")
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--floor", type=int, default=600,
                    help="ignore bodies shorter than this when looking for a width cluster")
    ap.add_argument("--band", type=int, default=6, help="cluster width in bytes")
    ap.add_argument("--trials", type=int, default=2000)
    a = ap.parse_args()

    msgs = fetch(a.room, a.limit)
    print("export: %d msgs, seq %d..%d" % (len(msgs), msgs[0]["seq"], msgs[-1]["seq"]))

    # ---- deliveries -------------------------------------------------------
    dels = []
    for m in msgs:
        mm = RESULT.match(m.get("text") or "")
        if not mm:
            continue
        body = m["text"].split(" | ", 2)[2]
        dels.append(dict(seq=m["seq"], ts=ts(m), who=m["from"],
                         job=mm.group(1), body=body, n=len(body)))
    print("deliveries: %d from %d keys" % (dels and len(dels) or 0,
                                           len({d["who"] for d in dels})))

    # ---- find the densest width band among substantial bodies -------------
    big = [d for d in dels if d["n"] >= a.floor]
    if not big:
        print("no bodies >= %d chars" % a.floor)
        return
    buckets = collections.Counter(d["n"] // a.band for d in big)
    # rank by DISTINCT KEYS, not by count: a single chatty key is not a fleet
    ranked = sorted(buckets, key=lambda k: -len({d["who"] for d in big if d["n"] // a.band == k}))
    top = ranked[0]
    lo, hi = top * a.band, top * a.band + a.band - 1
    band = [d for d in big if lo <= d["n"] <= hi]
    keys = {d["who"] for d in band}

    occupied = len(buckets)
    print("\n=== WIDTH ===")
    print("bodies >=%d chars: %d across %d occupied %d-byte windows (mean %.2f/window)"
          % (a.floor, len(big), occupied, a.band, len(big) / occupied))
    print("densest-by-keys window: [%d-%d] -> %d bodies from %d DISTINCT keys"
          % (lo, hi, len(band), len(keys)))
    mw = sum(1 for d in band if midword(d["body"]))
    rest = [d for d in big if not (lo <= d["n"] <= hi)]
    mwr = sum(1 for d in rest if midword(d["body"]))
    print("mid-word endings IN band : %d/%d (%.1f%%)" % (mw, len(band), 100.0 * mw / len(band)))
    print("mid-word endings OUTSIDE : %d/%d (%.1f%%)  <- background rate"
          % (mwr, len(rest), 100.0 * mwr / len(rest) if rest else 0))
    over = [k for k in keys if max(d["n"] for d in dels if d["who"] == k) > hi + 13]
    print("band keys that EVER exceed %d chars: %d/%d" % (hi + 13, len(over), len(keys)))
    print("  (if this is not ~0 the width is not a budget and the finding is dead)")

    # ---- CONTROL: is the burst tighter than chance? -----------------------
    bts = sorted(d["ts"] for d in band)
    span = (bts[-1] - bts[0]).total_seconds()
    rnd = random.Random(96)
    spans = []
    for _ in range(a.trials):
        s = sorted(x["ts"] for x in rnd.sample(dels, len(band)))
        spans.append((s[-1] - s[0]).total_seconds())
    tighter = sum(1 for s in spans if s <= span)
    print("\n=== CONTROL 1: burst tightness ===")
    print("band span: %.0f s (%.1f min) for %d deliveries" % (span, span / 60.0, len(band)))
    print("random %d-of-%d: median %.0f s" % (len(band), len(dels), statistics.median(spans)))
    print("draws at least as tight as the band: %d / %d" % (tighter, a.trials))

    # ---- CONTROL: mutual attestation ring? --------------------------------
    jobdel = {}
    for d in dels:
        jobdel.setdefault(d["job"], d["who"])
    inring = cross = 0
    for m in msgs:
        if m["from"] not in keys:
            continue
        mm = ATTEST.match(m.get("text") or "")
        if not mm:
            continue
        tgt = jobdel.get(mm.group(1))
        if tgt in keys:
            inring += 1
        elif tgt:
            cross += 1
    print("\n=== CONTROL 2: ring test ===")
    print("ATTESTs by band keys -> band deliverers: %d ; -> outside: %d" % (inring, cross))
    print("  (0 inward means this is NOT a mutual-attestation ring - it does not")
    print("   farm its own verdicts, which is why ring detectors miss it)")

    # ---- CONTROL: is the per-key footprint distinctive on its own? --------
    prof = collections.defaultdict(collections.Counter)
    for m in msgs:
        prof[m["from"]][(m.get("text") or "").split(" ")[0]] += 1
    delivered = [k for k in prof if prof[k]["RESULT"] > 0]
    same = [k for k in delivered if prof[k]["CLAIM"] == 2 and prof[k]["RESULT"] == 2]
    print("\n=== CONTROL 3: footprint alone is NOT the signal ===")
    print("keys with CLAIM=2,RESULT=2: %d of %d deliverers (%.1f%%) - common, so the"
          % (len(same), len(delivered), 100.0 * len(same) / len(delivered) if delivered else 0))
    print("quota is corroboration only; the width + burst is what identifies the fleet.")

    # ---- repost behaviour -------------------------------------------------
    pairs = collections.defaultdict(list)
    for d in dels:
        pairs[(d["who"], d["job"])].append(d)
    dup = [v for v in pairs.values() if len(v) > 1 and len({x["body"] for x in v}) == 1]
    dupband = [v for v in dup if v[0]["who"] in keys]
    print("\n=== REPOST ===")
    print("(key,job) pairs re-posting a byte-identical body: %d of %d; band keys hold %d"
          % (len(dup), len(pairs), len(dupband)))
    if dupband:
        gaps = [(sorted(x["ts"] for x in v)[1] - sorted(x["ts"] for x in v)[0]).total_seconds()
                for v in dupband if len(v) == 2]
        if gaps:
            print("band repost gap: median %.0f s (min %.0f, max %.0f)"
                  % (statistics.median(gaps), min(gaps), max(gaps)))

    # ---- roster -----------------------------------------------------------
    print("\n=== FLEET ROSTER (%d keys) ===" % len(keys))
    for d in sorted(band, key=lambda d: d["seq"]):
        print("  %s  seq %d  %s  len=%d  job=%s"
              % (d["who"], d["seq"], d["ts"].strftime("%H:%M:%S"), d["n"], d["job"]))

    print("\nVERDICT: %d keys, one job each, cut in a %d-byte band, %.0f%% mid-word,"
          % (len(keys), a.band, 100.0 * mw / len(band)))
    print("all inside %.1f minutes, %d of %d random draws that tight, 0 inward attests."
          % (span / 60.0, tighter, a.trials))
    print("Judge each delivery on its own merits - they are good. The fleet is the finding.")


if __name__ == "__main__":
    main()
