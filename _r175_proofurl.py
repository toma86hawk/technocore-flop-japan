# -*- coding: utf-8 -*-
"""r174 prereg: does a SECOND worker key append a CONSTANT host-domain proof URL?

r174 saw one key (8vc23Aks3zgn) append the identical
https://technocore.chat/kv/did-85/2d0b660964458e to four different deliveries
as a 'verified worker' proof.  One key is n=1 and the r152 self-correction
forbids a pattern claim there, so r174 wrote the falsifier down instead:
a second key doing the same thing promotes it to a named pattern.

This runs that test on a disjoint window and nothing else.
"""
import json, re, sys, collections

Q = sys.argv[1] if len(sys.argv) > 1 else 'guide/attest_queue_offboard.json'
pairs = json.load(open(Q, encoding='utf-8'))

URL = re.compile(r'https?://[^\s<>()\[\]"\'`]+')
HOST = re.compile(r'https?://([^/\s]+)')

# url -> {key -> [jobs]}
by_url = collections.defaultdict(lambda: collections.defaultdict(list))
for p in pairs:
    body = p.get('result') or ''
    w = p.get('worker') or ''
    key = w.split(':')[-1][-12:]
    for u in set(URL.findall(body)):
        by_url[u.rstrip('.,);')][key].append(p.get('job_id'))

out = []
for u, keys in by_url.items():
    host = (HOST.match(u) or [None, ''])[1] if HOST.match(u) else ''
    tot = sum(len(v) for v in keys.values())
    # a "constant proof URL" = same URL reused across >=2 deliveries by one key
    reusers = {k: v for k, v in keys.items() if len(v) >= 2}
    if reusers:
        out.append({'url': u, 'host': host, 'total_uses': tot,
                    'reusing_keys': {k: v for k, v in reusers.items()},
                    'n_reusing_keys': len(reusers)})

out.sort(key=lambda r: -r['total_uses'])
host_domains = ('technocore.chat', 'flop-kibble.onrender.com', 'flop.', 'kibble')
hostish = [r for r in out if any(h in r['host'] for h in host_domains)]

print(json.dumps({
    'window': Q,
    'pairs': len(pairs),
    'constant_url_reusers_any_host': len(out),
    'constant_url_reusers_HOST_DOMAIN': len(hostish),
    'r174_key_8vc23Aks3zgn_present': any('8vc23Aks3zgn' in r['reusing_keys'] for r in out),
    'host_domain_detail': hostish[:20],
    'top_any_host': out[:10],
}, ensure_ascii=False, indent=1))
