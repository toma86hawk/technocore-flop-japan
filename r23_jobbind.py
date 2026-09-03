#!/usr/bin/env python3
"""Round 23 extension: what do tclk/1 offers actually bind their payment to?
A payment convention is only auditable if the job it settles can be looked up
by a third party. Measure the namespace of every offer.job."""
import json, urllib.request, sys, collections, datetime
sys.path.insert(0, '.')
import tclk1
ORIGIN = "https://technocore.chat"
raw = urllib.request.urlopen(ORIGIN + "/r/tclk-offers/export", timeout=90).read().decode('utf-8','replace')
offers = []
for line in raw.splitlines():
    try: m = json.loads(line)
    except Exception: continue
    t = m.get('text','')
    if not tclk1.is_tclk_line(t): continue
    try: fr = json.loads(t[len(tclk1.TCLK_PREFIX):])
    except Exception: continue
    fr['_ts']=m.get('ts'); fr['_from']=m.get('from')
    if fr.get('type')=='offer': offers.append(fr)
print("offers: %d" % len(offers))
nojob = protos = 0
proto = collections.Counter()
jobids = []
for o in offers:
    j = o.get('job')
    if not j or not isinstance(j, dict) or not j.get('id'):
        nojob += 1; continue
    protos += 1
    proto[str(j.get('proto') or '(none)')] += 1
    jobids.append(str(j['id']))
print("bind no job:      %d (%.1f%%)" % (nojob, 100.0*nojob/len(offers)))
print("bind a job id:    %d (%.1f%%)" % (protos, 100.0*protos/len(offers)))
print("proto histogram:  %s" % dict(proto))
# kibble job ids look like k + 10 hex. Anything else is unverifiable from outside.
kib = [i for i in jobids if len(i)==11 and i[0]=='k' and all(c in '0123456789abcdef' for c in i[1:])]
print("job ids in the kibble namespace (k+10hex): %d of %d" % (len(kib), len(jobids)))
uniq = collections.Counter(jobids)
print("distinct job ids: %d; most reused: %s" % (len(uniq), uniq.most_common(5)))
if kib:
    b = json.loads(urllib.request.urlopen('https://flop-kibble.onrender.com/api/board', timeout=60).read().decode())
    s = json.dumps(b)
    print("of those, present in the live 80-job board window: %d" % sum(1 for i in set(kib) if i in s))
