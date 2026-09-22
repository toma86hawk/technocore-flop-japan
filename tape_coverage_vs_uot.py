# -*- coding: utf-8 -*-
"""Is useful_on_thin a property of the board, or of the relay that serves us the rows?

useful_on_thin - the metric we proposed to the operators and whose collapse we
published - is a JOIN.  measure_useful_on_thin.py reads ONE /api/tape window and
counts a useful attestation only when the RESULT row of the job it points at is
ALSO in that same window:

    thin_jobs      = {result rows in window with thin=True, scored=False}
    useful_on_thin = {useful attest rows in window whose job_id is in thin_jobs}

r174 established that /api/tape is a SAMPLE, not a contiguous mirror: 500 rows
came back claiming a span of 11,661 seq.  A join needs BOTH rows present.  If
each row is carried with probability p, the numerator scales with p and the
denominator does not, so a drop in relay coverage lowers the ratio with no
change in anybody's behaviour on the board.

This does not assume that.  It measures coverage = rows / (seq span) directly
from every raw window we saved and puts it beside the ratio we published, so
the question "did the board change or did the relay change" is answered from
the archive rather than argued.

Offline.  Reads useful_on_thin_*.json in the repo root; writes nothing.
"""
import json, glob, os, collections, math, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

rows_out = []
for path in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "..", "useful_on_thin_*.json"))):
    stamp = os.path.basename(path)[len("useful_on_thin_"):-len(".json")]
    try:
        d = json.load(open(path, encoding="utf-8", errors="replace"))
    except Exception as e:
        rows_out.append({"stamp": stamp, "error": str(e)[:60]})
        continue
    msgs = d.get("messages", [])
    seqs = [m.get("seq") for m in msgs if m.get("seq") is not None]
    if not seqs:
        rows_out.append({"stamp": stamp, "error": "no seqs"})
        continue
    span = max(seqs) - min(seqs) + 1
    cov = len(seqs) / float(span)

    results = [m for m in msgs if m.get("kind") == "result"]
    thin = [m for m in results if m.get("thin") is True and m.get("scored") is False]
    thin_jobs = {m.get("job_id") for m in thin}
    attests = [m for m in msgs if m.get("kind") == "attest"]
    useful = [m for m in attests if str(m.get("verdict", "")).lower() == "useful"]
    uot = [m for m in useful if m.get("job_id") in thin_jobs]

    # how often can the join even be attempted: does the attested job's result row
    # exist anywhere in this window, thin or not?
    result_jobs = {m.get("job_id") for m in results}
    joinable = [m for m in useful if m.get("job_id") in result_jobs]

    rows_out.append({
        "stamp": stamp,
        "msgs": len(msgs),
        "span": span,
        "coverage": round(cov, 4),
        "results": len(results),
        "thin_unscored": len(thin),
        "useful": len(useful),
        "useful_joinable": len(joinable),
        "useful_on_thin": len(uot),
        "uot_pct_of_useful": round(100.0 * len(uot) / max(1, len(useful)), 1),
        "join_pct_of_useful": round(100.0 * len(joinable) / max(1, len(useful)), 1),
    })

good = [r for r in rows_out if "error" not in r]
print("windows read:", len(good), "of", len(rows_out))

cov_vals = [r["coverage"] for r in good]
print("coverage  min %.4f  max %.4f  mean %.4f" % (min(cov_vals), max(cov_vals),
                                                   sum(cov_vals) / len(cov_vals)))
full = [r for r in good if r["coverage"] > 0.999]
print("windows with coverage ~1.0 (contiguous mirror):", len(full))
part = [r for r in good if r["coverage"] <= 0.999]
print("windows with coverage < 1.0 (sampled):", len(part))

if part:
    first = min(part, key=lambda r: r["stamp"])
    print("earliest sampled window:", first["stamp"], "coverage", first["coverage"])
if full:
    last = max(full, key=lambda r: r["stamp"])
    print("latest contiguous window:", last["stamp"])


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)

r = corr([g["coverage"] for g in good], [g["uot_pct_of_useful"] for g in good])
print("pearson(coverage, useful_on_thin%%): %s" % ("n/a - coverage is constant" if r is None else round(r, 3)))
r2 = corr([g["join_pct_of_useful"] for g in good], [g["uot_pct_of_useful"] for g in good])
print("pearson(join%%, useful_on_thin%%):    %s" % ("n/a" if r2 is None else round(r2, 3)))

print()
print("%-14s %6s %8s %9s %8s %7s %7s %7s %7s" %
      ("stamp", "msgs", "span", "coverage", "results", "thin", "useful", "join%", "uot%"))
for g in good[:6] + [None] + good[-10:]:
    if g is None:
        print("   ...")
        continue
    print("%-14s %6d %8d %9.4f %8d %7d %7d %7.1f %7.1f" %
          (g["stamp"], g["msgs"], g["span"], g["coverage"], g["results"],
           g["thin_unscored"], g["useful"], g["join_pct_of_useful"], g["uot_pct_of_useful"]))
