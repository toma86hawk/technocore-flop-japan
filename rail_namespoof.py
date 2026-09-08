#!/usr/bin/env python3
"""Pattern 83 - rail-string near-miss ("paper wearing a non-paper name").

The tclk/1 value rail is honest about one thing: `rail=paper` moves nothing.
Every watcher, ours included, therefore classifies a lock as interesting with
an exact-match test:

    if rail.lower() != "paper":   # <- the bug

That test is defeated by any rail string that is not literally "paper" but is
paper in substance. Two such strings are live on the tape right now:

    paperrail   22 locks   median lock->reveal 0.142 s
    kv-paper    16 locks   median lock->reveal 4.205 s

Both self-identify as paper in their own `ref` field - `paperrail-4-<epoch>`,
`https://technocore.chat/kv/tclk-paper-9d/...` - carry no `amount` and no
`asset`, and produce zero work messages. `paperrail` is in fact *more*
degenerate than the sanctioned paper rail: it reveals in ~140 ms, 30x faster
than the 4.399 s median we measured over 86 paper rooms, which is same-process
timing, not settlement.

Contrast the one rail in the window that is not name-spoofed:

    flop-htlc   54 locks   median 4.972 s   ref `escrow-<contract prefix>`
                            0/54 refs mention paper

So the test that actually separates them is not the rail name. It is:
  (a) does the ref self-identify as paper, and
  (b) is lock->reveal inside the paper regime with no work message.

This script recomputes the classification from tclk_rail_state.json and
prints, per rail, how much of a "non-paper" count is name-spoofed paper.

Usage:  python rail_namespoof.py [tclk_rail_state.json]
"""
import json, re, sys, statistics as st, datetime as dt, collections

PAPER_RE = re.compile(r"paper", re.I)


def is_paper_rail(rail):
    """Substring test, not equality - the whole point of the pattern."""
    return PAPER_RE.search(str(rail)) is not None


def main(path="tclk_rail_state.json"):
    st_ = json.load(open(path, encoding="utf-8"))
    locks = st_.get("nonpaper_locks") or []
    by = collections.defaultdict(list)
    for r in locks:
        by[r.get("rail", "?")].append(r)

    spoofed = sum(len(v) for k, v in by.items() if is_paper_rail(k))
    total = len(locks)
    print(f"locks classified non-paper by exact match : {total}")
    print(f"of those, name-spoofed paper (substring)  : {spoofed} "
          f"({100.0*spoofed/total:.1f}%)" if total else "")
    print()
    for rail, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        flag = "SPOOFED-PAPER" if is_paper_rail(rail) else "value-bearing?"
        dids = len({r.get("from") for r in v})
        print(f"  {rail:<12} {len(v):>3} locks  {dids:>3} distinct DIDs  {flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
