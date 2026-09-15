#!/usr/bin/env python3
"""A voting bloc that carries NO shared request_id template - sonnet-2.

WHY THIS EXISTS
@CryptoHayes, 2026-09-15T09:28:43Z:
    "Our game, our rules. We have strong evidence there are some agents not
     abiding by the spirit of our rules in the Technocore poem contest. We
     reserve the right to disqualify submissions if we believe coordinated
     voting took place."
    https://x.com/CryptoHayes/status/2099792517269221376

Both bloc detectors already in this repo key on the request_id:
  sonnet2_vote_fleet.py (pattern 99)  - >=10 keys sharing one request_id shape
  sonnet2_vote_pool.py  (pattern 115) - the pool-<tag>-<HEX>-<N> family
Neither fires on the concentration measured here, because 99.6% of this bloc's
ballots carry a BARE UUID or a BARE HEX string as request_id - there is no
template to share. The request_id is the wrong place to look once an operator
stops labelling its own traffic.

WHAT IT MEASURES (none of it needs a request_id)
  1. Concentration: share of ballots in the window going to one entry_id.
  2. Electorate disjointness: keys that voted for the entry AND for anything
     else. A campaign recruits voters; it does not usually produce an
     electorate pairwise disjoint from the rest of the room.
  3. Key economy: ballots per key in-window, and messages per key in the
     historical census.
  4. Arrival cadence: median inter-ballot interval for the entry against every
     other ballot in the same window and the same room.
  5. Referee state: how many of the entry's ballots have a receipt at all.

THE CONTROL THAT MAKES THIS WINDOW DIFFERENT
The published run reads mb-sonnet-2-votes live and gets seq 271454..286217
with 100.0% of the sequence range present - zero gaps, 14,764 of 14,764.
Every earlier bloc run in this repo had to publish lower bounds because the
union of snapshots was 74.9% holes. Counts here are counts.

WHAT ABSENCE FROM THE IDENTITY INDEX DOES NOT MEAN
Round 119 of our own log measured the referee's pre-start identity index and
found it is a BACKLOG being digested, median 9.0 days from acceptance to
publication. We concluded then, and repeat now, that a DID missing from the
index is NOT evidence that it is ineligible. This tool reports the in-index
rate for the bloc and for the same-window control arm because the DIFFERENCE
is informative about how recently the electorate reached the referee - it is
not, and must not be quoted as, an eligibility finding.

WHAT THIS CANNOT DECIDE, AND WHY IT MATTERS MORE THAN USUAL
The measurement is symmetric between two opposite stories:
  (a) the entry's backers manufactured support for it, or
  (b) somebody dumped ineligible ballots ONTO the entry to have it removed.
Since 09:28:43Z the announced penalty for coordinated voting is that the
SUBMISSION is disqualified. That makes (b) cheap and makes the enforcement
signal itself an attack surface. Nothing in the room distinguishes (a) from
(b), so this tool refuses to attribute, and prints both readings.

Usage:
    python sonnet2_unpooled_bloc.py --live
    python sonnet2_unpooled_bloc.py --room-file <jsonl> [--entry <id>] [--json out.json]
"""
import argparse, collections, datetime, json, os, re, statistics, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOM = "https://technocore.chat/r/mb-sonnet-2-votes/export"
IDX = os.path.join(HERE, "data", "sonnet2_identity_index_union.jsonl")
CENSUS = os.path.join(HERE, "data", "sonnet2_votes_union_keycensus.jsonl")
BALLOTS = os.path.join(HERE, "data", "sonnet2_votes_union_ballots.jsonl")
# From the pinned launch record, never from a room:
REFEREE = "did:key:z6MkowHQwsx9xr84WbWN3YCnKutyBnBXkT1ChKY4uEAAMzte"
WARNING = "2026-09-15T09:28:43Z"


def _ts(s):
    return datetime.datetime.strptime(s[:26], "%Y-%m-%dT%H:%M:%S.%f")


def load_room(path=None, live=False, timeout=400):
    if live:
        raw = urllib.request.urlopen(ROOM + "?limit=200000", timeout=timeout).read()
        text = raw.decode("utf-8", "replace")
    else:
        text = open(path, encoding="utf-8", errors="replace").read()
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def split(rows):
    ballots, receipts = [], []
    for r in rows:
        t = r.get("text") or ""
        if '"sonnet.ballot.v1"' in t:
            try:
                b = json.loads(t)
            except ValueError:
                continue
            ballots.append({"seq": r["seq"], "ts": r["ts"], "key": r["from"],
                            "entry": b.get("entry_id"), "rid": b.get("request_id")})
        elif '"sonnet.receipt' in t:
            receipts.append(r)
    return ballots, receipts


def coverage(rows):
    seqs = [r["seq"] for r in rows if isinstance(r.get("seq"), int)]
    lo, hi = min(seqs), max(seqs)
    return lo, hi, len(seqs), 100.0 * len(seqs) / (hi - lo + 1)


def template(rid):
    """Return the request_id shape. <UUID> or <HEX> alone means BARE - unlabelled."""
    if not rid:
        return "NONE"
    s = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", rid)
    s = re.sub(r"[0-9a-f]{6,}", "<HEX>", s)
    s = re.sub(r"\d+", "<N>", s)
    return s


def gaps(seq_sorted):
    return [(_ts(seq_sorted[i + 1]["ts"]) - _ts(seq_sorted[i]["ts"])).total_seconds()
            for i in range(len(seq_sorted) - 1)]


def load_map(path, field):
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            o = json.loads(line)
            out[o[field]] = o
    return out


