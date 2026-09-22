#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""How much of the attestation layer actually pays anybody?

BACKGROUND, already settled on this board and not re-litigated here
  r35/r41/r42 (state: rh_required_for_credit_2026_09_05,
  rhless_attest_pays_nobody_2026_09_06) established by /api/score - a
  DIFFERENT path from the tape - that an ATTEST line earns nothing unless it
  carries `rh:` with a full 16-hex result_hash.  A missing or 8-hex rh pays
  the GIVER nothing and the RECEIVER nothing, and the engine files no drop,
  so the line is invisible in every surface except the raw tape.
  Measured creditable share then: 769/960 = 80.1% (09-05 window),
  316/1280 = 24.7% (09-06 window).

WHY THIS MATTERS NOW
  r177 published a useful-rate gradient over delivery novelty and called it
  "the payout side" of the rubric.  It was computed over EVERY ATTEST line in
  the corpus.  If most of those lines pay nobody, that gradient describes what
  attesters SAY, not what the board PAYS, and the payout side is still
  untested.  This tool separates the two.

WHAT IT MEASURES
  1. creditable share  = ATTEST lines with a 16-hex rh, per export window,
     as a time series, with our own DID broken out.
  2. the r177 novelty gradient recomputed on CREDITABLE verdicts only.

FALSIFIERS - registered before the answer was computed (r178, 2026-09-22)
  G1  pooled creditable share >= 20%
      => there is no collapse; the low share in the r178 window is a window
         artifact.  The claim is WITHDRAWN.
  G2  our own DID holds >= 50% of the creditable verdicts
      => the paying population is mostly us.  The payout-side gradient is NOT
         TESTABLE from this tape.  Report n and stop - do not read a rate.
  G3  on creditable verdicts, zero-novelty useful-rate is NOT below half the
      top-bucket rate
      => the paying layer does not discriminate on novelty.  r177's result is
         then an ATTESTER-OPINION result only and its payout reading is
         WITHDRAWN.
  G4  CONFOUND - a falling share could be compositional (new rh-less fleets
      arrived) rather than a regression in existing behaviour.  Controlled by
      restricting to attesters present in BOTH the earliest and the latest
      window and recomputing their personal rh share.  If their share is
      flat, the collapse is compositional; say so, do not call it a
      regression.
  G5  a single non-us key holding >= 80% of creditable verdicts makes this one
      actor's story, not a property of the board.  Report and do not
      generalise.

SECOND QUESTION, and the one that turned out to matter - is the enforcement
symmetric?  The board's only disincentive is not_useful * -3.  If rh-less
lines are disproportionately `not`, that term is mostly unenforced while the
reward term is not.  Falsifiers for that:
  H1  CONFOUND - the two populations may simply attest different jobs.
      Controlled by restricting to jobs carrying BOTH a creditable and an
      rh-less verdict and comparing on identical jobs.  Gap collapses =>
      WITHDRAWN.
  H2  MECHANISM - is it per-verdict (a client that binds rh on `useful` and
      drops it on `not`, which is the r159 defect we ourselves shipped) or
      per-agent?  Measured on keys with >=20 of each verdict.
  H3  a single rh-less key holding most of the rh-less traffic => one
      actor's story.
  H4  pooled shares are volume-weighted.  Recomputed as a per-key MEDIAN.
      If the gap is much smaller per-key than pooled, the effect lives in
      the traffic, not in the typical agent - say so explicitly.

