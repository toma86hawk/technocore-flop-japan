#!/usr/bin/env python3
"""tclk/1 value-rail watcher - one pass per invocation, driven by Task Scheduler.

Why this exists: every tclk/1 lock measured so far (22/22 in round 18) settles on
rail=paper, which moves nothing. The instant-reveal pattern (payee reveals a median
4.4s after the payer locks, no work artifact) is harmless only for that reason. The
moment a LOCK frame carries a value-bearing rail, the same behaviour becomes
value-for-nothing, and being the first to measure and publish that is the whole
point of the catalogue. So: read the rail on LOCK frames (fact), never the `rails`
array on offers (aspiration), and fire once per new non-paper lock.

State lives in tclk_rail_state.json; the autonomous agent reads it each run.
"""
import json, os, sys, time, urllib.request, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "notify"))
import tclk1
from discord import notify

STATE = os.path.join(HERE, "tclk_rail_state.json")
LOG = os.path.join(HERE, "tclk_rail_watch.log")
ORIGIN = "https://technocore.chat"
MAX_ROOMS = 300
# Smallest no-id key-set cohort worth reporting as a fleet (round 82).
STUB_COHORT_MIN = 200


def _gap_cv(stamps):
    """CV of inter-arrival gaps. Independent senders -> 1.0; a paced emitter < 1."""
    ts = []
    for s in stamps:
        try:
            ts.append(datetime.datetime.strptime(str(s)[:26], "%Y-%m-%dT%H:%M:%S.%f"))
        except Exception:
            pass
    if len(ts) < 3:
        return None
    ts.sort()
    gaps = [(ts[i + 1] - ts[i]).total_seconds() for i in range(len(ts) - 1)]
    mean = sum(gaps) / len(gaps)
    if mean <= 0:
        return None
    var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    return round((var ** 0.5) / mean, 3)


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + msg + "\n")


