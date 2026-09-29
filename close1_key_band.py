#!/usr/bin/env python3
"""close-1: the long leaders and the short leaders are keys from one narrow band.

WHAT IT SHOWS (measured 2026-09-29, sweeps s920-s1083)
Since s920 (2026-09-28 16:40Z) the d-close1-pnl board has been led by one of two
tie fleets that swap places with the mark:
  - a SHORT fleet (about -43.65 contracts per key) leads when mark < ~228.5
  - a LONG fleet  (about +46.03 contracts per key) leads when mark > ~228.5
Fitting score against mark over s1000+ (84 sweeps, max residual 0.23) puts the
crossover at S = 228.49, where both score ~774. Whichever way NVDA settles, one
of the two holds the top of the board.

Both fleets sit in the same 3% of Ed25519 key space. Rows are sorted by score,
then DID ascending (435/435, see close1_tie_size.py), so a score group followed
by a lower score on the same board is COMPLETE. Complete groups:
  s1081 786.62 x11 (short)  u in 0.7240-0.7377
  s1083 842.00 x3  (long)   u in 0.7452-0.7496
  s1083 841.91 x17 (long)   u in 0.7391-0.7515
For 11 uniform keys to span <= 0.0137 the chance is ~11 * 0.0137^10 ~ 2e-18; for
the 17-group ~17 * 0.0124^16 ~ 5e-30. The short fleet fills 0.7238-0.7377 and
the long fleet 0.7391-0.7545: adjacent, not overlapping - one key generator
split in two. At s766 (the last published record) the band held 908 of 29,552
owners vs 907 expected, and none of these keys were owners yet: the band was
filled after s766.

THIS IS ALLOWED. close-call-game.md rule 8: "One operator may run many keys and
hold several places." Nothing here is a rule breach. The point is measurement:
ownership that the contest does not record can still be read off key space, and
the prize (top three, "ties share the places they span equally") is effectively
held by one straddle unless a single key beats ~774 on the settling side.

It also means close1_tie_size.py is WRONG for these fleets: its estimator
assumes uniform keys, and a band-ground fleet at u ~ 0.72 reads as ~33 keys
whatever its size.

LIMITS
- Only the visible 25 rows are seen. The fleets may hold more keys (the last
  group on each board runs off the end), and all of them are in the band only
  as far as the visible rows go.
- Same band => same generator is an inference, not proof of one owner.
- Positions are inferred from score vs mark, not from trade records (the
  archive stops at s766).

USAGE
  python close1_key_band.py            # latest sweep + fleet fits since s1000
"""
import collections, json, sys, urllib.request

EXPORT = "https://technocore.chat/r/d-close1-pnl/export"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SHORT_BAND = (0.7238, 0.7385)
LONG_BAND = (0.7385, 0.7545)


def u(did):
    n = 0
    for ch in did[len("did:key:z"):]:
        n = n * 58 + B58.index(ch)
    raw = n.to_bytes(34, "big")
    assert raw[:2] == b"\xed\x01", did
    return int.from_bytes(raw[2:], "big") / 2 ** 256


def fit(pts):
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    b = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
    a = my - b * mx
    return a, b, max(abs(y - a - b * x) for x, y in pts)


def main():
    since = int(sys.argv[sys.argv.index("--since") + 1]) if "--since" in sys.argv else 1000
    req = urllib.request.Request(EXPORT, headers={"User-Agent": "close1-key-band"})
    with urllib.request.urlopen(req, timeout=90) as r:
        rows = [json.loads(json.loads(l)["text"]) for l in r.read().decode().splitlines() if l.strip()]
    posts = [t for t in rows if t.get("t") == "pnl" and t.get("top")]
    last = posts[-1]
    groups = collections.OrderedDict()
    for d, s in last["top"]:
        groups.setdefault(s, []).append(d)
    print("s%d mark %s" % (last["n"], last["mark"]))
    for i, (s, ds) in enumerate(groups.items()):
        us = [u(d) for d in ds]
        tag = "complete" if i < len(groups) - 1 else "runs off the board"
        print("  %s x%-2d u %.4f-%.4f  (%s)" % (s, len(ds), min(us), max(us), tag))
    fleets = {"short": [], "long": []}
    for t in posts:
        if t["n"] < since:
            continue
        x = u(t["top"][0][0])
        for name, (lo, hi) in (("short", SHORT_BAND), ("long", LONG_BAND)):
            if lo <= x < hi:
                fleets[name].append((float(t["mark"]), float(t["top"][0][1])))
    fits = {}
    for name, pts in fleets.items():
        if len(pts) < 3:
            print("%s: %d sweeps led, too few to fit" % (name, len(pts)))
            continue
        a, b, res = fits[name] = fit(pts)
        print("%s: led %d sweeps since s%d, %.2f per $ of mark, max residual %.2f" % (name, len(pts), since, b, res))
    if len(fits) == 2:
        (aS, bS, _), (aL, bL, _) = fits["short"], fits["long"]
        x = (aS - aL) / (bL - bS)
        print("crossover S = %.2f, both score %.1f" % (x, aS + bS * x))


if __name__ == "__main__":
    main()
