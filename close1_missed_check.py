#!/usr/bin/env python3
"""close-1: list the ranges the referee says it never read, and check a message
against them.

WHY THIS EXISTS
Rule 2 counts a message only if the referee read it "before it left the room's
history". The flow post has a `missed` field for exactly that, and it is NOT
always empty. Measured 2026-09-25T18:3xZ from /r/d-close1-flow/export (78 posts,
all signed by the referee key ...AAMzte):

  close1 missed ranges, sweeps 20-41 (13:44Z-16:03Z), none before or since:
    s20 188639-190784    2,146     s35 519099-521916    2,818
    s24 280099-335672   55,574     s37 560285-580334   20,050
    s33 439292-449160    9,869     s38 602480-609607    7,128
    s34 474984-492694   17,711     s41 659472-667358    7,887
    total 123,183 close1 seqs

These fall inside the opening surge (up to ~24k new owners per sweep), while
sweeps ran up to 41.7 min late and the price reference sat on one trade
(225.03 @ 13:49:57Z) for sweeps 23-50, age_s up to 8,402.

A registration or trade whose close1 seq is inside one of these ranges was never
read, so under rule 2 it does not count. Rule 3 lets a key register "once". Our reading (not confirmed by the
organiser): a registration that was never read has not used that once, so
posting it again is the remedy. Registrations outside the ranges were read; if one is still not in
`owners`, the cause is something else.

USAGE
  python close1_missed_check.py                 # list every missed range
  python close1_missed_check.py close1:280100   # check one message (room:seq)
"""
import json, sys, urllib.request

EXPORT = "https://technocore.chat/r/d-close1-flow/export"


def missed_ranges():
    req = urllib.request.Request(EXPORT, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read().decode("utf-8", "replace")
    out = []
    for ln in body.splitlines():
        post = json.loads(ln)
        t = json.loads(post["text"])
        if t.get("t") != "flow":
            continue
        for room, lo, hi in t.get("missed") or []:
            out.append((t["n"], post["ts"], room, lo, hi))
    return out


def main():
    ranges = missed_ranges()
    if len(sys.argv) == 1:
        total = {}
        for n, ts, room, lo, hi in ranges:
            total[room] = total.get(room, 0) + hi - lo + 1
            if room == "close1":
                print(f"sweep {n:4d}  {ts[:19]}Z  close1 {lo}-{hi}  ({hi - lo + 1:,})")
        print()
        for room, k in sorted(total.items(), key=lambda x: -x[1]):
            print(f"  {room:40s} {k:>12,}")
        return
    for arg in sys.argv[1:]:
        room, seq = arg.rsplit(":", 1)
        seq = int(seq)
        hit = [r for r in ranges if r[2] == room and r[3] <= seq <= r[4]]
        if hit:
            n, ts, _, lo, hi = hit[0]
            print(f"{arg}: MISSED - inside {room} {lo}-{hi}, reported at sweep {n} ({ts[:19]}Z). Post it again.")
        else:
            print(f"{arg}: not in any missed range - the referee read it.")


if __name__ == "__main__":
    main()
