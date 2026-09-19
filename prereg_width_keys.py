#!/usr/bin/env python3
"""Resolve the round-152 pre-registration about a ~1795-char stopping budget.

r152 pooled two disjoint export windows and found 14 low-volume worker keys
whose every observed body stopped inside 1791-1798.  That reading is only worth
keeping if it survives a window it was not fitted on, so r152 wrote the
falsifier down in advance:

    if 3 or more of the 14 keys emit a body over 1800 chars in a future
    window, the per-key reading is WITHDRAWN.
    if none do after 2 more disjoint windows, raise it to a named budget.

This runs that test and nothing else.  It prints, per key, the number of
opportunities it had in the new window, because "key K never exceeds W" is
vacuous when K wrote nothing - that is the r152 self-correction and it applies
to the falsifier too.  A key with zero rows is reported as NO DATA and counts
toward neither side.

Usage:  prereg_width_keys.py <pair-queue.json> [--keys k1,k2,...] [--width 1800]
The queue must be an attest_collect_offboard.py pair file (job/result rows with
a `worker` DID and the untruncated `result` body).
"""
import json, sys

R152_KEYS = ["TY3deNtMzG9V", "5mVHQgiZGD4A", "SgDGsQ9sna5m", "st8QFeQT9hhW",
             "LqZW22TA3WAy", "Rvv1nipwty9E", "P7ZmX8Mt89ap", "hpBRgWSmFTWF",
             "DqD9vBKjfKcK", "BJJ9owkaaDL9", "GmznvbSwf7RM", "J4VzFqXXU9Xq",
             "9fK6RK1KNhbC", "BCsG7BcXFX3f"]


def run(rows, keys, width=1800, band=(1791, 1798)):
    per = {k: [] for k in keys}
    for r in rows:
        w = (r.get("worker") or "")[-12:]
        if w in per:
            body = r.get("result") or ""
            per[w].append(len(body))
    out, over, silent, held = {}, [], [], []
    for k in keys:
        lens = sorted(per[k])
        if not lens:
            silent.append(k)
            out[k] = {"rows": 0, "verdict": "NO DATA - no opportunity"}
            continue
        mx = max(lens)
        inband = sum(1 for n in lens if band[0] <= n <= band[1])
        if mx > width:
            over.append(k)
            v = "EXCEEDS"
        else:
            held.append(k)
            v = "held"
        out[k] = {"rows": len(lens), "max": mx, "min": min(lens),
                  "in_band": inband, "lens": lens[-6:], "verdict": v}
    if len(over) >= 3:
        verdict = ("WITHDRAWN - %d of the 14 keys exceeded %d (%s). The r152 "
                   "per-key reading does not survive this window."
                   % (len(over), width, ", ".join(over)))
    elif over:
        verdict = ("SURVIVES WITH DAMAGE - %d key(s) exceeded %d (%s), below "
                   "the 3 that would withdraw it, but the population is no "
                   "longer clean." % (len(over), width, ", ".join(over)))
    elif held:
        verdict = ("SURVIVES - %d of the 14 keys wrote in this window and none "
                   "exceeded %d; %d had no opportunity and prove nothing."
                   % (len(held), width, len(silent)))
    else:
        verdict = ("NOT TESTED - none of the 14 keys wrote in this window. "
                   "Zero evidence either way; do not count this as a window.")
    return {"width": width, "band": list(band), "keys_tested": len(held) + len(over),
            "keys_silent": len(silent), "exceeded": over, "held": held,
            "silent": silent, "verdict": verdict, "per_key": out}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    rows = json.load(open(sys.argv[1], encoding="utf-8"))
    keys = R152_KEYS
    width = 1800
    for i, a in enumerate(sys.argv):
        if a == "--keys":
            keys = sys.argv[i + 1].split(",")
        if a == "--width":
            width = int(sys.argv[i + 1])
    print(json.dumps(run(rows, keys, width), ensure_ascii=False, indent=1))
