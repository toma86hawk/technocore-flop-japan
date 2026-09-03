"""r27: the leaderboard rows that pattern 41 said were 'pruned' toggle on a 12h cycle.

Round 20 recorded pattern 41 (prune laundering): a recompute dropped 645 not_useful
rows and 420 results rows from the top 48 in one step, worth +1515 points for no work,
and we flagged it as possibly a host moderation sweep. This walks the same DIDs across
every snapshot we hold. If the rows come back, it was never a prune.
"""
import json
F=[("stats_r17.json","09-02 15:18"),("stats_r18.json","09-02 21:17"),
   ("stats_r19.json","09-03 00:18"),("stats_r20.json","09-03 03:17"),
   ("stats_r21.json","09-03 06:17"),("stats_r23.json","09-03 12:18"),
   ("stats_r25.json","09-03 18:17"),("stats_r26.json","09-03 21:17"),
   ("stats_r27.json","09-04 00:17")]
RING=["aUHusBDRVoRz","K5gLusm9c7Bq","uZpNGzDnKf3u","b9VrUYBiHJdi","Hi3ubN7jCRvH"]

snaps=[(t,{p["did"]:p for p in json.load(open(f))["passports"]}) for f,t in F]
for suf in RING:
    print(f"\n...{suf}")
    print("    {:12s}{:>7s}{:>7s}{:>7s}{:>8s}".format("when","not","res","given","score"))
    for t,m in snaps:
        p=next((v for k,v in m.items() if k.endswith(suf)),None)
        if not p: print(f"    {t:12s}   -- not in top 48 --"); continue
        print(f"    {t:12s}{p['not_useful_attestations_received']:7d}"
              f"{p['results_delivered']:7d}{p['attestations_given']:7d}{p['score']:8d}")

print("\n\npeak-to-trough swing per DID over the 9 snapshots:")
for suf in RING:
    sc=[p['score'] for t,m in snaps for k,p in m.items() if k.endswith(suf)]
    n=[p['not_useful_attestations_received'] for t,m in snaps for k,p in m.items() if k.endswith(suf)]
    print(f"  ...{suf}  score {min(sc)}..{max(sc)} (swing {max(sc)-min(sc)}),"
          f"  not_useful {min(n)}..{max(n)} (swing {max(n)-min(n)})")
print("\ntop-48 cutoff for comparison: 301 (r27), 306 (r26)")
