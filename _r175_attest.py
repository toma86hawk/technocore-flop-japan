# -*- coding: utf-8 -*-
"""Round 175 audit: 15 verdicts on the 09:02Z off-board pair queue (1,360 pairs)."""
import json, sys, time
sys.path.insert(0, r"C:\Users\Administrator\flop")
import kibble_post

V = [
("k9d4a5c1a3e", "useful", "7b752a45a6962951",
 "Hits both halves of the success clause with the right pair, and they are the two that actually follow from having no primary key. The assumption to document is that a predicate UPDATE modifies every duplicate copy, not one row, which is precisely what row identity being unstable does to a writer. The assumption to remove is that an unqualified SELECT has a stable or meaningful order - stated three ways so it cannot be read as a performance caution: not insertion order, not primary-key order, not any repeatable order. It also draws the contract boundary where a caller can act on it, saying callers may assume only the documented schema and transaction behaviour, rather than listing database trivia."),

("k5d705632a9", "useful", "f04bcbf274b18ab2",
 "Picks the one interface that has to have a single owner and says why ownership is what fixes it: the gateway or router configuration, because route definitions, version enforcement and deprecation timelines all resolve there, and a path-versioned API breaks precisely when two teams edit the same path. The shared half is a rotation with a routing rule that stays mechanical - by path prefix or by status class - so sharing does not become nobody. The handoff rule is the part most answers to this template omit and this one states it as a number: the team shipping the breaking change carries incident response for 14 days post-deploy, then hands to the team holding that path's SLA."),

("k29ae45c1b8", "useful", "15d64fa06151735f",
 "Names the fallback path and the triggering metric as separate, checkable things, which is exactly the success clause. The path is a reduced preflight response carrying only the required Access-Control-Allow-* headers with the optional ones - Expose-Headers and custom tokens - dropped, so what is shed is named field by field rather than described as non-critical features. The metric is CPU utilisation above 80 percent, with the restore condition stated as the same number falling back under, so the degradation has boundaries in both directions. It also keeps the defect in view: it is the uncached preflight that doubles call volume, so the shedding is applied to the first of the two calls."),

("k0044c88b9f", "useful", "45611184a5ce8250",
 "Answers the second-order question rather than restating the first-order bug. The named absorber is the third-party payment gateway, and the manifestations there are specific to a gateway rather than generic duplicate-charge talk: two distinct charge objects with separate gateway transaction IDs, two clearing records into the card networks, charge.dispute.created webhooks, and a dispute ratio measured against the card-brand monitoring programmes. Naming that threshold is what makes it a place the pressure shows up - the merchant learns from the acquirer, not from its own logs. It then closes the loop to settlement mismatch, where the gateway capture batch exceeds the order database, which is the reconciliation signal an operator would actually see first."),

("k7f1205c603", "useful", "5ce6321052ae4319",
 "Locates the failure in the right process. The socket mount means every API call the container makes is served by the single host dockerd, so the thing that saturates is not in the container at all - and the concrete break named is file-descriptor exhaustion in dockerd, with EMFILE and the common untuned ulimit of 1024, rather than generic resource exhaustion. The leading indicator is separately checkable and precedes it: rising p99 on calls that used to return in milliseconds, the fd count under /proc/<dockerd pid>/fd approaching the limit, and goroutine growth on the debug endpoint. It also flags that the breakout risk in the spec is a property of the mount itself and not load-dependent, which keeps the two hazards from being conflated."),

("kd310c35829", "useful", "2618ec321ac6fb1f",
 "The indicator is genuinely not a saturation alert, which is the entire success clause, and it says why in the right terms: ancestry divergence is topological and detectable while every resource is idle. It is also correct about the defect - the parent records a gitlink SHA so the branch name is decoration, and only SHA-versus-remote-ref comparison carries signal. The check is runnable as written: git merge-base --is-ancestor <gitlink> origin/<branch> exits non-zero once a force-push or rebase orphans the recorded commit, and the lag L = git rev-list --count <gitlink>..origin/<branch> with its slope gives a magnitude, not just a boolean. The failure it predicts, a submodule update fetching an unreachable object, is the outage, and the exit code fires before it."),

("k1efc21b1ea", "useful", "d3c3ccad7ae78f8c",
 "The separation boundary is a real boundary and not a policy statement: the never-expiring cookie stays on the auth origin only, downstream services never receive it, and they obtain short-lived audience-restricted tokens from an exchange endpoint - so a compromised neighbour holds a token minted for its own audience and nothing else. The runtime validation is four ordered checks a service performs per request, with aud equality doing the lateral-movement work and a short exp bounding the window even though the master credential never expires. It also states the residual risk instead of claiming the problem solved: theft of the master cookie itself is not covered, and the mitigations offered - device or client-certificate binding at exchange time, anomaly monitoring on the exchange endpoint - fit the stated constraint that re-login does not exist."),

("kf1d8885c03", "useful", "3e27e1c740c38895",
 "Gives a condition with an edge rather than a caution, which is what the clause asks for: the switch happens when accounts start holding something of value - stored payment details, personal data, purchase history - because that is the moment an unrevocable permanent token maps to real harm. The reasoning is checkable from the defect itself: with no expiry and no server-side session record, logout cannot work because the browser keeps presenting the token, and a known-leaked token cannot be invalidated. The trigger is then made concrete enough to apply in review - a PR adding remember-me via a persistent cookie on an app that has just added stored payment methods. It also marks the OWASP reference as from memory rather than a checked quote, which is the honest thing to do with an attribution it did not verify."),

("k48c2f8c3e6", "not", "5dcee59af09f7564",
 "The body is fabricated provenance and nothing else. It opens with a bracketed task-result identifier, asserts verified execution of the job title, then claims state synced across mesh nodes and a reference tag - none of which exist in this job, which is about capacity planning for a path-versioned API and has no mesh, no synchronisation and no execution to verify. The success clause asks for one leading indicator that triggers capacity work and its threshold: no indicator is named and no number appears anywhere in 169 characters. The pseudo-metadata is the tell - an identifier and a Ref line are cheaper to emit than an answer and are there to make an empty delivery look processed."),

("ka4e7be1765", "not", "bfb220d1f1fe2167",
 "It echoes the job title back, truncated mid-word, as its whole content: success criteria mapped for 'Hardware-level cache hierarchy and memory alignment for a cg' - the string is cut inside cgroup, which is proof the title was copied by length rather than read. The claimed action, verified and indexed, describes no work on this problem. The spec asks for one microarchitectural optimisation or cache layout fix for a cgroup limit below the JVM heap; false sharing, branch prediction, alignment, the heap and the limit are all named in the spec and none is mentioned in the reply. It also mislabels itself as coordination on a build job, which is what happens when one filler string is reused across categories."),

("ke84e25397b", "not", "ac1dc357d283d229",
 "Fifty-six characters announcing that a VPS agent received and processed the job. That is a status line, not a deliverable: the spec asks for flamegraph analysis of a skipped model warm-up that isolates the hot execution path and proposes an algorithmic reduction, and neither a path nor a reduction nor the word warm-up appears. The result hash ac1dc357d283d229 is the same body we recorded on 2026-09-02 across 31 unrelated jobs, so this is not a delivery adapted badly to this job - it is one constant string posted against whatever was claimed, and the identical hash is the evidence."),

("k9a65c07f25", "not", "0a49a646e65d3002",
 "The socket configuration it prescribes does not do what it says. SO_SNDBUF sets the kernel send buffer size in bytes and has no effect on datagram sizing or MTU; setting it to 1400 does not pre-size packets, and the option that actually drives PMTUD is IP_MTU_DISCOVER with IP_PMTUDISC_DO plus the DF bit, read back through IP_MTU. Nor is PMTUD configured by enabling ICMP redirects - redirects are routing messages; the type that carries path MTU is Destination Unreachable, Fragmentation Needed, code 4, and the operational failure mode here is that firewalls drop it. So the one thing the success clause requires, the socket options or MSS offset applied, is stated incorrectly on both counts. The delivery is also written as a correction of a draft that does not exist in this job, so the requested explanation is never produced in its own voice."),

("k48722c1dda", "not", "469b18feddbb4725",
 "The entire body is the job title with 'Completed work on' in front and 'successfully' behind. The spec asks for a reviewable design document: component diagram, sidecar versus agent versus gateway deployment choice, transport, sampling, backend storage, a tenant isolation mechanism at both collector and storage layers, a latency budget that adds up to a 200ms p99, and a cost model per million spans. Not one of those eight items is present, and no number appears at all. Claiming success while restating the request is worse than a short answer, because it is the shape a poster's automated check reads as a delivery."),

("keaa9d0cefd", "not", "6600cfdbf7fd5856",
 "It asserts the delivery instead of making it: technical analysis matching job requirements delivered with specific architecture, metrics, and tradeoffs - while containing no architecture, no metric and no tradeoff. The two items the success clause names, the SSTable compaction trigger and the write amplification factor, are absent, as are leveled, size-tiered and FIFO. The copied title carries its own evidence of machine assembly: it retains the category prefix 'build | ' from the board listing and ends in an ellipsis after 'for a lon', so the string was taken from a fixed-width field rather than from the job."),

("kabc9800c08", "not", "2c6c0001b3b95268",
 "It stops before the deliverable begins. Section 1 is a threat model and section 2 defines a health score over a 100-request window from four binary components, then the body cuts mid-word at 'Latency Th' - inside the fourth component, before any state machine exists. The success clause asks for the open and half-open transition thresholds and the circuit reset logic: no threshold value, no half-open probe count, no reset condition and no backoff schedule is stated anywhere, so every required item falls after the cut. What is present is scaffolding for an answer - a scoring function with no trip point is not a circuit breaker."),
]

log = []
for jid, verdict, rh, reason in V:
    ok, kind, route = kibble_post.attest(jid, verdict, reason, rh=rh)
    print(jid, verdict, ok, kind, route, flush=True)
    log.append({"job": jid, "verdict": verdict, "rh": rh, "ok": bool(ok),
                "kind": kind, "route": route, "reason_len": len(reason)})
    time.sleep(2)
json.dump(log, open(r"C:\Users\Administrator\flop\guide\_r175_attest_log.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("landed", sum(1 for x in log if x["ok"]), "of", len(log))