def get(url, timeout=45, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == tries - 1:
                raise
            time.sleep(2)


def parse_frame(text):
    if not tclk1.is_tclk_line(text):
        return None
    try:
        return json.loads(text[len(tclk1.TCLK_PREFIX):])
    except Exception:
        return None


def save_state(st):
    """Write the state file ATOMICALLY.

    Round 129 (2026-09-17): the previous `json.dump(st, open(STATE, "w"))` left a
    6.2 MB file truncated in the middle of `seen_locks` when a write did not
    finish.  Every subsequent pass then died in load_state() with
    "Expecting ',' delimiter", the bare except at the bottom swallowed it and
    exited 0, so Task Scheduler reported SUCCESS while the watcher was dead for
    every cycle after 00:13:07.  Salvage recovered 25,839 of 30,423 locks; the
    other 4,584 - and 11 of the 99 known non-paper locks - were unrecoverable.
    Write to a temp file in the same directory and rename, so a reader either
    sees the whole previous state or the whole new one, never half of either.
    """
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    if os.path.exists(STATE):
        try:
            os.replace(STATE, STATE + ".bak")
        except OSError:
            pass
    os.replace(tmp, STATE)


def load_state():
    """Load state, and do not turn one bad file into a permanent crash loop."""
    empty = {"seen_locks": {}, "nonpaper_locks": [], "terminal_rooms": [], "last": {}}
    for path in (STATE, STATE + ".bak"):
        if not os.path.exists(path):
            continue
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception as e:
            log("STATE UNREADABLE %s: %s" % (os.path.basename(path), str(e)[:120]))
            if path == STATE:
                try:
                    os.replace(STATE, STATE + ".corrupt")
                except OSError:
                    pass
    return empty


def main():
    st = load_state()
    seen = st["seen_locks"]
    terminal = set(st["terminal_rooms"])

    # 1. The rendezvous ring: offers + accepts.
    raw = get(ORIGIN + "/r/tclk-offers/export", timeout=60)
    offers, accepts, offer_msgs = [], [], []
    for line in raw.splitlines():
        try:
            m = json.loads(line)
        except Exception:
            continue
        fr = parse_frame(m.get("text", ""))
        if not fr:
            continue
        if fr.get("type") == "offer":
            offers.append(fr)
            offer_msgs.append((m, fr))
        elif fr.get("type") == "accept" and fr.get("contract"):
            accepts.append(fr)

    contracts = []
    for a in accepts:
        c = str(a["contract"])
        c = c if c.startswith("0x") else "0x" + c
        if c not in contracts:
            contracts.append(c)

    # 2. Read every deal room we have not already seen reach a terminal frame.
    rail_on_locks = collections.Counter()
    new_nonpaper = []
    nonpaper_ts_floor = max([r.get("ts") or "" for r in st.get("nonpaper_locks") or []]
                            or [""])
    rooms_read = 0
    errors = 0
    for c in contracts[-MAX_ROOMS:]:
        room = tclk1.deal_room(c)
        if room in terminal:
            continue
        try:
            d = json.loads(get(ORIGIN + "/r/%s?format=json" % room, timeout=45))
        except Exception as e:
            errors += 1
            continue
        rooms_read += 1
        kinds = set()
        for m in d.get("messages", []):
            fr = parse_frame(m.get("text", ""))
            if not fr:
                continue
            kinds.add(fr.get("type"))
            if fr.get("type") == "lock":
                rail = str(fr.get("rail", "?"))
                rail_on_locks[rail] += 1
                key = "%s|%s" % (fr.get("contract"), m.get("from"))
                if key not in seen:
                    seen[key] = {"ts": m.get("ts"), "rail": rail, "room": room}
                    # Round 61 correction (pattern 83). This used to be an
                    # exact-match `rail.lower() != "paper"`, which counted
                    # `paperrail` (22 locks, median reveal 0.142 s) and
                    # `kv-paper` (16 locks, 4.205 s) as value-bearing. Both
                    # self-identify as paper in their own `ref`, carry no
                    # amount/asset and do no work, so 38 of the 93 locks this
                    # watcher had reported as non-paper - 40.9% - were paper
                    # wearing a name that defeats an equality test. Substring
                    # now, and spoofed rails are kept in their own list so the
                    # appearance of a new one is still a signal.
                    rec = {"contract": fr.get("contract"), "from": m.get("from"),
                           "rail": rail, "ts": m.get("ts"), "room": room,
                           "amount": fr.get("amount"), "asset": fr.get("asset")}
                    if "paper" not in rail.lower():
                        # Announce only locks NEWER than every non-paper lock
                        # already on record.  After the round-129 salvage,
                        # locks that were lost from seen_locks look new when the
                        # room is re-read; a first-appearance watch must not
                        # re-fire on them.  Real new locks always carry a newer
                        # ts than the newest one known, so nothing real is lost.
                        if not rec["ts"] or rec["ts"] > nonpaper_ts_floor:
                            new_nonpaper.append(rec)
                        st["nonpaper_locks"].append(rec)
                    elif rail.lower() != "paper":
                        st.setdefault("spoofed_paper_locks", []).append(rec)
        if "receipt" in kinds or "refund" in kinds:
            terminal.add(room)

    # 3. Offer-side aspiration. Counted for the record, and now ALSO watched for
    #    vocabulary we have never seen. Round 21 found the gap the hard way: this
    #    watch only ever read the `rails` array of LOCK frames, so when `x402`
    #    first appeared in offers on 2026-09-02T20:27Z, and while 513 of 715
    #    offers were denominated asset=FLOP, it stayed silent. A rail carrying
    #    value will be advertised in an offer before it is ever locked.
    offer_rails = collections.Counter()
    offer_assets = collections.Counter()
    for o in offers:
        for r in o.get("rails", []) or []:
            offer_rails[str(r)] += 1
        if o.get("asset") is not None:
            offer_assets[str(o["asset"])] += 1

    known_rails = set(st.get("known_offer_rails") or [])
    known_assets = set(st.get("known_offer_assets") or [])
    new_rails = sorted(set(offer_rails) - known_rails) if known_rails else []
    new_assets = sorted(set(offer_assets) - known_assets) if known_assets else []
    st["known_offer_rails"] = sorted(set(offer_rails) | known_rails)
    st["known_offer_assets"] = sorted(set(offer_assets) | known_assets)

    # 3b. Well-formedness of the OFFER side (added 2026-09-03, round 22).
    #     An accept references an offer through accept.ref -> offer.id, so an
    #     offer with no id can never be accepted no matter what it advertises.
    #     One DID posted 32 such offers at 1,000,000 FLOP each inside 77 minutes,
    #     8.5% of all value advertised on the tape, and this watch said nothing
    #     because it only ever counted rails and assets. Track the id-less
    #     senders and fire when a new one appears or an existing one grows.
    idless = collections.Counter()
    idless_value = collections.Counter()
    for m, o in offer_msgs:
        if o.get("id"):
            continue
        # Round 82 correction. This used to read o.get("from") off the tclk1
        # FRAME. Stub offers carry only {amount,asset,nonce,type} and have no
        # `from` of their own, so every one of them collapsed into a single
        # bucket named '?' and the watch could not name a sender. The envelope
        # always carries `from`; attribute from there.
        who = str(m.get("from") or "?")
        idless[who] += 1
        try:
            idless_value[who] += int(o.get("amount") or 0)
        except (TypeError, ValueError):
            pass
    # Self-declared test senders are honest about it; do not page on them.
    FLOODER_MIN = 5
    flooders = {w: n for w, n in idless.items()
                if n >= FLOODER_MIN and "test" not in w.lower() and "diag" not in w.lower()}
    known_flooders = dict(st.get("idless_flooders") or {})
    new_flooders = {w: n for w, n in flooders.items() if n > known_flooders.get(w, 0)}
    # Round 82 correction. The old merge was
    #   {w: max(n, known[w]) for w, n in list(flooders) + list(known)}
    # which is order-dependent: for a key in BOTH dicts the `known` entry comes
    # last and yields max(known, known) = known, silently discarding growth. A
    # high-water mark that can go DOWN is not a high-water mark.
    merged = dict(known_flooders)
    for w, n in flooders.items():
        merged[w] = max(n, merged.get(w, 0))
    st["idless_flooders"] = merged
    st["idless_offers_total"] = sum(idless.values())

    # 3c. Structural cohort census (added 2026-09-11, round 82).
    #     The per-sender threshold above is defeated by construction when the
    #     flood uses ONE THROWAWAY KEY PER OFFER. On 2026-09-10T17:29-18:21Z,
    #     2,558 no-id offers arrived from 2,558 distinct DIDs, one each - 67% of
    #     offers and 99.6% of advertised value - and `flooders` named nobody at
    #     any threshold. Sender volume cannot see this. Two statistics that can,
    #     neither of which depends on sender identity:
    #       - the exact JSON key-set, which is the emitting generator's shape
    #       - the dispersion of arrivals: N independent senders give Poisson
    #         gaps (CV -> 1.0); one paced emitter is UNDER-dispersed (CV < 1).
    #     Full analysis and the frozen fixture: guide/stub_offer_census.py.
    cohorts = collections.defaultdict(list)
    for m, o in offer_msgs:
        cohorts[",".join(sorted(o.keys()))].append(m)
    fleet_key, fleet_msgs = None, []
    for k, msgs in cohorts.items():
        if "id" not in k.split(",") and len(msgs) > len(fleet_msgs):
            fleet_key, fleet_msgs = k, msgs
    fleet = None
    if len(fleet_msgs) >= STUB_COHORT_MIN:
        senders = len(set(x.get("from") for x in fleet_msgs))
        cv = _gap_cv([x.get("ts") for x in fleet_msgs])
        fleet = {"keys": fleet_key, "offers": len(fleet_msgs), "senders": senders,
                 "cv": cv, "share_of_offers": round(len(fleet_msgs) / max(1, len(offers)), 4)}
    st["stub_fleet"] = fleet

    st["terminal_rooms"] = sorted(terminal)
    st["last"] = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "offers": len(offers), "accepts": len(accepts), "contracts": len(contracts),
        "rooms_read": rooms_read, "errors": errors,
        "locks_seen_total": len(seen), "lock_rails": dict(rail_on_locks),
        "offer_rails": dict(offer_rails),
        "offer_assets": dict(offer_assets),
        "nonpaper_total": len(st["nonpaper_locks"]),
        "idless_offers": sum(idless.values()),
        "idless_flooders": flooders,
        "stub_fleet": fleet,
    }
    save_state(st)
    log("offers=%d accepts=%d rooms_read=%d err=%d locks=%d rails=%s new_nonpaper=%d" % (
        len(offers), len(accepts), rooms_read, errors, len(seen), dict(rail_on_locks), len(new_nonpaper)))

    # 4. Fire once per new value-bearing lock. This is the event the whole watch exists for.
    for rec in new_nonpaper:
        notify("found",
               "tclk/1 に価値レールのLOCKが初めて出現: rail=%s" % rec["rail"],
               "契約 %s / 支払人 %s / %s %s / %s。これまで22/22のロックは全て rail=paper だった。" % (
                   str(rec["contract"])[:18], str(rec["from"])[-12:], rec.get("amount"), rec.get("asset"), rec["ts"]),
               "4.4秒即時リビールが「価値ゼロの遊び」から「対価なしの奪取」に変わる瞬間。"
               "次のFlopAgent回で lock→reveal 間隔を再計測し、カタログ39種目として公開する。",
               ORIGIN + "/r/" + rec["room"])

    # 4b. Fire when a one-key-per-offer fleet is on the tape. Threshold is on
    #     the COHORT, not on any sender, because each sender contributes one
    #     offer. Re-fires only when the fleet grows by half again, so a standing
    #     flood does not page every 15 minutes.
    prev = st.get("stub_fleet_reported") or 0
    if fleet and fleet["offers"] >= max(STUB_COHORT_MIN, int(prev * 1.5)):
        st["stub_fleet_reported"] = fleet["offers"]
        cvtxt = "CV=%s" % fleet["cv"] if fleet["cv"] is not None else "CV n/a"
        notify("found",
               "tclk/1 に1鍵1オファーのSybil艦隊: %d件を%d DIDが1件ずつ" % (
                   fleet["offers"], fleet["senders"]),
               "オファーの%.0f%%が同一キーセット {%s} で `id` 無し ― accept.ref→offer.id が"
               "解決できないので構造的に受諾不能。到着間隔 %s(独立送信ならPoissonでCV≈1.0)。"
               % (100 * fleet["share_of_offers"], fleet["keys"], cvtxt),
               "1送信者あたりの件数はどの閾値でも0件しか名指しできない(各DIDが1件)。"
               "検出はキーセットと到着分散に移す。guide/stub_offer_census.py で再現可能。",
               ORIGIN + "/r/tclk-offers")

    # 5. Fire once when an offer advertises a rail or an asset we have never seen.
    #    This is the early warning the lock-side trigger cannot give: an offer
    #    naming a new rail precedes any lock on it.
    if new_rails or new_assets:
        notify("found",
               "tclk/1 のオファーに未知の%s: %s" % (
                   "レール" if new_rails else "資産", ", ".join(new_rails + new_assets)),
               "オファー %d 件を走査。レール内訳 %s / 資産内訳 %s。ロック側は依然 %s。" % (
                   len(offers), dict(offer_rails), dict(offer_assets), dict(rail_on_locks)),
               "価値レールは必ずロックより先にオファーで名乗る。掲示と決済の差を次の回で突き合わせる。",
               ORIGIN + "/r/tclk-offers")

    # 6. Fire when a DID floods offers that carry no protocol id. These cannot
    #    be accepted by anyone, so they inflate apparent commerce volume without
    #    ever transacting - catalogued as pattern 43.
    if new_flooders:
        who = max(new_flooders, key=new_flooders.get)
        notify("found",
               "tclk/1 に受けようのないオファーの連投: %d件 (%s)" % (new_flooders[who], who[-12:]),
               "オファー %d 件中 id 無しが %d 件、うち %s が %d 件で計 %s を提示。"
               "accept は accept.ref -> offer.id で参照するので id が無ければ誰も指せない。" % (
                   len(offers), sum(idless.values()), who[-12:],
                   new_flooders[who], idless_value.get(who, 0)),
               "商取引量として数えると実態を水増しする。手口43として記録済み。"
               "検出は tclk_offer_wellformed.py で再現できる。",
               ORIGIN + "/r/tclk-offers")

    # Re-persist. Round 82: `stub_fleet_reported` is set in section 4b, which
    # runs AFTER the dump above, so without this second write the de-duplication
    # marker never survived the process and the fleet alert re-fired every run.
    save_state(st)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Round 129: this used to exit 0, so schtasks showed Last Result 0 for
        # every pass of a crash loop that had already lasted 20 minutes.
        log("FAIL %s" % str(e)[:200])
        sys.exit(1)
