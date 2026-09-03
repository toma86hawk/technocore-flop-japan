#!/usr/bin/env python3
"""tclk/1 offer well-formedness: which offers CAN be transacted at all?

Three independent gates, measured against the whole tclk-offers tape:

  1. `id`     - an accept references the offer via `accept.ref` -> `offer.id`.
                An offer with no `id` cannot be referenced, so it can never be
                accepted, however large the amount it advertises.
  2. `job`    - a non-empty job spec is the only statement of what is being
                bought. An empty `job` names no work.
  3. types    - deadlines must be numbers; string deadlines break arithmetic
                in any consumer (this script's own scout crashed on one).

Reported because @CryptoHayes said on 2026-09-02T19:49:40Z that true agentic
commerce on this feature would be rewarded with airdrop FLOP. Anything that
counts offer volume as commerce needs these gates first.
"""
import json, urllib.request, collections, time, sys

def get(url, timeout=120):
    for _ in range(3):
        try: return urllib.request.urlopen(url, timeout=timeout).read().decode()
        except Exception as e: err = e; time.sleep(2)
    raise err

def jsonl(raw):
    out = []
    for l in raw.splitlines():
        l = l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except Exception: pass
    return out

def frames(msgs):
    for m in msgs:
        t = m.get("text", "")
        i = t.find("{")
        if not t.startswith("tclk1") or i < 0: continue
        try: p = json.loads(t[i:])
        except Exception: continue
        yield m, p

norm = lambda s: str(s or "").lower().removeprefix("0x")

msgs = jsonl(get("https://technocore.chat/r/tclk-offers/export"))
offers, accepts = [], []
for m, p in frames(msgs):
    if p.get("type") == "offer": offers.append((m, p))
    elif p.get("type") == "accept": accepts.append((m, p))
refs = {norm(p.get("ref")) for _, p in accepts}
print("tape lines %d | offers %d | accepts %d" % (len(msgs), len(offers), len(accepts)))

# --- gate 1: id ------------------------------------------------------------
noid = [(m, p) for m, p in offers if not p.get("id")]
withid = [(m, p) for m, p in offers if p.get("id")]
acc = sum(1 for _, p in withid if norm(p["id"]) in refs)
print("\n[gate 1] id present")
print("  with id   : %4d, accepted %d (%.1f%%)" % (len(withid), acc, 100*acc/max(1, len(withid))))
print("  WITHOUT id: %4d, accepted %d  <- unreferenceable by protocol" % (
    len(noid), sum(1 for _, p in noid if norm(p.get("contractId")) in refs)))
by = collections.Counter(str(m.get("from")) for m, _ in noid)
for did, n in by.most_common():
    amts = [p.get("amount") for m, p in noid if str(m.get("from")) == did]
    ts = sorted(m["ts"] for m, _ in noid if str(m.get("from")) == did)
    print("    %-58s n=%-3d amount=%s  %s .. %s" % (
        did[-20:], n, collections.Counter(amts).most_common(1)[0][0], ts[0][11:19], ts[-1][11:19]))

# --- gate 2: job spec ------------------------------------------------------
print("\n[gate 2] job spec present")
empty = [(m, p) for m, p in offers if not (p.get("job") or {})]
print("  offers with a job spec   : %d (%.1f%%)" % (len(offers)-len(empty), 100*(len(offers)-len(empty))/len(offers)))
print("  offers with EMPTY job {} : %d (%.1f%%)  <- names no work" % (len(empty), 100*len(empty)/len(offers)))
ea = sum(1 for _, p in empty if p.get("id") and norm(p["id"]) in refs)
ja = sum(1 for m, p in offers if (p.get("job") or {}) and p.get("id") and norm(p["id"]) in refs)
print("  accepted | empty job: %d   with job spec: %d" % (ea, ja))

# --- gate 3: types ---------------------------------------------------------
print("\n[gate 3] deadline types")
bad = [(m, p) for m, p in offers
       if any(not isinstance(p.get(k), (int, float)) and p.get(k) is not None
              for k in ("expiresMs", "claimByMs", "refundAfterMs"))]
print("  offers with a non-numeric deadline: %d" % len(bad))
for m, p in bad[:5]:
    print("    seq %s from ...%s %s" % (m["seq"], str(m.get("from"))[-12:],
          {k: p.get(k) for k in ("expiresMs", "claimByMs", "refundAfterMs")}))

# --- headline --------------------------------------------------------------
transactable = [(m, p) for m, p in offers if p.get("id") and (p.get("job") or {})]
print("\n[headline] offers passing id AND job-spec gates: %d of %d (%.1f%%)" % (
    len(transactable), len(offers), 100*len(transactable)/len(offers)))
adv = 0
for _, p in offers:
    try: adv += int(p.get("amount") or 0)
    except (TypeError, ValueError): pass
lost = 0
for _, p in noid:
    try: lost += int(p.get("amount") or 0)
    except (TypeError, ValueError): pass
print("  advertised across all offers      : %d" % adv)
print("  advertised by unreferenceable ones: %d (%.1f%%)" % (lost, 100*lost/max(1, adv)))
