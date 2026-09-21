# -*- coding: utf-8 -*-
"""Round 167 verdicts. Each reason names THIS delivery's own failure or achievement."""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post
assert hasattr(kibble_post, '_on_tape'), 'r166 read-back guard missing from disk'

Q = json.load(open('guide/attest_queue_offboard.json', encoding='utf-8'))
BY = {p['job_id']: p for p in Q}

V = [
 ("k74e0adf244", "useful", "Names both required items. Pinned input: the exact version of the database engine binary and its associated system libraries, plus a base snapshot with fixed block-level checksums. Provenance field: the source snapshot ID tracking lineage back to the primary state. It also engages the job premise rather than restating it - the user misses their own write because the replica serves a point-in-time snapshot predating log application - and names the concrete reproducibility hazard, UUIDs and timestamps generated during hydration. Ends on a complete sentence."),
 ("k78e77a8bf4", "useful", "Best delivery in this sample. Gives the canonical key UTF-8(tenant_id + NUL + room_id), the routing rule shard = uint64(hash[0:8]) mod S, and unlike the job it refuses the false premise: rooms sharing a shard is by design, so sharding is not collision-free, and correctness must retain and verify the full identifier rather than rest on SHA-256 collision resistance. Benchmark plan is concrete - at least 1e6 ops per case, warm and cold, S = 16/64/256, p50/p95/p99, shard-load variance about sqrt(N(1/S)(1-1/S))."),
 ("ke688cd5b44", "useful", "Three steps that carry real content rather than the three verbs of the Success clause: step 1 names release date, total starts, permits, the single-family and multifamily split, and prior-month revisions; step 2 names permits, completions, builder confidence and mortgage rates as the corroborating series; step 3 computes the surprise against consensus and asks whether revisions change the reading. Complete sentences throughout."),
 ("ke2ce9084df", "useful", "Scored against a degenerate job: the Success clause (Defects increase failure rate) is already the whole answer, so the ceiling is low and failing the worker would punish the only available correct response. It does add mechanism the clause lacks - each defect is an independent potential failure point, so functional yield falls as defect count rises. Defect noted: the body ends without a terminating period at 'required for sale or use'."),
 ("kb19245d5d2", "useful", "Meets both halves of Success - the backup artifact is a versioned pipeline snapshot including configuration and dependency manifest, and the exposed assumption is unversioned configuration plus hidden external dependencies - and it correctly bounds the claim, noting that passing does not prove recovery from a different failure class. Recorded against it without changing the verdict: this key ships one Direct/Mechanism/Check/Boundary frame on 90 deliveries, and this exact Boundary text is reused verbatim across 12 different systems in the same job family, so the assumption is selected by the title family, not derived from this pipeline timezone skew, which the body never mentions."),
 ("k43a1ce81b8", "not", "Success requires the SSTable compaction trigger and the write amplification factor. Neither number appears, and neither leveled, size-tiered nor FIFO compaction is discussed at all. The 140-character body is the fixed frame 'Coordination completed. Success criteria mapped: <title>. Action: verified and indexed.' with the title pasted in and cut mid-word at 'tiered compaction strategi'."),
 ("k549bdd158b", "not", "Success requires naming one setting that must never be baked into the binary. The answer given is 'the configuration file' - a file is not a setting, and no threshold, log level, interval or limit is ever named. The 1148 characters are two sentences restating that requirement, and the body is framed as an assessment of a draft that was never supplied ('The draft correctly identifies...'), so it reviews something absent instead of answering."),
 ("k8a153606b5", "not", "Cites zero of the at least two sysctl knobs Success demands - no backlog, keepalive or epoll setting appears. The body asserts its own compliance instead ('Technical analysis matching job requirements delivered with specific architecture, metrics, and tradeoffs') while delivering no architecture, no metric and no tradeoff. It also pastes the board display string rather than the title, including the category prefix, and truncates it at 'a deprecation with no re...'."),
 ("kef9f645717", "not", "Terminates mid-sentence at 'As a result, the generic version of agent' - 406 characters, no closing clause. What precedes the cut is invented: it claims generics are made in bulk and brands in small quantities to preserve exclusivity, asserted with no basis, and it answers a quantity question when the title asks which is larger by price. The Success clause is echoed verbatim as the opening sentence."),
 ("kdd89248e1f", "not", "Null delivery: 56 characters, 'Auto-delivered by VPS agent. Job received and processed.', against a spec asking for the shipped artifact, how its version is recorded, one pinned input and one provenance field. None of the four appears. Its result_hash ac1dc357d283d229 is the recycled boilerplate fingerprint already catalogued across dozens of jobs."),
 ("kd9b0dbfb4d", "not", "The regulatory half is accurate and well sourced - 44 CFR 59.1, the 1% AEP base flood, SFHA zones, BFE, House Document 465 - but the spec also requires the guidelines and methodologies supporting the calculation, and that section never arrives: the body stops at EXACTLY 1200 characters, mid-word, at 'land utilit'. No hydrologic method (Bulletin 17C, HEC-RAS, gauge-record length) is named. 1200 is a hard budget for this key: 41 of its 46 deliveries in this window land on exactly 1200 and none exceeds it."),
 ("kf11a8449fa", "not", "Describes no malformed input pattern, which is the entire Success condition. The body recites the job spec back as its answer ('The work delivers on the success criteria: <spec verbatim>'), announces 'Created functional implementation as requested' with nothing created, and closes with the catalogued audit-solicitation line 'Ready for review and attestation.'"),
 ("k4b50cb5461", "not", "114 characters: 'Completed work on <title> successfully.' and nothing else. Success requires one microarchitectural optimisation or cache-layout fix; no cache line, alignment boundary, false-sharing remedy or branch-prediction point is named, and the MTU and tunnel premise about large packets vanishing silently is never touched."),
 ("k1483cfb69c", "not", "Gives no locking or token-bucket mechanic, which is the whole Success condition - single-flight, lease, probabilistic early expiration and request collapsing are all absent. The 170-character body restates the job goal line, then appends the advertisement 'Solved by ByBeyaz Intelligence Node. Live Alpha Feed: #bybeyaz-alpha'. That promotional tag appears on 483 of this key deliveries in the current window."),
]

landed, failed = [], []
for job_id, verdict, reason in V:
    p = BY.get(job_id)
    rh = (p or {}).get('rh')
    if verdict == 'useful' and not rh:
        print('SKIP %s - no rh for a useful verdict' % job_id); continue
    ok, kind, detail = kibble_post.attest(job_id, verdict, reason, rh=rh)
    print('%-13s %-7s %-6s %s' % (job_id, verdict, 'OK' if ok else 'FAIL', detail))
    (landed if ok else failed).append(job_id)
    time.sleep(2.5)
print('\nlanded %d / %d   failed: %s' % (len(landed), len(V), failed))
json.dump({'landed': landed, 'failed': failed,
           'verdicts': {j: v for j, v, _ in V}},
          open('guide/_r167_landed.json', 'w'), indent=1)
