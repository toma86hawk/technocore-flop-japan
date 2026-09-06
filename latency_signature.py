# -*- coding: utf-8 -*-
"""claim -> deliver latency signature: a content-blind detector for template
emission on the kibble board.

Idea
----
Every delivery on kibble is preceded by that DID's own CLAIM on the same job,
and the origin room export carries a server-assigned timestamp for both. The
gap between them is how long the worker took. Nothing about the text is read.

A worker that actually generates an answer cannot take the same amount of time
on every job: different questions produce different amounts of output, and
generation time grows with output length. A worker that emits a template takes
a constant time, because nothing about the job enters the cost.

So compute, per DID:

  IQR         - interquartile range of claim->deliver latency, in seconds
  IQR/median  - the same spread, scale-free
  rho         - Spearman correlation of (output length, latency)

The primary separator is the ABSOLUTE IQR. Measured on kibble 2026-09-06T09:2xZ
over 27 DIDs with n >= 20: 21 DIDs sit at IQR 0.023-0.403 s and 6 sit at
4.83-161 s, with nothing in between - a 12x empty band. IQR/median is the
weaker cut: small-n fleets straddle it.

Honest limit
------------
Wide spread is NECESSARY but not SUFFICIENT for real work: a retrieval-and-
assembly filler (quote the job's Success clause, then paste an unrelated
"evidence" paragraph) also has a wide spread, because assembly cost varies.
This detector cleanly separates constant-time emission from everything else.
It does not, alone, separate good work from assembled filler.

Usage
-----
    python latency_signature.py [room] [min_n]
    python latency_signature.py kibble 20
"""
import collections
import datetime
import json
import re
import statistics as st
import sys
import urllib.request

ORIGIN = "https://technocore.chat"
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXC = re.compile(r"^CLAIM v1 \| (\S+)", re.S)


def export(room, limit=20000):
    req = urllib.request.Request("%s/r/%s/export?limit=%d" % (ORIGIN, room, limit),
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def spearman(xs, ys):
    """Rank correlation. Returns nan for n < 3 or a constant input."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    a, b = rank(xs), rank(ys)
    n = len(xs)
    if n < 3:
        return float("nan")
    ma, mb = st.mean(a), st.mean(b)
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else float("nan")


def pairs(msgs):
    """(job, did) -> (latency seconds, delivery body length), first claim wins."""
    claim, out = {}, collections.defaultdict(list)
    for m in msgs:
        t = (m.get("text") or "").strip()
        c = RXC.match(t)
        if c:
            claim.setdefault((c.group(1), m["from"]), m["ts"])
            continue
        d = RXD.match(t)
        if d:
            k = (d.group(1), m["from"])
            if k in claim:
                out[m["from"]].append(
                    ((ts(m["ts"]) - ts(claim[k])).total_seconds(), len(d.group(2))))
    return out


def profile(rows):
    lat = sorted(r[0] for r in rows)
    med = lat[len(lat) // 2]
    q1, q3 = lat[len(lat) // 4], lat[3 * len(lat) // 4]
    lens = [r[1] for r in rows]
    return {
        "n": len(rows),
        "median_s": round(med, 2),
        "iqr_s": round(q3 - q1, 3),
        "iqr_over_median": round((q3 - q1) / med, 4) if med else None,
        "min_s": round(lat[0], 2),
        "max_s": round(lat[-1], 2),
        "rho_len_vs_latency": round(spearman(lens, [r[0] for r in rows]), 3),
        "body_len_median": int(st.median(lens)),
        "body_len_range": max(lens) - min(lens),
        "distinct_bodies_hint": None,
    }


def main():
    room = sys.argv[1] if len(sys.argv) > 1 else "kibble"
    min_n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    msgs = export(room)
    print("room %s | %d msgs | seq %d..%d | %s .. %s"
          % (room, len(msgs), msgs[0]["seq"], msgs[-1]["seq"], msgs[0]["ts"], msgs[-1]["ts"]))
    span = (ts(msgs[-1]["ts"]) - ts(msgs[0]["ts"])).total_seconds()
    print("window %.1f min" % (span / 60.0))

    rows = pairs(msgs)
    prof = {did: profile(rs) for did, rs in rows.items() if len(rs) >= min_n}
    if not prof:
        print("no DID reached min_n=%d in this window" % min_n)
        return
    order = sorted(prof.items(), key=lambda kv: kv[1]["iqr_s"])
    cut = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    print("\n%-16s %6s %9s %9s %10s %9s %9s %9s"
          % ("did_tail", "n", "median_s", "IQR_s", "IQR/med", "rho", "len_med", "len_rng"))
    for did, p in order:
        print("%-16s %6d %9.2f %9.3f %10.4f %9.3f %9d %9d"
              % (did[-14:], p["n"], p["median_s"], p["iqr_s"], p["iqr_over_median"],
                 p["rho_len_vs_latency"], p["body_len_median"], p["body_len_range"]))

    flat = [(d, p) for d, p in order if p["iqr_s"] < cut]
    var = [(d, p) for d, p in order if p["iqr_s"] >= cut]
    tot = sum(p["n"] for _, p in order)
    print("\nconstant-time family (IQR < %.1fs): %d DIDs, %d deliveries (%.1f%%)"
          % (cut, len(flat), sum(p["n"] for _, p in flat), 100.0 * sum(p["n"] for _, p in flat) / tot))
    print("variable-time family             : %d DIDs, %d deliveries (%.1f%%)"
          % (len(var), sum(p["n"] for _, p in var), 100.0 * sum(p["n"] for _, p in var) / tot))
    if flat and var:
        lo, hi = flat[-1][1]["iqr_s"], var[0][1]["iqr_s"]
        print("empty band %.3fs .. %.3fs = %.1fx" % (lo, hi, hi / lo if lo else float("inf")))
        print("max |rho| in the constant-time family: %.3f"
              % max(abs(p["rho_len_vs_latency"]) for _, p in flat))
        print("  (rho ~ 0 while body length varies is the point: generation time"
              " that ignores output size is not generation)")

        # Fleet grouping: DIDs sharing a latency constant are sharing a scheduler.
        buckets = collections.defaultdict(list)
        for d, p in flat:
            buckets[round(p["median_s"], 1)].append((d[-14:], p["n"], p["body_len_median"]))
        print("\nlatency constants shared by >1 DID (one scheduler, several identities):")
        for c, members in sorted(buckets.items()):
            if len(members) > 1:
                print("  %.1fs : %d DIDs, n=%s, median body len=%s"
                      % (c, len(members), [m[1] for m in members], sorted({m[2] for m in members})))
                print("          %s" % [m[0] for m in members])

    json.dump({d: p for d, p in order}, open("latency_signature.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote latency_signature.json")


if __name__ == "__main__":
    main()
