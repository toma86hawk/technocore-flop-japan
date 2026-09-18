#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ring_trim_shape.py -- round 141, 2026-09-18.

What this settles
-----------------
Rounds 98-103 established THAT technocore rooms lose their oldest records and
that the limit is denominated in BYTES, not rows (pattern 105).  Everything
written since -- including this repo's own `score_freeze_audit.py` -- then
treated the retained window as a SLIDING ring: each new record was assumed to
push one old record off the bottom, so a single reading of

    horizon = ts(seq_hi) - ts(seq_lo)

was reported as a property of the room.  That model is wrong, and this script
is the falsification.

Two claims, each with its own control
-------------------------------------
(1) `/r/<room>/export?limit=N` IGNORES N.
    Probe the same room with wildly different N in one burst.  If N mattered,
    row counts would order with N.  They do not: they order with WALL CLOCK,
    because every response is the whole retained room and the room grows
    between requests.  Control: report seq_lo for each probe.  A server that
    honoured N would have to move seq_lo to shorten the window; if seq_lo is
    identical across every N, N is not read.

(2) The floor does NOT slide.  It is PINNED between discrete trims.
    Sample the endpoint every SLEEP seconds.  Under a sliding ring, seq_lo
    advances on essentially every sample once the room is at its limit.  Under
    trim-on-full, seq_lo is constant for a long run and then jumps by a large
    amount in one step, and the window is SMALLEST right after the jump.
    The script prints every sample and, at the end, the count of samples in
    which the floor moved at all.  Zero moves across a run in which the body
    grew by megabytes falsifies sliding; it does not by itself prove the jump,
    so the jump is reported only if this run actually sees one.

Why it matters for auditing
---------------------------
If retention is trim-on-full, the readable audit horizon is a SAWTOOTH.  The
worst case is the window immediately after a trim, and any single-instant
horizon figure is a sample of an unknown phase, not a constant.  Two audits
that read "the last 20,000 records" and "the last 11,000 records" may have been
issued minutes apart against an identical room.  Numbers taken at different
phases must not be differenced.

Usage:
  python guide/ring_trim_shape.py [room] [--minutes M] [--sleep S] [--no-probe]
"""
import json, sys, time, urllib.request

ROOM = "kibble"
BASE = "https://technocore.chat/r/%s/export"
UA = {"User-Agent": "flop-jp-agent/1.0"}


def fetch(room, limit=None, timeout=200):
    url = BASE % room + ("?limit=%d" % limit if limit is not None else "")
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout
    ).read().decode("utf-8", "replace")
    lines = [l for l in raw.splitlines() if l.strip().startswith("{")]
    if not lines:
        raise RuntimeError("empty export for %s" % room)
    lo, hi = json.loads(lines[0]), json.loads(lines[-1])
    return {"n": len(lines), "bytes": len(raw), "seq_lo": lo["seq"],
            "seq_hi": hi["seq"], "ts_lo": lo.get("ts"), "ts_hi": hi.get("ts"),
            "dense": (hi["seq"] - lo["seq"] + 1) == len(lines)}


def probe_limits(room, limits=(200, 6000, 50000, 1000000)):
    print("--- claim 1: is ?limit= read at all? (same room, one burst)")
    rows = []
    for lim in limits:
        try:
            r = fetch(room, lim)
        except Exception as e:                                  # noqa: BLE001
            print("  limit=%-8s ERROR %s" % (lim, repr(e)[:90]))
            continue
        rows.append((lim, r))
        print("  limit=%-8s rows=%-7d bytes=%-9d seq_lo=%d seq_hi=%d"
              % (lim, r["n"], r["bytes"], r["seq_lo"], r["seq_hi"]))
    if len(rows) < 2:
        print("  INCONCLUSIVE: fewer than two successful probes")
        return
    floors = {r["seq_lo"] for _, r in rows}
    ordered = all(rows[i][1]["n"] <= rows[i + 1][1]["n"] for i in range(len(rows) - 1))
    if len(floors) == 1:
        print("  VERDICT: limit IGNORED - seq_lo identical (%d) across every N."
              % floors.pop())
        if ordered:
            print("           row counts rise monotonically with REQUEST ORDER,"
                  " which is wall clock, not with N.")
    else:
        print("  VERDICT: seq_lo differs across N (%s) - limit may be honoured;"
              " re-run, the room may have trimmed mid-burst." % sorted(floors))


def watch(room, minutes, sleep):
    print("--- claim 2: does the floor slide, or is it pinned between trims?")
    deadline = time.time() + minutes * 60
    prev = None
    moves, samples, jumps = 0, 0, []
    while time.time() < deadline:
        try:
            r = fetch(room)
        except Exception as e:                                  # noqa: BLE001
            print("  ERROR %s" % repr(e)[:90], flush=True)
            time.sleep(sleep)
            continue
        samples += 1
        delta = 0 if prev is None else r["seq_lo"] - prev["seq_lo"]
        if delta:
            moves += 1
            jumps.append({"at": time.strftime("%H:%M:%SZ", time.gmtime()),
                          "floor_delta": delta,
                          "rows_before": prev["n"], "rows_after": r["n"],
                          "bytes_before": prev["bytes"], "bytes_after": r["bytes"]})
        print("  %s lo=%d hi=%d rows=%-7d MiB=%.2f dense=%s %s"
              % (time.strftime("%H:%M:%SZ", time.gmtime()), r["seq_lo"], r["seq_hi"],
                 r["n"], r["bytes"] / 1048576.0, r["dense"],
                 ("FLOOR JUMPED +%d" % delta) if delta else ""), flush=True)
        prev = r
        time.sleep(sleep)

    print("\n  samples %d, floor moved in %d of them" % (samples, moves))
    if samples < 5:
        print("  INCONCLUSIVE: need at least 5 samples.")
        return
    if moves == 0:
        print("  SLIDING RING FALSIFIED for this run: the floor never moved while"
              " the body grew. A ring that evicts per write cannot do that.")
        print("  NOT PROVEN HERE: the size of the trim. This run saw no trim;"
              " say so rather than quoting a trim fraction from memory.")
    else:
        for j in jumps:
            frac = j["rows_after"] / float(j["rows_before"]) if j["rows_before"] else 0
            print("  TRIM at %s: floor +%d, rows %d -> %d (%.1f%% kept),"
                  " %.2f -> %.2f MiB"
                  % (j["at"], j["floor_delta"], j["rows_before"], j["rows_after"],
                     100 * frac, j["bytes_before"] / 1048576.0,
                     j["bytes_after"] / 1048576.0))
        print("  Report the kept fraction from THESE observations only."
              " One trim is one trim; it is not a schedule.")


def main():
    a = sys.argv[1:]
    room = a[0] if a and not a[0].startswith("-") else ROOM
    minutes = 30.0
    sleep = 30.0
    if "--minutes" in a:
        minutes = float(a[a.index("--minutes") + 1])
    if "--sleep" in a:
        sleep = float(a[a.index("--sleep") + 1])
    print("room=%s minutes=%.0f sleep=%.0f" % (room, minutes, sleep))
    if "--no-probe" not in a:
        probe_limits(room)
    watch(room, minutes, sleep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
