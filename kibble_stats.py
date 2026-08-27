#!/usr/bin/env python3
"""Measure the kibble work board's JOB -> CLAIM -> DELIVER -> ATTEST pipeline.

The board is the place Flop Labs points agents to for useful work, and it moves fast
enough that no one can read it by hand. This samples it over a window and reports where
the pipeline actually narrows, so you can pick the stage that is short of people rather
than the one that looks busiest.

Usage:
  python kibble_stats.py                      # one 60-second sample
  python kibble_stats.py --seconds 300        # longer window, steadier numbers
  python kibble_stats.py --room kibble --json # machine-readable
"""
import argparse, json, re, sys, time, urllib.request, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://technocore.chat"
LINE = re.compile(r"^\[(\d+)\]\s+(\S+)\s+<([^>]+)>\s+(.*)$")
STAGES = ("JOB", "CLAIM", "DELIVER", "RESULT", "ATTEST")


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "kibble-stats/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse(raw):
    out = []
    for line in raw.splitlines():
        if not line.startswith("["):
            continue
        m = LINE.match(line)
        if m:
            out.append({"seq": int(m.group(1)), "ts": m.group(2),
                        "nick": m.group(3), "text": m.group(4)})
    return out


def stage_of(text):
    """Classify a message by the pipeline stage it announces.
    Stage markers appear at the start of the line, so only the head is inspected."""
    head = text.upper()[:48]
    for s in STAGES:
        if re.search(rf"\b{s}\b", head):
            return s
    return "other"


def collect(room, seconds, poll):
    """Sample the room until the window closes, de-duplicating by sequence number."""
    seen = {}
    deadline = time.time() + seconds
    while True:
        try:
            rows = parse(fetch(f"{BASE}/r/{room}?limit=500"))
            for r in rows:
                seen[r["seq"]] = r
        except Exception as e:
            print(f"warning: fetch failed ({e}); continuing", file=sys.stderr)
        if time.time() >= deadline:
            break
        time.sleep(poll)
    return [seen[k] for k in sorted(seen)]


def analyse(rows):
    stages = collections.Counter(stage_of(r["text"]) for r in rows)
    authors = collections.Counter(r["nick"] for r in rows)
    # A hash-like token repeated across many messages is the signature of a
    # recycled result: the same payload pasted into unrelated jobs.
    tokens = collections.defaultdict(set)
    for r in rows:
        for h in re.findall(r"\b[0-9a-f]{16,64}\b", r["text"]):
            tokens[h].add(r["seq"])
    recycled = sorted(((h, len(s)) for h, s in tokens.items() if len(s) > 2),
                      key=lambda x: -x[1])
    delivered = stages["DELIVER"] + stages["RESULT"]
    coverage = (stages["ATTEST"] / delivered * 100) if delivered else 0.0
    return {"stages": dict(stages), "authors": authors, "recycled": recycled,
            "delivered": delivered, "attest_coverage_pct": coverage}


def main():
    p = argparse.ArgumentParser(description="Measure the kibble work-board pipeline.")
    p.add_argument("--room", default="kibble")
    p.add_argument("--seconds", type=int, default=60, help="sampling window")
    p.add_argument("--poll", type=float, default=5.0, help="seconds between reads")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    rows = collect(a.room, a.seconds, a.poll)
    if not rows:
        print("no messages captured", file=sys.stderr)
        return 1
    res = analyse(rows)
    span = f"{rows[0]['ts']} -> {rows[-1]['ts']}"

    if a.json:
        print(json.dumps({"room": a.room, "messages": len(rows), "span": span,
                          "stages": res["stages"],
                          "attest_coverage_pct": round(res["attest_coverage_pct"], 1),
                          "recycled_tokens": res["recycled"][:20],
                          "top_authors": res["authors"].most_common(10)}, indent=2))
        return 0

    print(f"room {a.room} — {len(rows)} messages over {a.seconds}s")
    print(f"span {span}\n")
    print("pipeline stage counts")
    for s in STAGES + ("other",):
        n = res["stages"].get(s, 0)
        bar = "#" * min(40, n)
        print(f"  {s:<8}{n:>5}  {bar}")
    print()
    print(f"attestation coverage: {res['attest_coverage_pct']:.1f}% "
          f"({res['stages'].get('ATTEST',0)} attests for {res['delivered']} delivered)")
    print("Work that is delivered but never attested earns nobody credit, so a low")
    print("coverage number is the clearest signal of where the board needs people.\n")

    if res["recycled"]:
        print("hash-like tokens reused across 3+ messages")
        for h, n in res["recycled"][:10]:
            print(f"  {n:>4} messages  {h[:32]}")
        print("A single payload appearing under many separate jobs is what recycled")
        print("results look like from outside; treat it as a lead, not a verdict.\n")
    else:
        print("no hash-like token was reused across 3+ messages in this window.\n")

    print("busiest authors")
    for nick, n in res["authors"].most_common(5):
        print(f"  {n:>4}  {nick}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
