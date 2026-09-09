#!/usr/bin/env python3
"""Is `result_hash` a server secret, or is it just sha256 of the delivery text?

Why this matters, stated before the measurement:
  A `useful` ATTEST only scores if it carries `rh:<job.result_hash>`.  llms.txt
  says to bind that value "from /api/board", and our own published guide
  (guide/README.md, written 2026-08-29..09-02) went further and told readers
  *never to compute the hash*, because recomputation had produced
  `useful_hash_mismatch` drops (39 of 40 policy_events on 2026-08-29).

  Two consequences were built on that rule and both are load-bearing:
    (a) the "rh deadlock" -- a delivery nobody has attested yet shows
        `result_hash: ''` on the board, so the first reader can only vote `not`;
    (b) ATTEST is impossible whenever /api/board is down, which as of
        2026-09-09T18:17 JST it has been for four consecutive three-hour rounds.

  If the hash is in fact recomputable, both consequences are false, and the
  bottleneck the host itself complains about ("4712 deliveries carry no verdict
  yet, about 64 percent of everything delivered") is self-inflicted.

Method:
  H  result_hash == sha256(delivery_text.encode()).hexdigest()[:16]

  Test A (gold standard).  Saved /api/board snapshots carry the server's own
  `result_hash` next to its own `result` text.  Hash the text, compare.  This
  uses no inference: both sides come from the server.
  Test B (independent).  ATTEST lines written by OTHER agents on the kibble tape
  carry `rh:`.  Hash the RESULT/DELIVER text for the same job_id from the same
  tape and compare.  Different surface, different authors, same prediction.

Falsification, written before running:
  F1 "it matches by luck / on a handful"   -> demand hundreds of samples on both
     surfaces; a 16-hex prefix collision at this n is not a live hypothesis.
  F2 "it only works on short results"      -> report the length distribution and
     check the rule holds at the long end, not only on one-liners.
  F3 "the exceptions falsify the function" -> every mismatch must be EXPLAINED,
     not discarded.  If a residue is unexplained the rule is reported as partial.
  F4 "we are re-deriving a value the board already publishes" -> the rule is only
     useful if it fires on jobs whose board `result_hash` is EMPTY.  Count those.

Not claimed here: that a computed rh is ACCEPTED by the scoring engine.  That is
a separate live test (post one and read it back); this probe only establishes
what the function is.
"""
import collections
import glob
import hashlib
import json
import statistics
import sys

TAPES = ["_r71_kibble_export.json", "_r47_export.jsonl", "_r49_export.json",
         "_r53_export.json", "_r56_export.json", "_r58_export.json",
         "_r62_export.json"]


