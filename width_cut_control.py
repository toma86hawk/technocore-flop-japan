#!/usr/bin/env python3
"""Is an exact-width pile-up a writer's budget, or just where prose ends?

Round 37 (2026-09-05) recorded three DIDs whose deliveries stop at exactly
1200 characters and never exceed it, and round 97/127 recorded a second,
looser band at 1792-1798 shared across many keys.  Both were argued from the
pile-up alone: "N bodies land on one exact length, therefore a budget".

That argument has a hole.  Prose has natural stopping points, and any
histogram of 2,000 bodies has peaks.  The thing that separates a budget from
a coincidence is not the height of the peak, it is WHERE IN THE SENTENCE the
body ends.  A writer who finishes stops on punctuation.  A counter that trips
stops in the middle of a word.  So this tool reports one number the earlier
runs never computed: the mid-word cut rate INSIDE the band against the
mid-word cut rate in a neighbouring length range from the same window.

Without the control the measurement is not falsifiable - a band with a 3%
cut rate looks exactly like a band with a 93% cut rate if you only count rows.

A low mid-word rate does NOT mean "no generator".  A fixed-width TEMPLATE
(round 75, pattern 87) lands on one exact width and ends on a constant suffix,
so it is 100% punctuation-terminated.  The tool separates the two cases by
looking at the shared tail, and says which one it found.

Usage:  python guide/width_cut_control.py <queue.json> <width|lo-hi> [span]
        queue.json is an attest_collect*/attest_collect_offboard queue
        (needs body_len, result, worker per row).

Reads nothing from the network.  Makes no claim about whether a truncated
delivery fails its job: round 97 and round 127 both found band members that
satisfied their Success clause before the cut, and round 151 found three that
did not.  That judgement is a human reading the spec, not this script.
"""
import json, sys, collections

# A body that ends on a letter, digit, or an opener/separator was still being
# written when it stopped.  Terminal punctuation, a closing bracket or a quote
# means the writer chose to stop there.
OPEN_OR_MID = "-(,/[{&+="


def mid_word(body):
    s = (body or "").rstrip()
    return bool(s) and (s[-1].isalnum() or s[-1] in OPEN_OR_MID)


def shared_tail(band, tail=20, need=0.5):
    """The longest common ending shared by at least `need` of the band."""
    if not band:
        return ""
    ends = collections.Counter((r["result"] or "").rstrip()[-tail:] for r in band)
    end, n = ends.most_common(1)[0]
    return end if n >= need * len(band) else ""


def run(rows, width, span=300):
    wlo, whi = width if isinstance(width, tuple) else (width, width)
    band = [r for r in rows if wlo <= r["body_len"] <= whi]
    lo = wlo - span
    ctl = [r for r in rows if lo <= r["body_len"] < wlo]
    hi = [r for r in rows if whi < r["body_len"] <= whi + span]

    def rate(g):
        n = len(g)
        c = sum(1 for r in g if mid_word(r["result"]))
        return {"n": n, "mid_word": c,
                "pct": round(100.0 * c / n, 1) if n else None}

    per = collections.defaultdict(lambda: {"n": 0, "mid_word": 0})
    for r in band:
        k = r["worker"]
        per[k]["n"] += 1
        per[k]["mid_word"] += mid_word(r["result"])

    keys = sorted(per, key=lambda k: -per[k]["n"])
    over = {k[-12:]: max(r["body_len"] for r in rows if r["worker"] == k)
            for k in keys}
    tail = shared_tail(band)
    return {
        "width": [wlo, whi],
        "shared_tail_of_band": tail,
        "window_rows": len(rows),
        "at_width": rate(band),
        "control_below": {"range": [lo, wlo - 1], **rate(ctl)},
        "control_above": {"range": [whi + 1, whi + span], **rate(hi)},
        "keys_at_width": {k[-12:]: per[k] for k in keys},
        "key_max_body_len_in_window": over,
        "verdict": _verdict(rate(band), rate(ctl), rate(hi), over, whi, tail),
    }


def _verdict(band, ctl, hi, over, width, tail):
    if band["n"] < 10:
        return "INCONCLUSIVE: fewer than 10 bodies at this width"
    ref = ctl if ctl["pct"] is not None else hi
    if band["pct"] is None or ref["pct"] is None:
        return "INCONCLUSIVE: both controls are empty"
    if band["pct"] < 50:
        if tail:
            return ("FIXED-WIDTH TEMPLATE, NOT A CUT BUDGET: the bodies end on a "
                    "shared constant tail %r, so the width is imposed by a "
                    "formatter that finishes its sentence. This is round 75 "
                    "pattern 87 territory - use detect_fixed_width_delivery.py, "
                    "which tests length quantisation, not punctuation." % tail)
        return ("NOT A BUDGET: most bodies at this width end on punctuation, "
                "so the width is where the writing ended, not where it was cut")
    ceiling = all(v <= width for v in over.values())
    return ("BUDGET: %.1f%% cut mid-word at the width against %.1f%% in the "
            "control%s" % (band["pct"], ref["pct"],
                           "; no key in the window ever exceeds the width"
                           if ceiling else
                           "; but at least one key exceeds the width, so it is "
                           "a common stop, not a hard ceiling"))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    rows = json.load(open(sys.argv[1], encoding="utf-8"))
    span = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    arg = sys.argv[2]
    w = tuple(int(x) for x in arg.split("-")) if "-" in arg else int(arg)
    print(json.dumps(run(rows, w, span), ensure_ascii=False, indent=1))
