"""
Depth Variation Audit — 2-hour order book snapshot collector.
Runs 120 collection rounds (one per 60 s) for all 12 active markets.
Saves raw snapshots to depth_audit_raw.json, then computes all metrics
and writes DEPTH_VARIATION_AUDIT.md.
"""

import asyncio
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── Active markets ────────────────────────────────────────────────────────────
MARKETS = [
    {"label": "BTC/5m",  "yes": "92885420129369730059795062238827273043088588732358965459884500701045519479211", "no": "77617248722259045014584692134055454861491747782541581454071167750177614069174"},
    {"label": "BTC/15m", "yes": "43884444897312384541482674525610037343619831552955404334877222241501252768349", "no": "18322667448246504189358604588907745211513817225653340541860855872872702356386"},
    {"label": "BTC/1H",  "yes": "80976720722390001809263682690786409213099461845205278823377310106319104574061", "no": "21864334069718658326423203590976374768273659548163922461290564202308409924824"},
    {"label": "ETH/5m",  "yes": "63949987561261150626992266712523825252017435691544291949870760650783285202551", "no": "79467917997752407723398873052161710112284618653398744974923258719738080212554"},
    {"label": "ETH/15m", "yes": "6759336286533467258201293359421515967775360249081039598078044458660887583220",  "no": "92724753328442819016475870725066066206074414121531362506234596517446267421157"},
    {"label": "ETH/1H",  "yes": "51708225764774039125634154196931082902516127534149531820014099656073141485977", "no": "83149737151721530084074562172312285710093202622079667130102073253784105607976"},
    {"label": "SOL/5m",  "yes": "60725051504990458975131235111990760702195757480715306342405337179893302635008", "no": "30704786618078916787693189184617882038793577642813402253360322538559449324779"},
    {"label": "SOL/15m", "yes": "74657480812110424261682102565264704284491138737617912298111038968064334828798", "no": "71811935155307741100721267932281723660500257530264453572541002854867269078600"},
    {"label": "SOL/1H",  "yes": "101343165381051665705907913919336108057571692552150539049545330722698094867929","no": "37103949939972568800172825537893436419623645329094151325405158842591877676103"},
    {"label": "XRP/5m",  "yes": "10666894998884025139593901295804858016619021134662733101423969159301761093165", "no": "51180577865972548180877147937709789597792418884328796854809210989399776295912"},
    {"label": "XRP/15m", "yes": "112169833204574670391878990287818169070906257894007675920047145356833546732436","no": "12641286949074382232485305693655110633718229515943621288607401160881077936163"},
    {"label": "XRP/1H",  "yes": "57102854029231900626818858982094364113149453514735448775969318409659953912917", "no": "68841425451941783011701378760810805013268781103739006434786524120704828377020"},
]

CLOB_BASE = "https://clob.polymarket.com"
ROUNDS = 120          # 120 × 60 s = 2 hours
INTERVAL_S = 60
RAW_OUT = Path("depth_audit_raw.json")
REPORT_OUT = Path("DEPTH_VARIATION_AUDIT.md")
LOG_OUT = Path("depth_audit_progress.log")


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_OUT.open("a") as f:
        f.write(line + "\n")


# ── Order book metrics ────────────────────────────────────────────────────────