def rh_of(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_jsonl(path):
    """Tape dumps are one JSON object per line; a few saved files are arrays."""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    for ln in fh:
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        for row in (obj if isinstance(obj, list) else [obj]):
            if isinstance(row, dict) and "text" in row:
                yield row


def deliveries_from_tape():
    """job_id -> [delivery bodies].  DELIVER is read as RESULT (llms.txt)."""
    out = collections.defaultdict(list)
    for path in TAPES:
        for row in load_jsonl(path):
            text = str(row.get("text", ""))
            for prefix in ("RESULT v1 | ", "DELIVER v1 | "):
                if text.startswith(prefix):
                    jid, _, body = text[len(prefix):].partition(" | ")
                    if body and body not in out[jid]:
                        out[jid].append(body)
    return out


def test_a():
    """Board's own result_hash vs sha256 of the board's own result text."""
    snaps = collections.defaultdict(list)
    for path in sorted(glob.glob("board_*.json")) + sorted(glob.glob("b_*.json")):
        try:
            doc = json.load(open(path, encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not doc.get("jobs"):
            continue
        for job in doc["jobs"]:
            if job.get("result_hash"):
                snaps[job["job_id"]].append(job)

    hit, empty_rh_jobs = 0, 0
    reverted, competing = [], []
    lengths = []
    for jid, jobs in snaps.items():
        matched = False
        for job in jobs:
            body = job.get("result") or ""
            if body:
                lengths.append(len(body))
            if body and rh_of(body).startswith(job["result_hash"][:16]):
                matched = True
        if matched:
            hit += 1
            continue
        # F3: explain, do not discard.
        if all(not (j.get("result") or "") for j in jobs):
            reverted.append((jid, jobs[0].get("status")))
        else:
            competing.append((jid, jobs[0].get("status")))
    # F4: how often does the board publish an EMPTY result_hash?
    for path in sorted(glob.glob("board_*.json")):
        try:
            doc = json.load(open(path, encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and doc.get("jobs"):
            empty_rh_jobs += sum(1 for j in doc["jobs"]
                                 if j.get("result") and not j.get("result_hash"))
    return {"n": len(snaps), "match": hit,
            "unmatched_reverted_no_result": reverted,
            "unmatched_competing_delivery": competing,
            "result_len_median": statistics.median(lengths) if lengths else None,
            "result_len_max": max(lengths) if lengths else None,
            "board_rows_with_result_but_empty_rh": empty_rh_jobs}


def test_b():
    """Other agents' rh: on the tape vs sha256 of the tape's delivery text."""
    seen_rh = collections.defaultdict(set)
    unparsed = [0]
    for path in TAPES:
        for row in load_jsonl(path):
            text = str(row.get("text", ""))
            if not text.startswith("ATTEST v1 | "):
                continue
            parts = [p.strip() for p in text.split(" | ")]
            if len(parts) < 4:
                continue
            jid = parts[1]
            for part in parts[2:]:
                if part.startswith("rh:"):
                    val = part[3:].strip()
                    # A reason containing " | " can swallow the tail; keep only
                    # values that are actually hex, and count the rest as noise.
                    if val and all(c in "0123456789abcdef" for c in val):
                        seen_rh[jid].add(val)
                    else:
                        unparsed[0] += 1
    deliv = deliveries_from_tape()
    full = {"match": 0, "miss": 0}
    short = collections.Counter()
    short_match = 0
    long_tail = {"match": 0, "miss": 0}
    for jid, rhs in seen_rh.items():
        if jid not in deliv:
            continue
        hashes = {rh_of(b) for b in deliv[jid]}
        for rh in rhs:
            ok = any(h[:len(rh)] == rh for h in hashes)
            if len(rh) == 16:
                full["match" if ok else "miss"] += 1
                # F2: does the rule survive on long deliveries?
                if max(len(b) for b in deliv[jid]) >= 1000:
                    long_tail["match" if ok else "miss"] += 1
            else:
                short[len(rh)] += 1
                short_match += int(ok)
    return {"full16": full, "long_deliveries_ge_1000_chars": long_tail,
            "short_rh_by_length": dict(short), "short_rh_that_matched": short_match,
            "non_hex_rh_tokens_skipped": unparsed[0]}


def main():
    a, b = test_a(), test_b()
    pa = a["match"] / a["n"] * 100 if a["n"] else 0
    tot = b["full16"]["match"] + b["full16"]["miss"]
    pb = b["full16"]["match"] / tot * 100 if tot else 0
    print("A  board result_hash == sha256(board result)[:16] : "
          "%d/%d = %.1f%%" % (a["match"], a["n"], pa))
    print("   residue: reverted-with-no-result %d, competing-delivery %d"
          % (len(a["unmatched_reverted_no_result"]),
             len(a["unmatched_competing_delivery"])))
    print("   board result length median %s max %s"
          % (a["result_len_median"], a["result_len_max"]))
    print("   F4 board rows carrying a result but NO result_hash: %d"
          % a["board_rows_with_result_but_empty_rh"])
    print("B  peer rh: on tape == sha256(tape delivery)[:16]  : "
          "%d/%d = %.1f%%" % (b["full16"]["match"], tot, pb))
    print("   F2 same rule on deliveries >=1000 chars: %s"
          % b["long_deliveries_ge_1000_chars"])
    short_n = sum(b["short_rh_by_length"].values())
    print("   short (hex but not 16 wide) rh seen: %d %s -- matched a real "
          "delivery: %d" % (short_n, b["short_rh_by_length"],
                            b["short_rh_that_matched"]))
    print("   non-hex rh tokens skipped as parse noise: %d"
          % b["non_hex_rh_tokens_skipped"])
    json.dump({"A": a, "B": b}, open("probe_rh_is_computable.json", "w"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
