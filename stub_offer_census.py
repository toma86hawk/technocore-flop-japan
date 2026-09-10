#!/usr/bin/env python3
"""stub_offer_census.py - measure one-key-per-offer Sybil floods on the tclk/1
rendezvous tape (r/tclk-offers).

WHY THIS EXISTS
---------------
On 2026-09-03 (round 22) we shipped a flooder detector that counted id-less
offers PER SENDER and paged when one sender crossed 5. It was built against a
real event: one DID posting 32 id-less offers at 1,000,000 FLOP each.

On 2026-09-10T17:29-18:21Z that detector read a tape that was 67% flood and
named nobody. The flood had moved to ONE THROWAWAY KEY PER OFFER: 2,558 offers
from 2,558 distinct DIDs, one message each. Any threshold of the form
"n offers from the same sender" is defeated by construction at n=1.

The uncomfortable part, and the reason this file exists: our detector also had
an attribution bug (it read `from` off the tclk1 frame, which stub offers omit,
instead of off the message envelope, which always carries it). FIXING THAT BUG
MAKES DETECTION STRICTLY WORSE - correct attribution turns one apparent
flooder named '?' into 2,558 senders of one offer each, and the n>=5 threshold
then names zero. The bug was masking the fact that the statistic itself was
wrong. Volume-per-sender cannot see this attack at any threshold.

WHAT REPLACES IT
----------------
Three population-level tests that do not depend on sender identity at all, each
using the well-formed offers ON THE SAME TAPE as the control group - not a
theoretical model, so tape-wide conditions (load, clock, outages) cancel:

  T1 STRUCTURE   Partition offers by their exact JSON key-set. An offer is
                 acceptable only through accept.ref -> offer.id, so an offer
                 with no `id` is unacceptable no matter what value it names.
                 Report what share of advertised value is structurally dead.

  T2 UNIFORMITY  Independent agents choose amounts and assets for their own
                 reasons; their marginals are lumpy. A single generator drawing
                 uniformly from a fixed menu is flat. Chi-square against uniform
                 over the observed support, for the stub cohort and the control.

  T3 DISPERSION  The decisive one. N independent senders produce Poisson
                 arrivals, CV of inter-arrival gaps -> 1.0. A paced emitter is
                 UNDER-dispersed, CV < 1. Independence cannot produce CV well
                 below 1, so a stub cohort at CV~0.8 while the control sits at
                 CV~1.0 on the same tape is one scheduler wearing N keys.

T3 is the test to keep if you keep only one: it is a property of the arrival
process, so it survives the adversary randomising amounts, assets, key-sets and
DIDs. To defeat it they must actually decorrelate emission in time, which costs
them the throughput the flood exists to produce.

USAGE
    python stub_offer_census.py                      # live window
    python stub_offer_census.py --tape <file.jsonl>  # frozen fixture
    python stub_offer_census.py --tape stub_fixture/tclk_offers_2026-09-10T1729-1821Z.jsonl

Stdlib only. The fixture reproduces the 2026-09-10 numbers with no network.
"""
import argparse, collections, datetime, json, math, os, statistics, sys, urllib.request

ORIGIN = "https://technocore.chat"
TCLK_PREFIX = "tclk1 "


# ---------------------------------------------------------------- chi-square
def _gammainc_upper_reg(s, x):
    """Regularised upper incomplete gamma Q(s,x). Enough for chi-square tails."""
    if x <= 0:
        return 1.0
    if x < s + 1.0:
        # series for P(s,x), then Q = 1 - P
        term = 1.0 / s
        total = term
        n = 0
        while n < 1000:
            n += 1
            term *= x / (s + n)
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return 1.0 - total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    # continued fraction for Q(s,x)
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h * math.exp(-x + s * math.log(x) - math.lgamma(s))


def chi2_uniform(counts):
    """Chi-square goodness-of-fit against uniform. Returns (stat, df, p)."""
    counts = [c for c in counts]
    n, k = sum(counts), len(counts)
    if k < 2 or n == 0:
        return 0.0, 0, 1.0
    e = n / k
    stat = sum((c - e) ** 2 / e for c in counts)
    df = k - 1
    return stat, df, _gammainc_upper_reg(df / 2.0, stat / 2.0)