def compute_metrics(bids: list, asks: list) -> dict:
    """
    bids: list of {"price": str, "size": str} — sorted ascending by price (best bid = last)
    asks: list of {"price": str, "size": str} — sorted descending by price (best ask = last)
    """
    def parse(levels):
        return [(float(l["price"]), float(l["size"])) for l in levels]

    bid_levels = parse(bids)  # asc: cheapest first, best bid last
    ask_levels = parse(asks)  # desc: most expensive first, best ask last

    n_bid = len(bid_levels)
    n_ask = len(ask_levels)

    # Best 5 and 10 levels (closest to mid)
    top5_bids = bid_levels[-5:]  if n_bid >= 5  else bid_levels
    top5_asks = ask_levels[-5:]  if n_ask >= 5  else ask_levels
    top10_bids = bid_levels[-10:] if n_bid >= 10 else bid_levels
    top10_asks = ask_levels[-10:] if n_ask >= 10 else ask_levels

    def size_sum(levels): return sum(s for _, s in levels)

    top5_bid_sz  = size_sum(top5_bids)
    top5_ask_sz  = size_sum(top5_asks)
    top10_bid_sz = size_sum(top10_bids)
    top10_ask_sz = size_sum(top10_asks)
    total_bid_sz = size_sum(bid_levels)
    total_ask_sz = size_sum(ask_levels)

    def imbalance(b, a):
        denom = b + a
        return (b - a) / denom if denom > 0 else 0.0

    bid_pressure_pct = (total_bid_sz / (total_bid_sz + total_ask_sz) * 100
                        if (total_bid_sz + total_ask_sz) > 0 else 50.0)

    # Best bid/ask prices
    best_bid = bid_levels[-1][0] if bid_levels else None
    best_ask = ask_levels[-1][0] if ask_levels else None
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
    spread = (best_ask - best_bid) if (best_bid and best_ask) else None

    return {
        "depth_imbalance_top5":  round(imbalance(top5_bid_sz, top5_ask_sz), 6),
        "depth_imbalance_top10": round(imbalance(top10_bid_sz, top10_ask_sz), 6),
        "total_bid_size":  round(total_bid_sz, 2),
        "total_ask_size":  round(total_ask_sz, 2),
        "bid_pressure_pct": round(bid_pressure_pct, 4),
        "number_of_bid_levels": n_bid,
        "number_of_ask_levels": n_ask,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread": spread,
    }


async def fetch_book(client: httpx.AsyncClient, token_id: str) -> list | None:
    try:
        r = await client.get(f"{CLOB_BASE}/book", params={"token_id": token_id}, timeout=10)
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


async def collect_round(client: httpx.AsyncClient, round_idx: int) -> list:
    ts = time.time()
    tasks = [fetch_book(client, m["yes"]) for m in MARKETS]
    books = await asyncio.gather(*tasks)
    records = []
    for market, book in zip(MARKETS, books):
        if book is None:
            records.append({"label": market["label"], "round": round_idx,
                            "ts": ts, "error": "fetch_failed"})
            continue
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        metrics = compute_metrics(bids, asks)
        records.append({"label": market["label"], "round": round_idx,
                        "ts": ts, **metrics})
    return records


# ── Statistics ────────────────────────────────────────────────────────────────

METRICS_TO_ANALYZE = [
    "depth_imbalance_top5",
    "depth_imbalance_top10",
    "total_bid_size",
    "total_ask_size",
    "bid_pressure_pct",
    "number_of_bid_levels",
    "number_of_ask_levels",
]


