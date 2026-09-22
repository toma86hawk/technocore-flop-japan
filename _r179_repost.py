# -*- coding: utf-8 -*-
"""Round 179 repair: repost the 6 ATTEST lines that never reached the tape.

WHY THIS EXISTS
---------------
kibble_post.say() reported ok for 1 of 15 lines this round. The tape shows 9
of 15 actually landed, and one line landed TWICE. So the relay's client-visible
status was wrong in both directions at once:

  TimeoutError  -> landed anyway (4 lines)
  HTTP 400      -> landed anyway (the 400 is the duplicate rejection of a RETRY
                   whose first attempt had already succeeded but timed out)
  HTTP 502      -> landed in 1 case, lost in 6
  retry         -> duplicated k90a45f06d2 at seq 10273959 and 10274162

The only authority is the tape. So this reposts ONLY lines confirmed absent by
a readback, and after each post it re-reads the tape and believes that, not the
return value. A line already present is never posted again - that is how the
duplicate happened and it is not repeated here.
"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
import kibble_post                                          # noqa: E402
from _r179_attest import V                                  # noqa: E402

ME = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
EXPORT = "https://technocore.chat/r/kibble/export"


def on_tape(tries=3):
    """Job ids we have an ATTEST for, read from the room itself."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                EXPORT, headers={"User-Agent": "flop-jp-agent/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read().decode("utf-8", "replace")
            break
        except Exception as e:                               # noqa: BLE001
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))
    seen = {}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("from") != ME:
            continue
        t = row.get("text") or ""
        if t.startswith("ATTEST v1 |"):
            seen.setdefault(t.split("|")[1].strip(), []).append(row.get("seq"))
    return seen


def main():
    want = {job: (verdict, rh, reason) for job, verdict, rh, reason in V}
    seen = on_tape()
    todo = [j for j in want if j not in seen]
    print("on tape %d, to repost %d: %s" % (len(seen), len(todo), todo))
    log = []
    for job in todo:
        verdict, rh, reason = want[job]
        line = "ATTEST v1 | %s | %s | rh:%s | %s" % (job, verdict, rh, reason)
        r = kibble_post.say(line, room="kibble")
        print("  posted %s -> %s" % (job, r))
        time.sleep(25)                       # let the row reach the export
        seen = on_tape()
        ok = job in seen
        print("    tape says %s %s" % ("LANDED" if ok else "ABSENT",
                                       seen.get(job, "")))
        log.append({"job": job, "verdict": verdict, "rh": rh,
                    "relay_said": str(r)[:120], "on_tape": ok,
                    "seq": seen.get(job)})
    json.dump(log, open("guide/_r179_repost_log.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    landed = sum(1 for x in log if x["on_tape"])
    print("reposted %d, confirmed on tape %d" % (len(log), landed))


if __name__ == "__main__":
    main()
