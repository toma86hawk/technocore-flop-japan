#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does a message that claims to be coordinating have a counterparty?

Technocore replies carry their own context: the wire form is

    Re: '<first ~30 chars of the parent>' | <body>

so a claim about what is being continued can be checked against the thing it
quotes, with no model and no judgement call. That gives two mechanical tests for
manufactured coordination evidence:

1. ORPHANED CLAIM. The body asserts it is continuing/verifying/building on a
   thread about topic T, and the quoted parent contains no token from T. The
   message is then coordinating with a counterparty who never raised T.

2. SENTENCE TEMPLATE UNDER A NONCE. Many fleets defeat verbatim de-duplication
   by appending a short random tag (`... poetry grows.' - 70e4`). Strip a
   trailing 1-8 character alphanumeric tag and the quoted parent, and count what
   is left. A pool of two or three sentences shared across many identities is a
   dictionary, not a conversation.

Neither test needs to know what good coordination looks like. Test 1 fails only
when the message's own quoted context contradicts its own claim; test 2 reports
counts.

Usage
-----
    python coordination_theater.py <room> [limit] [topic-regex]

    python coordination_theater.py lobby 4000 'poetry|poem|stanza|verse|sonnet|rhyme'

Reads https://technocore.chat/r/<room>/export, stdlib only.

First run, 2026-09-10 (round 79), room lobby, 26,036 messages, seq
40119710-40145745, a 14m50s window opening 3h08m after @CryptoHayes announced a
Technocore poetry contest "that requires coordination amongst agents" whose rules
had not yet been published: 43 topic lines, 40 of them replies, 0 percent with a
topic-bearing parent, 3 sentences covering 40 of 43, 19 identities.
"""
import collections
import json
import re
import sys
import urllib.request

RE_PREFIX = re.compile(r"^Re:\s*'(.*?)'\s*\|\s*(.*)$", re.S)
# trailing nonce: separator glyphs these fleets use, then a short alnum tag
TAG = re.compile(r"[\s\-–■◆●·•\*]+([0-9a-z]{1,8})\s*$", re.I)
QUOTED = re.compile(r"'([^']{10,})'")
CLAIM = re.compile(r"\b(captured|verified|received|completing|continuing|building|"
                   r"adding|collaborat\w*|coordinat\w*|joining|extending)\b", re.I)
WS = re.compile(r"\s+")


def fetch(room, limit):
    req = urllib.request.Request(
        "https://technocore.chat/r/%s/export?limit=%d" % (room, limit),
        headers={"User-Agent": "coordination-theater/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip().startswith("{")]


def body_of(text):
    """-> (parent_excerpt or None, body). Handles nested Re: chains."""
    t = text.strip()
    parent = None
    m = RE_PREFIX.match(t)
    while m:
        parent = m.group(1)
        t = m.group(2).strip()
        m = RE_PREFIX.match(t)
    return parent, t


def template(body):
    return WS.sub(" ", TAG.sub("", body.strip())).strip()


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    room = argv[0]
    limit = int(argv[1]) if len(argv) > 1 else 4000
    # word boundaries matter: a bare `verse` also matches "universe"
    topic = re.compile(argv[2] if len(argv) > 2 else
                       r"\b(poetry|poems?|poetic|haiku|verse|stanza|sonnet|rhymes?|"
                       r"couplet)\b", re.I)

    ms = fetch(room, limit)
    print("room %s: %d messages, seq %s..%s" % (room, len(ms), ms[0].get("seq"),
                                                ms[-1].get("seq")))
    print("window: %s .. %s" % (ms[0].get("ts"), ms[-1].get("ts")))

    rows = []
    for m in ms:
        text = m.get("text") or ""
        if not topic.search(text):
            continue
        parent, body = body_of(text)
        rows.append({"seq": m.get("seq"), "ts": m.get("ts"),
                     "who": m.get("did") or m.get("from") or "?",
                     "parent": parent, "body": body, "text": text})
    print("topic-matching lines: %d (%.3f%% of the window)"
          % (len(rows), 100.0 * len(rows) / max(1, len(ms))))
    if not rows:
        return 0

    # --- test 1: orphaned claims -------------------------------------------
    replies = [r for r in rows if r["parent"] is not None]
    claiming = [r for r in replies if CLAIM.search(r["body"])]
    orphan = [r for r in claiming if not topic.search(r["parent"])]
    print("\n-- test 1: orphaned coordination claims --")
    print("   replies                              : %d (non-replies %d)"
          % (len(replies), len(rows) - len(replies)))
    print("   ... that CLAIM to continue the topic : %d" % len(claiming))
    print("   ... whose quoted parent has no topic : %d (%.1f%% of claims)"
          % (len(orphan), 100.0 * len(orphan) / max(1, len(claiming))))
    print("   most-quoted parents of orphaned claims:")
    for p, n in collections.Counter(r["parent"] for r in orphan).most_common(8):
        print("      %3d x  %s" % (n, p[:100]))

    # --- test 2: sentence pool under a nonce -------------------------------
    tm = collections.Counter(template(r["body"]) for r in rows)
    tagged = [r for r in rows if TAG.search(r["body"].strip())]
    tags = {TAG.search(r["body"].strip()).group(1) for r in tagged}
    print("\n-- test 2: sentence pool --")
    print("   distinct bodies verbatim             : %d"
          % len({WS.sub(' ', r['body'].strip()) for r in rows}))
    print("   distinct bodies after nonce stripping: %d" % len(tm))
    print("   lines carrying a trailing nonce      : %d/%d, distinct nonces %d"
          % (len(tagged), len(rows), len(tags)))
    top = tm.most_common(5)
    cover = sum(n for _, n in top)
    print("   top 5 sentences cover %d/%d lines (%.1f%%)"
          % (cover, len(rows), 100.0 * cover / len(rows)))
    for t, n in tm.most_common(10):
        print("      %3d x  %s" % (n, t[:130]))

    # --- who -----------------------------------------------------------------
    byd = collections.Counter(r["who"] for r in rows)
    print("\n-- identities --")
    print("   distinct DIDs: %d, top DID holds %.1f%% of the lines"
          % (len(byd), 100.0 * byd.most_common(1)[0][1] / len(rows)))
    for d, n in byd.most_common(8):
        print("      ...%s  %d" % (d[-12:], n))
    shared = [(t, len({r["who"] for r in rows if template(r["body"]) == t}))
              for t, n in tm.most_common(5)]
    print("   identities per top sentence (a pool shared across DIDs is a dictionary):")
    for t, k in shared:
        print("      %2d DIDs  %s" % (k, t[:110]))

    # --- the content actually contributed -----------------------------------
    q = collections.Counter()
    for r in rows:
        for s in QUOTED.findall(TAG.sub("", r["body"])):
            q[WS.sub(" ", s.strip())] += 1
    # A candidate contributed line is any quoted string of >=5 words that is not
    # just the echoed parent excerpt. The count of DISTINCT ones is how much text
    # the whole population actually wrote.
    parents = {WS.sub(" ", (r["parent"] or "").strip()) for r in rows}
    own = [(t, n) for t, n in q.items()
           if len(t.split()) >= 5 and t not in parents and not t.endswith("...")]
    print("\n-- distinct candidate lines contributed by the whole population: %d --"
          % len(own))
    for t, n in sorted(own, key=lambda x: -x[1])[:10]:
        print("   %3d x  \"%s\"" % (n, t[:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
