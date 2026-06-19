"""
AMM Repricing Test — Audit #3
Samples all 12 Up/Down markets every 10s for 60 minutes (360 rounds).
Writes raw data to amm_reprice_raw.json and progress log to amm_reprice.log.
Generates AMM_REPRICE_REPORT.md when complete.
"""

import json, time, math, statistics, sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

RAW_FILE    = Path("amm_reprice_raw.json")
LOG_FILE    = Path("amm_reprice.log")
REPORT_FILE = Path("AMM_REPRICE_REPORT.md")

ROUNDS    = 360
INTERVAL  = 10   # seconds

MARKETS = [
    {"label": "BTC/5m",  "token": "92885420129369730059795062238827273043088588732358965459884500701045519479211"},
    {"label": "BTC/15m", "token": "43884444897312384541482674525610037343619831552955404334877222241501252768349"},
    {"label": "BTC/1H",  "token": "80976720722390001809263682690786409213099461845205278823377310106319104574061"},
    {"label": "ETH/5m",  "token": "63949987561261150626992266712523825252017435691544291949870760650783285202551"},
    {"label": "ETH/15m", "token": "6759336286533467258201293359421515967775360249081039598078044458660887583220"},
    {"label": "ETH/1H",  "token": "51708225764774039125634154196931082902516127534149531820014099656073141485977"},
    {"label": "SOL/5m",  "token": "60725051504990458975131235111990760702195757480715306342405337179893302635008"},
    {"label": "SOL/15m", "token": "74657480812110424261682102565264704284491138737617912298111038968064334828798"},
    {"label": "SOL/1H",  "token": "101343165381051665705907913919336108057571692552150539049545330722698094867929"},
    {"label": "XRP/5m",  "token": "10666894998884025139593901295804858016619021134662733101423969159301761093165"},
    {"label": "XRP/15m", "token": "112169833204574670391878990287818169070906257894007675920047145356833546732436"},
    {"label": "XRP/1H",  "token": "57102854029231900626818858982094364113149453514735448775969318409659953912917"},
]

CLOB_URL = "https://clob.polymarket.com/book?token_id={token_id}"

