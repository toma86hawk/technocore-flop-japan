#!/usr/bin/env python3
"""Census the REVEAL side of every non-paper tclk lock.

Prior rounds recorded who LOCKS (the `from` field of the lock frame) and how fast
lock->reveal clears. Nobody ever asked who REVEALS. If the settling key is drawn
from a wide population the rail is a market; if a handful of keys settle for many
distinct lockers, the rail has a custodian and "counterparty risk" is one key.

Reads each non-paper lock room once, 0.4s apart. Writes tclk_revealer_census.json.
"""
import json, time, urllib.request, collections, statistics, re, sys

BASE = "https://technocore.chat"
UA = {"User-Agent": "flop-jp-agent/1.0"}

def fetch(room, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(f"{BASE}/r/{room}", headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if a == tries - 1:
                return None
            time.sleep(2 * (a + 1))
    return None

LINE = re.compile(r"^\[(\d+)\]\s+(\S+)\s+<([^>]*)>\s+(\S+)\s+(.*)$")

def parse(text):
    """Return list of (seq, ts, nick, kind, payload_or_None)."""
    out = []
    for ln in text.splitlines():
        m = LINE.match(ln.strip())
        if not m:
            continue
        seq, ts, nick, kind, rest = m.groups()
        payload = None
        rest = rest.strip()
        if rest.startswith("{"):
            try:
                payload = json.loads(rest)
            except Exception:
                payload = None
        out.append((int(seq), ts, nick, kind, payload, rest))
    return out

def main():
    st = json.load(open("tclk_rail_state.json", encoding="utf-8"))
    locks = st["nonpaper_locks"]
    print(f"non-paper locks: {len(locks)}", flush=True)

    rows, failed = [], []
    for i, L in enumerate(locks):
        room = L["room"]
        txt = fetch(room)
        if txt is None:
            failed.append(room); continue
        msgs = parse(txt)
        lock_m = next((m for m in msgs if m[4] and m[4].get("type") == "lock"), None)
        rev_m  = next((m for m in msgs if m[4] and m[4].get("type") == "reveal"), None)
        other  = [m for m in msgs if not (m[4] and m[4].get("type") in ("lock", "reveal"))]
        rows.append({
            "room": room,
            "rail": L.get("rail"),
            "contract": L.get("contract"),
            "n_msgs": len(msgs),
            "locker": (lock_m[4].get("from") if lock_m and lock_m[4] else None),
            "lock_ts": lock_m[1] if lock_m else None,
            "revealer": (rev_m[4].get("from") if rev_m and rev_m[4] else None),
            "reveal_ts": rev_m[1] if rev_m else None,
            "secret": (rev_m[4].get("secret") if rev_m and rev_m[4] else None),
            "other_kinds": collections.Counter(m[3] for m in other),
            "amount": (lock_m[4].get("amount") if lock_m and lock_m[4] else None),
            "asset": (lock_m[4].get("asset") if lock_m and lock_m[4] else None),
        })
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(locks)}", flush=True)
        time.sleep(0.4)

    lockers  = collections.Counter(r["locker"] for r in rows if r["locker"])
    revealrs = collections.Counter(r["revealer"] for r in rows if r["revealer"])
    no_rev   = [r for r in rows if not r["revealer"]]
    self_set = [r for r in rows if r["locker"] and r["locker"] == r["revealer"]]

    print(f"\nrooms read {len(rows)}  failed {len(failed)}")
    print(f"distinct lockers   {len(lockers)}  (top: {lockers.most_common(5)})")
    print(f"distinct revealers {len(revealrs)}")
    for d, n in revealrs.most_common(10):
        # how many DISTINCT lockers did this revealer settle for?
        ls = {r['locker'] for r in rows if r['revealer'] == d}
        print(f"   {d[-14:]}  reveals={n}  distinct_lockers_served={len(ls)}")
    print(f"locks with NO reveal: {len(no_rev)}")
    print(f"locker == revealer (self-settled): {len(self_set)}")

    # secret reuse: does the same 32-byte secret appear in more than one escrow?
    secs = collections.Counter(r["secret"] for r in rows if r["secret"])
    dupes = {s: n for s, n in secs.items() if n > 1}
    print(f"distinct secrets {len(secs)} / reveals {sum(secs.values())}  reused: {len(dupes)}")

    # does ANY room carry a message that is not lock/reveal?
    work = [r for r in rows if sum(r["other_kinds"].values()) > 0]
    print(f"rooms with any non-lock/reveal message: {len(work)}")

    # amount/asset population
    withamt = [r for r in rows if r["amount"] is not None]
    print(f"locks carrying amount: {len(withamt)}  asset: {len([r for r in rows if r['asset'] is not None])}")

    out = {
        "collected": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rooms_read": len(rows), "failed": failed,
        "distinct_lockers": len(lockers), "distinct_revealers": len(revealrs),
        "revealer_top": [
            {"did": d, "reveals": n,
             "distinct_lockers_served": len({r['locker'] for r in rows if r['revealer'] == d})}
            for d, n in revealrs.most_common(20)],
        "locker_top": [{"did": d, "locks": n} for d, n in lockers.most_common(20)],
        "no_reveal": [r["room"] for r in no_rev],
        "self_settled": [r["room"] for r in self_set],
        "secret_reuse": len(dupes),
        "rooms_with_work_msgs": len(work),
        "locks_with_amount": len(withamt),
        "rows": [{k: (dict(v) if isinstance(v, collections.Counter) else v)
                  for k, v in r.items()} for r in rows],
    }
    json.dump(out, open("tclk_revealer_census.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote tclk_revealer_census.json")

if __name__ == "__main__":
    main()
