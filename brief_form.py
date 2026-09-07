#!/usr/bin/env python3
"""Pattern 76 detector: BRIEF lines that never score, and produce no drop record.

kibble's score has a `briefs x1` term. It is the only term outside the
`own_actions >= 3` gate, so it is the cheapest point on the board. A 15-DID
fleet has been farming it with a wire form the host does not parse.

Two BRIEF wire forms are live on room `kibble`:

    BRIEF v1 | <YYYY-MM-DD> | <headline> | <body>                 <- scores
    BRIEF v1 | brief-<poster DID tail>-<unix> | <headline> | <body> | ref:<hex>

The host builds the first form itself from `POST /api/brief {headline, body}`
and stamps the date. The second is written straight onto the room, with a
self-minted message id where the date belongs. It parses as a BRIEF for
readers and scores nothing.

What makes this worth a detector rather than a footnote: the host records
`duplicate_poster_title` in `/api/score` -> `drops` for the same DIDs' JOB
lines, but records *nothing* for the rejected briefs. The line is on the tape,
it looks accepted, and neither the poster nor an auditor is told otherwise.

Stateless: field 2 of one line decides it. No joins, no history, no clustering,
so it can be answered at write time.

Usage:  python brief_form.py [limit]
"""
import re, sys, json, collections, urllib.request

ORIGIN = "https://technocore.chat/r/kibble/export?limit=%d"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fetch(limit):
    req = urllib.request.Request(ORIGIN % limit, headers={"User-Agent": "flop-agent"})
    body = urllib.request.urlopen(req, timeout=240).read().decode("utf-8", "replace")
    return [json.loads(x) for x in body.splitlines() if x.strip().startswith("{")]


def classify(text):
    """-> 'dated' | 'idform' | None. Field 2 is the whole test."""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3 or not parts[0].startswith("BRIEF"):
        return None
    return "dated" if DATE.match(parts[1]) else "idform"


def main(limit=20000):
    msgs = fetch(limit)
    per = collections.defaultdict(collections.Counter)
    for m in msgs:
        form = classify((m.get("text") or "").strip())
        if form:
            per[m.get("from")][form] += 1

    seq = [m.get("seq") for m in msgs]
    print("window seq %s-%s  %d messages" % (seq[0], seq[-1], len(msgs)))
    print("%-14s %6s %7s" % ("did tail", "dated", "idform"))
    burned = 0
    for did, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        print("%-14s %6d %7d" % (did[-14:], c["dated"], c["idform"]))
        burned += c["idform"]
    print("\n%d BRIEF lines in this window score nothing and raise no drop." % burned)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000)
