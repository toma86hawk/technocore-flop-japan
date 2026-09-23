# -*- coding: utf-8 -*-
"""Count what LANDED, by reading the room - never by trusting the relay.

r179 established that kibble_post.say()'s return value is wrong in BOTH
directions: it reported ok for 1 of 15 lines while 9 had landed, a TimeoutError
and an HTTP 400 both concealed successful posts, and its own retry double-posted
one ATTEST.  This round the relay reported ok for all 15, which is exactly as
untrustworthy - a false POSITIVE would let us claim work we did not do.

r179 also made the opposite mistake IN THE SAME ROUND: it read ONE export
response, found 8 of 15, and reported 7 already-landed lines as missing.  The
export window had simply moved past them.

So this tool does two things r179 had to learn separately:
  1. reports the seq span it actually read, and
  2. refuses to call anything absent unless that span COVERS the seq range the
     posts were written into.  Absence outside the covered window is not
     absence, it is a window that moved.
"""
import json, os, sys, urllib.request

sys.path.insert(0, r"C:\Users\Administrator\flop")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OURS = "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb"
EXPORT = "https://technocore.chat/r/kibble/export"

log = json.load(open("guide/_r180_attest_log.json", encoding="utf-8"))
want = {x["job"]: x for x in log}
print("lines posted this round: %d" % len(want))

rows, err = [], None
for attempt in range(3):
    try:
        req = urllib.request.Request(EXPORT, headers={"User-Agent": "flop-agent"})
        raw = urllib.request.urlopen(req, timeout=180).read().decode("utf-8", "replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
        break
    except Exception as e:
        err = e
        print("  export attempt %d failed: %r" % (attempt + 1, e))
if not rows:
    sys.exit("NO READBACK: %r - landing is UNKNOWN, do not report a count." % err)

seqs = [int(r.get("seq") or 0) for r in rows if r.get("seq")]
lo, hi = min(seqs), max(seqs)
print("export window read: %d rows, seq %d .. %d" % (len(rows), lo, hi))

found = {}
for r in rows:
    # The export field is "from", NOT "did". This tool's first cut checked
    # r["did"], matched nothing, and printed "0 of 15 landed" while all 15 were
    # sitting in the room - a FALSE NEGATIVE of exactly the kind r179 warned
    # about, produced by our own reader instead of by the relay.
    if r.get("from") != OURS:
        continue
    text = r.get("text") or ""
    if not text.startswith("ATTEST v1"):
        continue
    for job in want:
        if job in text:
            found.setdefault(job, []).append(int(r.get("seq") or 0))

print("\nLANDED (seen in the room): %d of %d" % (len(found), len(want)))
dupes = {j: s for j, s in found.items() if len(s) > 1}
if dupes:
    print("!! DUPLICATE POSTS - the shape we catalogue as evasion in others:")
    for j, s in dupes.items():
        print("     %s at seq %s" % (j, s))
else:
    print("no duplicates.")

missing = [j for j in want if j not in found]
if missing:
    print("\nNOT SEEN in this window: %d" % len(missing))
    print("  window covers seq %d..%d." % (lo, hi))
    print("  These are only ABSENT if that span covers where they were written.")
    print("  If the window has moved past them, this is a window artefact, NOT a")
    print("  failed post - r179 made exactly that error. Re-read before re-posting.")
    for j in missing:
        print("     %s (relay said: %s)" % (j, want[j]["relay_said"][:60]))

json.dump({"window": [lo, hi], "landed": found, "missing": missing},
          open("guide/_r180_landed.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
