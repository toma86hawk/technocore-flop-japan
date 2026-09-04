#!/usr/bin/env python3
"""r35: /api/score?did= returned found:false for 26/30 DIDs at 00:26 and
found:true for 22 of the same 30 at 00:31. Poll a fixed set repeatedly to
decide between 'coverage grew' and 'the endpoint flaps'."""
import json, urllib.request, urllib.parse, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIDS = [
    "did:key:z6MkhRW86xnk2VsudkN9j2AiBcq9CxtKnTJf69ddcEaX7nZ7",  # GLM-5.3-Flash attestor
    "did:key:z6MkvudSY2Ezd4suJDfD2DYE8GAVUBCGHgjHjPMowhojvBUG",  # thin deliverer
    "did:key:z6Mkpfu8vLXgXR49mvknyv7Gb9uKUKgGDyFPYzWik7YeBSvG",
    "did:key:z6Mkpjt48fahhtdXLpw9Tvzutd5KeYSSkMLaSbfAmfxfdwqb",  # ours (control)
    "did:key:z6MkptCMeKbxLZKjzBfpWXxVQpvFNk7UqeUWNyhCDEiseaD4",  # rank 1 (control)
]
ROUNDS = 6
hist = {d: [] for d in DIDS}
for r in range(ROUNDS):
    for d in DIDS:
        u = "https://flop-kibble.onrender.com/api/score?did=" + urllib.parse.quote(d, safe="")
        try:
            j = json.loads(urllib.request.urlopen(u, timeout=60).read().decode())
            hist[d].append((bool(j.get("found")), j.get("score"),
                            j.get("breakdown", {}).get("terms", {})
                             .get("attestations_given", {}).get("count")))
        except Exception as e:                                    # noqa: BLE001
            hist[d].append(("ERR", repr(e)[:40], None))
        time.sleep(1.0)
    print("round", r + 1, "done", time.strftime("%H:%M:%S"))
    time.sleep(6)

print()
for d in DIDS:
    seq = hist[d]
    print("...%s" % d[-14:])
    print("   found  :", [x[0] for x in seq])
    print("   score  :", [x[1] for x in seq])
    print("   given  :", [x[2] for x in seq])
json.dump({d: hist[d] for d in DIDS}, open("r35_score_flap.json", "w"), indent=1)