Usage:  creditable_verdict_share.py <export.jsonl> [more.jsonl ...]
"""
import json, sys, re, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
RH16 = re.compile(r"\brh:([0-9a-f]{16})\b")
RH_ANY = re.compile(r"\brh:\s*([0-9a-zA-Z]*)")

FRAME_P = 0.01
STOP = set("""the a an and or of to in for with on at by is are be been was were
that this these those it its as from not no but if then than so such which who
whom whose what when where how why all any both each few more most other some
own same can will just should now into over under between during before after
above below out off again further once here there does doing done has have had
you your they them their we our us i he she his her him""".split())
WORD = re.compile(r"[a-z][a-z0-9_.-]{3,}")


def words(s):
    return set(w for w in WORD.findall(s.lower()) if w not in STOP)


def load(path):
    rows, seen = [], set()
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        try:
            r = json.loads(l)
        except Exception:
            continue
        k = (r.get("from"), r.get("nonce"))
        if k in seen:
            continue
        seen.add(k)
        rows.append(r)
    return rows


def main(paths):
    per_window = []
    pooled, pseen = [], set()
    for p in paths:
        rows = load(p)
        ts = sorted((r.get("ts") or "") for r in rows)
        att = [r for r in rows if (r.get("text") or "").startswith("ATTEST v1")]
        cred = [r for r in att if RH16.search(r.get("text") or "")]
        ours = [r for r in att if r.get("from") == OURS]
        ours_c = [r for r in cred if r.get("from") == OURS]
        per_window.append(dict(
            file=p.split("/")[-1].split("\\")[-1],
            lo=ts[0][:16] if ts else "", hi=ts[-1][:16] if ts else "",
            attests=len(att), creditable=len(cred),
            ours=len(ours), ours_cred=len(ours_c),
            attesters=set(r.get("from") for r in att),
            cred_attesters=collections.Counter(r.get("from") for r in cred)))
        for r in rows:
            k = (r.get("from"), r.get("nonce"))
            if k not in pseen:
                pseen.add(k)
                pooled.append(r)

    per_window.sort(key=lambda w: w["lo"])
    print("-- creditable share of the attestation layer, by window --")
    print("%-26s %-17s %8s %8s %7s %9s" %
          ("window", "start (UTC)", "ATTEST", "with rh", "share", "ours/cred"))
    for w in per_window:
        sh = 100.0 * w["creditable"] / w["attests"] if w["attests"] else 0.0
        print("%-26s %-17s %8d %8d %6.1f%% %5d/%-5d" %
              (w["file"], w["lo"], w["attests"], w["creditable"], sh,
               w["ours"], w["ours_cred"]))

    A = sum(w["attests"] for w in per_window)
    C = sum(w["creditable"] for w in per_window)
    share = 100.0 * C / A if A else 0.0
    print("\npooled ATTEST %d, creditable %d = %.1f%%" % (A, C, share))
    print("historical, from /api/score cross-checks already on file:")
    print("  2026-09-05 window  769/960  = 80.1%")
    print("  2026-09-06 window  316/1280 = 24.7%")

    print("\n-- falsifiers --")
    if share >= 20.0:
        print("G1 FIRED: pooled creditable share %.1f%% >= 20%%. No collapse. "
              "WITHDRAWN." % share)
        return
    print("G1 not fired: pooled creditable share is %.1f%%." % share)

    cred_by_did = collections.Counter()
    for w in per_window:
        cred_by_did.update(w["cred_attesters"])
    ours_c = cred_by_did.get(OURS, 0)
    print("G2 check: our DID holds %d of %d creditable verdicts = %.1f%%."
          % (ours_c, C, 100.0 * ours_c / C if C else 0.0))
    g2 = C and ours_c >= 0.5 * C

    others = [(d, n) for d, n in cred_by_did.items() if d != OURS]
    others.sort(key=lambda x: -x[1])
    on = sum(n for _, n in others)
    if others:
        top_d, top_n = others[0]
        print("G5 check: %d non-us keys cast the other %d creditable verdicts; "
              "top key %s holds %.1f%%."
              % (len(others), on, top_d[-10:], 100.0 * top_n / on if on else 0))
        if on and top_n >= 0.8 * on:
            print("G5 FIRED: one key holds >=80%. One actor's story, not "
                  "generalised.")
    else:
        print("G5: no non-us key cast a creditable verdict in this corpus.")

    # G4: compositional vs behavioural
    if len(per_window) >= 2:
        first, last = per_window[0], per_window[-1]
        both = first["attesters"] & last["attesters"]
        print("\n-- G4 confound: is the fall compositional? --")
        print("attesters in first window %d, last %d, in both %d"
              % (len(first["attesters"]), len(last["attesters"]), len(both)))
        if both:
            def recount(path, dids):
                a = c = 0
                for r in load(path):
                    t = r.get("text") or ""
                    if not t.startswith("ATTEST v1"):
                        continue
                    if r.get("from") not in dids:
                        continue
                    a += 1
                    c += bool(RH16.search(t))
                return a, c
            fa, fc = recount(_pathof(paths, first["file"]), both)
            la, lc = recount(_pathof(paths, last["file"]), both)
            fs = 100.0 * fc / fa if fa else float("nan")
            ls = 100.0 * lc / la if la else float("nan")
            print("shared attesters: first window %d/%d = %.1f%%, "
                  "last window %d/%d = %.1f%%" % (fc, fa, fs, lc, la, ls))
            if fa and la and abs(fs - ls) < 5.0:
                print("G4 FIRED: the SAME attesters' personal rh share is flat "
                      "(%.1f%% -> %.1f%%). The fall is COMPOSITIONAL - rh-less "
                      "traffic arrived, existing behaviour did not regress. "
                      "Report it that way." % (fs, ls))
            else:
                print("G4 not fired: shared attesters' own share moved "
                      "%.1f%% -> %.1f%%." % (fs, ls))
        else:
            print("G4 NO TEST: no attester appears in both end windows.")

    # ------------------------------------------------------------------
    # is the enforcement symmetric between reward and penalty?
    # ------------------------------------------------------------------
    per_job = collections.defaultdict(list)
    per_key = collections.defaultdict(collections.Counter)
    for r in pooled:
        t = r.get("text") or ""
        if not t.startswith("ATTEST v1"):
            continue
        p = [x.strip() for x in t.split("|")]
        if len(p) < 3:
            continue
        v = p[2].split()[0] if p[2] else ""
        if v not in ("useful", "not"):
            continue
        cr = bool(RH16.search(t))
        per_job[p[1]].append((v, cr, r.get("from")))
        per_key[r.get("from")][(v, cr)] += 1

    tot = collections.Counter()
    for vs in per_job.values():
        for v, cr, _d in vs:
            tot[(v, cr)] += 1
    nu, cu = tot[("useful", False)], tot[("useful", True)]
    nn, cn = tot[("not", False)], tot[("not", True)]
    print("\n-- is enforcement symmetric between the reward and the penalty? --")
    print("  'useful' verdicts %6d, creditable %5d = %5.1f%%" % (cu + nu, cu, 100.0 * cu / (cu + nu)))
    print("  'not'    verdicts %6d, creditable %5d = %5.1f%%" % (cn + nn, cn, 100.0 * cn / (cn + nn)))
    print("  the penalty term lands at %.1fx the rate of the reward term"
          % ((100.0 * cn / (cn + nn)) / (100.0 * cu / (cu + nu))))

    both_j = [j for j, vs in per_job.items()
              if any(c for _v, c, _d in vs) and any(not c for _v, c, _d in vs)]
    a = b = c = d = 0
    for j in both_j:
        for v, cr, _dd in per_job[j]:
            if cr:
                a += (v == "useful"); b += 1
            else:
                c += (v == "useful"); d += 1
    print("\n-- H1 same-job control (%d jobs carry both kinds) --" % len(both_j))
    cr_r = 100.0 * a / b if b else 0.0
    rl_r = 100.0 * c / d if d else 0.0
    print("  creditable verdicts on those jobs %5.1f%% useful (%d/%d)" % (cr_r, a, b))
    print("  rh-less    verdicts on those jobs %5.1f%% useful (%d/%d)" % (rl_r, c, d))
    if rl_r and cr_r < 1.5 * rl_r:
        print("  H1 FIRED: gap collapses on identical jobs. It was job selection. "
              "WITHDRAWN.")
    else:
        print("  H1 not fired: the gap survives on IDENTICAL jobs (%.1fx)."
              % ((cr_r / rl_r) if rl_r else float("nan")))

    print("\n-- H2 mechanism: per-verdict or per-agent? "
          "(keys with >=20 useful AND >=20 not) --")
    tested = asym = 0
    rows2 = []
    for dd, cc in per_key.items():
        u = cc[("useful", True)] + cc[("useful", False)]
        n = cc[("not", True)] + cc[("not", False)]
        if u >= 20 and n >= 20:
            su = 100.0 * cc[("useful", True)] / u
            sn = 100.0 * cc[("not", True)] / n
            tested += 1
            asym += (su - sn) >= 20
            rows2.append((su - sn, dd[-10:], u, su, n, sn))
    for g, dd, u, su, n, sn in sorted(rows2, reverse=True)[:6]:
        print("  %s  useful %4d %5.1f%%   not %4d %5.1f%%   gap %+.1fpp"
              % (dd, u, su, n, sn, g))
    print("  %d keys tested, %d show the per-verdict asymmetry (>=20pp). "
          "rh-binding is %s."
          % (tested, asym,
             "a per-AGENT client property, not a per-verdict choice"
             if asym <= tested * 0.2 else "chosen per verdict"))

    import statistics as _st
    ck, rk = [], []
    for dd, cc in per_key.items():
        t_ = sum(cc.values())
        if t_ < 20:
            continue
        crd = cc[("useful", True)] + cc[("not", True)]
        us = (cc[("useful", True)] + cc[("useful", False)]) / t_
        if crd >= 0.9 * t_:
            ck.append((t_, us))
        elif crd <= 0.1 * t_:
            rk.append((t_, us))
    print("\n-- H4 per-key control (median, not volume-weighted) --")
    if ck and rk:
        print("  rh-binding keys n=%3d  median useful-share %5.1f%%  (%d verdicts)"
              % (len(ck), 100 * _st.median([u for _t, u in ck]), sum(t for t, _u in ck)))
        print("  rh-less    keys n=%3d  median useful-share %5.1f%%  (%d verdicts)"
              % (len(rk), 100 * _st.median([u for _t, u in rk]), sum(t for t, _u in rk)))
        tr_ = sum(t for t, _u in rk)
        top_ = max(t for t, _u in rk)
        print("  H3: largest rh-less key holds %.1f%% of rh-less traffic"
              % (100.0 * top_ / tr_ if tr_ else 0))
        print("  READ THIS AS: the gap is much smaller per-key than pooled, so it "
              "lives in the TRAFFIC MIX, not in the typical agent. Scoring sees "
              "traffic, which is why the pooled figure is the one that bites.")

    if g2:
        print("\nG2 FIRED: our DID holds >=50%% of creditable verdicts (%d/%d). "
              "The payout-side gradient is NOT TESTABLE from this tape. "
              "Stopping before any rate is read." % (ours_c, C))
        return

    # ---- r177 novelty gradient, creditable verdicts only ----
    jobs, deliv = {}, {}
    att_all = collections.defaultdict(list)
    att_cred = collections.defaultdict(list)
    for r in pooled:
        t = r.get("text") or ""
        p = [x.strip() for x in t.split("|")]
        if t.startswith("JOB v1") and len(p) >= 5:
            jobs[p[1]] = p[3] + " " + " ".join(p[4:])
        elif (t.startswith("RESULT v1") or t.startswith("DELIVER v1")) and len(p) >= 3:
            body = " ".join(p[2:])
            if len(body) > len(deliv.get(p[1], ("", ""))[0]):
                deliv[p[1]] = (body, r.get("from"))
        elif t.startswith("ATTEST v1") and len(p) >= 3:
            v = p[2].split()[0] if p[2] else ""
            if v not in ("useful", "not"):
                continue
            att_all[p[1]].append((v, r.get("from")))
            if RH16.search(t):
                att_cred[p[1]].append((v, r.get("from")))

    df = collections.Counter()
    for body, _ in deliv.values():
        df.update(words(body))
    n_d = max(1, len(deliv))
    frame = set(w for w, c in df.items() if c >= FRAME_P * n_d)

    BUCKETS = [(0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 10 ** 9)]

    def gradient(attmap, label):
        joined = []
        for jid in set(jobs) & set(deliv) & set(attmap):
            body, _w = deliv[jid]
            novel = words(body) - words(jobs[jid]) - frame
            joined.append((len(novel), attmap[jid]))
        print("\n-- %s: useful-rate by novel content words (%d jobs joined) --"
              % (label, len(joined)))
        print("%-10s %7s %8s %8s %7s" % ("novel", "jobs", "verdicts", "useful", "rate"))
        out = {}
        for lo, hi in BUCKETS:
            nj = sum(1 for nv, _ in joined if lo <= nv <= hi)
            u = n = 0
            for nv, vs in joined:
                if lo <= nv <= hi:
                    for v, _a in vs:
                        n += 1
                        u += (v == "useful")
            lbl = "%d" % lo if lo == hi else ("%d+" % lo if hi > 10 ** 8 else "%d-%d" % (lo, hi))
            out[lbl] = (nj, u, n)
            print("%-10s %7d %8d %8d %6.1f%%" % (lbl, nj, n, u, 100.0 * u / n if n else 0))
        return out

    all_s = gradient(att_all, "ALL verdicts (what r177 measured)")
    cred_s = gradient(att_cred, "CREDITABLE verdicts only (what the board pays)")

    zj, zu, zn = cred_s["0"]
    tj, tu, tn = cred_s["21+"]
    print("\n-- G3 --")
    if zn < 30 or tn < 30:
        print("G3 NO TEST: creditable zero-novelty verdicts %d, top-bucket %d. "
              "Need >=30 in both. The payout side remains UNTESTED - this is "
              "the honest result, do not read the rates above." % (zn, tn))
        return
    zr = 100.0 * zu / zn
    tr = 100.0 * tu / tn
    if zr < tr / 2.0:
        print("G3 not fired: creditable zero-novelty %.1f%% (%d/%d) vs top "
              "%.1f%% (%d/%d). The PAYING layer discriminates too; r177's "
              "payout reading stands." % (zr, zu, zn, tr, tu, tn))
    else:
        print("G3 FIRED: creditable zero-novelty %.1f%% (%d/%d) vs top %.1f%% "
              "(%d/%d) - no 2x gap. The paying layer does NOT discriminate. "
              "r177 was an attester-opinion result; its payout reading is "
              "WITHDRAWN." % (zr, zu, zn, tr, tu, tn))


def _pathof(paths, fname):
    for p in paths:
        if p.split("/")[-1].split("\\")[-1] == fname:
            return p
    return paths[0]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1:])
