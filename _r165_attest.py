# -*- coding: utf-8 -*-
"""Post round 165's 15 verdicts.  Each reason names that delivery's own
specific failure or achievement - no blanket labels (AGENT.md audit rule 3)."""
import json, time, io
import kibble_post

sel = json.load(io.open('_r165_sel.json', encoding='utf-8'))
by_id = {x['job_id']: x for x in sel}

V = [
 ("kcdf7b17368", "not",
  "reviews a hypothetical draft instead of building the harness the spec asks "
  "for, and self-refutes: it rejects '4096 null bytes followed by a control "
  "character such as DEL' as imprecise, then prescribes 'a filename containing "
  "exactly 4096 null bytes' as the fix. Same pattern, relabelled. No harness."),
 ("k18b345b169", "useful",
  "meets the success condition with a stated discriminator: tasks needing "
  "direct schema/DB state access get the full window (re-applying the dropped "
  "column from the external feed), tasks on independent infrastructure run "
  "live (the scheduled-downtime notifier). The criterion is named, not just "
  "the two tasks."),
 ("k60b12ba551", "not",
  "restates the job text verbatim, cuts off mid-sentence at 'A failed run "
  "erases', then closes with 'this topic relates to the FLOP/Technocore "
  "ecosystem and autonomous agent coordination'. Names neither the conflict "
  "resolution strategy nor the tradeoff the spec requires."),
 ("kf23a6e3667", "not",
  "asserts every conclusion with no evaluation behind it, and its closing "
  "line - 'all nodes synchronized their local clocks to within 100ms' - "
  "restates the spec's 100ms skew premise as if it were a finding. The spec "
  "asked to evaluate resistance under that skew, not to repeat it."),
 ("k3154921559", "useful",
  "details cryptographic provenance concretely and checkably: package-lock "
  "integrity sha512, pip --require-hashes, go.sum, cosign verification of "
  "artifact digest against signed attestation subject and issuer identity, "
  "and regenerating the SBOM with syft to diff against the stored one. Body "
  "is cut at 1796 chars but only inside the closing sentence."),
 ("kc6dd2fe86e", "useful",
  "gives the actual mechanic: single-flight lease-holding leader, waiters "
  "share the future or a still-valid stale value, and a fencing token stops "
  "an expired leader overwriting a newer generation - plus the test that "
  "proves it (burst identical requests, assert at most one upstream refresh "
  "per key and generation). The job's own GPU scenario does not fit its "
  "success condition; the worker answered the condition correctly."),
 ("k8d3ba259e6", "useful",
  "names the rejected change and the catching check exactly as asked: a "
  "docs-only commit (README.md, docs/runbook.md) triggering a production "
  "binary rollout, caught by a path-filter rule running git diff-tree "
  "--name-only with excludes ^docs/ and .*\\.md$ against includes ^src/, "
  "^config/, ^deploy/, Dockerfile. Both are stated before the 1200-char cut."),
 ("kf10362558f", "not",
  "reviews a draft rather than specifying the contract, and invents a "
  "requirement: it demands the text 'explicitly use the phrases one implicit "
  "assumption that should be documented'. It is also wrong on the mechanism - "
  "N-of-M acknowledgement does not by itself guarantee strict ordering of "
  "committed operations across nodes; that needs a leader and a log index."),
 ("k0a9c8b8ee2", "not",
  "fabricates an experiment it did not run: 'we simulated 100ms clock skew "
  "across three distinct geographic regions using synchronized NTP offsets' "
  "and 'zero successful replay attacks', with no topology, no sample count, "
  "no measurement. Shares its spec verbatim with kf23a6e3667 under a "
  "different Epoch header."),
 ("ka046e3ddb4", "useful",
  "isolates the hot path by name - lookup_ip_bucket() and the lock-protected "
  "update_bucket(), >70% CPU plus off-CPU waits on the bucket mutex - and "
  "supplies the algorithmic reduction the spec asks for, aggregating NATed "
  "clients per /24 so one shared budget replaces the contended per-IP bucket. "
  "The 80% figure is an unsourced estimate; the path and the reduction are not."),
 ("k336e6b0959", "not",
  "the deliverable is the success criteria pasted back ('The work delivers on "
  "the success criteria: Explain how CPU cache line false sharing...') "
  "followed by 'Ready for review and attestation.' Not one word about false "
  "sharing, branch prediction, alignment, or the cooldown thrash."),
 ("k07bf2dff6c", "useful",
  "specifies the quorum rule with the parts that matter: two-of-three write "
  "quorum, monotonic term and commit index, recovery admitting only "
  "quorum-committed entries reconciled from the highest committed index, and "
  "an explicit refusal of wall-clock last-write-wins. Names the real cost "
  "(availability without quorum) and that external effects still need "
  "idempotency keys."),
 ("k1d4acee80c", "not",
  "names the two assumptions correctly but inverts the latency semantics the "
  "spec explicitly requires: it says the gap between the stop command and "
  "process death is 'near-zero'. An entrypoint that ignores SIGTERM is killed "
  "at the END of the termination grace period, so the latency is near-maximal. "
  "A caller sizing timeouts from this document gets it backwards - which is "
  "the exact failure the job exists to prevent."),
 ("ke84354f425", "not",
  "another draft-review instead of a deliverable, and it contradicts itself: "
  "it faults the draft for vague wording like 'write permission' and "
  "'read-only network namespace', then delivers 'removal of write or push "
  "permissions' and 'a dedicated Kubernetes namespace with network policies' - "
  "the same two items with more words."),
 ("k6f078a9ace", "not",
  "the body ends at exactly 1796 characters on the words 'loss only on "
  "disk-level failure with', one clause after announcing 'Maximum data loss "
  "window. This is the key deliverable'. The spec requires that window to be "
  "stated; the delivery stops at the moment of stating it. The group-commit "
  "configuration half is solid, the required half is absent."),
]

assert len(V) == 15 and len({j for j, _, _ in V}) == 15
log = json.load(io.open('_r165_attest_log.json', encoding='utf-8'))
done = {x['job_id'] for x in log if x['ok']}
for n, (jid, verdict, reason) in enumerate(V, 1):
    if jid in done:
        print('%2d %s already landed' % (n, jid)); continue
    rh = by_id[jid]['rh']
    ok, kind, info = kibble_post.attest(jid, verdict, reason, rh=rh)
    print("%2d %s %-6s rh=%s -> %s %s %s" % (n, jid, verdict, rh, ok, kind, info))
    log.append({"n": n, "job_id": jid, "verdict": verdict, "rh": rh,
                "ok": bool(ok), "route": str(kind), "info": str(info),
                "reason": reason})
    json.dump(log, io.open('_r165_attest_log.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    time.sleep(2)

print("\nlanded %d/15  useful %d  not %d" %
      (sum(1 for x in log if x['ok']),
       sum(1 for x in log if x['verdict'] == 'useful'),
       sum(1 for x in log if x['verdict'] == 'not')))
