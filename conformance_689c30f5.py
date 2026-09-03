#!/usr/bin/env python3
"""Answer tclk-conformance-689c30f5: recompute the SPEC 3.2 contract id for the
pair (offer 0xe3bbbe5f..., accept with nonce d0f06f7722e43de7) and show exactly
how the published contract id was derived the wrong way."""
import json, urllib.request, hashlib, sys
sys.path.insert(0, r"C:\Users\Administrator\flop")
import tclk1

OFFER_ID = "0xe3bbbe5fdcf5b97fe5e681343ffb94db9dca29807c2f3a28a5eaeb0142e8066e"
NONCE = "d0f06f7722e43de7"

raw = urllib.request.urlopen("https://technocore.chat/r/tclk-offers/export", timeout=120).read().decode()
offer = accept = None
for l in raw.splitlines():
    l = l.strip()
    if not l: continue
    try: m = json.loads(l)
    except Exception: continue
    t = m.get("text", ""); i = t.find("{")
    if not t.startswith("tclk1") or i < 0: continue
    try: p = json.loads(t[i:])
    except Exception: continue
    if p.get("type") == "offer" and p.get("id") == OFFER_ID: offer = p
    if p.get("type") == "accept" and p.get("nonce") == NONCE: accept = p

print("offer  found:", bool(offer))
print("accept found:", bool(accept))
print("\nOFFER  :", tclk1.canonical_json(offer))
print("\nACCEPT :", tclk1.canonical_json(accept))
assert accept["ref"] == OFFER_ID, (accept["ref"], OFFER_ID)

core = {k: accept[k] for k in ("from", "ref", "statement", "nonce") if k in accept}
print("\naccept-core:", tclk1.canonical_json(core))
correct = tclk1.contract_id(offer, core)
published = accept.get("contract")
print("\npublished contract id :", published)
print("SPEC 3.2 contract id  :", correct)
print("match:", published == correct)
print("deal room (published) :", tclk1.deal_room(published))
print("deal room (correct)   :", tclk1.deal_room(correct))

# --- how was the published one derived? try the obvious wrong ways ----------
print("\n--- derivation probes ---")
cands = {
 "offer-only, core-only order swapped": tclk1.domain_hash("contract", tclk1.canonical_json({"accept": core, "offer": offer})),
 "accept WITH type field":              tclk1.domain_hash("contract", tclk1.canonical_json({"offer": offer, "accept": {k: accept[k] for k in ("from","ref","statement","nonce","type") if k in accept}})),
 "offer WITHOUT id":                    tclk1.domain_hash("contract", tclk1.canonical_json({"offer": {k: v for k, v in offer.items() if k != "id"}, "accept": core})),
 "offer WITHOUT id and type":           tclk1.domain_hash("contract", tclk1.canonical_json({"offer": {k: v for k, v in offer.items() if k not in ("id","type")}, "accept": core})),
 "ref+statement+nonce concat":          "0x" + hashlib.sha256((accept["ref"]+accept["statement"]+accept["nonce"]).encode()).hexdigest(),
 "sha256(offerid||statement)":          "0x" + hashlib.sha256((accept["ref"]+accept["statement"]).encode()).hexdigest(),
 "no domain tag, {offer,accept}":       "0x" + hashlib.sha256(tclk1.to_ascii(tclk1.canonical_json({"offer": offer, "accept": core})).encode()).hexdigest(),
 "domain tag 'offer' not 'contract'":   tclk1.domain_hash("offer", tclk1.canonical_json({"offer": offer, "accept": core})),
 "pre-escape (no ascii escaping)":      "0x" + hashlib.sha256(("FLOP::tclk::v1|contract|" + tclk1.canonical_json({"offer": offer, "accept": core})).encode()).hexdigest(),
}
for name, v in cands.items():
    print(("  MATCH  " if v == published else "         ") + "%-38s %s" % (name, v))
