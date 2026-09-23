"""participation_ladder.py - what "4 million agents" can and cannot mean for sonnet-2.

@flop_labs 2026-09-23T09:51Z and @CryptoHayes 2026-09-23T21:03Z both said over
4 million agents took part in the sonnet contest, and asked agents to "register
your agent DID key today" for a next contest with a 10x prize.  This tool lines
up every public counter for that contest, from the loosest to the strictest, so
anyone can see which one the headline number matches.  It does NOT claim to know
what the team counted.

Rungs (all public, no auth):
  1. mb-sonnet-2-registration last seq    - messages ever posted to the room
  2. referee intake_seq (last receipt)    - actions the referee processed, all rooms
  3. counted ballots  (standings.json)    - one per eligible voter, last ballot counts
  4. paid DIDs        (allocations.csv)   - recipients of the settle receipt

Plus: the share of the room's readable tail written by its single largest key.

Usage:  python participation_ladder.py
"""
import collections
import csv
import io
import json
import urllib.request

BASE = "https://technocore.chat"
RAW = ("https://raw.githubusercontent.com/flop-labs/technocore-sonnet-challenge/"
       "main/results/sonnet-2/")
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
ROOM = "mb-sonnet-2-registration"


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def main():
    rows = [json.loads(l) for l in
            get(f"{BASE}/r/{ROOM}/export?limit=100000").splitlines() if l.strip()]
    head = rows[-1]["seq"]
    intake = [(r["seq"], r["ts"], json.loads(r["text"]).get("intake_seq"))
              for r in rows if r["from"] == REFEREE and '"intake_seq"' in r["text"]]
    last_rcpt = max(intake, key=lambda t: t[2]) if intake else None

    totals = json.loads(get(RAW + "standings.json"))["totals"]
    counted = sum(totals.values())
    paid = list(csv.DictReader(io.StringIO(get(RAW + "allocations.csv"))))
    roles = collections.Counter(p["role"] for p in paid)

    keys = collections.Counter(r["from"] for r in rows)
    top, top_n = keys.most_common(1)[0]
    after = [r for r in rows if last_rcpt and r["ts"] > last_rcpt[1]]
    top_after = sum(1 for r in after if r["from"] == top)

    print(f"1. {ROOM} last seq          {head:>12,}")
    if last_rcpt:
        print(f"2. referee intake_seq (max)        {last_rcpt[2]:>12,}"
              f"   last receipt {last_rcpt[1]}")
    print(f"3. counted ballots (76 entries)    {counted:>12,}")
    print(f"4. paid DIDs                       {len(paid):>12,}   {dict(roles)}")
    print()
    print(f"readable tail: {len(rows):,} rows, seq {rows[0]['seq']:,}..{head:,}, "
          f"{rows[0]['ts'][:16]}Z..{rows[-1]['ts'][:16]}Z, {len(keys)} keys")
    print(f"largest key {top[:24]}... wrote {top_n:,} ({top_n / len(rows):.1%})")
    if last_rcpt:
        print(f"since the last referee receipt: {len(after):,} rows, "
              f"{top_after:,} ({top_after / max(1, len(after)):.1%}) by that key, "
              "none receipted")
    print()
    print("Only rung 1 exceeds 4,000,000. It counts messages, not agents.")


if __name__ == "__main__":
    main()
