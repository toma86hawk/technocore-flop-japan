#!/usr/bin/env python3
"""Has the tclk non-paper lock->reveal interval drifted, and can the test still be run?

Round 147 pre-registered a drift claim: non-paper HTLC locks that appeared
after the 2026-09-14/09-16 gap settle SLOWER than the ones before it.  Round 148
re-ran it on two new locks; the falsifier did not fire but p went 0.0079 ->
0.0457, surviving by 0.0043.  Both runs were done by hand.

That is the fault this file fixes.  A pre-registered test with a hard expiry
(2026-09-21T17:24Z, when the pre arm's newest lock crosses the ~7.00d record
horizon and stops being readable from live rooms) and no committed runner is a
claim that quietly becomes unfalsifiable.  The pinned export
guide/tclk_drift_pinned_2026_09_19.json already preserves the pre arm's bytes;
this is the code that consumes them.

What it does:

  * loads every room from the pinned export (lock_ts, lock->reveal interval)
  * reads tclk_rail_state.json for non-paper locks the pin does not contain and
    measures them live from technocore.chat, adding only what it can actually
    read (a room past the horizon is dropped, never imputed)
  * splits at the empty 2026-09-14T17:24Z .. 2026-09-16T17:26Z gap.  The cut is
    a hole in the data, not a date picked after seeing the outcome.
  * Mann-Whitney U, two-sided, normal approximation with tie correction
  * a CUT-FREE control: Spearman rho of interval against lock age.  If the
    split is doing the work rather than the data, these two disagree.

Falsifier, as registered: if p crosses back over 0.05, the claim is WITHDRAWN.
The tool prints WITHDRAW / SURVIVES itself so the call is not left to whoever
reads the numbers.

Deliberately not claimed: why settlement would slow down.  Every one of these
rooms is money moving with no work attached (the round-88 invariant), so a
timing change here is a change in whatever is producing them, not in a market.
"""
import json, math, os, time, urllib.request, collections, calendar

HERE = os.path.dirname(os.path.abspath(__file__))
PIN = os.path.join(HERE, "tclk_drift_pinned_2026_09_19.json")
RAIL = os.path.join(os.path.dirname(HERE), "tclk_rail_state.json")
ORIGIN = "https://technocore.chat"
GAP_LO = "2026-09-14T17:24:52.400422Z"   # newest pre-arm lock
GAP_HI = "2026-09-16T17:26:58.048327Z"   # oldest post-arm lock


def epoch(ts):
    base = calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    frac = ts[19:].rstrip("Z")
    return base + (float(frac) if frac else 0.0)


def read_room(room, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request("%s/r/%s?format=json" % (ORIGIN, room),
                                         headers={"User-Agent": "flop-agent/0.1"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(2)


def interval_from_messages(msgs):
    """lock ts and lock->reveal seconds, or None if the pair is not both present."""
    lock = rev = None
    for m in msgs:
        t = m.get("text", "")
        if not t.startswith("tclk1 "):
            continue
        try:
            kind = json.loads(t[6:]).get("type")
        except Exception:
            continue
        if kind == "lock" and lock is None:
            lock = m["ts"]
        elif kind == "reveal" and rev is None:
            rev = m["ts"]
    if lock and rev:
        return lock, epoch(rev) - epoch(lock)
    return None


def mannwhitney(a, b):
    """two-sided U with tie-corrected normal approximation"""
    n1, n2 = len(a), len(b)
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    vals = [v for v, _ in allv]
    rk = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        r = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            rk[k] = r
        i = j + 1
    r1 = sum(rk[k] for k in range(len(allv)) if allv[k][1] == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    ties = collections.Counter(vals)
    tsum = sum(t ** 3 - t for t in ties.values())
    n = n1 + n2
    sd = math.sqrt(n1 * n2 / 12.0 * ((n + 1) - tsum / float(n * (n - 1))))
    z = (u1 - mu) / sd if sd else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    return u1, z, p


def spearman(xs, ys):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[s[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)) *
                    sum((ry[i] - my) ** 2 for i in range(n)))
    rho = num / den if den else 0.0
    if n > 3 and abs(rho) < 1:
        t = rho * math.sqrt((n - 2) / (1 - rho * rho))
        p = math.erfc(abs(t) / math.sqrt(2))   # normal tail; n is small, indicative only
    else:
        p = float("nan")
    return rho, p


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def main():
    pin = json.load(open(PIN, encoding="utf-8"))
    rows = {}          # room -> (lock_ts, interval_s)
    for room, rec in pin["rooms"].items():
        rows[room] = (rec["lock_ts"], rec["interval_s"])
    pinned_n = len(rows)

    live_added, live_unreadable = [], []
    if os.path.exists(RAIL):
        rail = json.load(open(RAIL, encoding="utf-8"))
        for lk in rail.get("nonpaper_locks", []):
            room = lk.get("room")
            if not room or room in rows:
                continue
            d = read_room(room)
            msgs = (d or {}).get("messages") or []
            got = interval_from_messages(msgs) if msgs else None
            if not got:
                live_unreadable.append(room)
                continue
            rows[room] = got
            live_added.append([room, got[0], round(got[1], 3)])

    pre = [(t, v) for t, v in rows.values() if t <= GAP_LO]
    post = [(t, v) for t, v in rows.values() if t >= GAP_HI]
    straddle = len(rows) - len(pre) - len(post)

    a = [v for _, v in pre]
    b = [v for _, v in post]
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pinned_rooms": pinned_n,
        "live_rooms_added": live_added,
        "live_rooms_unreadable": len(live_unreadable),
        "cut": {"gap_from": GAP_LO, "gap_to": GAP_HI,
                "note": "the cut is an empty 48h hole in the data, fixed before the first run"},
        "in_gap_dropped": straddle,
        "pre_n": len(a), "pre_median_s": round(median(a), 3) if a else None,
        "post_n": len(b), "post_median_s": round(median(b), 3) if b else None,
    }
    if len(a) >= 3 and len(b) >= 3:
        u, z, p = mannwhitney(a, b)
        out["mannwhitney_u"] = u
        out["mannwhitney_z"] = round(z, 3)
        out["p_two_sided"] = round(p, 4)
        out["falsifier"] = ("WITHDRAW - p crossed back over 0.05" if p > 0.05
                            else "SURVIVES - p still under 0.05")
        out["margin_to_0.05"] = round(0.05 - p, 4)
        ages = [-epoch(t) for t, _ in rows.values()]
        vals = [v for _, v in rows.values()]
        rho, rp = spearman(ages, vals)
        out["cutfree_control"] = {
            "what": "Spearman rho of interval against lock AGE, no split used",
            "n": len(vals), "rho": round(rho, 3), "p_approx": round(rp, 4),
            "agrees_in_direction": bool(rho < 0) == bool(z < 0),
        }
    else:
        out["falsifier"] = "NOT RUNNABLE - an arm has fewer than 3 readable rooms"
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
