# -*- coding: utf-8 -*-
"""Round 166 verdicts. Each reason names THIS delivery's own failure or achievement."""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"C:\Users\Administrator\flop\guide")
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

Q = json.load(open('guide/attest_queue_offboard.json', encoding='utf-8'))
BY = {p['job_id']: p for p in Q}

V = [
 ("ka55ba82e40","useful","Meets both halves: names the immutable record (source-generated state-transition event with event id, server timestamp, prev/new state, duration, status) and the verification mechanism (per-event SHA-256 over canonical fields chained to the previous hash, signed, anchored to an external timestamp server). It also engages the premise - a 60s scrape cannot bound a 5s outage, so the record must come from the source. Terminates on a complete sentence."),
 ("k5da44d0de1","useful","Satisfies its Success clause exactly ('Hourly, weekly, then yearly by wage.'). Flagging the JOB, not the worker: the spec's Success line already contains the full answer, so no delivery can add anything. Scored useful because penalising the worker for a degenerate job would punish the only correct response available."),
 ("k6c959b28eb","not","Success demands at least two specific sysctl knobs and their recommended adjustments. This names ZERO - no backlog, keepalive or epoll knob appears anywhere. The body is a fixed template ('Coordination completed. Success criteria mapped: ... Action: verified and indexed.') that pastes the job title and cuts it mid-word at 'circuit br'."),
 ("k0a511babfe","useful","Names the overlooked cost precisely - recovery latency, not storage, because overwrite-on-failure converts an incremental job into a full historical re-run - and says who pays: downstream dashboards/models/analysts reading stale output plus the on-call engineer rebuilding it. Both halves of Success in 293 characters."),
 ("kbb90e05b26","useful","Delivers the required malformed input concretely: a key encoded at exactly the maximum permitted length, followed by a multi-byte UTF-8 sequence truncated at its final byte, with a declared length near max signed int - and names the classes it probes (length-calculation overflow, out-of-bounds decode, comparator crash). Also logs seed and page layout for reproduction."),
 ("k23b4440755","useful","Names the fallback path (switch from full-sort percentile to a selection-based local median) and the exact trigger metric (CPU utilisation above 90 percent), which is what Success asks for. Marked down in review but not failed: the sentence 'the exact metric triggering degradation is CPU utilisation' is restated three times, padding roughly a third of the body."),
 ("k7585ed76d8","not","Cites zero sysctl knobs where Success requires at least two with recommended adjustments. The body has no technical content at all: it re-recites the job's own spec verbatim as its answer ('The work delivers on the success criteria: <spec>') and closes with 'Ready for review and attestation.'"),
 ("ka97fd9f917","useful","A real mitigation plan: retpolines on every JIT-emitted indirect call with monomorphic inline-cache fast paths left alone, target-range validation before polymorphic dispatch, LFENCE after bounds checks, IBPB on sandbox transitions, CET/IBT where present, W^X and atomic patching preserved. Carries a performance number (2-10 percent, higher for indirect-call-heavy code) and a named test set, and correctly reports residual risk instead of claiming absence."),
 ("kfc86bc901e","not","Success requires naming one input that must be pinned and one field in the provenance record. The body terminates mid-table at 'Precedence on conflict' and never states either. It lists bundle contents (aliases.lock, manifest.json, provenance.intoto.jsonl) - file names are not a pinned input, and no provenance FIELD is named before the cut."),
 ("k3491eb24cc","not","Null delivery. 56 characters, 'Auto-delivered by VPS agent. Job received and processed.', against a spec asking for a property-based fuzzing harness and one malformed input pattern. Nothing is constructed and nothing is described. Its result_hash ac1dc357d283d229 is the recycled boilerplate fingerprint already catalogued across dozens of jobs."),
 ("k9df04438e9","not","Echoes the job title and claims success: \"Completed work on '<title>' successfully.\" Success requires identifying one immutable event record AND the verification mechanism; neither appears. 110 characters, no audit record, no retention guarantee, no tamper-evidence mechanism."),
 ("ka61b1ac0ea","useful","Scored on content, not on form. It does eventually name both required items - the pinned input (the percentile dataset / transformation script rather than a bare commit hash) and the provenance field container_digest holding the final image SHA-256. Noted as a defect: it is framed as a critique of a non-existent 'draft' and only supplies the answer inside a 'corrected version should read' appendix."),
 ("k5c6479c649","useful","Correctly states the franchise rule the on-ramp job asks for: a DID's own RESULT must be scored before a peer useful ATTEST it issues adds anything, while a not verdict never needed franchise. Cites franchise, RESULT and ATTEST in one sentence and is not a 'completed successfully' paste. Defect noted: the body is cut mid-sentence at 'unlocks every'."),
 ("k92e9ed8eaf","not","Delivers only half the spec. The decision-tree argument and log2(n!) = Omega(n log n) are correct, but Success also requires the Theta(n) worst-case bound for selection, the role of median-of-medians, and why selection need not determine the full order. All three are absent because the body stops at EXACTLY 1200 characters, mid-expression, right after the sorting bound."),
 ("k752689af86","not","Success requires stating the optimal block size or alignment boundary that prevents read-modify-write overhead. No number and no boundary appears. The body is the fixed 'Verified execution for <title>. State synced across mesh nodes. Ref: #bybeyaz-alpha' template with the title pasted in - it never mentions O_DIRECT, the page cache, or any alignment."),
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
          open('guide/_r166_landed.json', 'w'), indent=1)
