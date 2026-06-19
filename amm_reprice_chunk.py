"""
AMM Repricing Test — Audit #3  (chunk runner)
Each invocation appends 11 rounds to amm_reprice_raw.json (10s per round = ~110s/call).
Run 33 times to reach 360 rounds (60-minute observation window).
Final report written after every chunk to AMM_REPRICE_REPORT.md.
"""

import json, time, statistics
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
import urllib.request

RAW_FILE    = Path("amm_reprice_raw.json")
REPORT_FILE = Path("AMM_REPRICE_REPORT.md")

ROUNDS_PER_CHUNK = 11
INTERVAL         = 10   # seconds
TARGET_ROUNDS    = 360  # 60 minutes

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

# ─── helpers ────────────────────────────────────────────────────────────────────

def fetch_book(token_id: str) -> dict:
    url = CLOB_URL.format(token_id=token_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def parse_book(data: dict) -> dict:
    bids = data.get("bids", [])
    asks = data.get("asks", [])

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

    top5_bids = bid_pairs[-5:]
    top5_asks = ask_pairs[-5:]

    return {
        "best_bid":        best_bid,
        "best_ask":        best_ask,
        "mid":             mid,
        "spread":          spread,
        "top5_bid_depth":  round(sum(s for _, s in top5_bids), 4),
        "top5_ask_depth":  round(sum(s for _, s in top5_asks), 4),
        "top5_bid_levels": [(p, s) for p, s in top5_bids],
        "top5_ask_levels": [(p, s) for p, s in top5_asks],
        "bid_levels":      len(bid_pairs),
        "ask_levels":      len(ask_pairs),
    }

# ─── load existing data ──────────────────────────────────────────────────────────

existing = []
if RAW_FILE.exists():
    existing = json.loads(RAW_FILE.read_text())

rounds_done = (max(r["round"] for r in existing) + 1) if existing else 0

if rounds_done >= TARGET_ROUNDS:
    print(f"Already at {rounds_done} rounds — target {TARGET_ROUNDS} reached.")
    raise SystemExit(0)

# build last-seen state per market (needed for change detection)
prev = {m["label"]: None for m in MARKETS}
for rec in sorted(existing, key=lambda r: r["round"]):
    if not rec.get("error"):
        prev[rec["label"]] = {
            "best_bid":        rec.get("best_bid"),
            "best_ask":        rec.get("best_ask"),
            "mid":             rec.get("mid"),
            "spread":          rec.get("spread"),
            "top5_bid_depth":  rec.get("top5_bid_depth"),
            "top5_ask_depth":  rec.get("top5_ask_depth"),
        }

# record collection start time (first chunk only)
if rounds_done == 0:
    meta_started = datetime.now(timezone.utc).isoformat()
    # store in a sidecar
    Path("amm_reprice_meta.json").write_text(json.dumps({"started_at": meta_started}))

# ─── collect chunk ───────────────────────────────────────────────────────────────

new_records = []
chunk_end   = min(rounds_done + ROUNDS_PER_CHUNK, TARGET_ROUNDS)

for rnd in range(rounds_done, chunk_end):
    ts      = time.time()
    snap_ok = 0
    round_data = []

    for mkt in MARKETS:
        rec = {
            "round": rnd,
            "ts":    ts,
            "label": mkt["label"],
            "error": None,
        }
        try:
            raw    = fetch_book(mkt["token"])
            parsed = parse_book(raw)
            rec.update(parsed)

            p = prev[mkt["label"]]
            if p is not None:
                bid_changed   = parsed["best_bid"]       != p["best_bid"]
                ask_changed   = parsed["best_ask"]       != p["best_ask"]
                mid_changed   = parsed["mid"]            != p["mid"]
                spread_chgd   = parsed["spread"]         != p["spread"]
                depth_bid_chg = parsed["top5_bid_depth"] != p["top5_bid_depth"]
                depth_ask_chg = parsed["top5_ask_depth"] != p["top5_ask_depth"]
                any_change    = bid_changed or ask_changed or mid_changed or depth_bid_chg or depth_ask_chg
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

            if any_change and p:
                rec["bid_delta"] = round(parsed["best_bid"] - p["best_bid"], 6) if bid_changed else 0.0
                rec["ask_delta"] = round(parsed["best_ask"] - p["best_ask"], 6) if ask_changed else 0.0
                rec["mid_delta"] = round(parsed["mid"]      - p["mid"],      6) if mid_changed else 0.0
            else:
                rec["bid_delta"] = 0.0
                rec["ask_delta"] = 0.0
                rec["mid_delta"] = 0.0

            prev[mkt["label"]] = {
                "best_bid":       parsed["best_bid"],
                "best_ask":       parsed["best_ask"],
                "mid":            parsed["mid"],
                "spread":         parsed["spread"],
                "top5_bid_depth": parsed["top5_bid_depth"],
                "top5_ask_depth": parsed["top5_ask_depth"],
            }
            snap_ok += 1

        except Exception as e:
            rec["error"] = str(e)

        round_data.append(rec)

    changed = [r["label"] for r in round_data if r.get("any_change")]
    flag    = f"  *** REPRICE: {changed} ***" if changed else ""
    print(f"  Round {rnd:>3}: {snap_ok}/12 ok{flag}")

    new_records.extend(round_data)

    elapsed   = time.time() - ts
    sleep_for = max(0, INTERVAL - elapsed)
    if sleep_for > 0:
        time.sleep(sleep_for)

# ─── persist ─────────────────────────────────────────────────────────────────────

all_records = existing + new_records
RAW_FILE.write_text(json.dumps(all_records, indent=2))
total_rounds = max(r["round"] for r in all_records) + 1
print(f"Total rounds stored: {total_rounds}")

# ─── generate report ─────────────────────────────────────────────────────────────

valid   = [r for r in all_records if not r.get("error")]
labels  = [m["label"] for m in MARKETS]
first_ts = min(r["ts"] for r in valid)
last_ts  = max(r["ts"] for r in valid)
span_s   = last_ts - first_ts
n_rounds = total_rounds

meta = json.loads(Path("amm_reprice_meta.json").read_text()) if Path("amm_reprice_meta.json").exists() else {}
started_at = meta.get("started_at", datetime.fromtimestamp(first_ts, tz=timezone.utc).isoformat())
ended_at   = datetime.now(timezone.utc).isoformat()

lines = []
A = lines.append

A("# AMM_REPRICE_REPORT.md")
A("")
A(f"**Collection started:** {started_at}")
A(f"**Collection ended:**   {ended_at}  *(in progress — {n_rounds}/{TARGET_ROUNDS} rounds)*" if n_rounds < TARGET_ROUNDS else f"**Collection ended:**   {ended_at}")
A(f"**Observation span:**   {span_s/60:.1f} minutes ({span_s:.0f} s)")
A(f"**Sampling interval:**  10 s")
A(f"**Rounds completed:**   {n_rounds} / {TARGET_ROUNDS}")
A(f"**Valid snapshots:**    {len(valid)} ({len(all_records)-len(valid)} failed)")
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
A("## 2. Per-Market Results")
A("")

market_summary = {}

for label in labels:
    recs = sorted([r for r in valid if r["label"] == label], key=lambda r: r["round"])
    reprice_events = [r for r in recs if r.get("any_change")]
    bid_events     = [r for r in recs if r.get("bid_changed")]
    ask_events     = [r for r in recs if r.get("ask_changed")]
    mid_events     = [r for r in recs if r.get("mid_changed")]
    depth_events   = [r for r in recs if r.get("depth_bid_chg") or r.get("depth_ask_chg")]

    bids    = [r["best_bid"] for r in recs if r.get("best_bid") is not None]
    asks    = [r["best_ask"] for r in recs if r.get("best_ask") is not None]
    mids    = [r["mid"]      for r in recs if r.get("mid")      is not None]
    spreads = [r["spread"]   for r in recs if r.get("spread")   is not None]

    market_summary[label] = {
        "n": len(recs),
        "reprice_count":  len(reprice_events),
        "bid_events":     len(bid_events),
        "ask_events":     len(ask_events),
        "mid_events":     len(mid_events),
        "depth_events":   len(depth_events),
        "reprice_rounds": [r["round"] for r in reprice_events],
        "reprice_ts":     [r["ts"]    for r in reprice_events],
    }

    A(f"### {label}  (n={len(recs)}, reprice events: {len(reprice_events)})")
    A("")

    if bids:
        A(f"| Metric | Min | Max | Unique values |")
        A(f"|---|---|---|---|")
        A(f"| `best_bid`  | {min(bids):.4f} | {max(bids):.4f} | {sorted(set(bids))} |")
        A(f"| `best_ask`  | {min(asks):.4f} | {max(asks):.4f} | {sorted(set(asks))} |")
        A(f"| `mid`       | {min(mids):.4f} | {max(mids):.4f} | {sorted(set(mids))} |")
        A(f"| `spread`    | {min(spreads):.4f} | {max(spreads):.4f} | {sorted(set(spreads))} |")
        A("")

    if not reprice_events:
        A("**→ ZERO REPRICING EVENTS**")
    else:
        A(f"**→ {len(reprice_events)} REPRICING EVENT(S) DETECTED**")
        A("")
        A("| Round | Timestamp (UTC) | bid Δ | ask Δ | mid Δ | depth_bid chg | depth_ask chg |")
        A("|---|---|---|---|---|---|---|")
        for e in reprice_events:
            ts_str = datetime.fromtimestamp(e["ts"], tz=timezone.utc).strftime("%H:%M:%S")
            A(f"| {e['round']:>3} | {ts_str} | {e.get('bid_delta',0):+.6f} | {e.get('ask_delta',0):+.6f} | {e.get('mid_delta',0):+.6f} | {'YES' if e.get('depth_bid_chg') else 'no'} | {'YES' if e.get('depth_ask_chg') else 'no'} |")
        mid_deltas = [abs(e.get("mid_delta", 0)) for e in mid_events]
        if mid_deltas:
            A("")
            A(f"Mid-price move magnitude — min: {min(mid_deltas):.6f}, max: {max(mid_deltas):.6f}, mean: {statistics.mean(mid_deltas):.6f}")
    A("")

A("---")
A("")
A("## 3. Markets Summary")
A("")

zero_reprice   = [l for l in labels if market_summary[l]["reprice_count"] == 0]
has_reprice_l  = [l for l in labels if market_summary[l]["reprice_count"] > 0]

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

A("### C. All repricing events (chronological)")
A("")
all_events = []
for label in labels:
    for r in sorted([x for x in valid if x["label"] == label], key=lambda x: x["round"]):
        if r.get("any_change"):
            all_events.append((r["ts"], label, r["round"],
                               r.get("bid_delta",0), r.get("ask_delta",0), r.get("mid_delta",0),
                               r.get("depth_bid_chg",False), r.get("depth_ask_chg",False)))

if not all_events:
    A("*(no repricing events detected so far)*")
else:
    all_events.sort()
    A("| Timestamp (UTC) | Market | Round | bid Δ | ask Δ | mid Δ | depth chg |")
    A("|---|---|---|---|---|---|---|")
    for ts, label, rnd, bd, ad, md, dbc, dac in all_events:
        ts_str     = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
        depth_flag = "bid+ask" if (dbc and dac) else ("bid" if dbc else ("ask" if dac else "no"))
        A(f"| {ts_str} | {label} | {rnd:>3} | {bd:+.6f} | {ad:+.6f} | {md:+.6f} | {depth_flag} |")
A("")

A("### D. Magnitude of changes")
A("")
bid_deltas_all = [abs(r.get("bid_delta",0)) for r in valid if r.get("bid_changed")]
ask_deltas_all = [abs(r.get("ask_delta",0)) for r in valid if r.get("ask_changed")]
mid_deltas_all = [abs(r.get("mid_delta",0)) for r in valid if r.get("mid_changed")]

def mag_line(name, vals):
    if vals:
        return f"- **{name}:** n={len(vals)}, min={min(vals):.6f}, max={max(vals):.6f}, mean={statistics.mean(vals):.6f}"
    return f"- **{name}:** none observed"

A(mag_line("Best-bid moves", bid_deltas_all))
A(mag_line("Best-ask moves", ask_deltas_all))
A(mag_line("Mid-price moves", mid_deltas_all))
A("")

A("### E. Simultaneous repricing across markets")
A("")
by_round = defaultdict(list)
for ts, label, rnd, *_ in all_events:
    by_round[rnd].append(label)
simultaneous = {r: mkts for r, mkts in by_round.items() if len(mkts) >= 2}

if not simultaneous:
    A("No simultaneous repricing detected — no single round had 2+ markets repricing at the same time.")
else:
    A(f"**{len(simultaneous)} round(s)** had 2+ markets repricing simultaneously:")
    A("")
    A("| Round | Timestamp (UTC) | Markets repriced simultaneously |")
    A("|---|---|---|")
    for rnd in sorted(simultaneous):
        ts_rnd = next(ts for ts, lb, r, *_ in all_events if r == rnd)
        ts_str = datetime.fromtimestamp(ts_rnd, tz=timezone.utc).strftime("%H:%M:%S")
        A(f"| {rnd} | {ts_str} | {', '.join(simultaneous[rnd])} |")
A("")
A("---")
A("")
A("## 4. Final Conclusion")
A("")

total_reprice      = sum(s["reprice_count"] for s in market_summary.values())
markets_with_reprice = len(has_reprice_l)

A(f"**Total repricing events observed:** {total_reprice} (across {markets_with_reprice}/12 markets)  ")
A(f"**Observation window so far:** {span_s/60:.1f} minutes ({n_rounds}/{TARGET_ROUNDS} rounds complete)  ")
A("")

if n_rounds < TARGET_ROUNDS:
    A("*Collection in progress — final verdict pending completion.*")
elif total_reprice == 0:
    A("### Verdict: AMM IS COMPLETELY STATIC")
    A("")
    A(f"No bid price, ask price, mid price, or depth change was observed in any of the 12 markets")
    A(f"across the full 60-minute observation window ({n_rounds} rounds × 10s).")
    A("")
    A("**Interpretation:**")
    A("- The AMM has not reacted to any external price feed during the observation period.")
    A("- No periodic rebalancing occurred.")
    A("- No order flow adjusted the book structure.")
    A("- The books are frozen at their initial AMM-seeded state.")
    A("- Consistent with a **pure initialization phase**: the AMM was seeded once at launch")
    A("  and has received no updates. All 12 markets remain at their seed configuration.")
    A("")
    A("**Trading signal implication:**  ")
    A("Until at least one repricing event is observed, these markets carry no intra-period")
    A("price information. The bid/ask spread reflects AMM seed parameters only, not market consensus.")
elif simultaneous:
    A("### Verdict: AMM IS PERIODICALLY REBALANCED (SYNCHRONIZED)")
    A("")
    A(f"Repricing occurred in {markets_with_reprice}/12 markets.")
    A(f"Simultaneous repricing across {len(simultaneous)} round(s) strongly suggests a centralized")
    A("rebalancing trigger — a shared oracle price feed or scheduled batch update.")
else:
    A("### Verdict: AMM IS PERIODICALLY REBALANCED (UNSYNCHRONIZED)")
    A("")
    A(f"Repricing occurred in {markets_with_reprice}/12 markets with no detected simultaneity.")
    A("Markets may reprice independently based on individual order-flow triggers.")

A("")
A("*All data collected live from the Polymarket CLOB API. No synthetic or cached values used.*")

REPORT_FILE.write_text("\n".join(lines))
print(f"Report written → {REPORT_FILE}  ({len(lines)} lines)")
