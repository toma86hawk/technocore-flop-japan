# -*- coding: utf-8 -*-
"""Read post times straight out of X status ids, and test a set of accounts for
a shared posting order.

Round 253 (2026-10-02): six accounts posted "Technocore contribution recorded"
proof lines in the community template (`Signed Technocore record: room
technocore, sequence N`, copied from the did-starter READMEs). Each proof's
"Contribution:" link is the same account's own post from ~35 minutes earlier.
The question is whether these are six people or one script.

An X status id is a snowflake: (id >> 22) + 1288834974657 is the post time in
epoch milliseconds. No API, no login, no trust in a search summary - the id in
the URL is the timestamp. If several accounts post in the SAME ORDER in two
separate waves, that order is a loop, not a crowd.

Usage:
    python x_snowflake_order.py handle:wave1_id:wave2_id [...]
    python x_snowflake_order.py --r253      # the six accounts seen in round 253
"""
import sys
import datetime as dt

EPOCH_MS = 1288834974657

R253 = [
    # handle, contribution post (wave 1), proof post (wave 2)
    ("KimberlyCa53977", 2105841809226416458, 2105850831597982024),
    ("MichelleRi8346", 2105842189976867266, 2105850939471184219),
    ("JennyFranc18465", 2105842278141145431, 2105851037777334737),
    ("Daniell19875321", 2105842346961383791, 2105851145533136967),
    ("JeffryCagle4", 2105842671000694881, 2105851234867659085),
    ("RobinGarci11459", 2105839961316684052, 2105851296649712051),
]


def when(status_id):
    ms = (int(status_id) >> 22) + EPOCH_MS
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)


def kendall_tau(a, b):
    """Rank agreement of two orderings of the same items, -1..1."""
    pos = {x: i for i, x in enumerate(b)}
    n, s = len(a), 0
    for i in range(n):
        for j in range(i + 1, n):
            s += 1 if pos[a[i]] < pos[a[j]] else -1
    return s / (n * (n - 1) / 2)


def main(rows):
    w1 = sorted(rows, key=lambda r: r[1])
    w2 = sorted(rows, key=lambda r: r[2])
    for name, wave in (("wave 1", w1), ("wave 2", w2)):
        k = 1 if name == "wave 1" else 2
        t0 = when(wave[0][k])
        print("%s  %s .. %s  (%.0f s)" % (
            name, t0.strftime("%H:%M:%S"), when(wave[-1][k]).strftime("%H:%M:%S"),
            (when(wave[-1][k]) - t0).total_seconds()))
        for r in wave:
            print("   %-18s %s" % (r[0], when(r[k]).strftime("%Y-%m-%d %H:%M:%S")))
    o1, o2 = [r[0] for r in w1], [r[0] for r in w2]
    tau = kendall_tau(o1, o2)
    print("order agreement between waves: Kendall tau = %.2f" % tau)
    # Tau punishes a rotation (A B C D -> B C D A) hard; the longest run kept in
    # the same relative order does not. Report both.
    lcs = [[0] * (len(o2) + 1) for _ in range(len(o1) + 1)]
    for i, x in enumerate(o1):
        for j, y in enumerate(o2):
            lcs[i + 1][j + 1] = lcs[i][j] + 1 if x == y else max(lcs[i][j + 1], lcs[i + 1][j])
    print("accounts kept in the same relative order: %d of %d" % (lcs[-1][-1], len(o1)))
    rot = [o1[k:] + o1[:k] for k in range(len(o1))]
    if o2 in rot:
        print("wave 2 is wave 1 rotated by %d: one loop, started at a different account" % rot.index(o2))


if __name__ == "__main__":
    if "--r253" in sys.argv or len(sys.argv) == 1:
        main(R253)
    else:
        main([(h, int(a), int(b)) for h, a, b in (x.split(":") for x in sys.argv[1:])])
