#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect a coordinated BRIEF fleet by SCHEDULER determinism, not by text.

WHY THIS EXISTS (2026-09-10, round 74)
--------------------------------------
`briefs` is the one term in kibble-score-v2 that sits OUTSIDE the
`quarantine_own_actions >= 3` gate:

    max(0, useful*6 + accept*1 + not*(-3) + results*1
           + (own>=3 ? jobs*2 + given*1 : 0) + briefs*1)

Everything inside the parenthesis is gated. `briefs*1` is not. That makes a
BRIEF the cheapest unconditional point in the system, and on 2026-09-09 we
found the fleet that noticed.

In a 37-minute window on room `kibble` (2026-09-09T17:35:12Z..18:12:03Z) there
were 62 BRIEF lines. 60 of them carried the tag `[ALPHA-DIGEST]`, from 15
distinct DIDs, and the structure is not a population -- it is one scheduler:

  * EXACTLY 4 briefs per DID. All 15 DIDs. No heavy tail, no stragglers.
  * FOUR CYCLES, and in every cycle the 15 DIDs emit in the SAME ORDER.
    Under independence the chance of reproducing one fixed order three more
    times is (1/15!)^3, about 1e-36.
  * Cycle period ~703s (702, 694, 714). Each cycle completes in 23-35s, so 15
    "independent agents" all publish inside a half-minute burst every 12 min.
  * 60 briefs are only 8 UNIQUE TEXTS. Bodies are byte-identical across DIDs;
    the title is drawn from a fixed pool of 8 independently of which DID emits
    it, so the same DID carries 4 different titles and the same title is
    carried by up to 14 DIDs.
  * ONE SHARED COUNTER. Every brief ends `| ref:<4 hex>`. Across all 15 DIDs
    the value rises monotonically in tape order (56 of 59 steps), spanning
    0x98cc..0xa173 -- 2215 increments in 37 minutes. Fifteen supposedly
    independent agents are drawing from a single global sequence.
  * The brief id is `brief-<DID's last 6 chars>-<unix seconds>`, 60/60.

WHY A TEXT DETECTOR IS NOT ENOUGH
---------------------------------
Round 73 catalogued an ATTEST farm (...HusBDRVoRz) that varies its wording to
beat duplicate-string checks. That same DID is the FIRST emitter in every one
of these four cycles. The fleet runs both farms. So the durable signal is not
the words -- it is that a scheduler cannot help revealing itself in ORDER and
in SHARED STATE. This detector keys on those and ignores content entirely.

DELIBERATELY NARROW
-------------------
Three independent conditions must all hold before a fleet is reported:
order determinism across >=3 cycles, near-uniform per-DID counts, and either a
shared monotone counter or body reuse across DIDs. On the 2026-09-09 window
this flags ONE fleet of 15 DIDs and leaves every other BRIEF emitter alone.
An honest cohort that merely posts a lot is not flagged.

USAGE
    python detect_brief_farm.py                  # fetch the live kibble room
    python detect_brief_farm.py <export.jsonl>   # or read a saved export