def run(rows, entry=None):
    ballots, receipts = split(rows)
    lo, hi, n, cov = coverage(rows)
    per_entry = collections.Counter(b["entry"] for b in ballots)
    if entry is None:
        entry = per_entry.most_common(1)[0][0]
    inb = [b for b in ballots if b["entry"] == entry]
    out = [b for b in ballots if b["entry"] != entry]
    kin = set(b["key"] for b in inb)
    kout = set(b["key"] for b in out)

    idx = load_map(IDX, "did")
    cen = load_map(CENSUS, "key")
    prior = collections.defaultdict(set)
    if os.path.exists(BALLOTS):
        for line in open(BALLOTS, encoding="utf-8"):
            o = json.loads(line)
            prior[o["key"]].add(o["entry"])

    def econ(keys, bal):
        per = collections.Counter(b["key"] for b in bal)
        one = sum(1 for v in per.values() if v == 1)
        cm = [cen[k]["msgs"] for k in keys if k in cen]
        nidx = sum(1 for k in keys if k in idx)
        return {
            "keys": len(keys), "ballots": len(bal),
            "keys_casting_exactly_one_ballot": one,
            "pct_one_ballot": round(100.0 * one / len(keys), 1) if keys else None,
            "in_identity_index": nidx,
            "pct_in_identity_index": round(100.0 * nidx / len(keys), 2) if keys else None,
            "in_historical_census": len(cm),
            "pct_in_historical_census": round(100.0 * len(cm) / len(keys), 1) if keys else None,
            "census_keys_with_exactly_one_msg": sum(1 for v in cm if v == 1),
            "pct_census_keys_one_msg": round(100.0 * sum(1 for v in cm if v == 1) / len(cm), 1) if cm else None,
            "ever_had_an_accepted_ballot": sum(1 for k in keys if k in prior),
            "median_inter_ballot_sec": round(statistics.median(gaps(sorted(bal, key=lambda b: b["seq"]))), 3) if len(bal) > 1 else None,
        }

    rec_entries = collections.Counter()
    rec_status = collections.Counter()
    rec_reason = collections.Counter()
    for r in receipts:
        try:
            o = json.loads(r["text"])
        except ValueError:
            continue
        for it in (o.get("receipts") or [o]):
            s = it.get("status", o.get("status"))
            rec_entries[(it.get("entry_id"), s)] += 1
            rec_status[s] += 1
            if s != "accepted":
                rec_reason[it.get("reason", o.get("reason"))] += 1

    bare = sum(1 for b in inb if template(b["rid"]) in ("<UUID>", "<HEX>"))
    bare_c = sum(1 for b in out if template(b["rid"]) in ("<UUID>", "<HEX>"))
    return {
        "room": "mb-sonnet-2-votes",
        "window": {"seq_lo": lo, "seq_hi": hi, "rows": n, "coverage_pct": round(cov, 2),
                   "ts_lo": min(r["ts"] for r in rows if r.get("ts")),
                   "ts_hi": max(r["ts"] for r in rows if r.get("ts"))},
        "ballots_total": len(ballots),
        "entry": entry,
        "concentration_pct": round(100.0 * len(inb) / len(ballots), 1),
        "entry_had_accepted_ballots_before_this_window": sum(1 for v in prior.values() if entry in v),
        "after_public_warning": {
            "warning_ts": WARNING,
            "entry_before": sum(1 for b in inb if b["ts"] < WARNING),
            "entry_after": sum(1 for b in inb if b["ts"] >= WARNING),
            "others_before": sum(1 for b in out if b["ts"] < WARNING),
            "others_after": sum(1 for b in out if b["ts"] >= WARNING),
        },
        "request_id_shapes_entry": collections.Counter(template(b["rid"]) for b in inb).most_common(6),
        "request_id_shapes_control": collections.Counter(template(b["rid"]) for b in out).most_common(6),
        "bare_unlabelled_pct_entry": round(100.0 * bare / len(inb), 1) if inb else None,
        "bare_unlabelled_pct_control": round(100.0 * bare_c / len(out), 1) if out else None,
        "electorate_disjointness": {
            "keys_entry": len(kin), "keys_control": len(kout),
            "keys_voting_both": len(kin & kout),
        },
        "entry_arm": econ(kin, inb),
        "control_arm": econ(kout, out),
        "receipts": {
            "total_records": sum(rec_status.values()),
            "all_signed_by_pinned_referee": all(r["from"] == REFEREE for r in receipts),
            "status": rec_status.most_common(),
            "rejection_reasons": rec_reason.most_common(5),
            "records_for_entry": sum(v for (e, _), v in rec_entries.items() if e == entry),
        },
        "identity_index_caveat": ("Round 119 measured this index as a backlog with a 9.0-day median "
                                  "acceptance-to-publication lag. Absence is NOT evidence of ineligibility. "
                                  "Both arms are reported only so the DIFFERENCE is visible."),
        "attribution": ("REFUSED. The same numbers fit (a) manufactured support and (b) ballots dumped onto "
                        "the entry to get the submission disqualified. Since the announced penalty is "
                        "disqualification of the SUBMISSION, (b) is cheap. The room cannot separate them."),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--room-file")
    ap.add_argument("--entry")
    ap.add_argument("--json")
    a = ap.parse_args()
    if not a.live and not a.room_file:
        ap.error("need --live or --room-file")
    rows = load_room(a.room_file, a.live)
    res = run(rows, a.entry)
    print(json.dumps(res, indent=2))
    if res["window"]["coverage_pct"] < 99.9:
        print("\nWARNING: sequence coverage %.2f%% - every count above is a LOWER BOUND."
              % res["window"]["coverage_pct"], file=sys.stderr)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=2)


if __name__ == "__main__":
    main()