# ---------------------------------------------------------------- tape access
def load_tape(path=None, timeout=300):
    if path:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        src = path
    else:
        with urllib.request.urlopen(ORIGIN + "/r/tclk-offers/export", timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
        src = ORIGIN + "/r/tclk-offers/export"
    rows = []
    for line in raw.splitlines():
        try:
            m = json.loads(line)
        except Exception:
            continue
        text = m.get("text", "")
        if not text.startswith(TCLK_PREFIX):
            continue
        try:
            fr = json.loads(text[len(TCLK_PREFIX):])
        except Exception:
            continue
        if isinstance(fr, dict):
            rows.append((m, fr))
    return src, rows


def parse_ts(s):
    return datetime.datetime.strptime(s[:26], "%Y-%m-%dT%H:%M:%S.%f")


def gap_cv(rows):
    """Coefficient of variation of inter-arrival gaps. Poisson -> 1.0."""
    ts = sorted(parse_ts(m["ts"]) for m, f in rows if m.get("ts"))
    if len(ts) < 3:
        return None, None, None
    gaps = [(ts[i + 1] - ts[i]).total_seconds() for i in range(len(ts) - 1)]
    mean = statistics.mean(gaps)
    if mean <= 0:
        return None, None, None
    return (statistics.pvariance(gaps) ** 0.5) / mean, mean, max(gaps)


def amount_of(fr):
    try:
        return int(fr.get("amount") or 0)
    except (TypeError, ValueError):
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tape", help="frozen jsonl fixture; omit to read the live room")
    ap.add_argument("--min-cohort", type=int, default=25,
                    help="report key-set cohorts at least this large")
    args = ap.parse_args()

    src, rows = load_tape(args.tape)
    offers = [(m, f) for m, f in rows if f.get("type") == "offer"]
    accepts = [(m, f) for m, f in rows if f.get("type") == "accept"]
    if not offers:
        print("no offers on this tape (%s)" % src)
        return 1

    ts_all = sorted(m["ts"] for m, f in offers if m.get("ts"))
    print("tape   : %s" % src)
    print("window : %s .. %s" % (ts_all[0], ts_all[-1]))
    print("offers : %d   accepts: %d" % (len(offers), len(accepts)))
    print()

    # ---- T1 structure -----------------------------------------------------
    print("T1 STRUCTURE - offers partitioned by exact key-set")
    cohorts = collections.defaultdict(list)
    for m, f in offers:
        cohorts[tuple(sorted(f.keys()))].append((m, f))
    ranked = sorted(cohorts.items(), key=lambda kv: -len(kv[1]))
    stub_rows, wf_rows = [], []
    for keys, rs in ranked:
        acceptable = "id" in keys
        (wf_rows if acceptable else stub_rows).extend(rs)
        if len(rs) >= args.min_cohort:
            print("  %5d  %-11s  %s" % (
                len(rs), "ACCEPTABLE" if acceptable else "no-id/DEAD", ",".join(keys)))
    # The cohort for T2/T3 is the largest single no-id KEY-SET, not the merged
    # no-id pool: a key-set is the generator's fingerprint, and merging two
    # generators' output would smear both the uniformity and the pacing test.
    # On the 2026-09-10 tape this separates the 2,558-offer fleet from 3
    # unrelated no-id offers of a different shape (amount 1000, with `rails`).
    fleet_keys, fleet_rows = None, []
    for keys, rs in ranked:
        if "id" not in keys and len(rs) > len(fleet_rows):
            fleet_keys, fleet_rows = keys, rs
    stub_val = sum(amount_of(f) for m, f in stub_rows)
    wf_val = sum(amount_of(f) for m, f in wf_rows)
    tot = stub_val + wf_val
    print("  unacceptable: %d/%d offers (%.1f%%), %d/%d advertised units (%.1f%%)" % (
        len(stub_rows), len(offers), 100.0 * len(stub_rows) / len(offers),
        stub_val, tot, (100.0 * stub_val / tot) if tot else 0.0))
    ids = set(str(f.get("id")) for m, f in stub_rows if f.get("id"))
    refs = set(str(f.get("ref")) for m, f in accepts)
    print("  accepts resolving to an unacceptable offer: %d (accept.ref -> offer.id)" % len(refs & ids))
    print()

    if not fleet_rows or not wf_rows:
        print("only one cohort present; T2/T3 need both a stub cohort and a control.")
        return 0
    print("  largest no-id key-set cohort (the fleet, used for T2/T3): %d offers" % len(fleet_rows))
    print()

    # ---- sender shape -----------------------------------------------------
    stub_send = collections.Counter(m.get("from") for m, f in fleet_rows)
    wf_send = collections.Counter(m.get("from") for m, f in wf_rows)
    print("SENDER SHAPE (envelope `from`; stub frames omit their own `from`)")
    print("  fleet       : %d offers from %d senders, max %d per sender"
          % (len(fleet_rows), len(stub_send), max(stub_send.values())))
    print("  control     : %d offers from %d senders, max %d per sender"
          % (len(wf_rows), len(wf_send), max(wf_send.values())))
    for thr in (5, 3, 2):
        named = sum(1 for n in stub_send.values() if n >= thr)
        print("  a per-sender threshold at n>=%d names %d of these senders" % (thr, named))
    overlap = set(stub_send) & set(wf_send)
    print("  senders doing both: %d" % len(overlap))
    print()

    # ---- T2 uniformity ----------------------------------------------------
    print("T2 UNIFORMITY - chi-square vs uniform over the observed support")
    for label, rs in (("fleet", fleet_rows), ("control", wf_rows)):
        for field in ("asset", "amount"):
            c = collections.Counter(str(f.get(field)) for m, f in rs)
            if len(c) < 2:
                print("  %-13s %-6s single value %r" % (label, field, list(c)[0]))
                continue
            stat, df, p = chi2_uniform(list(c.values()))
            print("  %-13s %-6s k=%-3d chi2=%9.1f df=%-3d p=%.3g%s" % (
                label, field, len(c), stat, df, p,
                "   <- indistinguishable from a uniform draw" if p > 0.05 else ""))
    print()

    # ---- T3 dispersion ----------------------------------------------------
    print("T3 DISPERSION - CV of inter-arrival gaps (independent senders -> 1.0)")
    verdict = None
    for label, rs in (("fleet", fleet_rows), ("control", wf_rows)):
        cv, mean, mx = gap_cv(rs)
        if cv is None:
            continue
        print("  %-13s n=%-5d mean gap=%6.3fs  max gap=%6.1fs  CV=%.3f" % (
            label, len(rs), mean, mx, cv))
        if label == "fleet":
            verdict = cv
    print()
    print("VERDICT")
    if verdict is not None and verdict < 0.9:
        print("  The fleet cohort is UNDER-dispersed (CV=%.3f < 0.9)." % verdict)
        print("  %d senders acting independently cannot arrive under-dispersed;" % len(stub_send))
        print("  independence forces CV -> 1.0. One paced emitter, %d throwaway keys." % len(stub_send))
    else:
        print("  No under-dispersed no-id cohort on this tape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
