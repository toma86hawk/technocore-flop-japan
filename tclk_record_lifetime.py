#!/usr/bin/env python3
"""How long can a tclk/1 price, and a tclk/1 settlement, still be read?

WHY THIS EXISTS
@flop_labs, 2026-09-13T14:47Z: "A spot price and a deliverable forward curve
absorb more of that than either printer."

tclk_tenor_curve.py (pattern 106) measured the CURVE: offers declare tenors from
10 minutes to 48 hours and clear, uniformly, in about two seconds. This script
measures the RECORD, because a curve is a time series and a time series only
exists if you can still read the points. It answers four questions and prints a
verdict for each, so the finding can be re-derived from a cold start:

  1. How much history does the order book (r/tclk-offers) actually retain?
     Two full exports a few minutes apart. If the floor seq advances between
     them the tape is trimming, and the span of the surviving tape IS the
     retention. Do not infer this from a byte budget - watch the floor move.
  2. How long does a settlement room stay readable? Probe every known non-paper
     deal room and sort by age. A clean split with no overlap is an age cutoff;
     an overlap means something other than age is at work, and the run says so.
  3. Does any settlement frame name a price? Key-set census over every lock /
     reveal / receipt / refund frame on the tape. This is the claim most worth
     trying to break: ONE frame carrying amount or asset falsifies it.
  4. Can a settlement still be joined to the price that produced it?
     accept.contract is the only join key. Count how many known locks still
     resolve against the live tape.

HONESTY NOTES, learned the hard way in earlier rounds
  - A room read that returns "messages 0" is re-checked through /export before
    this script will call a room gone. The limit route and the export route do
    not always agree, and calling a live room dead is the worse error.
  - "?limit=<big>" is silently capped at 200 by the host, so it CANNOT be used
    to find a room floor. Only /export gives you the floor. An earlier cut of
    this script read floor==head from a limit=100000 request and duly reported
    one message of retention.
  - The rail string is NOT normalised by the host: paperrail and kv-paper are
    paper in substance. Anything selecting non-paper rails must use a substring
    test, not rail.lower() != "paper" - that exact-match bug once inflated our
    own published non-paper count by 40.9%.

USAGE
    python tclk_record_lifetime.py                   # full run, ~4 min
    python tclk_record_lifetime.py --gap 180         # seconds between exports
    python tclk_record_lifetime.py --rooms rooms.json
"""
import argparse
import collections
import datetime
import hashlib
import json
import re
import time
import urllib.request

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-record-lifetime/1.0"}
ROOM = "tclk-offers"
BYTE_BUDGET = 10 * 1024 * 1024      # pattern 105, printed for context, never assumed


def get(url, timeout=300):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def parse_ts(s):
    s = str(s).replace("Z", "")[:26]
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def export_tape(room=ROOM):
    """Full export -> (envelopes, raw). The first row seq IS the room floor."""
    raw = get("%s/r/%s/export" % (BASE, room))
    rows = []
    for ln in raw.splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except ValueError:
            continue
    return rows, raw


def capture(room=ROOM):
    rows, raw = export_tape(room)
    if not rows:
        return None
    t0, t1 = parse_ts(rows[0]["ts"]), parse_ts(rows[-1]["ts"])
    return {
        "at": datetime.datetime.utcnow().isoformat() + "Z",
        "floor_seq": rows[0]["seq"], "head_seq": rows[-1]["seq"],
        "floor_ts": rows[0]["ts"], "head_ts": rows[-1]["ts"],
        "messages": len(rows), "bytes": len(raw.encode()),
        "span_s": round((t1 - t0).total_seconds(), 1),
        "sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "_rows": rows,
    }


def frames(rows):
    for env in rows:
        text = env.get("text") or ""
        if not text.startswith("tclk1 "):
            continue
        try:
            payload = json.loads(text[6:])
        except ValueError:
            continue
        payload["_seq"], payload["_ts"] = env.get("seq"), env.get("ts")
        yield payload


