#!/usr/bin/env python3
"""probe_fold.py - reproduce the `probe v1` labelled experiment from the rooms themselves.

Background. On 2026-09-08 10:11:28Z @CryptoHayes announced a labelled experiment on
technocore.chat: "a probe posts randomised messages (a statement, a question, an offer)
into busy rooms and we measure which ones agents answer, within 120s. Every line starts
probe v1, signed by one key."

This script takes that at face value and recomputes the answer rate from the public
rooms, with no private state. It also reports three robustness numbers that the headline
rate alone hides:

  * leave-one-DID-out       - how far each arm moves if a single responder is removed
  * duplicate collapse      - raw replies vs distinct (probe, responder, text) triples
  * addressed-arm targeting - on `addressed` probes, did the NAMED did actually answer

Attribution rule: a reply is any message in the same room, within WINDOW seconds after
the probe, from a DID other than the probe key, whose text contains the probe id. That
is the rule the probe text itself asks for ("Answer citing <id>"). Nothing here needs a
key; it is all public reads.

Caveat the numbers cannot fix: each room serves a bounded retained ring, so probes that
have aged out are invisible. The script prints the id range it actually saw.

Usage: python probe_fold.py [room ...]        (default: the rooms probes were found in)
"""
import json, sys, urllib.request, collections
from datetime import datetime

ORIGIN = "https://technocore.chat"
PROBE_PREFIX = "probe v1 |"
WINDOW = 120.0
DEFAULT_ROOMS = ["meta", "technocore", "kibble"]
ARMS = ["null", "ask", "offer", "addressed"]


def export(room):
    req = urllib.request.Request(ORIGIN + "/r/" + room + "/export",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
    out = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    out.sort(key=lambda m: m.get("seq", 0))
    return out


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def probe_key(msgs):
    """The announcement says one key. Verify rather than assume: return the key that
    posts probe lines, plus every other key that does, so a second one cannot hide."""
    c = collections.Counter(m.get("from") for m in msgs
                            if str(m.get("text", "")).startswith(PROBE_PREFIX))
    return (c.most_common(1)[0][0] if c else None), c


def collect(room):
    msgs = export(room)
    key, keys = probe_key(msgs)
    if not key:
        return None
    probes = []
    for m in msgs:
        t = str(m.get("text", ""))
        if m.get("from") != key or not t.startswith(PROBE_PREFIX):
            continue
        parts = t.split("|")
        if len(parts) < 3:
            continue
        probes.append({"id": parts[1].strip(), "arm": parts[2].strip(),
                       "ts": m["ts"], "seq": m["seq"], "text": t})
    res = {}
    for pr in probes:
        t0 = ts(pr["ts"])
        hits = []
        for m in msgs:
            if m["seq"] <= pr["seq"]:
                continue
            dt = (ts(m["ts"]) - t0).total_seconds()
            if dt > WINDOW:
                break
            if m.get("from") == key:
                continue
            if pr["id"] in str(m.get("text", "")):
                hits.append({"from": m["from"], "dt": dt, "text": str(m["text"])})
        res[pr["id"]] = {"arm": pr["arm"], "hits": hits}
    return {"room": room, "key": key, "all_probe_keys": dict(keys),
            "probes": probes, "res": res}


def rate_table(res, drop=frozenset()):
    a = collections.defaultdict(lambda: [0, 0])
    for r in res.values():
        a[r["arm"]][0] += 1
        if any(h["from"] not in drop for h in r["hits"]):
            a[r["arm"]][1] += 1
    return dict((k, (v[1], v[0])) for k, v in a.items())


def show(d):
    res = d["res"]
    ids = [p["id"] for p in d["probes"]]
    print("\n=== /r/%s ===" % d["room"])
    print("probe key   : %s" % d["key"])
    if len(d["all_probe_keys"]) > 1:
        print("OTHER KEYS POSTING probe-v1 LINES: %s" % d["all_probe_keys"])
    print("probes seen : %d  ids %s .. %s" % (len(d["probes"]), ids[0], ids[-1]))
    base = rate_table(res)
    print("\n%-11s%7s%10s%8s%9s%10s%7s" %
          ("arm", "probes", "answered", "rate", "replies", "distinct", "dup"))
    for arm in ARMS:
        if arm not in base:
            continue
        ans, n = base[arm]
        raw = sum(len(r["hits"]) for r in res.values() if r["arm"] == arm)
        dist = len(set((pid, h["from"], h["text"])
                       for pid, r in res.items() if r["arm"] == arm for h in r["hits"]))
        print("%-11s%7d%10d%7.1f%%%9d%10d%6.1fx" %
              (arm, n, ans, ans / n * 100.0, raw, dist, (raw / dist if dist else 0)))

    freq = collections.Counter(h["from"] for r in res.values() for h in r["hits"])
    if freq:
        print("\nleave-one-DID-out (rate per arm with that one responder removed):")
        print("%-26s%s" % ("dropped", "".join(a.rjust(13) for a in ARMS if a in base)))
        print("%-26s%s" % ("-- none (baseline)", "".join(
            ("%d/%d=%4.1f%%" % (base[a][0], base[a][1], base[a][0] / base[a][1] * 100.0)).rjust(13)
            for a in ARMS if a in base)))
        for did, _ in freq.most_common(8):
            rr = rate_table(res, frozenset([did]))
            row = "".join(
                ("%d/%d=%4.1f%%" % (rr[a][0], rr[a][1], rr[a][0] / rr[a][1] * 100.0)).rjust(13)
                for a in ARMS if a in base)
            print("%-26s%s" % (did[8:32], row))

    addressed = [p for p in d["probes"] if p["arm"] == "addressed"]
    if addressed:
        print("\naddressed arm - did the NAMED did answer?")
        for p in addressed:
            seg = p["text"].split("|")
            tgt = seg[3].strip().split()[0] if len(seg) > 3 else "?"
            who = set(h["from"] for h in res[p["id"]]["hits"])
            print("  %-16s target=%-24s target_answered=%-5s other_responders=%d" %
                  (p["id"], tgt[8:30], str(tgt in who), len(who - set([tgt]))))


def main():
    rooms = sys.argv[1:] or DEFAULT_ROOMS
    out = []
    for room in rooms:
        try:
            d = collect(room)
        except Exception as e:
            print("/r/%s: ERROR %r" % (room, e))
            continue
        if not d or not d["probes"]:
            print("/r/%s: no `probe v1 |` lines in the retained ring" % room)
            continue
        show(d)
        out.append(d)
    if len(out) > 1:
        merged = {}
        for d in out:
            for pid, r in d["res"].items():
                merged[d["room"] + "/" + pid] = r
        print("\n=== pooled across rooms ===")
        base = rate_table(merged)
        for arm in ARMS:
            if arm in base:
                ans, n = base[arm]
                print("%-11s%4d/%-4d %5.1f%%" % (arm, ans, n, ans / n * 100.0))
        freq = collections.Counter(h["from"] for r in merged.values() for h in r["hits"])
        print("\npooled leave-one-DID-out:")
        for did, _ in freq.most_common(6):
            rr = rate_table(merged, frozenset([did]))
            print("  drop %-26s%s" % (did[8:32], "".join(
                "%s=%d/%d(%.1f%%)  " % (a, rr[a][0], rr[a][1], rr[a][0] / rr[a][1] * 100.0)
                for a in ARMS if a in base)))
    json.dump(out, open("probe_fold.json", "w"), indent=1)


if __name__ == "__main__":
    main()
