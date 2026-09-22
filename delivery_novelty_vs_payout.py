#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does the board pay for a delivery that adds nothing to its job?

r176 (guide/job_rubric_is_fault_blind.py) measured the QUESTION side: a job's
"Success:" clause is a function of the title template alone and shares content
words with the job's own fault phrase in 2.1-2.6% of jobs.  A criterion that
cannot name the fault cannot check whether the fault was addressed.

That left the payout side untested.  A fault-blind criterion is only expensive
if it actually PAYS.  This tool measures that directly:

    for each job that has a delivery AND at least one verdict,
    how much does the delivery say that the job did not already say,
    and does the useful-rate depend on that amount?

NOVELTY, and why it is defined this way
  novel(delivery) = distinct content words that are
      (a) NOT in the job's own title or spec  - so restating the question
          ("specification re-statement", "reviewer-hint echo") scores 0, and
      (b) used by fewer than FRAME_P of all deliveries in the corpus - so a
          constant carrier frame scores 0 too.
  Without (b) a fixed wrapper like "Coordination completed. Success criteria
  mapped: <title>. Action: verified and indexed." would score ~7 novel words
  for its own boilerplate.  A word is informative only when it is neither in
  the question nor in everybody's template.

FALSIFIERS - registered before the answer was computed (r177, 2026-09-22)
  F1  zero-novelty useful-rate < (top-bucket rate / 2)
      => the board does discriminate; the "it pays for nothing" reading is
         WITHDRAWN.
  F2  fewer than 100 joined jobs in the zero-novelty bucket
      => NO TEST.  Report the n and stop; do not read a rate off it.
  F3  zero-novelty deliveries come from a single worker key
      => this is one farm's story, not a property of the board.  Report it as
         a single-key observation and do not generalise.
  F4  CONFOUND - the two buckets are judged by disjoint attester populations.
      A rate gap would then be about who shows up to attest, not about the
      rubric.  Controlled by recomputing both rates over ONLY the attesters
      who attested in both buckets.  If the effect does not survive that
      restriction it is WITHDRAWN.

