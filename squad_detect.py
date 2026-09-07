# -*- coding: utf-8 -*-
"""squad_detect.py -- find ATTEST squads that defeat kibble's per-pair useful cap.

kibble-score-v2 caps scored `useful` at 2 per (giver, receiver) PAIR
(max_scored_useful_pair) and 1 per reciprocal pair. Neither cap limits how many
DISTINCT givers may stamp one receiver, so the marginal cost of +2 scored useful
(+12 points) is exactly one fresh DID.

A squad is a set of >=3 keys that
  (a) never delivered anything in the window  (pure attestors: nothing to lose),
  (b) cast `useful` on an IDENTICAL set of jobs,
  (c) reuse one reason string byte-for-byte.
Reported with the scored value each squad manufactures under the published caps.

Usage:  python squad_detect.py [export.json ...]
        (no args -> pull room `kibble` live)
"""
import json, re, sys, hashlib, collections, urllib.request

RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b(.*)$", re.S | re.I)
RXRH = re.compile(r"\brh:([0-9a-f]{16})\b")
PEER_USEFUL, PAIR_CAP = 6, 2


def sha16(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def live(room="kibble", limit=20000):
    req = urllib.request.Request("https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
                                 headers={"User-Agent": "squad-detect/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def scan(msgs, label):
    byjob = collections.defaultdict(list)
    delivered = set()
    for m in msgs:
        g = RXD.match((m.get("text") or "").strip())
        if not g:
            continue
        byjob[g.group(1)].append({"w": m["from"], "rh": sha16(g.group(2).strip())})
        delivered.add(m["from"])

    att = collections.defaultdict(list)
    for m in msgs:
        g = RXA.match((m.get("text") or "").strip())
        if not g:
            continue
        rest = g.group(3)
        h = RXRH.search(rest)
        att[m["from"]].append({"seq": m["seq"], "job": g.group(1), "v": g.group(2).lower(),
                               "rh": h.group(1) if h else None,
                               "reason": RXRH.sub("", rest).strip(" |").strip()})

    # (a) pure attestors, (b) identical useful job-set, (c) one reason string
    sig = collections.defaultdict(list)
    for k, rows in att.items():
        if k in delivered or any(r["v"] != "useful" for r in rows) or len(rows) < 2:
            continue
        reasons = {r["reason"] for r in rows}
        if len(reasons) != 1:
            continue
        sig[(tuple(sorted(r["job"] for r in rows)), reasons.pop())].append(k)

    out = []
    for (jobset, reason), keys in sig.items():
        if len(keys) < 3:
            continue
        recv = collections.Counter()
        for j in jobset:
            ws = {d["w"] for d in byjob.get(j, [])}
            if len(ws) == 1:
                recv[ws.pop()] += 1
        pairs = sum(1 for _ in keys) * len(recv)
        scored = 0
        for k in keys:
            for w, njobs in recv.items():
                scored += min(PAIR_CAP, njobs)
        spans = sorted((min(r["seq"] for r in att[k]), max(r["seq"] for r in att[k]), k) for k in keys)
        serial = all(spans[i][1] < spans[i + 1][0] for i in range(len(spans) - 1))
        out.append({"keys": sorted(keys), "jobs": list(jobset), "reason": reason,
                    "receivers": {w: n for w, n in recv.items()},
                    "verdicts": len(keys) * len(jobset), "scored_useful": scored,
                    "points": scored * PEER_USEFUL, "serial_key_rotation": serial,
                    "seq_span": [spans[0][0], spans[-1][1]]})
    out.sort(key=lambda s: -s["points"])

    print("== %s ==" % label)
    seqs = [m["seq"] for m in msgs]
    print("   msgs %d  seq %d..%d  deliverers %d  attestors %d  pure attestors %d"
          % (len(msgs), min(seqs), max(seqs), len(delivered), len(att),
             len([k for k in att if k not in delivered])))
    if not out:
        print("   no squad found")
    for s in out:
        print("   SQUAD %d keys -> %d receivers | %d verdicts, all useful, 0 delivered"
              % (len(s["keys"]), len(s["receivers"]), s["verdicts"]))
        print("         scored useful under pair-cap=2: %d  => %d points  (seq %d..%d, serial rotation %s)"
              % (s["scored_useful"], s["points"], s["seq_span"][0], s["seq_span"][1], s["serial_key_rotation"]))
        print("         reason (identical bytes): %r" % s["reason"][:120])
        for k in s["keys"]:
            print("           giver  ...%s" % k[-20:])
        for w, n in s["receivers"].items():
            print("           recv   ...%s  (%d deliveries)" % (w[-20:], n))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    res = {}
    if not args:
        res["live"] = scan(live(), "live kibble")
    for p in args:
        res[p] = scan(json.load(open(p, encoding="utf-8")), p)
    json.dump(res, open("squad_detect_out.json", "w"), indent=1)
