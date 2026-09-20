# -*- coding: utf-8 -*-
"""useful_on_thin with the r155/r156 PROXY: /api/tape is HTTP 000, so 'thin'
is body length <= 119 chars measured on the verified export, not the host flag."""
import json, io, sys, re, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
rows = [json.loads(l) for l in io.open(sys.argv[1], encoding="utf-8") if l.strip().startswith("{")]
body = {}          # job_id -> delivery body
for r in rows:
    t = r.get("text") or ""
    m = re.match(r"^(RESULT|DELIVER) v1 \| (k[0-9a-f]+) \|", t)
    if m:
        b = t.split("|", 2)[2].strip()
        body.setdefault(m.group(2), b)
THIN = 119
thin = {j for j, b in body.items() if len(b) <= THIN}
useful = useful_thin = 0
att = collections.Counter()
for r in rows:
    t = r.get("text") or ""
    m = re.match(r"^ATTEST v1 \| (k[0-9a-f]+) \| (useful|not)\b", t)
    if not m:
        continue
    att[m.group(2)] += 1
    if m.group(2) != "useful":
        continue
    j = m.group(1)
    if j not in body:
        continue
    useful += 1
    if j in thin:
        useful_thin += 1
print("window seq %d..%d  rows %d" % (rows[0]["seq"], rows[-1]["seq"], len(rows)))
print("deliveries with body      %d" % len(body))
print("thin (<=%d chars)          %d  = %.1f%% of deliveries" % (THIN, len(thin), 100.0*len(thin)/max(1,len(body))))
print("ATTEST useful/not         %d / %d" % (att["useful"], att["not"]))
print("useful with a body here   %d" % useful)
print("useful_on_thin            %d  = %.1f%%" % (useful_thin, 100.0*useful_thin/max(1,useful)))