def stats_for(values: list[float]) -> dict:
    if len(values) < 2:
        return {"n": len(values), "min": None, "max": None,
                "mean": None, "stddev": None, "cv": None}
    mn = min(values)
    mx = max(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    cv = (std / abs(mean) * 100) if mean != 0 else (0.0 if std == 0 else float("inf"))
    return {
        "n": len(values),
        "min":    round(mn, 6),
        "max":    round(mx, 6),
        "mean":   round(mean, 6),
        "stddev": round(std, 6),
        "cv_pct": round(cv, 4),
    }


def analyze(all_records: list) -> dict:
    """Return per-market stats dict."""
    from collections import defaultdict
    by_market: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for rec in all_records:
        if "error" in rec:
            continue
        label = rec["label"]
        for m in METRICS_TO_ANALYZE:
            if m in rec and rec[m] is not None:
                by_market[label][m].append(rec[m])

    result = {}
    for label, metric_series in by_market.items():
        result[label] = {m: stats_for(vals) for m, vals in metric_series.items()}
    return result


# ── Report generation ─────────────────────────────────────────────────────────

CV_THRESHOLD_MEANINGFUL = 1.0  # CV% > 1.0 % considered meaningful variation


def classify_market(market_stats: dict) -> str:
    """DEPTH STATIC / DEPTH CHANGING BUT RANDOM / DEPTH CHANGING WITH STRUCTURE"""
    cvs = [s["cv_pct"] for m, s in market_stats.items() if s["cv_pct"] is not None]
    if not cvs:
        return "UNKNOWN"
    max_cv = max(cvs)
    mean_cv = statistics.mean(cvs)
    # "Structure" heuristic: total_bid_size and total_ask_size both vary but
    # imbalance does NOT (book grows/shrinks symmetrically) — or imbalance varies
    # alongside sizes (book shifts directionally).
    size_cv = max(
        market_stats.get("total_bid_size", {}).get("cv_pct", 0) or 0,
        market_stats.get("total_ask_size", {}).get("cv_pct", 0) or 0,
    )
    imbal_cv = max(
        market_stats.get("depth_imbalance_top5", {}).get("cv_pct", 0) or 0,
        market_stats.get("depth_imbalance_top10", {}).get("cv_pct", 0) or 0,
    )
    if mean_cv < CV_THRESHOLD_MEANINGFUL:
        return "DEPTH STATIC"
    # If sizes vary but imbalance does not (both sides move together): size
    # changes but no directional pressure → "CHANGING BUT RANDOM"
    # If imbalance also varies significantly → structured directional change
    if size_cv >= CV_THRESHOLD_MEANINGFUL and imbal_cv >= CV_THRESHOLD_MEANINGFUL:
        return "DEPTH CHANGING WITH STRUCTURE"
    return "DEPTH CHANGING BUT RANDOM"


def overall_classification(per_market: dict) -> str:
    classes = [classify_market(s) for s in per_market.values()]
    if all(c == "DEPTH STATIC" for c in classes):
        return "DEPTH STATIC"
    if any(c == "DEPTH CHANGING WITH STRUCTURE" for c in classes):
        return "DEPTH CHANGING WITH STRUCTURE"
    return "DEPTH CHANGING BUT RANDOM"


def fmt(v, decimals=4):
    if v is None:
        return "—"
    return f"{v:.{decimals}f}"


def write_report(all_records: list, per_market_stats: dict, started_at: str):
    total_records = len([r for r in all_records if "error" not in r])
    error_records = len([r for r in all_records if "error" in r])
    rounds_seen = max((r["round"] for r in all_records if "error" not in r), default=0) + 1

    lines = []
    A = lines.append

    A("# DEPTH_VARIATION_AUDIT.md")
    A("")
    A(f"**Collection period:** {started_at} UTC → {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    A(f"**Rounds completed:** {rounds_seen} of {ROUNDS} (interval: 60 s)")
    A(f"**Total snapshots:** {total_records} valid, {error_records} failed")
    A(f"**Markets audited:** {len(MARKETS)}")
    A("")
    A("---")
    A("")
    A("## 1. Methodology")
    A("")
    A("- Source: `GET https://clob.polymarket.com/book?token_id={yes_token_id}`")
    A("- One snapshot per market per 60-second round")
    A("- YES-token order book used for all metrics (bids sorted ascending, asks sorted descending per CLOB convention)")
    A("- Metrics computed from raw bid/ask arrays per snapshot")
    A("- `depth_imbalance = (bid_size − ask_size) / (bid_size + ask_size)` where +1 = pure bids, −1 = pure asks")
    A("- `bid_pressure_pct = total_bid_size / (total_bid_size + total_ask_size) × 100`")
    A("- CV threshold for 'meaningful variation': CV% > 1.0%")
    A("")
    A("---")
    A("")
    A("## 2. Per-Market Metric Statistics")
    A("")

    for label in [m["label"] for m in MARKETS]:
        mstats = per_market_stats.get(label, {})
        n = next((s["n"] for s in mstats.values() if s), 0)
        A(f"### {label} (n={n} snapshots)")
        A("")
        A("| Metric | Min | Max | Mean | Std Dev | CV% |")
        A("|---|---|---|---|---|---|")
        for metric in METRICS_TO_ANALYZE:
            s = mstats.get(metric, {})
            if not s:
                A(f"| {metric} | — | — | — | — | — |")
                continue
            A(f"| {metric} | {fmt(s['min'])} | {fmt(s['max'])} | {fmt(s['mean'])} | {fmt(s['stddev'])} | {fmt(s['cv_pct'], 2)}% |")
        A("")
        cls = classify_market(mstats)
        A(f"**Classification: {cls}**")
        A("")

    A("---")
    A("")
    A("## 3. Cross-Market Comparison")
    A("")
    A("### Mean CV% per metric across all 12 markets")
    A("")
    A("| Metric | Min CV% | Max CV% | Mean CV% | Markets with CV% > 1.0 |")
    A("|---|---|---|---|---|")
    for metric in METRICS_TO_ANALYZE:
        cvs = []
        for label in [m["label"] for m in MARKETS]:
            s = per_market_stats.get(label, {}).get(metric, {})
            if s and s.get("cv_pct") is not None:
                cvs.append(s["cv_pct"])
        if not cvs:
            A(f"| {metric} | — | — | — | — |")
            continue
        above = sum(1 for v in cvs if v > CV_THRESHOLD_MEANINGFUL)
        A(f"| {metric} | {fmt(min(cvs), 2)}% | {fmt(max(cvs), 2)}% | {fmt(statistics.mean(cvs), 2)}% | {above}/12 |")
    A("")

    A("### Per-market classification")
    A("")
    A("| Market | Max CV% | Classification |")
    A("|---|---|---|")
    classifications = {}
    for label in [m["label"] for m in MARKETS]:
        mstats = per_market_stats.get(label, {})
        cvs = [s["cv_pct"] for s in mstats.values() if s and s.get("cv_pct") is not None]
        max_cv = max(cvs) if cvs else 0.0
        cls = classify_market(mstats)
        classifications[label] = cls
        A(f"| {label} | {fmt(max_cv, 2)}% | {cls} |")
    A("")

    A("---")
    A("")
    A("## 4. Statistical Distinctness")
    A("")
    # Compare total_bid_size mean across markets to flag outliers
    means_by_market = {}
    for label in [m["label"] for m in MARKETS]:
        s = per_market_stats.get(label, {}).get("total_bid_size", {})
        if s and s.get("mean") is not None:
            means_by_market[label] = s["mean"]

    if len(means_by_market) >= 2:
        all_means = list(means_by_market.values())
        global_mean = statistics.mean(all_means)
        global_std = statistics.stdev(all_means) if len(all_means) > 1 else 0
        A(f"Total bid size across markets: global mean={fmt(global_mean, 0)}, stddev={fmt(global_std, 0)}")
        A("")
        A("| Market | Mean bid size | Z-score vs pool | Distinct? |")
        A("|---|---|---|---|")
        for label, mean_val in sorted(means_by_market.items()):
            z = (mean_val - global_mean) / global_std if global_std > 0 else 0
            distinct = "YES (|z|>2)" if abs(z) > 2 else "no"
            A(f"| {label} | {fmt(mean_val, 0)} | {fmt(z, 2)} | {distinct} |")
        A("")
    else:
        A("Insufficient data for cross-market comparison.")
        A("")

    A("---")
    A("")
    A("## 5. Overall Conclusion")
    A("")
    overall = overall_classification(per_market_stats)
    A(f"### {overall}")
    A("")

    # Count classifications
    cls_counts = {}
    for c in classifications.values():
        cls_counts[c] = cls_counts.get(c, 0) + 1

    for cls, count in sorted(cls_counts.items()):
        A(f"- **{cls}**: {count}/12 markets")
    A("")

    # Evidence summary
    all_cvs = []
    for label in [m["label"] for m in MARKETS]:
        mstats = per_market_stats.get(label, {})
        for s in mstats.values():
            if s and s.get("cv_pct") is not None:
                all_cvs.append(s["cv_pct"])

    if all_cvs:
        A(f"**All-metric CV% range:** {fmt(min(all_cvs), 4)}% – {fmt(max(all_cvs), 4)}%")
        A(f"**All-metric mean CV%:** {fmt(statistics.mean(all_cvs), 4)}%")
        A("")

    A("**Evidence basis:**")
    A("")

    # Determine the key findings
    size_cvs = []
    imbal_cvs = []
    levels_cvs = []
    for label in [m["label"] for m in MARKETS]:
        mstats = per_market_stats.get(label, {})
        for metric in ["total_bid_size", "total_ask_size"]:
            s = mstats.get(metric, {})
            if s and s.get("cv_pct") is not None:
                size_cvs.append(s["cv_pct"])
        for metric in ["depth_imbalance_top5", "depth_imbalance_top10"]:
            s = mstats.get(metric, {})
            if s and s.get("cv_pct") is not None:
                imbal_cvs.append(s["cv_pct"])
        for metric in ["number_of_bid_levels", "number_of_ask_levels"]:
            s = mstats.get(metric, {})
            if s and s.get("cv_pct") is not None:
                levels_cvs.append(s["cv_pct"])

    if size_cvs:
        A(f"- Total bid/ask size CV%: mean {fmt(statistics.mean(size_cvs), 4)}%, max {fmt(max(size_cvs), 4)}%")
    if imbal_cvs:
        A(f"- Depth imbalance CV%: mean {fmt(statistics.mean(imbal_cvs), 4)}%, max {fmt(max(imbal_cvs), 4)}%")
    if levels_cvs:
        A(f"- Level count CV%: mean {fmt(statistics.mean(levels_cvs), 4)}%, max {fmt(max(levels_cvs), 4)}%")

    A("")
    A("*All data collected live. No synthetic or cached values were used.*")

    REPORT_OUT.write_text("\n".join(lines))
    log(f"Report written to {REPORT_OUT}")


# ── Main loop ─────────────────────────────────────────────────────────────────

async def main():
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    log(f"Depth audit starting — {ROUNDS} rounds × {INTERVAL_S}s = {ROUNDS*INTERVAL_S//3600}h")
    log(f"Markets: {[m['label'] for m in MARKETS]}")

    all_records: list = []

    async with httpx.AsyncClient() as client:
        for i in range(ROUNDS):
            t0 = time.monotonic()
            log(f"Round {i+1}/{ROUNDS} collecting...")
            records = await collect_round(client, i)
            all_records.extend(records)

            # Save raw data every round
            RAW_OUT.write_text(json.dumps(all_records, indent=2))

            errors = sum(1 for r in records if "error" in r)
            ok = len(records) - errors
            log(f"  Round {i+1} done: {ok} ok, {errors} errors")

            # Write intermediate report every 10 rounds
            if (i + 1) % 10 == 0 or i == ROUNDS - 1:
                per_market = analyze(all_records)
                write_report(all_records, per_market, started_at)
                log(f"  Intermediate report written (round {i+1})")

            # Sleep for remainder of interval
            elapsed = time.monotonic() - t0
            sleep_for = max(0, INTERVAL_S - elapsed)
            if i < ROUNDS - 1:
                log(f"  Sleeping {sleep_for:.1f}s until next round")
                await asyncio.sleep(sleep_for)

    log("Collection complete. Writing final report...")
    per_market = analyze(all_records)
    write_report(all_records, per_market, started_at)
    log("Done.")


if __name__ == "__main__":
    asyncio.run(main())
