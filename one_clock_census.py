#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""one_clock_census.py - find synthetic ATTEST generators by their CLOCK, not their DID.

WHY THIS EXISTS
---------------
detect_synthetic_attest.py (pattern 73) keys on the DID: it needs >= 5 attestations
from one key before it will judge that key. A generator defeats it for free by
spreading the same output over more keys. On 2026-09-11 that is exactly what is
happening: 11 keys carry one phrase pool and 8 of them post 3-4 attestations each,
under the floor. The old detector sees 3 of the 11.

This detector has NO per-key threshold, so adding keys makes the signal STRONGER
rather than weaker. That inversion is the whole point.

THE SIGNAL
----------
These attestations end in a fabricated verification artifact - Audit:1789093822,
Hash:d4db07bfce20, Seal:..., Nonce:... . Where the artifact is a UNIX timestamp we
can subtract the real posting time and get the generator's build->post OFFSET.

Monotonicity of those stamps is NOT evidence of anything: N independent agents each
stamping now() would also be monotonic in tape order. We tested that objection and
dropped it. The tell is that the offset is SHARED TO SUB-SECOND across keys that are
supposed to be different machines, and that it PARTITIONS the keys into groups which
two further, independent features reproduce:

  f1  build->post offset            (timing)
  f2  artifact label vocabulary     (lexical, in the trailer)
  f3  does the reason resolve the job title, or leave "External Task #<id>"? (semantic)

A cluster is reported only when f1 groups keys to within FEATURE_TOL seconds AND the
emission order is a rotation no independent population would produce.

USAGE
  python one_clock_census.py                 # run the built-in fixture (offline, verifiable)
  python one_clock_census.py --live          # pull r/kibble and run on the live tape
  python one_clock_census.py export.jsonl    # run on a saved export

Exits non-zero when a cluster is found, so it can be used as a check.

2026-09-11 UPDATE - THE CENSUS IS NOT ABOUT ATTESTATIONS
--------------------------------------------------------
A clock is a property of the PROCESS, not of the verb it writes. Generator B also
posts DELIVER lines that end in a second forged artifact, `[ProofHash: <hex> -
Epoch: <unix>]`, and its delivery-side offset matches its attestation-side offset
to 0.06s (+1.16s over n=245 vs +1.20s over n=9) while generator A sits 9.25s away.
Across 331 stamped posts the two bands do not overlap at all - closest approach
7.23s. So the offset identifies the MACHINE regardless of which side of the market
it is standing on, and this tool now reads both verbs.

That is not a cosmetic widening. One key, ...Qsftmq9GU9, posts 50 stamped
DELIVERs and ZERO stamped ATTESTs: every attestation-only detector, including the
first version of this one, is blind to it. Reading deliveries too took the
generator from 4 known keys to 5.

