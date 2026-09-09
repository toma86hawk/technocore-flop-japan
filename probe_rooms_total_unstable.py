#!/usr/bin/env python3
"""The `total` and `capacity` fields of technocore.chat/rooms are not stable
values, so no single read of them supports a claim about the size of the room
namespace.

Written 2026-09-09 to CORRECT a claim this project published earlier the same
day ("the 51,842-room namespace"). That figure came from one read. It does not
survive repetition.

Two independent instabilities are measured:
  A. Between identical requests. Repeated GETs with the SAME limit return a
     small set of distinct values, consistent with more than one backend
     serving the route from different state.
  B. Across the `limit` parameter. `total` is supposed to describe the whole
     namespace and `capacity` a fixed ceiling, so neither should depend on how
     many rows the caller asked for. Both do.

If A shows one value per limit and B shows one value across limits, the fields
are stable and this probe reports exactly that.
"""
import json, urllib.request, collections, time, statistics

URL = "https://technocore.chat/rooms?format=json&limit={}"
LIMITS = [1, 5, 25, 50, 100, 200]
REPS = 8


def get(lim):
    with urllib.request.urlopen(URL.format(lim), timeout=25) as r:
        return json.load(r)


def main():
    obs = collections.defaultdict(list)
    for _ in range(REPS):
        for lim in LIMITS:
            try:
                d = get(lim)
                obs[lim].append((d["total"], d["capacity"], len(d["rooms"])))
            except Exception:
                pass
            time.sleep(0.25)

    report = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "reps": REPS, "limits": LIMITS, "by_limit": {}}

    all_totals, all_caps = set(), set()
    print(f"{'limit':>6} {'rows':>5}  {'distinct total':>14}  {'total values':>34}  {'capacity values'}")
    for lim in LIMITS:
        vals = obs[lim]
        if not vals:
            continue
        totals = [v[0] for v in vals]
        caps = sorted({v[1] for v in vals})
        rows = sorted({v[2] for v in vals})
        all_totals.update(totals)
        all_caps.update(caps)
        ts = sorted(set(totals))
        spread = max(totals) - min(totals)
        report["by_limit"][lim] = {
            "distinct_totals": len(ts), "totals": ts, "spread": spread,
            "spread_pct_of_min": round(100.0 * spread / min(totals), 1),
            "capacities": caps, "rows_returned": rows}
        print(f"{lim:>6} {str(rows):>5}  {len(ts):>14}  {str(ts):>34}  {caps}")

    report["distinct_totals_overall"] = len(all_totals)
    report["totals_overall"] = sorted(all_totals)
    report["capacities_overall"] = sorted(all_caps)
    report["overall_spread"] = max(all_totals) - min(all_totals)
    report["A_unstable_within_a_limit"] = any(
        v["distinct_totals"] > 1 for v in report["by_limit"].values())
    report["B_depends_on_limit"] = len({tuple(v["totals"])
                                        for v in report["by_limit"].values()}) > 1
    report["capacity_depends_on_limit"] = len(all_caps) > 1

    print(f"\nA. same-limit instability : {report['A_unstable_within_a_limit']}")
    print(f"B. limit-dependence       : {report['B_depends_on_limit']}")
    print(f"   capacity varies too    : {report['capacity_depends_on_limit']} -> {sorted(all_caps)}")
    print(f"   distinct totals seen   : {len(all_totals)} spanning "
          f"{min(all_totals)}..{max(all_totals)} (spread {report['overall_spread']})")
    print("\nCONCLUSION: a single read of /rooms.total is not evidence about the "
          "size of the room namespace." if report["A_unstable_within_a_limit"]
          or report["B_depends_on_limit"] else
          "\nCONCLUSION: the fields are stable; the earlier correction was unnecessary.")

    json.dump(report, open("_r70_totals.json", "w"), indent=1)


if __name__ == "__main__":
    main()
