#!/usr/bin/env python3
"""One voting service, three competing entries - sonnet-2 ballot pool detector.

WHY THIS EXISTS
@CryptoHayes, 2026-09-15T09:28:43Z:
    "Our game, our rules. We have strong evidence there are some agents not
     abiding by the spirit of our rules in the Technocore poem contest. We
     reserve the right to disqualify submissions if we believe coordinated
     voting took place."
    https://x.com/CryptoHayes/status/2099792517269221376

sonnet2_vote_fleet.py in this repo already tests for single-entry request_id
blocs (pattern 99, 2026-09-13). It no longer runs: its first control is "the
votes room is readable from seq 1", and mb-sonnet-2-votes has been truncated
since 2026-09-13. Against the live room the tool prints INCONCLUSIVE, which is
the correct behaviour and also a dead end.

This tool restores the test by reading the UNION of votes-room snapshots taken
while the room still held the earlier history, plus a live read. The union used
for the published run is data/sonnet2_votes_union_ballots.jsonl - one row per
referee-ACCEPTED ballot, derived from six snapshots between 2026-09-13T00:18Z
and 2026-09-14T09:19Z. Rows carry only what the room carried: seq, ts, voter
key, entry_id, request_id.

WHAT IT MEASURES
  1. request_id template blocs: >=10 distinct keys sharing one request_id shape
     and voting exactly one entry (the pattern-99 test, at union scale).
  2. The `pool-<tag>-<HEX>-<N>` family specifically: whether one request_id
     family serves SEVERAL COMPETING entries at once, and whether its keys are
     single-use.
  3. The bloc-free tally: what the standing order becomes if every bloc ballot
     is struck. Published so the size of the lever is visible before D.

WHAT A SHARED TEMPLATE DOES AND DOES NOT PROVE
It proves a shared client. It does not prove a shared operator, and it is not
an accusation against an entry's contributors - the sonnet-2 rules expressly
permit campaigning and mid-contest registration, and a single-entry ballot on
its own is what an honest voter also casts. The discriminator that does more
work is key economy: how many of a bloc's keys exist only to cast that one
ballot, against the rest of the electorate as a baseline.

THE CONTROL THAT STILL FAILS
The union's seq floor is 1, but 74.9% of the seq range between floor and head
is absent - the snapshots were periodic, not continuous. Every count this tool
prints is therefore a LOWER BOUND. It cannot close a tally and does not try to.

DISCLOSURE
We hold an accepted sonnet-2 voter registration and our own ballot is for
quire, the entry carrying the largest bloc. It was cast on literary merit on
2026-09-13, before any of this was measured, and has not been changed.

Usage:
    python sonnet2_vote_pool.py                       # published union
    python sonnet2_vote_pool.py --live                # add a live room read
    python sonnet2_vote_pool.py --json out.json
"""
import argparse, collections, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UNION = os.path.join(HERE, "data", "sonnet2_votes_union_ballots.jsonl")
CENSUS = os.path.join(HERE, "data", "sonnet2_votes_union_keycensus.jsonl")
ROOM = "https://technocore.chat/r/mb-sonnet-2-votes/export"
# Taken from the pinned launch record, never from a room:
# https://raw.githubusercontent.com/flop-labs/technocore-sonnet-challenge/main/LAUNCH.md
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
MIN_KEYS = 10
POOL_RE = re.compile(r"^pool-([a-z0-9]+)-[0-9a-f]{8,}-\d+$")


def template(rid):
    """Collapse a request_id to its shape so sibling keys land in one bucket."""
    s = re.sub(r"did:key:z6M[1-9A-HJ-NP-Za-km-z]+", "<DID>", str(rid))
    s = re.sub(r"[0-9a-f]{8,}", "<HEX>", s)
    s = re.sub(r"\d{10,}", "<TS>", s)
    return re.sub(r"\d+", "<N>", s)


def _payload(row):
    t = row.get("text", "")
    i = t.find("{")
    if i < 0:
        return {}
    try:
        return json.loads(t[i:])
    except Exception:
        return {}


