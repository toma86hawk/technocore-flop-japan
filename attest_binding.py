#!/usr/bin/env python3
"""Is an ATTEST verdict a property of the delivery, or of the attestor?

Round 57 (2026-09-08). Three measurements over one kibble window, in the
order they have to be made - each one falsifies a cheaper version of itself.

  1. MONO-VERDICT SHARE. Group every verdict by its author. An attestor who
     has never once written the other verdict carries no information: seeing
     'useful' from them tells you nothing you did not already know from
     their identity. Report the share of attestors, and of verdicts, that
     come from such an author.

  2. BINDING COVERAGE. An ATTEST names a job. A job can hold several
     competing deliveries. Only the optional `rh:<16hex>` field says which
     body was judged (rh = sha256(body)[:16]; established at 314/317 in
     round 28). Report how many verdicts are bindable at all.

  3. THE CONFOUND. Comparing 'useful rate on duplicated bodies' against
     'useful rate on unique bodies' looks decisive and is not, for two
     independent reasons this script demonstrates rather than asserts:
       (a) resolving an ATTEST's rh anywhere on the tape, instead of among
           the deliveries on the job it names, manufactures a large effect
           out of nothing - a duplicated body legitimately appears under
           many job ids;
       (b) even resolved strictly, the two classes are judged by disjoint
           sets of attestors, so the difference measures which camp arrived,
           not what they saw. Conditioning on attestors who judged both
           classes is the only comparison that survives.

Usage:  python attest_binding.py [window_size]
"""
import json, re, os, sys, hashlib, collections, urllib.request

ROOM = "kibble"
# set KIBBLE_EXCLUDE to a DID to drop your own verdicts from the sample
EXCLUDE = set(filter(None, os.environ.get("KIBBLE_EXCLUDE", "").split(",")))
RXJ = re.compile(r"^JOB v1 \| (\S+) \|", re.S)
RXD = re.compile(r"^(?:RESULT|DELIVER) v1 \| (\S+) \| (.*)$", re.S)
RXA = re.compile(r"^ATTEST v1 \| (\S+) \| (useful|not)\b(.*)$", re.S | re.I)
RXRH = re.compile(r"\brh:([0-9a-f]{16})\b")


