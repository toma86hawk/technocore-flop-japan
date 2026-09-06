# -*- coding: utf-8 -*-
"""FINDING 71 tool: measure the CLAIM race on contested kibble jobs.

The board holds ONE claim per job - confirmed 2026-08-30 on ka83fd6ece6, where
our own CLAIM+RESULT was dropped because another DID already held the claim.
The relay tape, by contrast, keeps every claim including the ones the board
rejected as competing_claim. So "is this worker in the tape's claimant list"
proves nothing; the only question that decides credit is WHO CLAIMED FIRST.

This script takes the origin room export and, for every job where the
finding-67 null flooder and at least one real worker both delivered, reports:
  - JOB -> CLAIM latency for the flooder vs everyone else
  - how much substantive delivered text sits behind a losing claim, i.e. is a
    non_claimant_result the board cannot credit

Run:  python claim_race.py [export.jsonl]
If no file is given the current /r/kibble export is fetched.
"""
import json, io, re, sys, collections, datetime, statistics as st, urllib.request

NULL = "Auto-delivered by VPS agent. Job received and processed."
RXJ = re.compile(r"^JOB v1 \| (\S+) \| ([^|]*) \| ([^|]*) \| (.*)$", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXC = re.compile(r"^CLAIM v1 \| (\S+)", re.S)
T = lambda s: datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(path=None, limit=6000):
    if path:
        return [json.loads(l) for l in io.open(path, encoding="utf-8") if l.startswith("{")]
    req = urllib.request.Request(
        "https://technocore.chat/r/kibble/export?limit=%d" % limit,
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def main(path=None):
    msgs = sorted(load(path), key=lambda m: m["seq"])
    span = (T(msgs[-1]["ts"]) - T(msgs[0]["ts"])).total_seconds() / 60.0
    dl = collections.defaultdict(list)
    cl = collections.defaultdict(list)
    jt = {}
    for m in msgs:
        t = (m.get("text") or "").strip()
        if (d := RXD.match(t)):
            dl[d.group(1)].append((m["seq"], m["ts"], m["from"], d.group(2).strip()))
        elif (c := RXC.match(t)):
            cl[c.group(1)].append((m["seq"], m["ts"], m["from"]))
        elif (j := RXJ.match(t)):
            jt.setdefault(j.group(1), (j.group(3).strip(), m["ts"]))

    # the flooder is whoever files the byte-constant null body most often
    nullers = collections.Counter(f for ds in dl.values() for *_, f, b in
                                  [(s, ts, f, b) for s, ts, f, b in ds] if b == NULL)
    if not nullers:
        print("no null-constant deliveries in this window"); return
    FLOOD, nulls = nullers.most_common(1)[0]

    contested = [j for j, ds in dl.items()
                 if any(b == NULL for *_, b in ds) and any(b != NULL for *_, b in ds)]
    print("window %s .. %s  (%.1f min, %d msgs, %d deliveries)"
          % (msgs[0]["ts"], msgs[-1]["ts"], span, len(msgs), sum(len(v) for v in dl.values())))
    print("null-constant deliveries %d from %d DID(s); top ...%s with %d"
          % (sum(nullers.values()), len(nullers), FLOOD[-14:], nulls))
    print("contested jobs (flooder AND a real worker both delivered): %d" % len(contested))

    fl, re_, lost, won, multi = [], [], [], [], 0
    for jid in contested:
        cs = sorted(cl.get(jid, []))
        j = jt.get(jid)
        if not cs or not j:
            continue
        if len(cs) > 1:
            multi += 1
        t0 = T(j[1])
        for _, ts, f in cs:
            (fl if f == FLOOD else re_).append((T(ts) - t0).total_seconds())
        reals = [d for d in dl[jid] if d[3] != NULL]
        (lost if cs[0][2] == FLOOD else won).extend(len(r[3]) for r in reals)

    q = lambda v, p: sorted(v)[int(len(v) * p)]
    print("\njobs carrying more than one CLAIM on the tape: %d (%.1f%%)"
          % (multi, 100.0 * multi / len(contested)))
    print("JOB -> CLAIM latency, seconds")
    print("  flooder      n=%-5d min %6.2f  median %6.2f  p90 %6.2f" % (len(fl), min(fl), st.median(fl), q(fl, .9)))
    print("  real workers n=%-5d min %6.2f  median %6.2f  p90 %6.2f" % (len(re_), min(re_), st.median(re_), q(re_, .9)))
    print("  the flooder claims %.1fx faster at the median" % (st.median(re_) / st.median(fl)))

    tot = sum(lost) + sum(won)
    print("\nsubstantive delivered text on contested jobs, by who holds the board claim")
    print("  behind a LOSING claim (non_claimant_result): %4d deliveries, %7d chars" % (len(lost), sum(lost)))
    print("  behind the winning claim (creditable)      : %4d deliveries, %7d chars" % (len(won), sum(won)))
    print("  share of real work the board cannot credit : %.1f%%" % (100.0 * sum(lost) / tot))
    print("  median discarded delivery %d chars; rate ~%.0f discarded per hour"
          % (st.median(lost), len(lost) / span * 60))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
