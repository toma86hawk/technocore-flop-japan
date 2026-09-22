# -*- coding: utf-8 -*-
"""useful_on_thin is bounded by an artifact of the response, and the bound moved.

useful_on_thin counts a useful attestation only if the RESULT row of the job it
points at is in the SAME /api/tape response.  Call that the join rate:

    join%  = useful attests whose job's result row is present in this response
             --------------------------------------------------------------
                          all useful attests in this response

By construction  useful_on_thin% <= join%.  join% is not a property of anyone's
behaviour: it is a property of what the response happens to contain.

tape_window_is_a_window.py established two things about that response across all
137 saved windows: it is anchored at the tape head (seq_hi rises in 136 of 136
steps, so the series IS indexed by time), and it is capped at 1000 rows with gaps
in every single window.  A fixed row cap means the mix inside the response
follows the board's mix.  If the board's attest:result ratio rises, a response of
1000 rows holds more attests and fewer results, and join% falls with nothing
changing about how carefully anyone audits.

This measures join%, the mix that drives it, and how much of the published fall
in useful_on_thin the bound alone accounts for.

Offline.  Reads useful_on_thin_*.json in the repo root.
"""
import json, glob, os, math, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W = []
for path in sorted(glob.glob(os.path.join(root, "useful_on_thin_*.json"))):
    stamp = os.path.basename(path)[len("useful_on_thin_"):-len(".json")]
    try:
        d = json.load(open(path, encoding="utf-8", errors="replace"))
    except Exception:
        continue
    msgs = d.get("messages", [])
    if not msgs:
        continue
    results = [m for m in msgs if m.get("kind") == "result"]
    result_jobs = {m.get("job_id") for m in results}
    thin_jobs = {m.get("job_id") for m in results
                 if m.get("thin") is True and m.get("scored") is False}
    attests = [m for m in msgs if m.get("kind") == "attest"]
    useful = [m for m in attests if str(m.get("verdict", "")).lower() == "useful"]
    if not useful:
        continue
    joinable = [m for m in useful if m.get("job_id") in result_jobs]
    uot = [m for m in useful if m.get("job_id") in thin_jobs]
    W.append({
        "stamp": stamp,
        "results": len(results),
        "attests": len(attests),
        "useful": len(useful),
        "join": 100.0 * len(joinable) / len(useful),
        "uot": 100.0 * len(uot) / len(useful),
        # conditional rate: of the attests that COULD join, how many hit thin work
        "uot_given_join": (100.0 * len(uot) / len(joinable)) if joinable else None,
        "att_per_result": len(attests) / float(max(1, len(results))),
    })

print("windows with at least one useful verdict:", len(W))


def corr(xs, ys):
    xs = [x for x, y in zip(xs, ys) if x is not None and y is not None]
    ys = [y for y in ys if y is not None]
    n = min(len(xs), len(ys))
    xs, ys = xs[:n], ys[:n]
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


first, last = W[:12], W[-12:]


def avg(rows, k):
    vals = [r[k] for r in rows if r.get(k) is not None]
    return sum(vals) / len(vals) if vals else None


print()
print("                     first 12 windows      last 12 windows")
for k, lab in [("results", "result rows/window"), ("useful", "useful attests/window"),
               ("att_per_result", "attests per result"), ("join", "join% (the BOUND)"),
               ("uot", "useful_on_thin%"), ("uot_given_join", "uot% GIVEN it could join")]:
    a, b = avg(first, k), avg(last, k)
    print("  %-24s %10.1f %20.1f" % (lab, a, b))

print()
print("pearson(attests-per-result, join%%): %s" % round(corr([w["att_per_result"] for w in W],
                                                            [w["join"] for w in W]), 3))
print("pearson(join%%, useful_on_thin%%):    %s" % round(corr([w["join"] for w in W],
                                                             [w["uot"] for w in W]), 3))
viol = [w for w in W if w["uot"] > w["join"] + 1e-9]
print("windows where useful_on_thin%% exceeded the bound: %d (must be 0)" % len(viol))

print()
print("READING:")
ja, jb = avg(first, "join"), avg(last, "join")
ua, ub = avg(first, "uot"), avg(last, "uot")
ca, cb = avg(first, "uot_given_join"), avg(last, "uot_given_join")
print("  useful_on_thin fell %.1f%% -> %.1f%% (a factor of %.1f)." % (ua, ub, ua / max(ub, 1e-9)))
print("  its ceiling fell   %.1f%% -> %.1f%% (a factor of %.1f) over the same span," % (ja, jb, ja / max(jb, 1e-9)))
print("  and the ceiling is set by what the 1000-row response contains, not by auditors.")
print("  Conditioned on the join being possible at all, the rate went %.1f%% -> %.1f%%." % (ca, cb))
if cb is not None and ca is not None and cb > ca * 0.5:
    print("  That conditional rate is the behavioural quantity, and it did NOT collapse.")
    print("  So the published collapse is substantially the ceiling moving, not behaviour.")
