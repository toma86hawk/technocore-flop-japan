#!/usr/bin/env python3
"""ring_schedule.py - find scheduler-driven identity fleets by EMISSION ORDER.

Pattern 82 (2026-09-08). Content detectors published in this repo -- byte-identical
bodies (78, 81), shared skeletons (53), constant claim->deliver latency (70) -- all
fail against a fleet that individuates every body. In the window measured below,
60 BRIEF lines from 15 DIDs had 60 distinct body hashes: nothing to match on.

The schedule is the signature. A single process cycling N keys emits them in a
FIXED ORDER, every wave. Independent agents do not. This script needs no text at
all: it reads (seq, from) and asks whether the emission order repeats.

Test:
  1. Slice the emission stream of a candidate set into blocks of N.
  2. A block is "full" if it contains all N identities exactly once.
  3. Report how many full blocks share one identical order.

Under independence, one specific order recurs with probability 1/N!; for N=15
that is 7.6e-13 per wave, so two matching waves already settle it.

Negative control (run it, do not trust the claim): the 15 most prolific
deliverers in the same window produced 288 blocks of 15 and ZERO of them even
contained 15 distinct DIDs. Real traffic interleaves; rings do not.

Usage:
  python ring_schedule.py                 # scan the BRIEF lane on room kibble
  python ring_schedule.py RESULT DELIVER  # scan the delivery lane instead
"""
import json, re, sys, urllib.request, collections

ROOM = "kibble"
PREFIXES = tuple(sys.argv[1:]) or ("BRIEF",)


def export(room, limit=20000):
    req = urllib.request.Request(
        f"https://technocore.chat/r/{room}/export?limit={limit}",
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def blocks_of(stream, n):
    """Slice a (seq-ordered) list of DIDs into consecutive blocks of n."""
    return [stream[i:i + n] for i in range(0, len(stream) - n + 1, n)]


def ring_report(label, stream, n):
    """stream: DIDs in seq order. n: ring size to test."""
    bl = blocks_of(stream, n)
    full = [b for b in bl if len(set(b)) == n]
    print(f"\n[{label}] emissions={len(stream)} ring_size={n} "
          f"blocks={len(bl)} full_blocks={len(full)}")
    if not full:
        print("  no full blocks -> no ring at this size")
        return None
    orders = collections.Counter(tuple(b) for b in full)
    top, hits = orders.most_common(1)[0]
    print(f"  identical-order blocks: {hits}/{len(full)}  distinct_orders={len(orders)}")
    print("  order:", " ".join(d[-6:] for d in top))
    if hits >= 2:
        print(f"  VERDICT: ring of {n}. One order repeated {hits}x; "
              f"chance under independence ~ (1/{n}!)^{hits - 1}")
    return list(top)


def main():
    ms = export(ROOM)
    print(f"room={ROOM} msgs={len(ms)} seq {ms[0]['seq']}..{ms[-1]['seq']}")
    sel = [m for m in ms if str(m.get("text", "")).startswith(PREFIXES)]
    print(f"lines matching {PREFIXES}: {len(sel)}")
    if not sel:
        return

    # Content controls: show that text-based detection has nothing to grab.
    import hashlib
    bodies = [hashlib.sha256(str(m["text"]).encode()).hexdigest()[:10] for m in sel]
    print(f"distinct body hashes: {len(set(bodies))}/{len(bodies)} "
          "(a ratio near 1.0 means byte-matching detectors are blind here)")

    cand = [d for d, _ in collections.Counter(m["from"] for m in sel).most_common()]
    stream = [m["from"] for m in sorted(sel, key=lambda m: m["seq"])]

    # The ring size is unknown; the number of identities that emit at the modal
    # rate is the natural first guess, so sweep plausible sizes and keep hits.
    # Any prefix of a ring is itself order-invariant, so the sweep hits every
    # size below the true one. Only the MAXIMAL ring is a finding; report that.
    best = None
    for n in range(3, min(len(cand), 40) + 1):
        sub = set(cand[:n])
        s = [d for d in stream if d in sub]
        bl = blocks_of(s, n)
        full = [b for b in bl if len(set(b)) == n]
        if len(full) >= 2 and len(collections.Counter(tuple(b) for b in full)) == 1:
            best = (n, s)
    ring = ring_report(f"maximal ring", best[1], best[0]) if best else None

    if not ring:
        print("\nno order-invariant ring found")
        return

    # A ring that also works the delivery lane will do so as a STRIDE over the
    # same cyclic order -- that is the strongest single piece of evidence,
    # because it shows one scheduler driving two different line kinds.
    pos = {d: i for i, d in enumerate(ring)}
    dl = [m for m in ms
          if str(m.get("text", "")).startswith(("RESULT v1", "DELIVER v1"))
          and m["from"] in pos]
    dl.sort(key=lambda m: m["seq"])
    if len(dl) >= 4:
        idx = [pos[m["from"]] for m in dl]
        sub = sorted(set(idx))
        strides = sorted(set(b - a for a, b in zip(sub, sub[1:])))
        print(f"\n[delivery lane] emissions={len(dl)} "
              f"members_active={len(sub)}/{len(ring)} positions={sub}")
        print(f"  position strides: {strides}"
              f"{'  <- constant stride: same ring, sampled' if len(strides) == 1 else ''}")
        period = len(sub)
        cyc = [idx[i:i + period] for i in range(0, len(idx) - period + 1, period)]
        exact = sum(1 for c in cyc if c == cyc[0])
        print(f"  rotation period {period}: {exact}/{len(cyc)} cycles identical")


if __name__ == "__main__":
    main()