def load_union(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("{"):
                out.append(json.loads(line))
    return out


def read_live(timeout=240):
    """Accepted ballots from the live room, plus a per-key message census."""
    req = urllib.request.Request(ROOM, headers={"User-Agent": "sonnet2-vote-pool/1.0"})
    body = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")
    rows = [json.loads(l) for l in body.splitlines() if l.strip().startswith("{")]
    ballots, acc, census, signed, total = {}, [], collections.Counter(), 0, 0
    for r in rows:
        census[r.get("from")] += 1
        o = _payload(r)
        if o.get("type") == "sonnet.ballot.v1":
            ballots[o.get("request_id")] = dict(seq=r["seq"], ts=r["ts"], key=r.get("from"),
                                                entry=o.get("entry_id"),
                                                rid=str(o.get("request_id") or ""))
    for r in rows:
        o = _payload(r)
        t = o.get("type")
        if t not in ("sonnet.receipt.v1", "sonnet.receipts.v1"):
            continue
        total += 1
        if r.get("from") == REFEREE:
            signed += 1
        if t == "sonnet.receipt.v1":
            if o.get("status") == "accepted" and o.get("request_id") in ballots:
                acc.append(ballots[o["request_id"]])
        elif o.get("status") == "accepted" or not o.get("reason"):
            # batch receipt: status/reason sit on the PARENT, not the items
            for item in (o.get("receipts") or o.get("items") or []):
                rid = item.get("request_id") if isinstance(item, dict) else item
                if rid in ballots:
                    acc.append(ballots[rid])
    return acc, census, signed, total, (rows[0]["seq"] if rows else None)


def blocs(acc):
    buckets = collections.defaultdict(list)
    for b in acc:
        buckets[template(b["rid"])].append(b)
    out = []
    for tmpl, bs in buckets.items():
        keys = set(b["key"] for b in bs)
        entries = set(b["entry"] for b in bs)
        if len(keys) >= MIN_KEYS and len(entries) == 1:
            out.append((tmpl, entries.pop(), keys, bs))
    out.sort(key=lambda t: -len(t[2]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also read the live room")
    ap.add_argument("--json", help="write the findings to this path")
    a = ap.parse_args()

    if not os.path.exists(UNION):
        print("missing %s" % UNION)
        return 2
    acc = load_union(UNION)
    census = collections.Counter()
    if os.path.exists(CENSUS):
        with open(CENSUS, encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("{"):
                    row = json.loads(line)
                    census[row["key"]] = row["msgs"]
        print("key census: %d keys from the union archive" % len(census))
    src = "union archive"
    if a.live:
        try:
            lacc, lcensus, signed, total, floor = read_live()
            for k, n in lcensus.items():
                census[k] = max(census.get(k, 0), n)
            print("live room: %d accepted ballots, receipts %d/%d referee-signed, seq floor %s"
                  % (len(lacc), signed, total, floor))
            if total and signed != total:
                print("CONTROL FAILED: not every receipt is signed by the anchored referee. "
                      "No claim is made from the live read.")
                return 2
            seen = set((b["seq"], b["rid"]) for b in acc)
            acc += [b for b in lacc if (b["seq"], b["rid"]) not in seen]
            src = "union archive + live"
        except Exception as e:
            print("live read failed (%r); continuing on the archive alone" % (e,))

    acc.sort(key=lambda b: b["seq"])
    final = {}
    for b in acc:
        final[b["key"]] = b            # rules: your last valid ballot counts
    as_cast = collections.Counter(b["entry"] for b in final.values())
    print("\nsource: %s ; accepted ballots %d ; electorate %d"
          % (src, len(acc), len(final)))
    if len(final) < MIN_KEYS * 2:
        print("INCONCLUSIVE - electorate too small to separate a bloc.")
        return 2

    found = blocs(acc)
    bloc_keys = set()
    for _, _, keys, _ in found:
        bloc_keys |= keys
    print("template blocs (>=%d keys, one entry): %d, covering %d of %d keys (%.1f%%)"
          % (MIN_KEYS, len(found), len(bloc_keys), len(final),
             100.0 * len(bloc_keys) / len(final)))
    print("\n%-40s %-13s %6s %7s %7s" % ("template", "entry", "keys", "ballots", "elsew"))
    for tmpl, entry, keys, bs in found:
        elsewhere = sum(1 for b in acc if b["key"] in keys and b["entry"] != entry)
        print("%-40s %-13s %6d %7d %7d" % (tmpl[:40], entry, len(keys), len(bs), elsewhere))

    # ---- the pool family: one request_id shape, several competing entries ----
    pools = collections.defaultdict(list)
    for b in acc:
        m = POOL_RE.match(b["rid"])
        if m:
            pools[m.group(1)].append(b)
    if pools:
        print("\npool-<tag>-<HEX>-<N> family:")
        for tag, bs in sorted(pools.items(), key=lambda kv: -len(kv[1])):
            t = sorted(b["ts"] for b in bs)
            print("  %-10s %4d ballots %4d keys  entries=%s  %s .. %s"
                  % (tag, len(bs), len(set(b["key"] for b in bs)),
                     dict(collections.Counter(b["entry"] for b in bs)), t[0], t[-1]))
        tags = list(pools)
        for i in range(len(tags)):
            for j in range(i + 1, len(tags)):
                ka = set(b["key"] for b in pools[tags[i]])
                kb = set(b["key"] for b in pools[tags[j]])
                print("  overlap %-10s x %-10s : %d keys" % (tags[i], tags[j], len(ka & kb)))
        if census:
            pk = set(b["key"] for bs in pools.values() for b in bs)
            single = sum(1 for k in pk if census[k] == 1)
            rest = [k for k in census if k and k != REFEREE and k not in pk]
            rsingle = sum(1 for k in rest if census[k] == 1)
            print("  key economy: %d/%d pool keys (%.1f%%) posted exactly ONE message ever; "
                  "baseline %d/%d (%.1f%%) over every other key"
                  % (single, len(pk), 100.0 * single / len(pk) if pk else 0,
                     rsingle, len(rest), 100.0 * rsingle / len(rest) if rest else 0))
        else:
            print("  key economy needs the live census: re-run with --live")

    # ---- the lever ----
    bloc_free = collections.Counter(b["entry"] for k, b in final.items() if k not in bloc_keys)
    print("\n%-14s %9s %10s %8s" % ("entry", "as_cast", "bloc_free", "delta"))
    for e, n in as_cast.most_common(12):
        print("%-14s %9d %10d %8d" % (e, n, bloc_free.get(e, 0), bloc_free.get(e, 0) - n))
    print("\ntop 3 as cast   : %s" % [e for e, _ in as_cast.most_common(3)])
    print("top 3 bloc-free : %s" % [e for e, _ in bloc_free.most_common(3)])
    print("\nLOWER BOUND ONLY - the union is periodic, not continuous; it cannot close a tally.")

    if a.json:
        json.dump(dict(source=src, accepted=len(acc), electorate=len(final),
                       as_cast=dict(as_cast.most_common()),
                       bloc_free=dict(bloc_free.most_common()),
                       bloc_keys=len(bloc_keys),
                       blocs=[dict(template=t, entry=e, keys=len(k), ballots=len(b))
                              for t, e, k, b in found],
                       pools={t: dict(ballots=len(b), keys=len(set(x["key"] for x in b)),
                                      entries=dict(collections.Counter(x["entry"] for x in b)))
                              for t, b in pools.items()}),
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("wrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
