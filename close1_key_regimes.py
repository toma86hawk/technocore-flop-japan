#!/usr/bin/env python3
"""close-1: follow each leading key's position through time, and catch it when it flips.

WHAT IT SHOWS (measured 2026-09-29, sweeps s1000-s1156)
A key's board score is linear in the mark while its position is unchanged:
score = a + b * mark, b = contracts held (after fees, the fit residual stays
under ~0.3). When the key trades, the line breaks. This tool fits each key's
visible history backwards from the latest sweep, cuts it into regimes of one
line each, and reports where each line broke and the mark at which the old and
new lines cross - the effective (fee-inclusive) price of the trade.

First finding: the upper tier of the r230 LONG fleet (u 0.7478-0.7545, the
1019-1021 groups at s1155) was long +46.07 per key through s1107 (08:16Z) and is
short -44.84 per key from s1119 (09:16Z) on (residual 0.26 over 23 sweeps). The
two lines cross at mark ~231.33: that tier sold ~91 contracts per key near 231,
locking +258 per key at S=228.49 (774 -> 1033). The lower long tier
(u 0.7391-0.7467) had NOT flipped as of s1141 (11:06Z, +46.08, residual 0.23);
it has been below the visible 25 rows since, so later trades there are unseen.

So the r230 picture (one short and one long fleet crossing at S=228.49, ~774)
is out of date. Two in-band tiers now straddle the board:
  long  tier  774 + 46.1 * (S - 228.49)
  short tier 1033 - 44.8 * (S - 228.49)
crossing at S ~ 231.3, score ~ 905. The band's floor for the top place rose
from ~774 to ~905 at the worst settle, and ~1033 at S=228.49.

Still allowed (close-call-game.md rule 8). Nothing here is a breach.

LIMITS
- Only the 25 visible rows. A key's regime is seen only while it is on the board;
  the flip is located between the last sweep of the old line and the first of
  the new one (s1108-s1118 here - the key was off the board in between).
- The crossing price assumes a single trade. Several trades in the gap would
  give the same two lines and a different path.
- Positions are inferred from score vs mark, not from trade records.

USAGE
  python close1_key_regimes.py              # keys on the latest board + leaders since s1000
  python close1_key_regimes.py --since 1100 --tol 1.0
"""
import collections, json, sys, urllib.request

from close1_key_band import EXPORT, fit, u

REF = 228.49  # r230 crossover, used as a common reference mark


def load():
    req = urllib.request.Request(EXPORT, headers={"User-Agent": "close1-key-regimes"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = [json.loads(l) for l in r.read().decode().splitlines() if l.strip()]
    posts = []
    for m in raw:
        t = json.loads(m["text"])
        if t.get("t") == "pnl" and t.get("top"):
            t["ts"] = m["ts"]
            posts.append(t)
    return posts


def regimes(pts, tol):
    """pts: [(n, ts, mark, score)] oldest first. Greedy backwards split into lines."""
    out, end = [], len(pts)
    while end > 0:
        start = end - 1
        while start > 0:
            seg = pts[start - 1:end]
            marks = {p[2] for p in seg}
            if len(seg) >= 3 and len(marks) > 1:
                a, b, res = fit([(p[2], p[3]) for p in seg])
                if res > tol:
                    break
            start -= 1
        seg = pts[start:end]
        if len(seg) >= 3 and len({p[2] for p in seg}) > 1:
            a, b, res = fit([(p[2], p[3]) for p in seg])
        else:
            a = b = res = None
        out.append((seg, a, b, res))
        end = start
    return out[::-1]


def main():
    since = int(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else 1000
    tol = float(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 1.0
    posts = [t for t in load() if t["n"] >= since]
    last = posts[-1]
    keys = {d for d, _ in last["top"]} | {t["top"][0][0] for t in posts}
    hist = collections.defaultdict(list)
    for t in posts:
        for d, s in t["top"]:
            if d in keys:
                hist[d].append((t["n"], t["ts"][:16], float(t["mark"]), float(s)))
    print("s%d %s mark %s; %d keys, sweeps s%d-s%d, tol %.2f"
          % (last["n"], last["ts"][:16], last["mark"], len(keys), posts[0]["n"], last["n"], tol))
    # group keys whose regime sequence is the same (same slopes/levels to 0.5)
    sig = collections.defaultdict(list)
    for d, pts in hist.items():
        rs = [r for r in regimes(pts, tol) if r[1] is not None]
        if not rs:
            continue
        s = tuple((round(b), round(a + b * REF)) for _, a, b, _ in rs)
        sig[s].append((d, rs))
    for s, members in sorted(sig.items(), key=lambda kv: -len(kv[1])):
        us = [u(d) for d, _ in members]
        d, rs = max(members, key=lambda m: sum(len(r[0]) for r in m[1]))
        print("\n%d key(s), u %.4f-%.4f" % (len(members), min(us), max(us)))
        for i, (seg, a, b, res) in enumerate(rs):
            print("  s%d %s .. s%d %s  n=%-3d %+7.2f per $, @%.2f = %7.1f, resid %.2f"
                  % (seg[0][0], seg[0][1], seg[-1][0], seg[-1][1], len(seg), b, REF, a + b * REF, res))
            if i:
                _, a0, b0, _ = rs[i - 1]
                if abs(b - b0) > 1:
                    x = (a0 - a) / (b - b0)
                    print("    FLIP %+.2f -> %+.2f per key; old and new lines cross at mark %.2f"
                          " (effective trade price); level at %.2f moved %+.1f"
                          % (b0, b, x, REF, (a + b * REF) - (a0 + b0 * REF)))


if __name__ == "__main__":
    main()
