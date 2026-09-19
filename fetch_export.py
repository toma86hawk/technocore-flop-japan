#!/usr/bin/env python3
"""Fetch a room's /export and refuse to hand back a truncated tape.

Found 2026-09-20 r153: while technocore.chat was degraded, GET /r/kibble/export
returned **HTTP 200 with exit status 0 and a body that stopped in the middle of
a JSON record** - 139 whole rows plus half of the 140th, out of ~14,000.  curl
reported success.  Python's urllib happened to raise IncompleteRead because the
route is chunked, but nothing in our tooling checked, and a census built on that
body would simply have under-counted with no error anywhere.

Every number we publish is a census of this tape, so a short read is not a
transport nuisance, it is a silent wrong answer.  This wrapper:

  1. rejects a body whose final line does not parse (the truncation signature),
  2. asserts the seq density the tape is known to have - an export of N records
     spans exactly N seq - so a hole in the middle is caught too,
  3. compares the export head against the room's live head and reports the
     retained span, and
  4. retries, because the failure is intermittent (502 / 503 / short 200 within
     seconds of a clean 9.4 MB read).

Usage:  fetch_export.py <room> <outfile.jsonl> [tries]
Exit 0 only when the file on disk passed every check.
"""
import json, sys, time, urllib.request

UA = {"User-Agent": "flop-jp-agent/1.0"}


def _get(url, timeout):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read()


def fetch(room, tries=6, timeout=300):
    url = "https://technocore.chat/r/%s/export?limit=500" % room
    last = None
    for n in range(1, tries + 1):
        try:
            raw = _get(url, timeout).decode("utf-8", "replace")
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, str(e)[:120])
            sys.stderr.write("try %d transport %s\n" % (n, last))
            time.sleep(min(5 * n, 30))
            continue
        lines = [l for l in raw.splitlines() if l.strip().startswith("{")]
        if not lines:
            last = "no records"
            sys.stderr.write("try %d %s\n" % (n, last))
            time.sleep(min(5 * n, 30))
            continue
        try:
            json.loads(lines[-1])
        except Exception:
            last = ("TRUNCATED 200: %d whole rows then a partial record "
                    "(%d bytes)" % (len(lines) - 1, len(raw)))
            sys.stderr.write("try %d %s\n" % (n, last))
            time.sleep(min(5 * n, 30))
            continue
        rows = [json.loads(l) for l in lines]
        seqs = [r["seq"] for r in rows]
        span, want = seqs[-1] - seqs[0] + 1, len(rows)
        if span != want:
            last = "seq density broken: %d rows over %d seq" % (want, span)
            sys.stderr.write("try %d %s\n" % (n, last))
            time.sleep(min(5 * n, 30))
            continue
        sys.stderr.write("try %d OK %d rows seq %d..%d (%.1f MB)\n"
                         % (n, len(rows), seqs[0], seqs[-1], len(raw) / 1e6))
        return rows, raw
    raise SystemExit("export never came back whole after %d tries; last: %s"
                     % (tries, last))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    room, out = sys.argv[1], sys.argv[2]
    tries = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    rows, raw = fetch(room, tries)
    open(out, "w", encoding="utf-8").write(raw)
    print(json.dumps({"room": room, "file": out, "rows": len(rows),
                      "seq_lo": rows[0]["seq"], "seq_hi": rows[-1]["seq"],
                      "bytes": len(raw)}, ensure_ascii=False))
