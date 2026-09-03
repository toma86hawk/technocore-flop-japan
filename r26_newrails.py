#!/usr/bin/env python3
"""Round 26: who is posting the offer rails/assets that were NOT present at the
round-20 tclk_asset_gap measurement (evm-htlc, paper-htlc, flop-direct,
alpha-test-only-no-settlement) and the per-run FLOP-E2E-<id> assets?

Baseline (2026-09-03 ~03:5x, tclk_asset_gap.py): rails were only
paper / flop-htlc / PaperRail / paper-rail / x402; assets only FLOP / PAPER /
PAPER-REHEARSAL. Everything else in known_offer_* is newer than that.
"""
import json, sys, urllib.request, collections
sys.path.insert(0, ".")
import tclk1

ORIGIN = "https://technocore.chat"
NEW_RAILS = {"evm-htlc", "paper-htlc", "flop-direct", "alpha-test-only-no-settlement"}

raw = urllib.request.urlopen(ORIGIN + "/r/tclk-offers/export", timeout=90).read().decode("utf-8", "replace")
rows = []
for line in raw.splitlines():
    try:
        m = json.loads(line)
    except Exception:
        continue
    t = m.get("text", "")
    if not tclk1.is_tclk_line(t):
        continue
    try:
        fr = json.loads(t[len(tclk1.TCLK_PREFIX):])
    except Exception:
        continue
    rows.append((m, fr))

print("total tclk frames in tclk-offers:", len(rows))
offers = [(m, f) for m, f in rows if f.get("type") == "offer"]
print("offers:", len(offers))

hits = []
for m, f in offers:
    rails = f.get("rails") or ([f["rail"]] if f.get("rail") else [])
    asset = f.get("asset") or ""
    if (set(rails) & NEW_RAILS) or asset.startswith("FLOP-E2E") or asset == "ALPHA_TEST_ONLY":
        hits.append((m, f, rails, asset))

print("hits:", len(hits))
by_did = collections.Counter()
for m, f, rails, asset in sorted(hits, key=lambda x: x[0].get("ts") or ""):
    did = m.get("did") or m.get("from") or "?"
    by_did[did] += 1
    print("-", m.get("ts"), did[-14:], "rails=", rails, "asset=", asset,
          "amount=", f.get("amount"), "id=", (f.get("id") or "")[:20])
print("by_did:", by_did.most_common())

# earliest/latest timestamps of the whole offer stream for context
ts = sorted([m.get("ts") for m, f in offers if m.get("ts")])
print("offer ts range:", ts[0] if ts else None, "->", ts[-1] if ts else None)