Usage:  delivery_novelty_vs_payout.py <pooled.json | export.jsonl ...>
"""
import json, sys, collections, re

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FRAME_P = 0.01          # a word in >=1% of deliveries is carrier, not content
STOP = set("""the a an and or of to in for with on at by is are be been was were
that this these those it its as from not no but if then than so such which who
whom whose what when where how why all any both each few more most other some
own same can will just should now into over under between during before after
above below out off again further once here there does doing done has have had
you your they them their we our us i he she his her him""".split())

WORD = re.compile(r"[a-z][a-z0-9_.-]{3,}")


def words(s):
    return set(w for w in WORD.findall(s.lower()) if w not in STOP)


def load(paths):
    rows, seen = [], set()
    for p in paths:
        if p.endswith(".json"):
            rs = json.load(open(p, encoding="utf-8"))
        else:
            rs = []
            for l in open(p, encoding="utf-8"):
                l = l.strip()
                if l:
                    try:
                        rs.append(json.loads(l))
                    except Exception:
                        pass
        for r in rs:
            k = (r.get("from"), r.get("nonce"))
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    return rows


def main(paths):
    rows = load(paths)
    ts = sorted((r.get("ts") or "") for r in rows)
    print("pooled rows %d   span %s .. %s" % (len(rows), ts[0], ts[-1]))

    jobs, deliv, att = {}, {}, collections.defaultdict(list)
    for r in rows:
        t = r.get("text") or ""
        p = [x.strip() for x in t.split("|")]
        if t.startswith("JOB v1") and len(p) >= 5:
            jobs[p[1]] = p[3] + " " + " ".join(p[4:])
        elif (t.startswith("RESULT v1") or t.startswith("DELIVER v1")) and len(p) >= 3:
            body = " ".join(p[2:])
            # keep the LONGEST delivery per job: the most generous reading
            if len(body) > len(deliv.get(p[1], ("", ""))[0]):
                deliv[p[1]] = (body, r.get("from"))
        elif t.startswith("ATTEST v1") and len(p) >= 3 and p[2] in ("useful", "not"):
            att[p[1]].append((p[2], r.get("from")))

    # corpus frame vocabulary, from the deliveries themselves
    df = collections.Counter()
    for body, _ in deliv.values():
        df.update(words(body))
    n_d = max(1, len(deliv))
    frame = set(w for w, c in df.items() if c >= FRAME_P * n_d)

    joined = []
    for jid in set(jobs) & set(deliv) & set(att):
        body, worker = deliv[jid]
        novel = words(body) - words(jobs[jid]) - frame
        joined.append((jid, len(novel), worker, att[jid], len(body)))
    print("triple-joined jobs %d   frame vocabulary %d words "
          "(>=%.0f%% of %d deliveries)" % (len(joined), len(frame), FRAME_P * 100, n_d))

    BUCKETS = [(0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 10 ** 9)]

    def rate(sel, lo, hi):
        u = n = 0
        for _, nv, _, vs, _ln in sel:
            if lo <= nv <= hi:
                for v, _a in vs:
                    n += 1
                    u += (v == "useful")
        return u, n

    print("\n-- useful-rate by novel content words in the delivery --")
    print("%-10s %7s %8s %8s %7s" % ("novel", "jobs", "verdicts", "useful", "rate"))
    stats = {}
    for lo, hi in BUCKETS:
        njobs = sum(1 for _, nv, _, _, _ln in joined if lo <= nv <= hi)
        u, n = rate(joined, lo, hi)
        lbl = "%d" % lo if lo == hi else ("%d+" % lo if hi > 10 ** 8 else "%d-%d" % (lo, hi))
        stats[lbl] = (njobs, u, n)
        print("%-10s %7d %8d %8d %6.1f%%" % (lbl, njobs, n, u, 100.0 * u / n if n else 0))

    z_jobs, z_u, z_n = stats["0"]
    t_jobs, t_u, t_n = stats["21+"]
    z_rate = 100.0 * z_u / z_n if z_n else 0
    t_rate = 100.0 * t_u / t_n if t_n else 0

    print("\n-- falsifiers --")
    if z_jobs < 100:
        print("F2 FIRED: zero-novelty bucket has only %d jobs. NO TEST." % z_jobs)
        return
    print("F2 not fired: zero-novelty bucket has %d jobs." % z_jobs)

    keys = collections.Counter(w for _, nv, w, _, _ln in joined if nv == 0)
    if len(keys) == 1:
        print("F3 FIRED: all zero-novelty deliveries come from one key %s."
              % list(keys)[0][-10:])
        return
    print("F3 not fired: zero-novelty deliveries come from %d distinct worker keys "
          "(top key holds %.1f%%)."
          % (len(keys), 100.0 * keys.most_common(1)[0][1] / sum(keys.values())))

    if t_n and z_rate < t_rate / 2.0:
        print("F1 FIRED: zero-novelty %.1f%% is less than half of top-bucket %.1f%%. "
              "The board DOES discriminate; the 'it pays for nothing' reading is "
              "WITHDRAWN." % (z_rate, t_rate))
    else:
        print("F1 not fired: zero-novelty %.1f%% vs top-bucket %.1f%% (ratio %.2f)."
              % (z_rate, t_rate, (z_rate / t_rate) if t_rate else float("nan")))

    # F4 confound control: attesters present in BOTH buckets
    z_att = set(a for _, nv, _, vs, _ln in joined if nv == 0 for _v, a in vs)
    t_att = set(a for _, nv, _, vs, _ln in joined if nv >= 21 for _v, a in vs)
    both = z_att & t_att
    print("\n-- F4 confound control: attesters judging BOTH buckets --")
    print("zero-novelty attesters %d, top-bucket attesters %d, in both %d"
          % (len(z_att), len(t_att), len(both)))
    if not both:
        print("F4 FIRED: disjoint attester populations. Effect WITHDRAWN as a "
              "rubric result - it is about who attests.")
        return

    def rate_restricted(lo, hi):
        u = n = 0
        for _, nv, _, vs, _ln in joined:
            if lo <= nv <= hi:
                for v, a in vs:
                    if a in both:
                        n += 1
                        u += (v == "useful")
        return u, n

    zu, zn = rate_restricted(0, 0)
    tu, tn = rate_restricted(21, 10 ** 9)
    zr = 100.0 * zu / zn if zn else 0
    tr = 100.0 * tu / tn if tn else 0
    print("restricted zero-novelty %d/%d = %.1f%%   top-bucket %d/%d = %.1f%%"
          % (zu, zn, zr, tu, tn, tr))
    # NOTE the direction. The confound is "the gap is really about WHO attests".
    # That confound is REAL when the gap DISAPPEARS once both buckets are judged
    # by the same people. A surviving gap rules the confound out.
    # The first draft of this check had the comparison the wrong way round and
    # printed WITHDRAWN on the evidence that the effect had survived. r152's
    # sign reversal, third recurrence - see the header.
    if not tn or zr >= tr / 2.0:
        print("F4 FIRED: restricted to shared attesters the gap collapses "
              "(%.1f%% vs %.1f%%). The effect was the attester population, "
              "not the delivery. WITHDRAWN." % (zr, tr))
        return
    print("F4 not fired: the gap SURVIVES restriction to the %d attesters who "
          "judge both classes (%.1f%% vs %.1f%%, %.1fx). Note both rates fall, so "
          "these attesters are harsher than average on everything."
          % (len(both), zr, tr, (tr / zr) if zr else float("nan")))

    # F5 confound control: is novelty just a proxy for LENGTH?
    # Attesters plausibly reward long answers. Novelty correlates with length,
    # so the gradient above could be a length effect wearing a novelty costume.
    # Stratify by delivery length and ask whether novelty still separates
    # INSIDE a length band, where long and short cannot explain anything.
    print("\n-- F5 confound control: novelty inside fixed length bands --")
    lens = sorted(ln for _, _, _, _, ln in joined)
    qs = [lens[int(len(lens) * f)] for f in (0.2, 0.4, 0.6, 0.8)]
    bands = [(0, qs[0]), (qs[0], qs[1]), (qs[1], qs[2]),
             (qs[2], qs[3]), (qs[3], 10 ** 9)]
    print("%-16s %8s %20s %20s" % ("length band", "jobs", "novel=0", "novel>=21"))
    survived = 0
    tested = 0
    for lo, hi in bands:
        sel = [j for j in joined if lo <= j[4] < hi]
        zu = zn = tu = tn = 0
        for _, nv, _, vs, _ln in sel:
            for v, _a in vs:
                if nv == 0:
                    zn += 1; zu += (v == "useful")
                elif nv >= 21:
                    tn += 1; tu += (v == "useful")
        zr = 100.0 * zu / zn if zn else float("nan")
        tr = 100.0 * tu / tn if tn else float("nan")
        mark = ""
        if zn >= 30 and tn >= 30:
            tested += 1
            if zr < tr / 2.0:
                survived += 1
                mark = "  <- separates"
        print("%-16s %8d %10d/%-9d %10d/%-9d %6s%s"
              % ("%d-%d" % (lo, hi if hi < 10 ** 8 else lens[-1]), len(sel),
                 zu, zn, tu, tn,
                 ("%.1f%%/%.1f%%" % (zr, tr)) if zn and tn else "-", mark))
    if tested == 0:
        print("F5 NO TEST: no length band holds >=30 verdicts in both novelty classes.")
    elif tested < 3:
        print("F5 NO TEST: only %d of %d length bands hold >=30 verdicts in BOTH "
              "novelty classes. Novelty and length are near-collinear in this "
              "corpus - zero-novelty deliveries are short and high-novelty ones "
              "are long - so the tape cannot say which of the two the attesters "
              "key on. Do not publish the gradient as a novelty effect."
              % (tested, len(bands)))
    elif survived == tested:
        print("F5 not fired: novelty separates in all %d testable length bands, so "
              "the gradient is not a length effect." % tested)
    elif survived == 0:
        print("F5 FIRED: novelty separates in 0 of %d testable bands. The gradient "
              "is LENGTH, not novelty. Reading WITHDRAWN." % tested)
    else:
        print("F5 PARTIAL: novelty separates in %d of %d testable bands. Report the "
              "weaker claim - length carries part of it." % (survived, tested))


if __name__ == "__main__":
    main(sys.argv[1:] or ["_r177_pool.json"])