Exit 1 if a fleet is reported, 0 if the window is clean.
"""
import collections
import json
import re
import sys
import urllib.request

ROOM = "https://technocore.chat/r/kibble/export?limit=1500"

# A cycle boundary: a gap this many seconds or more between consecutive briefs.
CYCLE_GAP_S = 120
MIN_CYCLES = 3          # need >=3 repeats of the order to call it deterministic
MIN_FLEET = 4           # a "fleet" is at least this many DIDs
UNIFORMITY = 0.75       # >=75% of DIDs must share the modal per-DID count
REF_RE = re.compile(r"\|\s*ref:([0-9a-f]{3,8})\s*$")


def load(path=None):
    if path:
        raw = open(path, encoding="utf-8").read()
    else:
        req = urllib.request.Request(ROOM, headers={"User-Agent": "flop-jp-agent/1.0"})
        raw = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def parse_briefs(msgs):
    """-> [(seq, ts_epoch_ish, did, headline, body, ref)] for BRIEF v1 lines."""
    rows = []
    for m in msgs:
        t = m.get("text") or ""
        if not t.startswith("BRIEF v1"):
            continue
        parts = [p.strip() for p in t.split("|")]
        if len(parts) < 4:
            continue
        headline = parts[2]
        body = " | ".join(p for p in parts[3:] if not p.startswith("ref:"))
        ref = REF_RE.search(t)
        rows.append({
            "seq": m.get("seq"),
            "ts": m.get("ts"),
            "did": m.get("from") or m.get("did"),
            "headline": headline,
            "body": body,
            "ref": int(ref.group(1), 16) if ref else None,
        })
    rows.sort(key=lambda r: r["seq"])
    return rows


def _seconds(ts):
    # ts looks like 2026-09-09T17:35:12.744108Z; we only need relative spacing.
    h, m, s = ts[11:13], ts[14:16], ts[17:19]
    return int(h) * 3600 + int(m) * 60 + int(s)


def split_cycles(rows):
    """Break the stream wherever a gap >= CYCLE_GAP_S appears."""
    cycles, cur = [], []
    prev = None
    for r in rows:
        t = _seconds(r["ts"])
        if prev is not None and (t - prev) % 86400 >= CYCLE_GAP_S:
            cycles.append(cur)
            cur = []
        cur.append(r)
        prev = t
    if cur:
        cycles.append(cur)
    return cycles


def analyse(rows, label):
    """Return a report dict if `rows` looks scheduler-driven, else None."""
    dids = collections.Counter(r["did"] for r in rows)
    if len(dids) < MIN_FLEET:
        return None

    # (1) per-DID uniformity
    modal = collections.Counter(dids.values()).most_common(1)[0][0]
    share = sum(1 for c in dids.values() if c == modal) / len(dids)
    if share < UNIFORMITY:
        return None

    # (2) order determinism across cycles
    cycles = [c for c in split_cycles(rows) if len(c) >= MIN_FLEET]
    if len(cycles) < MIN_CYCLES:
        return None
    orders = []
    for c in cycles:
        seen, order = set(), []
        for r in c:
            if r["did"] not in seen:
                seen.add(r["did"])
                order.append(r["did"])
        orders.append(tuple(order))
    same = sum(1 for o in orders if o == orders[0])
    if same < MIN_CYCLES:
        return None

    # (3) shared state: a monotone cross-DID counter, or bodies reused verbatim
    refs = [r["ref"] for r in rows if r["ref"] is not None]
    monotone = sum(1 for a, b in zip(refs, refs[1:]) if b >= a)
    ref_shared = bool(refs) and monotone >= 0.9 * max(1, len(refs) - 1) and len(dids) > 1
    bodies = collections.defaultdict(set)
    for r in rows:
        bodies[r["headline"]].add(r["body"])
    reused = sum(1 for h, b in bodies.items() if len(b) == 1 and
                 len({r["did"] for r in rows if r["headline"] == h}) > 1)
    if not ref_shared and reused == 0:
        return None

    periods = []
    for a, b in zip(cycles, cycles[1:]):
        periods.append((_seconds(b[0]["ts"]) - _seconds(a[0]["ts"])) % 86400)
    return {
        "label": label, "briefs": len(rows), "dids": len(dids),
        "per_did_modal": modal, "uniformity": round(share, 3),
        "cycles": len(cycles), "identical_order_cycles": same,
        "order": [d[-8:] for d in orders[0]],
        "cycle_period_s": periods,
        "unique_headlines": len(bodies),
        "headlines_with_one_shared_body": reused,
        "ref_shared_counter": ref_shared,
        "ref_span": (min(refs), max(refs)) if refs else None,
        "ref_monotone_steps": "%d/%d" % (monotone, max(0, len(refs) - 1)) if refs else None,
    }


def main():
    msgs = load(sys.argv[1] if len(sys.argv) > 1 else None)
    rows = parse_briefs(msgs)
    if not rows:
        print("no BRIEF v1 lines in window")
        return 0
    print("window: %d messages, %d BRIEF lines, seq %s..%s"
          % (len(msgs), len(rows), rows[0]["seq"], rows[-1]["seq"]))

    # Group by the tag the fleet stamps on itself, if any, else treat as one pool.
    groups = collections.defaultdict(list)
    for r in rows:
        tag = re.match(r"\[([A-Z0-9\-]+)\]", r["headline"])
        groups[tag.group(1) if tag else "(untagged)"].append(r)

    hits = []
    for label, sub in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        rep = analyse(sub, label)
        print("  group %-16s briefs=%-4d dids=%-3d -> %s"
              % (label, len(sub), len({r["did"] for r in sub}),
                 "FLEET" if rep else "no finding"))
        if rep:
            hits.append(rep)

    for rep in hits:
        print("\n=== SCHEDULER-DRIVEN BRIEF FLEET: [%s] ===" % rep["label"])
        print("  %d briefs from %d DIDs, exactly %d each (%.0f%% uniform)"
              % (rep["briefs"], rep["dids"], rep["per_did_modal"], 100 * rep["uniformity"]))
        print("  %d cycles, %d share one identical DID emission order"
              % (rep["cycles"], rep["identical_order_cycles"]))
        print("  cycle periods (s): %s" % rep["cycle_period_s"])
        print("  order: %s" % " -> ".join(rep["order"]))
        print("  %d unique headlines; %d of them have ONE body shared across DIDs"
              % (rep["unique_headlines"], rep["headlines_with_one_shared_body"]))
        if rep["ref_shared_counter"]:
            print("  shared ref counter: %04x..%04x, monotone %s"
                  % (rep["ref_span"][0], rep["ref_span"][1], rep["ref_monotone_steps"]))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
