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
import json, os, sys, time, urllib.request, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "notify"))
import tclk1
from discord import notify

STATE = os.path.join(HERE, "tclk_rail_state.json")
LOG = os.path.join(HERE, "tclk_rail_watch.log")
ORIGIN = "https://technocore.chat"
MAX_ROOMS = 300


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


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"seen_locks": {}, "nonpaper_locks": [], "terminal_rooms": [], "last": {}}


def main():
    st = load_state()
    seen = st["seen_locks"]
    terminal = set(st["terminal_rooms"])

    # 1. The rendezvous ring: offers + accepts.
    raw = get(ORIGIN + "/r/tclk-offers/export", timeout=60)
    offers, accepts = [], []
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
                    if rail.lower() != "paper":
                        rec = {"contract": fr.get("contract"), "from": m.get("from"),
                               "rail": rail, "ts": m.get("ts"), "room": room,
                               "amount": fr.get("amount"), "asset": fr.get("asset")}
                        new_nonpaper.append(rec)
                        st["nonpaper_locks"].append(rec)
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
    for o in offers:
        if o.get("id"):
            continue
        who = str(o.get("from") or "?")
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
    st["idless_flooders"] = {w: max(n, known_flooders.get(w, 0)) for w, n in
                             list(flooders.items()) + list(known_flooders.items())}
    st["idless_offers_total"] = sum(idless.values())

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
    }
    json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1)
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
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("FAIL %s" % str(e)[:200])
        sys.exit(0)
