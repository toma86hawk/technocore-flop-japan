#!/usr/bin/env python3
"""close-1: check every position flip that close1_key_regimes.py infers against the trade record.

close1_key_regimes.py infers a trade from the board alone (score = a + b * mark;
when b changes sign the key traded, and the two lines cross at the effective,
fee-inclusive price). Until 2026-10-02 the official archive stopped at n=1119,
so every flip after that (s1460, s1537, s1643, s1784) stayed "inferred, held".
The archive now runs to n=1936. This tool reads the sweeps in each flip gap and
reports, per key, the settled trades it was party to:

  net contracts   (maker side as recorded; the taker is on the other side)
  vwap, fees, and the fee-inclusive effective price
  vs the board fit: slope change |b_new - b_old| and the crossing mark

A flip is CONFIRMED when the settled net quantity matches the slope change and
the effective price matches the crossing mark. Trades whose record is redacted
are counted as unknown, never as zero.

Side convention: 'side' is the maker's side. Calibrated on s1108, the trade
already confirmed in close1_key_regimes.py (band keys = maker sells at 234.11).

USAGE
  python close1_flip_verify.py                 # all flips on the current board since s1100
  python close1_flip_verify.py --since 1400
Archive files are cached under agent/_close1_archive/ (they are 2-5 MB each).
"""
import collections, json, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from close1_key_band import u
from close1_key_regimes import load, regimes

BASE = "https://challenges.technocore.chat/close-1/"
MAXGAP = 6  # longer gaps are the key leaving the visible rows (see close1_key_regimes r245)
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent", "_close1_archive")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "close1-flip-verify"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def sweep(index, n):
    x = index.get(n)
    if not x:
        return None
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "%d.json" % n)
    if not os.path.exists(p):
        j = get(BASE + x["path"])
        json.dump(j, open(p, "w"))
    return json.load(open(p))


def trades_of(j, did):
    out = {t["id"]: t for t in j["output"]["trades"] if "id" in t}
    rows, redacted = [], sum(1 for t in j["input"]["trades"] if "id" not in t)
    for t in j["input"]["trades"]:
        if "id" not in t or did not in (t["maker"], t["taker"]):
            continue
        o = out.get(t["id"], {})
        if o.get("outcome") != "settled":
            continue
        role = "maker" if t["maker"] == did else "taker"
        side = t["side"] if role == "maker" else ("buy" if t["side"] == "sell" else "sell")
        fee = float(o.get(role + "_fee", 0))
        if t["maker"] == t["taker"]:
            continue  # self-cross nets to zero contracts
        rows.append((side, float(t["px"]), float(t["qty"]), fee))
    return rows, redacted


def main():
    since = int(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else 1100
    index = {x["n"]: x for x in get(BASE + "index.json")["sweeps"]}
    amax = max(index)
    posts = [t for t in load() if t["n"] >= 1000]
    last = posts[-1]
    keys = {d for d, _ in last["top"]}
    hist = collections.defaultdict(list)
    for t in posts:
        for d, s in t["top"]:
            if d in keys:
                hist[d].append((t["n"], t["ts"][:16], float(t["mark"]), float(s)))
    print("board s%d mark %s; archive runs to n=%d" % (last["n"], last["mark"], amax))
    for d in sorted(keys, key=u):
        rs = [r for r in regimes(hist[d], 1.0) if r[1] is not None]
        for (s0, a0, b0, _), (s1, a1, b1, _) in zip(rs, rs[1:]):
            if (b0 > 0) == (b1 > 0):
                continue
            n0, n1 = s0[-1][0], s1[0][0]
            if n1 < since:
                continue
            cross = (a0 - a1) / (b1 - b0)
            head = "u %.4f  flip s%d..s%d  %+.2f -> %+.2f (|db| %.2f)  board cross %.2f" % (
                u(d), n0, n1, b0, b1, abs(b1 - b0), cross)
            if n1 > amax:
                print(head + "  -> NOT IN ARCHIVE YET", flush=True)
                continue
            if n1 - n0 > MAXGAP:
                print(head + "  -> gap of %d sweeps = off-board stretch, not readable as one trade" % (n1 - n0), flush=True)
                continue
            net, notional, fees, red, gap = 0.0, 0.0, 0.0, 0, n1 - n0
            for n in range(n0 + 1, n1 + 1):
                j = sweep(index, n)
                rows, r = trades_of(j, d)
                red += r
                for side, px, q, fee in rows:
                    sg = 1 if side == "buy" else -1
                    net += sg * q
                    notional += sg * q * px
                    fees += fee
            if abs(net) < 1e-9:
                print(head + "  -> no settled trade in %d sweep(s) (redacted rows in gap: %d)" % (gap, red), flush=True)
                continue
            vwap = notional / net
            eff = vwap + fees / net  # sell: net<0 -> vwap - fee/|q|; buy: vwap + fee/q
            ok = abs(abs(net) - abs(b1 - b0)) < 1.0 and abs(eff - cross) < 0.15
            print(head + "  -> record net %+.2f @ vwap %.2f, fees %.2f, eff %.2f  %s" % (
                net, vwap, fees, eff, "CONFIRMED" if ok else "MISMATCH"), flush=True)


if __name__ == "__main__":
    main()