def fetch_book(token_id: str) -> dict:
    url = CLOB_URL.format(token_id=token_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def parse_book(data: dict) -> dict:
    bids = data.get("bids", [])   # ascending  → best bid last
    asks = data.get("asks", [])   # descending → best ask last

    def to_pairs(levels):
        out = []
        for lvl in levels:
            try:
                out.append((float(lvl["price"]), float(lvl["size"])))
            except Exception:
                pass
        return out

    bid_pairs = to_pairs(bids)
    ask_pairs = to_pairs(asks)

    best_bid = bid_pairs[-1][0] if bid_pairs else None
    best_ask = ask_pairs[-1][0] if ask_pairs else None
    mid      = round((best_bid + best_ask) / 2, 6) if (best_bid is not None and best_ask is not None) else None
    spread   = round(best_ask - best_bid, 6)        if (best_bid is not None and best_ask is not None) else None

    # top-5 levels (closest to mid)
    top5_bids = bid_pairs[-5:]  # last 5 = highest prices
    top5_asks = ask_pairs[-5:]  # last 5 = lowest  prices

    top5_bid_depth = round(sum(s for _, s in top5_bids), 4)
    top5_ask_depth = round(sum(s for _, s in top5_asks), 4)

    return {
        "best_bid":       best_bid,
        "best_ask":       best_ask,
        "mid":            mid,
        "spread":         spread,
        "top5_bid_depth": top5_bid_depth,
        "top5_ask_depth": top5_ask_depth,
        "top5_bid_levels": top5_bids,
        "top5_ask_levels": top5_asks,
        "bid_levels":      len(bid_pairs),
        "ask_levels":      len(ask_pairs),
    }

def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a") as f:
        f.write(line + "\n")

def run_collection():
    log(f"=== AMM Reprice Audit start — {ROUNDS} rounds × {INTERVAL}s ===")
    started_at = datetime.now(timezone.utc).isoformat()

    all_rounds = []
    prev = {m["label"]: None for m in MARKETS}

    for rnd in range(ROUNDS):
        ts = time.time()
        snap_ok = 0
        round_data = []

        for mkt in MARKETS:
            rec = {
                "round":  rnd,
                "ts":     ts,
                "label":  mkt["label"],
                "token":  mkt["token"],
                "error":  None,
            }
            try:
                raw  = fetch_book(mkt["token"])
                parsed = parse_book(raw)
                rec.update(parsed)

                # detect repricing vs previous round
                p = prev[mkt["label"]]
                if p is not None:
                    bid_changed   = parsed["best_bid"]  != p["best_bid"]
                    ask_changed   = parsed["best_ask"]  != p["best_ask"]
                    mid_changed   = parsed["mid"]       != p["mid"]
                    spread_chgd   = parsed["spread"]    != p["spread"]
                    depth_bid_chg = parsed["top5_bid_depth"] != p["top5_bid_depth"]
                    depth_ask_chg = parsed["top5_ask_depth"] != p["top5_ask_depth"]
                    any_change = bid_changed or ask_changed or mid_changed or depth_bid_chg or depth_ask_chg
                else:
                    bid_changed = ask_changed = mid_changed = spread_chgd = False
                    depth_bid_chg = depth_ask_chg = any_change = False

                rec["bid_changed"]    = bid_changed
                rec["ask_changed"]    = ask_changed
                rec["mid_changed"]    = mid_changed
                rec["spread_changed"] = spread_chgd
                rec["depth_bid_chg"]  = depth_bid_chg
                rec["depth_ask_chg"]  = depth_ask_chg
                rec["any_change"]     = any_change

                if any_change:
                    bid_delta = round(parsed["best_bid"] - p["best_bid"], 6) if bid_changed else 0.0
                    ask_delta = round(parsed["best_ask"] - p["best_ask"], 6) if ask_changed else 0.0
                    mid_delta = round(parsed["mid"]      - p["mid"],      6) if mid_changed else 0.0
                    rec["bid_delta"] = bid_delta
                    rec["ask_delta"] = ask_delta
                    rec["mid_delta"] = mid_delta
                else:
                    rec["bid_delta"] = 0.0
                    rec["ask_delta"] = 0.0
                    rec["mid_delta"] = 0.0

                prev[mkt["label"]] = parsed
                snap_ok += 1

            except Exception as e:
                rec["error"] = str(e)

            round_data.append(rec)

        all_rounds.extend(round_data)

        changed_labels = [r["label"] for r in round_data if r.get("any_change")]
        change_info = f" REPRICE: {changed_labels}" if changed_labels else ""
        log(f"  Round {rnd:>3}: {snap_ok}/12 ok{change_info}")

        # flush raw data every 10 rounds
        if rnd % 10 == 0 or rnd == ROUNDS - 1:
            RAW_FILE.write_text(json.dumps(all_rounds, indent=2))

        elapsed = time.time() - ts
        sleep_for = max(0, INTERVAL - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)

    RAW_FILE.write_text(json.dumps(all_rounds, indent=2))
    log(f"Collection complete — {len(all_rounds)} records stored")
    generate_report(all_rounds, started_at)

# ─── Report generation ─────────────────────────────────────────────────────────

def generate_report(records, started_at):
    valid = [r for r in records if not r.get("error")]
    labels = [m["label"] for m in MARKETS]

    first_ts = min(r["ts"] for r in valid)
    last_ts  = max(r["ts"] for r in valid)
    span_s   = last_ts - first_ts
    n_rounds = max(r["round"] for r in valid) + 1

    ended_at = datetime.now(timezone.utc).isoformat()

    lines = []
    A = lines.append

    A("# AMM_REPRICE_REPORT.md")
    A("")
    A(f"**Collection started:** {started_at}")
    A(f"**Collection ended:**   {ended_at}")
    A(f"**Observation span:**   {span_s/60:.1f} minutes ({span_s:.0f} s)")
    A(f"**Sampling interval:**  10 s")
    A(f"**Rounds completed:**   {n_rounds}")
    A(f"**Valid snapshots:**    {len(valid)} ({len(records)-len(valid)} failed)")
    A(f"**Markets audited:**    {len(labels)}")
    A("")
    A("---")
    A("")
    A("## 1. Methodology")
    A("")
    A("**Source:** `GET https://clob.polymarket.com/book?token_id={yes_token_id}`  ")
    A("**Repricing event:** any round where `best_bid`, `best_ask`, or `mid` differs from the previous round.  ")
    A("**Depth shift:** any round where `top5_bid_depth` or `top5_ask_depth` changes.  ")
    A("**Simultaneous repricing:** two or more markets repricing within the same 10-second sampling round.  ")
    A("")
    A("---")
    A("")

    # ─── per-market analysis ────────────────────────────────────────────────
    A("## 2. Per-Market Results")
    A("")

    market_summary = {}

    for label in labels:
        recs = sorted([r for r in valid if r["label"] == label], key=lambda r: r["round"])
        reprice_events  = [r for r in recs if r.get("any_change")]
        bid_events      = [r for r in recs if r.get("bid_changed")]
        ask_events      = [r for r in recs if r.get("ask_changed")]
        mid_events      = [r for r in recs if r.get("mid_changed")]
        depth_events    = [r for r in recs if r.get("depth_bid_chg") or r.get("depth_ask_chg")]

        # price range
        bids = [r["best_bid"] for r in recs if r.get("best_bid") is not None]
        asks = [r["best_ask"] for r in recs if r.get("best_ask") is not None]
        mids = [r["mid"]      for r in recs if r.get("mid")      is not None]
        spreads = [r["spread"] for r in recs if r.get("spread")  is not None]

        market_summary[label] = {
            "n": len(recs),
            "reprice_count": len(reprice_events),
            "bid_events": len(bid_events),
            "ask_events": len(ask_events),
            "mid_events": len(mid_events),
            "depth_events": len(depth_events),
            "reprice_rounds": [r["round"] for r in reprice_events],
            "reprice_ts": [r["ts"] for r in reprice_events],
        }

        has_reprice = len(reprice_events) > 0
        A(f"### {label}  (n={len(recs)}, reprice events: {len(reprice_events)})")
        A("")

        if bids:
            bid_min, bid_max = min(bids), max(bids)
            ask_min, ask_max = min(asks), max(asks)
            mid_min, mid_max = min(mids), max(mids)
            spd_min, spd_max = min(spreads), max(spreads)
            A(f"| Metric | Min | Max | Unique values |")
            A(f"|---|---|---|---|")
            A(f"| `best_bid`  | {bid_min:.4f} | {bid_max:.4f} | {sorted(set(bids))} |")
            A(f"| `best_ask`  | {ask_min:.4f} | {ask_max:.4f} | {sorted(set(asks))} |")
            A(f"| `mid`       | {mid_min:.4f} | {mid_max:.4f} | {sorted(set(mids))} |")
            A(f"| `spread`    | {spd_min:.4f} | {spd_max:.4f} | {sorted(set(spreads))} |")
            A("")

        if not has_reprice:
            A("**→ ZERO REPRICING EVENTS** — price and depth completely static for the full observation window.")
        else:
            A(f"**→ {len(reprice_events)} REPRICING EVENT(S) DETECTED**")
            A("")
            A("| Round | Timestamp (UTC) | bid Δ | ask Δ | mid Δ | depth bid chg | depth ask chg |")
            A("|---|---|---|---|---|---|---|")
            for e in reprice_events:
                ts_str = datetime.fromtimestamp(e["ts"], tz=timezone.utc).strftime("%H:%M:%S")
                A(f"| {e['round']:>3} | {ts_str} | {e.get('bid_delta',0):+.6f} | {e.get('ask_delta',0):+.6f} | {e.get('mid_delta',0):+.6f} | {'YES' if e.get('depth_bid_chg') else 'no'} | {'YES' if e.get('depth_ask_chg') else 'no'} |")

            # magnitude summary
            mid_deltas = [abs(e.get("mid_delta", 0)) for e in mid_events]
            if mid_deltas:
                A("")
                A(f"Mid-price move magnitude: min={min(mid_deltas):.6f}, max={max(mid_deltas):.6f}, mean={statistics.mean(mid_deltas):.6f}")

        A("")

    A("---")
    A("")

    # ─── Section A & B ────────────────────────────────────────────────────────
    A("## 3. Markets Summary")
    A("")
    zero_reprice  = [l for l in labels if market_summary[l]["reprice_count"] == 0]
    has_reprice_l = [l for l in labels if market_summary[l]["reprice_count"] > 0]

    A("### A. Markets with ZERO repricing events")
    A("")
    if zero_reprice:
        for l in zero_reprice:
            A(f"- {l}")
    else:
        A("*(none — all markets had at least one repricing event)*")
    A("")

    A("### B. Markets with at least one repricing event")
    A("")
    if has_reprice_l:
        for l in has_reprice_l:
            cnt = market_summary[l]["reprice_count"]
            A(f"- {l} ({cnt} event{'s' if cnt>1 else ''})")
    else:
        A("*(none — all markets were completely static)*")
    A("")

    # ─── Section C: all reprice timestamps ────────────────────────────────────
    A("### C. All repricing events (chronological)")
    A("")
    all_events = []
    for label in labels:
        recs_sorted = sorted([r for r in valid if r["label"] == label], key=lambda r: r["round"])
        for r in recs_sorted:
            if r.get("any_change"):
                all_events.append((r["ts"], label, r["round"],
                                   r.get("bid_delta",0), r.get("ask_delta",0), r.get("mid_delta",0),
                                   r.get("depth_bid_chg",False), r.get("depth_ask_chg",False)))

    if not all_events:
        A("*(no repricing events detected during the observation window)*")
    else:
        all_events.sort()
        A("| Timestamp (UTC) | Market | Round | bid Δ | ask Δ | mid Δ | depth chg |")
        A("|---|---|---|---|---|---|---|")
        for ts, label, rnd, bd, ad, md, dbc, dac in all_events:
            ts_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
            depth_flag = "bid+ask" if (dbc and dac) else ("bid" if dbc else ("ask" if dac else "no"))
            A(f"| {ts_str} | {label} | {rnd:>3} | {bd:+.6f} | {ad:+.6f} | {md:+.6f} | {depth_flag} |")
    A("")

    # ─── Section D: magnitude ─────────────────────────────────────────────────
    A("### D. Magnitude of changes")
    A("")
    bid_deltas_all = [abs(r.get("bid_delta",0)) for r in valid if r.get("bid_changed")]
    ask_deltas_all = [abs(r.get("ask_delta",0)) for r in valid if r.get("ask_changed")]
    mid_deltas_all = [abs(r.get("mid_delta",0)) for r in valid if r.get("mid_changed")]

    if bid_deltas_all:
        A(f"- **Best-bid moves:** n={len(bid_deltas_all)}, min={min(bid_deltas_all):.6f}, max={max(bid_deltas_all):.6f}, mean={statistics.mean(bid_deltas_all):.6f}")
    else:
        A("- **Best-bid moves:** none observed")

    if ask_deltas_all:
        A(f"- **Best-ask moves:** n={len(ask_deltas_all)}, min={min(ask_deltas_all):.6f}, max={max(ask_deltas_all):.6f}, mean={statistics.mean(ask_deltas_all):.6f}")
    else:
        A("- **Best-ask moves:** none observed")

    if mid_deltas_all:
        A(f"- **Mid-price moves:** n={len(mid_deltas_all)}, min={min(mid_deltas_all):.6f}, max={max(mid_deltas_all):.6f}, mean={statistics.mean(mid_deltas_all):.6f}")
    else:
        A("- **Mid-price moves:** none observed")
    A("")

    # ─── Section E: simultaneity ───────────────────────────────────────────────
    A("### E. Simultaneous repricing across markets")
    A("")
    # group events by round
    from collections import defaultdict
    by_round = defaultdict(list)
    for ts, label, rnd, *_ in all_events:
        by_round[rnd].append(label)

    simultaneous = {r: mkts for r, mkts in by_round.items() if len(mkts) >= 2}

    if not simultaneous:
        A("No simultaneous repricing detected — no single round had 2+ markets repricing at the same time.")
    else:
        A(f"**{len(simultaneous)} round(s)** had 2 or more markets repricing simultaneously:")
        A("")
        A("| Round | Markets repriced simultaneously |")
        A("|---|---|")
        for rnd in sorted(simultaneous):
            A(f"| {rnd} | {', '.join(simultaneous[rnd])} |")
    A("")
    A("---")
    A("")

    # ─── Final conclusion ──────────────────────────────────────────────────────
    A("## 4. Final Conclusion")
    A("")

    total_reprice = sum(s["reprice_count"] for s in market_summary.values())
    markets_with_reprice = len(has_reprice_l)

    A(f"**Total repricing events observed:** {total_reprice} (across {markets_with_reprice}/12 markets)  ")
    A(f"**Observation window:** {span_s/60:.1f} minutes  ")
    A(f"**Expected events if AMM is static:** 0  ")
    A("")

    if total_reprice == 0:
        A("### Verdict: AMM IS COMPLETELY STATIC")
        A("")
        A("No bid price, ask price, mid price, or depth change was observed in any of the 12 markets")
        A(f"across the full {span_s/60:.0f}-minute observation window ({n_rounds} samples × 10s interval).")
        A("")
        A("**Interpretation:**")
        A("- The AMM has not reacted to any external price feed during the observation period.")
        A("- No periodic rebalancing occurred.")
        A("- No order flow (human or bot) adjusted the book structure.")
        A("- The books are frozen at their initial AMM-seeded state.")
        A("- This is consistent with a **pure initialization phase**: the AMM was seeded once at launch")
        A("  and has received no updates. All 12 markets remain at their seed configuration.")
        A("")
        A("**Trading signal implication:**  ")
        A("Until at least one repricing event is observed, these markets carry no intra-period price")
        A("information. The bid/ask spread reflects AMM seed parameters only, not market consensus.")
    elif total_reprice > 0 and len(simultaneous) > 0:
        A("### Verdict: AMM IS PERIODICALLY REBALANCED (SYNCHRONIZED)")
        A("")
        A(f"Repricing occurred in {markets_with_reprice}/12 markets.")
        A(f"Simultaneous repricing across multiple markets in {len(simultaneous)} round(s) suggests")
        A("a centralized rebalancing trigger — likely a shared price feed or cron-based update.")
    elif total_reprice > 0:
        A("### Verdict: AMM IS PERIODICALLY REBALANCED (UNSYNCHRONIZED)")
        A("")
        A(f"Repricing occurred in {markets_with_reprice}/12 markets, but no simultaneous multi-market")
        A("events were detected. Markets may reprice independently based on individual triggers.")

    A("")
    A("*All data collected live from the Polymarket CLOB API. No synthetic or cached values used.*")

    REPORT_FILE.write_text("\n".join(lines))
    log(f"Report written → {REPORT_FILE}  ({len(lines)} lines)")

if __name__ == "__main__":
    run_collection()