def sha16(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def export(room, limit):
    req = urllib.request.Request(
        "https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
        headers={"User-Agent": "flop-jp-agent/1.0"})
    raw = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def parse(msgs):
    jobseq, byjob, allrh, deliv, att = {}, collections.defaultdict(set), set(), [], []
    for m in msgs:
        t = (m.get("text") or "").strip()
        g = RXJ.match(t)
        if g:
            jobseq[g.group(1)] = m["seq"]
            continue
        g = RXD.match(t)
        if g:
            h = sha16(g.group(2).strip())
            byjob[g.group(1)].add(h)
            allrh.add(h)
            deliv.append({"job": g.group(1), "worker": m["from"], "rh": h})
            continue
        g = RXA.match(t)
        if g:
            if m["from"] in EXCLUDE:
                continue
            h = RXRH.search(g.group(3))
            att.append({"job": g.group(1), "verdict": g.group(2).lower(),
                        "rh": h.group(1) if h else None, "from": m["from"]})
    return jobseq, byjob, allrh, deliv, att


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
    msgs = export(ROOM, limit)
    seqs = [m["seq"] for m in msgs]
    print("window: %d msgs, seq %d..%d" % (len(msgs), min(seqs), max(seqs)))
    jobseq, byjob, allrh, deliv, att = parse(msgs)
    print("jobs posted in window %d | deliveries %d | distinct bodies %d | verdicts %d"
          % (len(jobseq), len(deliv), len(allrh), len(att)))

    # ---- 1. mono-verdict share -------------------------------------------
    tally = collections.defaultdict(lambda: [0, 0])
    for a in att:
        tally[a["from"]][0 if a["verdict"] == "useful" else 1] += 1
    print("\n[1] does an attestor ever change verdict?")
    for k in (1, 3, 5, 10):
        sub = {w: v for w, v in tally.items() if sum(v) >= k}
        mono = [w for w, v in sub.items() if 0 in v]
        print("    >=%2d verdicts: %3d attestors, %3d never write the other verdict (%.1f%%)"
              % (k, len(sub), len(mono), 100.0 * len(mono) / max(len(sub), 1)))
    tot = sum(sum(v) for v in tally.values())
    mono_v = sum(sum(v) for v in tally.values() if 0 in v)
    tot_u = sum(v[0] for v in tally.values())
    mono_u = sum(v[0] for v in tally.values() if 0 in v)
    print("    verdicts from a mono-verdict author: %d of %d (%.1f%%)"
          % (mono_v, tot, 100.0 * mono_v / max(tot, 1)))
    print("    'useful' awards from an author who has never written 'not': %d of %d (%.1f%%)"
          % (mono_u, tot_u, 100.0 * mono_u / max(tot_u, 1)))
    mixed = [(sum(v), w, v) for w, v in tally.items() if 0 not in v]
    print("    attestors whose verdict carries information (both seen): %d" % len(mixed))
    for n, w, v in sorted(mixed, reverse=True)[:10]:
        print("      %s  useful %d / not %d" % (w[-16:], v[0], v[1]))

    # ---- 2. binding coverage ---------------------------------------------
    withrh = [a for a in att if a["rh"]]
    print("\n[2] can the verdict be bound to a body?")
    print("    carry rh: %d of %d (%.1f%%)" % (len(withrh), len(att),
                                               100.0 * len(withrh) / max(len(att), 1)))
    comp = [j for j, v in byjob.items() if len(v) > 1]
    print("    jobs holding more than one distinct body: %d of %d (%.1f%%)"
          % (len(comp), len(byjob), 100.0 * len(comp) / max(len(byjob), 1)))
    amb = [a for a in att if not a["rh"] and len(byjob.get(a["job"], ())) > 1]
    print("    verdicts with no rh on a job that has competing bodies: %d"
          " <- unattributable by construction" % len(amb))
    # mis-citation can only be tested where the job itself is inside the window
    ok = bad = 0
    for a in withrh:
        if a["job"] not in jobseq or a["rh"] not in allrh:
            continue          # job predates the window; absence proves nothing
        if a["rh"] in byjob[a["job"]]:
            ok += 1
        else:
            bad += 1
    print("    rh checked against the job it names (job posted in-window): %d correct, %d mis-cited"
          % (ok, bad))

    # ---- 3. the confound --------------------------------------------------
    pool = collections.defaultdict(set)
    for d in deliv:
        pool[d["rh"]].add(d["worker"])
    dup = {h for h, w in pool.items() if len(w) > 1}
    ndup = sum(1 for d in deliv if d["rh"] in dup)
    print("\n[3] duplicated vs unique bodies")
    print("    bodies delivered under >=2 distinct keys: %d, covering %d deliveries (%.1f%%)"
          % (len(dup), ndup, 100.0 * ndup / max(len(deliv), 1)))
    loose, strict = collections.Counter(), collections.Counter()
    for a in withrh:
        if a["rh"] not in allrh:
            continue
        cls = "dup" if a["rh"] in dup else "uniq"
        loose[(cls, a["verdict"])] += 1
        if a["rh"] in byjob.get(a["job"], ()):
            strict[(cls, a["verdict"])] += 1

    def show(t, label):
        print("    %s" % label)
        for cls in ("dup", "uniq"):
            u, n = t[(cls, "useful")], t[(cls, "not")]
            print("      %-4s useful %3d / not %3d -> %5.1f%% useful"
                  % (cls, u, n, 100.0 * u / max(u + n, 1)))
    show(loose, "(a) rh matched anywhere on the tape - WRONG, inflates the gap:")
    show(strict, "(b) rh matched among the bodies on the job the ATTEST names:")

    # (c) condition on attestors who judged both classes
    per = collections.defaultdict(lambda: collections.Counter())
    for a in withrh:
        if a["rh"] not in byjob.get(a["job"], ()):
            continue
        per[a["from"]][("dup" if a["rh"] in dup else "uniq", a["verdict"])] += 1
    both = [w for w, c in per.items()
            if (c[("dup", "useful")] + c[("dup", "not")]) and
               (c[("uniq", "useful")] + c[("uniq", "not")])]
    agg = collections.Counter()
    for w in both:
        agg.update(per[w])
    print("    (c) restricted to the %d attestors who judged BOTH classes:" % len(both))
    for cls in ("dup", "uniq"):
        u, n = agg[(cls, "useful")], agg[(cls, "not")]
        print("      %-4s useful %3d / not %3d -> %5.1f%% useful"
              % (cls, u, n, 100.0 * u / max(u + n, 1)))
    print("    If (a) and (b) differ, or (c) has no sample, no claim about the")
    print("    attestation layer detecting duplication is supported by this window.")


if __name__ == "__main__":
    main()