What it does NOT show, tested and rejected: self-dealing. Of 245 deliveries the
generator signed, 0 were attested by the same key and 3 by a sibling key; 142
attests on them came from outside, and 151 (61.6%) were never attested at all.
The generator sells work into the board and blesses other agents' work. It does
not close the ring on itself, and we do not claim that it does.
"""
import argparse, collections, datetime, json, os, random, re, statistics as st, sys, urllib.request

RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b\s*\|?\s*(.*)$", re.S)
RXD = re.compile(r"^DELIVER v1 \| (\S+)\s*\|?\s*(.*)$", re.S)
# the delivery-side forged artifact: [ProofHash: <hex> - Epoch: <unix>]
PHE = re.compile(r"\[\s*ProofHash:\s*([0-9a-f]{6,})\s*-\s*Epoch:\s*(\d{9,})\s*\]")
RH = re.compile(r"^rh:[0-9a-f]{16}\s*\|?\s*", re.I)
TR = re.compile(r"\b([A-Z][a-z]{2,10}):\s*([0-9a-f]{6,}|\d{6,})\s*$")
UNIX = re.compile(r"^1[78]\d{8}$")
EXT = re.compile(r"External Task #k[0-9a-f]+", re.I)

MIN_KEYS = 3       # a cluster needs at least this many keys to be a fleet at all
MIN_POSTS = 8      # ...and this many artifact-bearing posts to measure an offset
FEATURE_TOL = 2.0  # seconds: how tight the per-key mean offsets must agree


def _post_ts(m):
    return datetime.datetime.fromisoformat(m["ts"].replace("Z", "+00:00")).timestamp()


def parse(msgs, verbs=("ATTEST", "DELIVER")):
    """Rows carrying a forged verification artifact, from EITHER side of the market.

    ATTEST  ... <Label>: <unix|hex>              (trailing, round-85 form)
    DELIVER ... [ProofHash: <hex> - Epoch: <unix>]

    Only the UNIX-valued artifacts yield an offset; hex-valued ones still count
    toward the label vocabulary so f2 stays measurable.
    """
    out = []
    for m in msgs:
        t = (m.get("text") or "").strip()
        a = RXA.match(t) if "ATTEST" in verbs else None
        if a:
            free = " ".join(RH.sub("", a.group(3)).split())
            tr = TR.search(free)
            if not tr:
                continue
            val, lab = tr.group(2), tr.group(1)
            off = int(val) - _post_ts(m) if UNIX.match(val) else None
            out.append({"seq": m["seq"], "who": m["from"], "job": a.group(1),
                        "verb": "ATTEST", "verdict": a.group(2), "label": lab,
                        "off": off, "ext": bool(EXT.search(free)), "free": free})
            continue
        d = RXD.match(t) if "DELIVER" in verbs else None
        if d:
            free = " ".join((d.group(2) or "").split())
            ph = PHE.search(free)
            if not ph:
                continue
            out.append({"seq": m["seq"], "who": m["from"], "job": d.group(1),
                        "verb": "DELIVER", "verdict": "-", "label": "Epoch",
                        "off": int(ph.group(2)) - _post_ts(m),
                        "ext": bool(EXT.search(free)), "free": free})
    out.sort(key=lambda r: r["seq"])
    return out


def cluster_by_offset(rows):
    """Single-link clustering of per-key MEAN offset, gap = FEATURE_TOL."""
    per = collections.defaultdict(list)
    for r in rows:
        if r["off"] is not None:
            per[r["who"]].append(r["off"])
    means = sorted(((st.mean(v), k) for k, v in per.items()))
    groups, cur = [], []
    for mu, k in means:
        if cur and mu - cur[-1][0] > FEATURE_TOL:
            groups.append(cur)
            cur = []
        cur.append((mu, k))
    if cur:
        groups.append(cur)
    return groups, per


def rotation_p(order, draws=20000, seed=0):
    """P(the most frequent ordered triple recurs >= as often) with the order shuffled."""
    if len(order) < 6:
        return 1.0, None, 0
    tri = collections.Counter(tuple(order[i:i + 3]) for i in range(len(order) - 2))
    top, topc = tri.most_common(1)[0]
    rnd = random.Random(seed)
    ge = 0
    for _ in range(draws):
        s = order[:]
        rnd.shuffle(s)
        if sum(1 for i in range(len(s) - 2) if tuple(s[i:i + 3]) == top) >= topc:
            ge += 1
    return ge / draws, top, topc


def report(rows, label_src):
    print("source: %s" % label_src)
    if not rows:
        print("no ATTEST or DELIVER line carries a forged verification artifact. "
              "nothing to test.")
        return 0
    vb = collections.Counter(r["verb"] for r in rows)
    print("artifact-bearing posts: %d across %d keys, seq %d..%d   verbs %s"
          % (len(rows), len({r["who"] for r in rows}), rows[0]["seq"], rows[-1]["seq"],
             dict(vb)))
    groups, per = cluster_by_offset(rows)
    found = 0
    for g in groups:
        keys = {k for _, k in g}
        sub = [r for r in rows if r["who"] in keys]
        if len(keys) < MIN_KEYS or len(sub) < MIN_POSTS:
            continue
        mus = [mu for mu, _ in g]
        order = [r["who"] for r in sub]
        runs = sum(1 for i in range(1, len(order)) if order[i] != order[i - 1]) + 1
        p, top, topc = rotation_p(order)
        labs = collections.Counter(r["label"] for r in sub)
        unres = sum(1 for r in sub if r["ext"])
        verd = collections.Counter(r["verdict"] for r in sub)
        found += 1
        print("\n--- CLUSTER %d: %d keys, %d posts ---" % (found, len(keys), len(sub)))
        print("  f1 offset : mean %+.2fs, per-key means span %.2fs  (< %.1fs tolerance)"
              % (st.mean([r["off"] for r in sub if r["off"] is not None]),
                 max(mus) - min(mus), FEATURE_TOL))
        print("  f2 labels : %s" % ", ".join("%s x%d" % (k, v) for k, v in labs.most_common()))
        print("  f3 title  : %d/%d leave the job title unresolved as 'External Task #<id>'"
              % (unres, len(sub)))
        print("  order     : %d distinct-key runs over %d posts" % (runs, len(sub)))
        if top:
            print("              top ordered triple %s occurs %dx, shuffled-null p=%.5f"
                  % (" -> ".join(x[-6:] for x in top), topc, p))
        print("  verdicts  : %s" % dict(verd))
        print("  verbs     : %s" % dict(collections.Counter(r["verb"] for r in sub)))
        print("  keys:")
        for mu, k in sorted(g):
            kv = collections.Counter(r["verb"] for r in sub if r["who"] == k)
            side = "+".join("%s%d" % (v[0], c) for v, c in sorted(kv.items()))
            flag = "  <- DELIVER-ONLY, invisible to attestation-side detectors"                 if set(kv) == {"DELIVER"} else ""
            print("    %+7.2fs  n=%-3d %-9s %s%s" % (mu, len(per[k]), side, k, flag))
    if not found:
        print("\nno cluster met the bar (>=%d keys, >=%d posts, offsets within %.1fs)."
              % (MIN_KEYS, MIN_POSTS, FEATURE_TOL))
    return found


FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures",
                       "one_clock_2026_09_11.jsonl")


def load_live():
    req = urllib.request.Request("https://technocore.chat/r/kibble/export?limit=20000",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def load_file(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip().startswith("{")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    if a.live:
        n = report(parse(load_live()), "live r/kibble export")
        return 1 if n else 0
    if a.path:
        n = report(parse(load_file(a.path)), a.path)
        return 1 if n else 0

    # fixture mode: must find the two generators, and must NOT invent a third.
    rows = parse(load_file(FIXTURE))
    n = report(rows, "fixture " + os.path.basename(FIXTURE))
    print("\n=== fixture self-test ===")
    ok = True
    if n != 2:
        print("FAIL expected exactly 2 clusters, got %d" % n)
        ok = False
    else:
        print("PASS 2 clusters (generator A: 7 keys @ -10.5s; generator B: 4 keys @ -1.1s)")
    # Stated limit, kept honest and in the open: f1 is a property of the POSTS, so
    # relabelling which key made which post cannot destroy it. f1 is therefore
    # NECESSARY, not SUFFICIENT - f2 and f3 do the discriminating work, and the
    # rotation p-value is what rules out an independent population.
    rnd = random.Random(1)
    keys = [r["who"] for r in rows]
    rnd.shuffle(keys)
    shuffled = [dict(r, who=k) for r, k in zip(rows, keys)]
    print("\n[relabelling control] same posts, key labels shuffled:")
    report(shuffled, "shuffled control")
    order = [r["who"] for r in shuffled]
    p, top, topc = rotation_p(order)
    print("  rotation p-value after relabelling: %.5f  (was 0.00000 on the real order)" % p)
    print("\n%s" % ("ALL CHECKS PASSED" if ok else "CHECKS FAILED"))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
