#!/usr/bin/env python3
"""Measure the growth of technocore.chat's four published capacity gauges and
project time-to-exhaustion.

Context: @flop_labs 2026-09-09T04:09Z cited /humans -- "10k+ agents across
thousands of rooms. No central orchestrator. Growing fast."  /rooms?format=json
publishes, alongside the 200 most recent rooms, four server-side gauges with
explicit capacities.  This probe samples them on a fixed cadence and reports
observed rate and headroom.  Bounded: it always stops at DEADLINE.

Falsification built in:
  F1 "it was a one-off burst"      -> reject only if the per-interval rate is
                                      positive across the majority of intervals.
  F2 "offset paginates the list"   -> tested explicitly; if the offset=0 and
                                      offset=N sets overlap, the 200-room window
                                      is all any caller can see and room-name
                                      composition CANNOT be censused from here.
"""
import json, time, urllib.request, sys, collections

URL = "https://technocore.chat/rooms?format=json&limit=200"
INTERVAL = 60
DEADLINE = 20 * 60          # hard stop, 20 minutes

GAUGES = [("total", "capacity"), ("bytes", "bytes_capacity")]


def get(url=URL):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def classify(name):
    """Bucket a room name.  UNTRUSTED per the server's own note: names are
    caller-chosen strings.  Used only to describe the visible window, never as a
    claim about who runs a room."""
    if name.startswith("mb-pair-"):
        return "mb-pair (pairwise mailbox)"
    if name.startswith("mb-p-"):
        return "mb-p (protocol mailbox)"
    if name.startswith("mb-"):
        return "mb (agent mailbox)"
    if name.startswith("d-"):
        return "d- (named room)"
    return "other (named room)"


def main():
    t0 = time.time()
    samples = []
    seen_rooms = set()
    while time.time() - t0 < DEADLINE:
        try:
            d = get()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] fetch failed: {e}", flush=True)
            time.sleep(INTERVAL)
            continue
        rooms = d.get("rooms", [])
        for r in rooms:
            seen_rooms.add(r["room"])
        s = {
            "t": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total": d["total"], "capacity": d["capacity"],
            "bytes": d["bytes"], "bytes_capacity": d["bytes_capacity"],
            "notes_total": d["notes"]["total"],
            "notes_capacity": d["notes"]["capacity"],
            "engagement": d.get("engagement", {}),
            "window_rooms": len(rooms),
        }
        samples.append(s)
        if len(samples) > 1:
            p = samples[-2]
            dt = s["t"] - p["t"]
            print(f"[{s['iso']}] rooms={s['total']} (+{s['total']-p['total']} "
                  f"= {(s['total']-p['total'])/dt:.2f}/s)  "
                  f"bytes={s['bytes']} (+{s['bytes']-p['bytes']})  "
                  f"notes={s['notes_total']} (+{s['notes_total']-p['notes_total']})",
                  flush=True)
        else:
            print(f"[{s['iso']}] rooms={s['total']}/{s['capacity']} "
                  f"bytes={s['bytes']}/{s['bytes_capacity']} "
                  f"notes={s['notes_total']}/{s['notes_capacity']}", flush=True)
        time.sleep(INTERVAL)

    # ---- F2: is the 200-room window paginable? -----------------------------
    a = {r["room"] for r in get(URL + "&offset=0")["rooms"]}
    b = {r["room"] for r in get(URL + "&offset=5000")["rooms"]}
    paginable = len(a & b) < len(a) * 0.5

    # ---- rates -------------------------------------------------------------
    span = samples[-1]["t"] - samples[0]["t"]
    out = {"samples": samples, "span_sec": round(span, 1), "n": len(samples),
           "offset_paginates": paginable, "offset_overlap": len(a & b),
           "distinct_rooms_ever_seen_in_window": len(seen_rooms),
           "window_composition": dict(collections.Counter(
               classify(r) for r in seen_rooms))}

    for cur, cap in [("total", "capacity"), ("bytes", "bytes_capacity"),
                     ("notes_total", "notes_capacity")]:
        d_val = samples[-1][cur] - samples[0][cur]
        rate = d_val / span if span else 0
        head = samples[-1][cap] - samples[-1][cur]
        deltas = [samples[i + 1][cur] - samples[i][cur]
                  for i in range(len(samples) - 1)]
        out[cur] = {
            "first": samples[0][cur], "last": samples[-1][cur],
            "delta": d_val, "rate_per_sec": round(rate, 4),
            "rate_per_hour": round(rate * 3600, 1),
            "capacity": samples[-1][cap], "headroom": head,
            "pct_full": round(100.0 * samples[-1][cur] / samples[-1][cap], 2),
            "hours_to_capacity": round(head / (rate * 3600), 2) if rate > 0 else None,
            "interval_deltas": deltas,
            # F1: a single burst would leave most intervals flat
            "intervals_positive": sum(1 for x in deltas if x > 0),
            "intervals_total": len(deltas),
        }

    json.dump(out, open("_r70_capacity.json", "w"), indent=1)
    print("\n=== SUMMARY ===")
    for cur in ["total", "bytes", "notes_total"]:
        o = out[cur]
        print(f"{cur:12s} {o['first']} -> {o['last']} (+{o['delta']}) "
              f"{o['rate_per_hour']}/h  {o['pct_full']}% full  "
              f"ETA {o['hours_to_capacity']}h  "
              f"positive intervals {o['intervals_positive']}/{o['intervals_total']}")
    print("offset paginates:", paginable, "(overlap", len(a & b), "of 200)")
    print("window composition:", out["window_composition"])


if __name__ == "__main__":
    main()
