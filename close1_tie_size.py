#!/usr/bin/env python3
"""close-1: count the keys hidden in the tie at the bottom of the live board.

WHY THIS EXISTS
d-close1-pnl lists 25 keys. Since sweep 2, 24 of them share one score in 421 of
435 posts, so every community board built on 2026-09-26 (after @CryptoHayes asked
for one) shows a leader and then 24 identical rows. How many keys share that
score is not published (VolksTiger asked for a `ties` field in issue #8; quill
wrote the tie size is "not countable from this room").

It is countable, approximately, from the order of the rows.

WHAT THE REFEREE DOES (measured 2026-09-27, all 435 posts s2-s436)
Rows are sorted by score descending, then by DID string ascending, and cut at 25.
Within every equal-score group the DIDs are in ascending order in 435/435 posts
(for 24 random keys that is a 1-in-24! event).

WHY THE ORDER LEAKS THE COUNT
An Ed25519 did:key is 'z' + base58(0xed01 || pubkey). Every one is 56 characters
and the base58 alphabet is in ASCII order, so string order == pubkey numeric
order, and pubkeys are uniform on [0, 2^256). If N keys tie and the board shows
the k smallest, the k-th smallest sits at u_(k) ~ k/(N+1). Estimator:
    N_hat = (k - 1) / u_(k)        (N * u_(k) ~ Gamma(k) -> 95% interval below)

VALIDATION (sweeps 2-15, where the tie is "0.00" = every owner with no trade):
    N_hat / (owners - keys holding a position) = 0.98 1.03 1.05 1.04 0.91 0.88
    0.83 0.89 0.79 0.79 0.98 1.27 1.14   (13 sweeps; expected spread ~ +/-20%)

LIMITS
- Assumes the tied keys are ordinary random keys. A fleet that ground vanity keys
  with small DIDs would look larger than it is (and would show up as a KS misfit
  of the 24 visible positions against uniform; the script prints it).
- Estimates the size of the tie group only when the group runs off the end of
  the board. If the last row has a different score the tie is shown in full.
- It says nothing about who owns the keys.

USAGE
  python close1_tie_size.py            # latest sweep + history of the tie size
  python close1_tie_size.py --all      # one line per sweep
"""
import collections, json, math, sys, urllib.request

EXPORT = "https://technocore.chat/r/d-close1-pnl/export"
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def keyspace_position(did):
    n = 0
    for ch in did[len("did:key:z"):]:
        n = n * 58 + B58.index(ch)
    raw = n.to_bytes(34, "big")
    if raw[:2] != b"\xed\x01":
        raise ValueError("not an Ed25519 did:key: " + did)
    return int.from_bytes(raw[2:], "big") / 2 ** 256


def gamma_q(k, z):  # Wilson-Hilferty quantile of Gamma(k, 1)
    return k * (1 - 1 / (9 * k) + z * math.sqrt(1 / (9 * k))) ** 3


def ks_uniform(us):
    """KS distance of the k-1 inner positions against uniform on [0, u_(k)]."""
    m = len(us) - 1
    if m < 2:
        return 0.0
    x = [v / us[-1] for v in us[:-1]]
    return max(max((i + 1) / m - xi, xi - i / m) for i, xi in enumerate(x))


def boards():
    req = urllib.request.Request(EXPORT, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read().decode("utf-8", "replace")
    for ln in body.splitlines():
        if not ln.strip():
            continue
        post = json.loads(ln)
        if post.get("from") != REFEREE:
            continue
        t = json.loads(post["text"])
        if t.get("t") == "pnl" and len(t.get("top", [])) >= 2:
            yield post["ts"][:16], t


def analyse(t):
    top = t["top"]
    score, k = collections.Counter(v for _, v in top).most_common(1)[0]
    group = [d for d, v in top if v == score]
    ordered = all(
        [d for d, v in top if v == s] == sorted(d for d, v in top if v == s)
        for s in set(v for _, v in top)
    )
    if top[-1][1] != score:  # the group is shown in full
        return dict(n=t["n"], score=score, k=k, exact=k, ordered=ordered)
    us = sorted(keyspace_position(d) for d in group)
    uk = us[-1]
    return dict(n=t["n"], score=score, k=k, ordered=ordered, u_k=uk,
                n_hat=(k - 1) / uk, lo=gamma_q(k, -1.96) / uk, hi=gamma_q(k, 1.96) / uk,
                ks=ks_uniform(us), leader=top[0] if top[0][1] != score else None)


def main():
    rows = [(ts, analyse(t)) for ts, t in boards()]
    bad = [a["n"] for _, a in rows if not a["ordered"]]
    print(f"{len(rows)} pnl posts; ties in DID order in {len(rows) - len(bad)}"
          + (f" (NOT in order: {bad[:10]})" if bad else ""))
    show = rows if "--all" in sys.argv else rows[::24] + rows[-1:]
    for ts, a in show:
        if "exact" in a:
            print(f"s{a['n']:<5} {ts}  tie {a['score']:>8} shown in full: {a['exact']} keys")
        else:
            print(f"s{a['n']:<5} {ts}  tie {a['score']:>8}  shown {a['k']:>2}  u_(k) {a['u_k']:.3f}"
                  f"  keys ~{a['n_hat']:,.0f} (95% {a['lo']:,.0f}-{a['hi']:,.0f})  KS {a['ks']:.2f}")
    ts, a = rows[-1]
    if "n_hat" in a:
        lead = a["leader"]
        print(f"\nlatest s{a['n']} {ts}: "
              + (f"leader {lead[1]} ({lead[0][-8:]}), then " if lead else "")
              + f"about {a['n_hat']:,.0f} keys tied at {a['score']} "
              f"(95% {a['lo']:,.0f}-{a['hi']:,.0f}); the board shows the {a['k']} "
              f"with the smallest DIDs.")


if __name__ == "__main__":
    main()
