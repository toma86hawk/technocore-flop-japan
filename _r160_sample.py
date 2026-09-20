import json, random, sys, io
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
q = json.load(io.open("guide/attest_queue_offboard.json", encoding="utf-8"))
SEED = 20260920160
random.seed(SEED)
idx = list(range(len(q)))
random.shuffle(idx)
seen_worker = {}
picked = []
for i in idx:
    p = q[i]
    w = p["worker"]
    if seen_worker.get(w, 0) >= 2:
        continue
    seen_worker[w] = seen_worker.get(w, 0) + 1
    picked.append(p)
    if len(picked) == 15:
        break
json.dump(picked, io.open("guide/_r160_picked.json", "w", encoding="utf-8"), ensure_ascii=False)
for n, p in enumerate(picked, 1):
    r = p.get("result") or ""
    print("="*100)
    print("[%d] %s  cat=%s  worker=%s  rh=%s  len=%d" % (n, p["job_id"], p.get("category"), p["worker"][-12:], p.get("rh"), len(r)))
    print("TITLE: " + (p.get("title") or ""))
    print("SPEC : " + (p.get("spec") or ""))
    print("-"*40 + " RESULT " + "-"*40)
    print(r[:2600])
    if len(r) > 2600:
        print("...[TRUNCATED %d more chars; tail:] ..." % (len(r)-2600) + r[-260:])