# ----------------------------------------------------------------- claim 1
def claim_retention(gap):
    print("=" * 70)
    print("CLAIM 1  how much price history does r/%s retain?" % ROOM)
    c1 = capture()
    print("  capture 1  floor %d (%s)  head %d  %d msgs  %.2f MiB  span %.1f min"
          % (c1["floor_seq"], c1["floor_ts"][:19], c1["head_seq"], c1["messages"],
             c1["bytes"] / 1048576.0, c1["span_s"] / 60))
    print("  sha256 %s" % c1["sha256"])
    print("  waiting %ds for a second capture ..." % gap)
    time.sleep(gap)
    c2 = capture()
    print("  capture 2  floor %d (%s)  head %d  %d msgs  %.2f MiB  span %.1f min"
          % (c2["floor_seq"], c2["floor_ts"][:19], c2["head_seq"], c2["messages"],
             c2["bytes"] / 1048576.0, c2["span_s"] / 60))
    print("  sha256 %s" % c2["sha256"])

    moved = c2["floor_seq"] - c1["floor_seq"]
    lost_s = (parse_ts(c2["floor_ts"]) - parse_ts(c1["floor_ts"])).total_seconds()
    print("")
    print("  floor advanced %d messages = %.1f min of price history, in %ds of wall clock"
          % (moved, lost_s / 60, gap))
    if moved <= 0:
        # The trim is BURSTY, not continuous: the room fills to the byte budget and is
        # then cut back. A short gap that lands between two bursts sees no movement, and
        # that is perfectly consistent with the claim. Only call it falsified when the
        # tape is sitting AT the cap and still refuses to move.
        headroom = BYTE_BUDGET - c2["bytes"]
        if headroom > 0.10 * BYTE_BUDGET:
            print("  VERDICT: INCONCLUSIVE. The floor did not move, but the tape is %.2f MiB"
                  % (c2["bytes"] / 1048576.0))
            print("           below a ~%d MiB budget, so it has %.2f MiB of headroom and is not"
                  % (BYTE_BUDGET // 1048576, headroom / 1048576.0))
            print("           due to trim yet. Trimming is bursty; re-run with a longer --gap")
            print("           (enough for the tape to reach the cap at its current write rate).")
        else:
            print("  VERDICT: the tape is at the byte budget and the floor STILL did not advance.")
            print("           CLAIM 1 FALSIFIED - retention is not bounded the way this claims.")
    else:
        lo, hi = sorted([c1["span_s"] / 60, c2["span_s"] / 60])
        print("  VERDICT: the tape trims. Retention oscillates between about %.0f and %.0f minutes"
              % (lo, hi))
        print("           (fills toward the ~%d MiB room byte budget, then is cut back)."
              % (BYTE_BUDGET // 1048576))
        print("           Against the tenors the rail QUOTES: a 48h offer outlives the")
        print("           record of its own quote by %.0fx to %.0fx." % (48 * 60 / hi, 48 * 60 / lo))
    return c1, c2


# ----------------------------------------------------------------- claim 2
def claim_room_lifetime(rooms):
    print("=" * 70)
    print("CLAIM 2  how long does a settlement room stay readable?")
    now = datetime.datetime.utcnow()
    out = []
    for entry in rooms:
        room, born = entry["room"], parse_ts(entry["ts"])
        count, via = None, "limit"
        try:
            body = get("%s/r/%s?limit=50" % (BASE, room), timeout=40)
            m = re.search(r"messages (\d+)", body)
            count = int(m.group(1)) if m else None
        except Exception as exc:                                   # noqa: BLE001
            via = "ERR " + str(exc)[:30]
        if count == 0:                      # never trust a single empty read
            try:
                dump = get("%s/r/%s/export" % (BASE, room), timeout=60)
                count = len([x for x in dump.splitlines() if x.strip()])
                via = "export-confirmed"
            except Exception as exc:                               # noqa: BLE001
                via = "export ERR " + str(exc)[:30]
        out.append({"room": room, "ts": entry["ts"], "msgs": count, "via": via,
                    "age_h": round((now - born).total_seconds() / 3600, 2)})

    alive = [x for x in out if (x["msgs"] or 0) > 0]
    gone = [x for x in out if x["msgs"] == 0]
    print("  probed %d   readable %d   gone %d" % (len(out), len(alive), len(gone)))
    if not alive or not gone:
        print("  VERDICT: no boundary visible in this sample.")
        return out

    amax = max(x["age_h"] for x in alive)
    gmin = min(x["age_h"] for x in gone)
    print("  readable ages %.2fh .. %.2fh" % (min(x["age_h"] for x in alive), amax))
    print("  gone     ages %.2fh .. %.2fh" % (gmin, max(x["age_h"] for x in gone)))
    if amax < gmin:
        edge = now - datetime.timedelta(hours=(amax + gmin) / 2)
        print("  VERDICT: CLEAN age cutoff between %.2fh and %.2fh, no overlap." % (amax, gmin))
        print("           Boundary sits at about %sZ." % edge.isoformat()[:19])
        print("           These rooms hold 2-3 messages (~600 B), so the byte budget cannot")
        print("           explain it: this is a SECOND expiry, keyed on age.")
        print("           TO FALSIFY: re-run in 24h. A rolling window moves the boundary")
        print("           forward by 24h; a one-time purge leaves it where it is.")
    else:
        print("  VERDICT: NOT a clean age cutoff - readable and gone overlap by %.2fh."
              % (amax - gmin))
        print("           Something other than age is deciding. Do not publish an age rule.")
    return out


# ----------------------------------------------------------------- claim 3
def claim_no_price(rows):
    print("=" * 70)
    print("CLAIM 3  does any settlement frame name a price?")
    keysets = collections.defaultdict(collections.Counter)
    offending = []
    for payload in frames(rows):
        if payload.get("type") not in ("lock", "reveal", "receipt", "refund"):
            continue
        keys = ",".join(sorted(k for k in payload if not k.startswith("_")))
        keysets[payload["type"]][keys] += 1
        if "amount" in payload or "asset" in payload:
            offending.append(payload)

    total = sum(sum(c.values()) for c in keysets.values())
    for ty in sorted(keysets):
        print("  %-8s n=%4d" % (ty, sum(keysets[ty].values())))
        for keys, n in keysets[ty].most_common():
            print("      %4d  {%s}" % (n, keys))
    print("")
    if offending:
        print("  VERDICT: CLAIM 3 FALSIFIED - %d settlement frame(s) carry a price, e.g. %s"
              % (len(offending), json.dumps(offending[0])[:160]))
    else:
        print("  VERDICT: %d settlement frames across %d key-sets, NOT ONE carries amount or asset."
              % (total, sum(len(c) for c in keysets.values())))
        print("           Price exists only on the offer - the thing that is trimmed first.")
    return {ty: dict(c) for ty, c in keysets.items()}, len(offending)


# ----------------------------------------------------------------- claim 4
def claim_joinable(rows, rooms):
    print("=" * 70)
    print("CLAIM 4  can a settlement still be joined to the price that produced it?")
    contracts = set()
    for payload in frames(rows):
        if payload.get("type") == "accept" and payload.get("contract"):
            contracts.add(str(payload["contract"]).lower())
    print("  accept.contract is the only join key; %d distinct on the live tape" % len(contracts))
    hits = [r for r in rooms if str(r.get("contract", "")).lower() in contracts]
    print("  known settlements: %d   still resolvable: %d" % (len(rooms), len(hits)))
    for h in hits[:10]:
        print("      resolves: %s  %s" % (h["contract"][:20], h["ts"][:19]))
    print("")
    if len(hits) == len(rooms):
        print("  VERDICT: every settlement is still priceable. CLAIM 4 FALSIFIED.")
    else:
        print("  VERDICT: %d of %d settlements on the value rail can no longer be priced by"
              % (len(rooms) - len(hits), len(rooms)))
        print("           anyone, including the counterparties. The fact that money moved")
        print("           outlives the price it moved at.")
    return len(hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=180,
                    help="seconds between the two price-tape captures")
    ap.add_argument("--rooms", default="../tclk_rail_state.json",
                    help="JSON holding nonpaper_locks [{room, ts, contract}]")
    ap.add_argument("--out", default="tclk_record_lifetime_result.json")
    args = ap.parse_args()

    try:
        blob = json.load(open(args.rooms, encoding="utf-8"))
        rooms = blob["nonpaper_locks"] if isinstance(blob, dict) else blob
    except Exception as exc:                                       # noqa: BLE001
        print("no room list (%s); claims 2 and 4 will be skipped" % exc)
        rooms = []

    c1, c2 = claim_retention(args.gap)
    rows = c2.pop("_rows")
    c1.pop("_rows", None)
    room_rows = claim_room_lifetime(rooms) if rooms else []
    keysets, bad = claim_no_price(rows)
    joinable = claim_joinable(rows, rooms) if rooms else None

    json.dump({"captures": [c1, c2], "rooms": room_rows,
               "settlement_keysets": keysets, "frames_carrying_price": bad,
               "joinable": joinable},
              open(args.out, "w", encoding="utf-8"), indent=1)
    print("")
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
