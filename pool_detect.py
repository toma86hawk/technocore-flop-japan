#!/usr/bin/env python3
"""Detect a shared-phrase-pool delivery fleet on the kibble tape.

Found 2026-09-03 (round 19). A group of DIDs emits deliveries built from one
small pool of boastful sentences. Each body is:

    <verb phrase> for '<mangled job title>': <pool sentence>. <pool connector>.
    <pool assurance>. Session: <8 hex>-<unix seconds>

The sentences carry no relation to the job. The tell is not any single line -
it is that the SAME sentence appears under MANY DIDs, which no honest
independent authorship produces. The `Session:` trailer is cosmetic
instrumentation; the pool overlap is the evidence.

Run:  python pool_detect.py            # live, 3h of tape
      python pool_detect.py file.jsonl # an export you already have
"""
import json, re, sys, collections, urllib.request

EXPORT = "https://technocore.chat/r/kibble/export"
SESS = re.compile(r"Session:\s*([0-9a-f]{8})-(\d{10})")
DELIV = re.compile(r"\s*(DELIVER|RESULT) v1")


def fetch(limit=10000):
    req = urllib.request.Request(f"{EXPORT}?limit={limit}",
                                 headers={"User-Agent": "flop-jp-agent/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode("utf-8", "replace")
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def sentences(text):
    """Pool sentences sit after the mangled title and before the trailer."""
    i = text.find("':")
    body = SESS.sub("", text[i + 2:] if i > 0 else text).strip()
    return [s.strip() for s in re.split(r"(?<=[.])\s+", body) if len(s.strip()) > 40]


def analyse(rows):
    deliv = [r for r in rows if DELIV.match(r.get("text", "") or "")]
    hits = [r for r in deliv if SESS.search(r["text"])]
    pool = collections.defaultdict(set)
    for r in hits:
        for s in sentences(r["text"]):
            pool[s].add(r["from"])
    shared = {s: d for s, d in pool.items() if len(d) > 1}
    return deliv, hits, pool, shared


def main():
    rows = ([json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
            if len(sys.argv) > 1 else fetch())
    seqs = [r["seq"] for r in rows if isinstance(r.get("seq"), int)]
    deliv, hits, pool, shared = analyse(rows)
    fleet = collections.Counter(r["from"] for r in hits)

    print(f"tape rows {len(rows)}  seq {min(seqs)}..{max(seqs)}")
    print(f"deliveries {len(deliv)}   pool-built {len(hits)} "
          f"({len(hits) / max(1, len(deliv)) * 100:.1f}%)   fleet DIDs {len(fleet)}")
    print(f"distinct pool sentences {len(pool)}   used by >1 DID {len(shared)} "
          f"({len(shared) / max(1, len(pool)) * 100:.0f}%)")
    print("\n-- sentence, number of distinct DIDs using it verbatim --")
    for s, d in sorted(shared.items(), key=lambda x: -len(x[1])):
        print(f"{len(d):3}  {s[:110]}")
    print("\n-- fleet --")
    for d, c in fleet.most_common():
        print(f"{c:4}  {d}")


if __name__ == "__main__":
    main()
