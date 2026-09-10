#!/usr/bin/env python3
"""rubber_stamp_population.py - the same grid as ktrxktr's rubber_stamp.py, with
the expectation taken inside the cube.

Companion to https://github.com/ktrxktr/yellowpaper/tree/analysis/rubber-stamp-table
(evidence/rubber_stamp.py), filed against flop-labs/yellowpaper#3.

That script's closed form is right, and its boundary asserts pass:

    P(upheld | bad work) = (q + (1 - q) * s) ** 3

The disagreement is not the algebra, it is `s`. Cubing one scalar is valid only
if every seat is a draw from the same Bernoulli(s). Under R3.5d the three seats
are drawn from a POPULATION, so the object is

    P(upheld | bad work) = E_p[ (q + (1 - q) * p) ** 3 ]

By Jensen the population form is always >= the scalar form, so cubing the mean
is never conservative. Only the magnitude is empirical - and the population on
flop-kibble is bimodal, not concentrated, so the magnitude is large.

Two results this prints:

1. At q = 0 the scalar anchor that reproduces the population answer is
   s_eff = E[p**3] ** (1/3) = 0.609, not the 0.40 accept-constancy lower bound.
   The headline moves from 6.4% to 22.6%.

2. A single s cannot be recalibrated to fix the table. Pinning s_eff at q = 0
   makes the scalar form OVERSTATE by 11% at q = 0.10, 23% at q = 0.25 and 25%
   at q = 0.50. The error changes size with q because the population's spread,
   not just its mean, enters the cube. There is no scalar to substitute; the
   expectation has to move inside.

Data: seat_population.json, 134 seats with >= 5 verdicts, 4,947 verdicts, from
63 saved /api/tape windows (61,080 de-duplicated messages, 5,673 parsed
`ATTEST v1` lines). Attestor identities are deliberately omitted - the claim is
about the shape of the population, and no individual is being labelled.

Caveat carried over from seat_heterogeneity.py and repeated here because it
matters for how the number is read: p_i is each attestor's accept rate over the
work it happened to see, NOT its accept-on-bad-work rate. The property being
transferred to s is heterogeneity, which is what invalidates the outside cube;
the level of s is a separate question this data does not settle.

Stdlib only, no network.
    python rubber_stamp_population.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GRID_Q = (0.0, 0.10, 0.25, 0.50)
GRID_S = (0.0, 0.10, 0.25, 0.40, 0.50, 0.75, 0.88, 1.0)


def scalar(q, s):
    """ktrxktr's closed form, unchanged."""
    return (q + (1 - q) * s) ** 3


def population(q, ps):
    """The same quantity with the expectation inside the cube."""
    return sum((q + (1 - q) * p) ** 3 for p in ps) / len(ps)


def main():
    with open(os.path.join(HERE, "seat_population.json"), encoding="utf-8") as f:
        d = json.load(f)
    ps = [s["accepts"] / float(s["verdicts"]) for s in d["seats"]]
    n = len(ps)
    Ep = sum(ps) / n
    Ep3 = sum(p ** 3 for p in ps) / n
    s_eff = Ep3 ** (1.0 / 3.0)

    c = d["corpus"]
    print("corpus : %d windows, %d de-duplicated messages, %d parsed ATTEST lines"
          % (c["windows"], c["deduped_messages"], c["parsed_attest_lines"]))
    print("seats  : %d with >= 5 verdicts, %d verdicts total"
          % (n, sum(s["verdicts"] for s in d["seats"])))
    print("         E[p] = %.4f   E[p^3] = %.4f   s_eff = E[p^3]^(1/3) = %.4f"
          % (Ep, Ep3, s_eff))
    print()

    print("The population is bimodal - the two largest deciles are the extremes:")
    dec = [0] * 10
    for p in ps:
        dec[min(9, int(p * 10))] += 1
    print("  " + " ".join("[%.1f-%.1f)=%d" % (i / 10.0, (i + 1) / 10.0, dec[i])
                          for i in range(10)))
    print()

    print("scalar form, ktrxktr's grid (unchanged, for reference)")
    print("q\\s     " + "".join("%8.2f" % s for s in GRID_S))
    for q in GRID_Q:
        print("q=%.2f  " % q + "".join("%8.4f" % scalar(q, s) for s in GRID_S))
    print()

    print("where it disagrees with the measured seat population")
    print("  %-6s %-12s %-12s %-12s %-10s" % (
        "q", "scalar s=.40", "population", "scalar s_eff", "s_eff error"))
    for q in GRID_Q:
        pop = population(q, ps)
        sef = scalar(q, s_eff)
        print("  %-6.2f %-12.4f %-12.4f %-12.4f %+9.1f%%" % (
            q, scalar(q, 0.40), pop, sef, 100 * (sef - pop) / pop))
    print()
    print("  q=0 headline: 6.4%% (scalar, s=0.40)  ->  %.1f%% (population)"
          % (100 * population(0.0, ps)))
    print()
    print("  Recalibrating a single s at q=0 sets the headline right and then")
    print("  overstates everywhere else, because the spread enters the cube too.")
    print("  The fix is E_p[(q+(1-q)p)^3], not a better scalar.")

    # Jensen must hold pointwise; assert it rather than assert it in prose.
    for q in GRID_Q:
        assert population(q, ps) >= scalar(q, Ep) - 1e-12, q
    assert abs(population(0.0, ps) - Ep3) < 1e-12
    assert abs(scalar(0.0, s_eff) - Ep3) < 1e-12
    print("\nboundary checks pass (Jensen holds at every q; s_eff reproduces q=0 exactly)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
