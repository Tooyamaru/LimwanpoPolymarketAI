"""
Chunked depth collector — run repeatedly.
Each invocation collects ROUNDS_PER_RUN rounds at INTERVAL_S seconds.
Data accumulates in depth_audit_raw.json between runs.
Pass --report to generate the final report without collecting.
"""
import asyncio
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

MARKETS = [
    {"label": "BTC/5m",  "yes": "92885420129369730059795062238827273043088588732358965459884500701045519479211"},
    {"label": "BTC/15m", "yes": "43884444897312384541482674525610037343619831552955404334877222241501252768349"},
    {"label": "BTC/1H",  "yes": "80976720722390001809263682690786409213099461845205278823377310106319104574061"},
    {"label": "ETH/5m",  "yes": "63949987561261150626992266712523825252017435691544291949870760650783285202551"},
    {"label": "ETH/15m", "yes": "6759336286533467258201293359421515967775360249081039598078044458660887583220"},
    {"label": "ETH/1H",  "yes": "51708225764774039125634154196931082902516127534149531820014099656073141485977"},
    {"label": "SOL/5m",  "yes": "60725051504990458975131235111990760702195757480715306342405337179893302635008"},
    {"label": "SOL/15m", "yes": "74657480812110424261682102565264704284491138737617912298111038968064334828798"},
    {"label": "SOL/1H",  "yes": "101343165381051665705907913919336108057571692552150539049545330722698094867929"},
    {"label": "XRP/5m",  "yes": "10666894998884025139593901295804858016619021134662733101423969159301761093165"},
    {"label": "XRP/15m", "yes": "112169833204574670391878990287818169070906257894007675920047145356833546732436"},
    {"label": "XRP/1H",  "yes": "57102854029231900626818858982094364113149453514735448775969318409659953912917"},
]

CLOB_BASE = "https://clob.polymarket.com"
RAW_OUT = Path("depth_audit_raw.json")
REPORT_OUT = Path("DEPTH_VARIATION_AUDIT.md")
ROUNDS_PER_RUN = 11
INTERVAL_S = 10

METRICS_LIST = [
    "depth_imbalance_top5",
    "depth_imbalance_top10",
    "total_bid_size",
    "total_ask_size",
    "bid_pressure_pct",
    "number_of_bid_levels",
    "number_of_ask_levels",
]
CV_THRESHOLD = 1.0  # CV% considered meaningful


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(bids, asks):
    def parse(levels):
        return [(float(l["price"]), float(l["size"])) for l in levels]

    bl = parse(bids)
    al = parse(asks)
    n_bid, n_ask = len(bl), len(al)

    def sz(levels): return sum(s for _, s in levels)

    top5b = sz(bl[-5:] if n_bid >= 5 else bl)
    top5a = sz(al[-5:] if n_ask >= 5 else al)
    top10b = sz(bl[-10:] if n_bid >= 10 else bl)
    top10a = sz(al[-10:] if n_ask >= 10 else al)
    tb, ta = sz(bl), sz(al)

    def imb(b, a): return (b - a) / (b + a) if (b + a) > 0 else 0.0

    bp = tb / (tb + ta) * 100 if (tb + ta) > 0 else 50.0

    best_bid = bl[-1][0] if bl else None
    best_ask = al[-1][0] if al else None
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
    spread = (best_ask - best_bid) if (best_bid and best_ask) else None

    return {
        "depth_imbalance_top5":  round(imb(top5b, top5a), 6),
        "depth_imbalance_top10": round(imb(top10b, top10a), 6),
        "total_bid_size":        round(tb, 2),
        "total_ask_size":        round(ta, 2),
        "bid_pressure_pct":      round(bp, 4),
        "number_of_bid_levels":  n_bid,
        "number_of_ask_levels":  n_ask,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread": spread,
    }


async def fetch_book(client, token_id):
    try:
        r = await client.get(f"{CLOB_BASE}/book", params={"token_id": token_id}, timeout=8)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


async def collect_round(client, round_idx):
    ts = time.time()
    books = await asyncio.gather(*[fetch_book(client, m["yes"]) for m in MARKETS])
    records = []
    for market, book in zip(MARKETS, books):
        if book is None:
            records.append({"label": market["label"], "round": round_idx, "ts": ts, "error": True})
            continue
        m = compute_metrics(book.get("bids", []), book.get("asks", []))
        records.append({"label": market["label"], "round": round_idx, "ts": ts, **m})
    return records


# ── Stats ─────────────────────────────────────────────────────────────────────

def stats_for(values):
    if len(values) < 2:
        return {"n": len(values), "min": None, "max": None, "mean": None, "stddev": None, "cv_pct": None}
    mn, mx = min(values), max(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    cv = (std / abs(mean) * 100) if mean != 0 else (0.0 if std == 0 else float("inf"))
    return {"n": len(values), "min": round(mn, 6), "max": round(mx, 6),
            "mean": round(mean, 6), "stddev": round(std, 6), "cv_pct": round(cv, 4)}


def analyze(all_records):
    from collections import defaultdict
    by_market = defaultdict(lambda: defaultdict(list))
    for rec in all_records:
        if rec.get("error"):
            continue
        for m in METRICS_LIST:
            if m in rec and rec[m] is not None:
                by_market[rec["label"]][m].append(rec[m])
    return {label: {m: stats_for(vals) for m, vals in ms.items()} for label, ms in by_market.items()}


def classify_market(mstats):
    cvs = [s["cv_pct"] for s in mstats.values() if s.get("cv_pct") is not None]
    if not cvs or max(cvs) < CV_THRESHOLD:
        return "DEPTH STATIC"
    size_cv = max(
        mstats.get("total_bid_size", {}).get("cv_pct", 0) or 0,
        mstats.get("total_ask_size", {}).get("cv_pct", 0) or 0,
    )
    imbal_cv = max(
        mstats.get("depth_imbalance_top5", {}).get("cv_pct", 0) or 0,
        mstats.get("depth_imbalance_top10", {}).get("cv_pct", 0) or 0,
    )
    if size_cv >= CV_THRESHOLD and imbal_cv >= CV_THRESHOLD:
        return "DEPTH CHANGING WITH STRUCTURE"
    return "DEPTH CHANGING BUT RANDOM"


def overall_classification(per_market):
    classes = [classify_market(s) for s in per_market.values()]
    if all(c == "DEPTH STATIC" for c in classes):
        return "DEPTH STATIC"
    if any(c == "DEPTH CHANGING WITH STRUCTURE" for c in classes):
        return "DEPTH CHANGING WITH STRUCTURE"
    return "DEPTH CHANGING BUT RANDOM"


def f(v, d=4):
    return "—" if v is None else f"{v:.{d}f}"


# ── Report ────────────────────────────────────────────────────────────────────

def write_report(all_records, per_market, started_at):
    valid = [r for r in all_records if not r.get("error")]
    err   = [r for r in all_records if r.get("error")]
    rounds_seen = (max(r["round"] for r in valid) + 1) if valid else 0
    span_sec = (max(r["ts"] for r in valid) - min(r["ts"] for r in valid)) if len(valid) > 1 else 0

    L = []
    W = L.append

    W("# DEPTH_VARIATION_AUDIT.md")
    W("")
    W(f"**Collection started:** {started_at} UTC")
    W(f"**Collection ended:**   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    W(f"**Observation span:**   {span_sec/60:.1f} minutes ({span_sec:.0f} s)")
    W(f"**Sampling interval:**  {INTERVAL_S} s")
    W(f"**Rounds completed:**   {rounds_seen}")
    W(f"**Valid snapshots:**    {len(valid)} ({len(err)} failed)")
    W(f"**Markets audited:**    {len(MARKETS)}")
    W("")
    W("---")
    W("")
    W("## 1. Methodology")
    W("")
    W("**Source:** `GET https://clob.polymarket.com/book?token_id={yes_token_id}`  ")
    W("**Sampling:** One YES-token order book snapshot per market per round.  ")
    W("**Book convention:** bids sorted ascending (best bid = last element); asks sorted descending (best ask = last element).  ")
    W("")
    W("**Metric definitions:**")
    W("")
    W("| Metric | Formula |")
    W("|---|---|")
    W("| `depth_imbalance_top5` | `(Σbid_size_top5 − Σask_size_top5) / (Σbid_size_top5 + Σask_size_top5)` — range [−1, +1] |")
    W("| `depth_imbalance_top10` | Same using top-10 levels |")
    W("| `total_bid_size` | Sum of all resting bid sizes (USDC notional) |")
    W("| `total_ask_size` | Sum of all resting ask sizes (USDC notional) |")
    W("| `bid_pressure_pct` | `total_bid / (total_bid + total_ask) × 100` |")
    W("| `number_of_bid_levels` | Count of distinct bid price levels |")
    W("| `number_of_ask_levels` | Count of distinct ask price levels |")
    W("")
    W("**Variation threshold:** CV% > 1.0% classified as meaningful.  ")
    W("**Classification rule:**")
    W("- `DEPTH STATIC`: all metric CV% ≤ 1.0%")
    W("- `DEPTH CHANGING WITH STRUCTURE`: size CV% > 1.0% AND imbalance CV% > 1.0% (directional shift)")
    W("- `DEPTH CHANGING BUT RANDOM`: size varies but imbalance does not (symmetric noise)")
    W("")
    W("---")
    W("")
    W("## 2. Per-Market Results")
    W("")

    classifications = {}
    for mkt in MARKETS:
        label = mkt["label"]
        ms = per_market.get(label, {})
        n = next((s["n"] for s in ms.values() if s and s.get("n")), 0)
        cls = classify_market(ms)
        classifications[label] = cls

        # mid price range from raw data
        mids = [r["mid"] for r in valid if r["label"] == label and r.get("mid") is not None]
        mid_range = f"{min(mids):.4f} – {max(mids):.4f}" if mids else "—"

        W(f"### {label}  (n={n}, mid price range: {mid_range})")
        W("")
        W("| Metric | Min | Max | Mean | Std Dev | CV% |")
        W("|---|---|---|---|---|---|")
        for metric in METRICS_LIST:
            s = ms.get(metric, {})
            if not s:
                W(f"| `{metric}` | — | — | — | — | — |")
            else:
                W(f"| `{metric}` | {f(s['min'])} | {f(s['max'])} | {f(s['mean'])} | {f(s['stddev'])} | {f(s['cv_pct'],2)}% |")
        W("")
        W(f"**→ {cls}**")
        W("")

    W("---")
    W("")
    W("## 3. Cross-Market Comparison")
    W("")
    W("### 3.1  CV% distribution by metric (all 12 markets)")
    W("")
    W("| Metric | Min CV% | Max CV% | Mean CV% | Markets with CV% > 1.0 |")
    W("|---|---|---|---|---|")
    for metric in METRICS_LIST:
        cvs = [per_market.get(lb, {}).get(metric, {}).get("cv_pct")
               for lb in [m["label"] for m in MARKETS]]
        cvs = [v for v in cvs if v is not None]
        if not cvs:
            W(f"| `{metric}` | — | — | — | — |")
        else:
            above = sum(1 for v in cvs if v > CV_THRESHOLD)
            W(f"| `{metric}` | {f(min(cvs),2)}% | {f(max(cvs),2)}% | {f(statistics.mean(cvs),2)}% | {above}/12 |")
    W("")

    W("### 3.2  Per-market classification summary")
    W("")
    W("| Market | Max CV% | Best-bid mean | Total-bid mean | Classification |")
    W("|---|---|---|---|---|")
    for label in [m["label"] for m in MARKETS]:
        ms = per_market.get(label, {})
        cvs_all = [s["cv_pct"] for s in ms.values() if s and s.get("cv_pct") is not None]
        max_cv = max(cvs_all) if cvs_all else 0.0
        bid_mean = ms.get("total_bid_size", {}).get("mean")
        best_bid_vals = [r["best_bid"] for r in valid if r["label"] == label and r.get("best_bid") is not None]
        bb_mean = statistics.mean(best_bid_vals) if best_bid_vals else None
        W(f"| {label} | {f(max_cv,2)}% | {f(bb_mean,4)} | {f(bid_mean,0)} | {classifications[label]} |")
    W("")

    W("### 3.3  Statistical distinctness (total bid size)")
    W("")
    means_tb = {}
    for label in [m["label"] for m in MARKETS]:
        v = per_market.get(label, {}).get("total_bid_size", {}).get("mean")
        if v is not None:
            means_tb[label] = v

    if len(means_tb) >= 2:
        gm = statistics.mean(means_tb.values())
        gs = statistics.stdev(means_tb.values())
        W(f"Global mean total bid size: {gm:.0f} USDC  |  Std dev across markets: {gs:.0f} USDC")
        W("")
        W("| Market | Mean bid size | Z-score | Statistically distinct? |")
        W("|---|---|---|---|")
        for label, mv in sorted(means_tb.items()):
            z = (mv - gm) / gs if gs > 0 else 0.0
            flag = "**YES** (|z| > 2)" if abs(z) > 2 else "no"
            W(f"| {label} | {mv:.0f} | {z:+.2f} | {flag} |")
        W("")
    else:
        W("Insufficient data for cross-market z-score comparison.")
        W("")

    W("---")
    W("")
    W("## 4. Temporal Structure Analysis")
    W("")
    # Check if there's a trend in total_bid_size for any market (first-half vs second-half mean)
    W("First-half vs second-half mean comparison (total_bid_size) — detects slow drift:")
    W("")
    W("| Market | First-half mean | Second-half mean | Δ% | Drift present? |")
    W("|---|---|---|---|---|")
    for label in [m["label"] for m in MARKETS]:
        vals = [(r["round"], r["total_bid_size"])
                for r in valid if r["label"] == label and "total_bid_size" in r]
        vals.sort()
        if len(vals) < 4:
            W(f"| {label} | — | — | — | insufficient data |")
            continue
        half = len(vals) // 2
        m1 = statistics.mean(v for _, v in vals[:half])
        m2 = statistics.mean(v for _, v in vals[half:])
        delta_pct = (m2 - m1) / m1 * 100 if m1 != 0 else 0.0
        drift = "YES" if abs(delta_pct) > 2.0 else "no"
        W(f"| {label} | {m1:.0f} | {m2:.0f} | {delta_pct:+.2f}% | {drift} |")
    W("")

    # Imbalance series: any market with imbalance CV% > 0? Flag direction
    W("Imbalance (top-5) range across rounds — detects directional pressure:")
    W("")
    W("| Market | Min imbalance | Max imbalance | Range | Any non-zero? |")
    W("|---|---|---|---|---|")
    for label in [m["label"] for m in MARKETS]:
        vals = [r["depth_imbalance_top5"]
                for r in valid if r["label"] == label and "depth_imbalance_top5" in r]
        if not vals:
            W(f"| {label} | — | — | — | — |")
            continue
        mn, mx = min(vals), max(vals)
        rng = mx - mn
        nonzero = "YES" if any(abs(v) > 0.0001 for v in vals) else "no"
        W(f"| {label} | {mn:+.6f} | {mx:+.6f} | {rng:.6f} | {nonzero} |")
    W("")

    W("---")
    W("")
    W("## 5. Conclusion")
    W("")
    overall = overall_classification(per_market)
    W(f"### Overall: {overall}")
    W("")
    cls_counts = {}
    for c in classifications.values():
        cls_counts[c] = cls_counts.get(c, 0) + 1
    for cls, cnt in sorted(cls_counts.items()):
        W(f"- **{cls}:** {cnt}/12 markets")
    W("")

    all_cvs = [s["cv_pct"] for ms in per_market.values()
               for s in ms.values() if s and s.get("cv_pct") is not None]

    if all_cvs:
        W(f"**All-metric CV% range across all markets:** {min(all_cvs):.4f}% – {max(all_cvs):.4f}%")
        W(f"**All-metric mean CV%:** {statistics.mean(all_cvs):.4f}%")
        W("")

    # Summary evidence paragraphs — filled in based on actual findings
    size_cvs = [per_market.get(lb, {}).get(m, {}).get("cv_pct")
                for lb in [mk["label"] for mk in MARKETS]
                for m in ["total_bid_size", "total_ask_size"]
                if per_market.get(lb, {}).get(m, {}).get("cv_pct") is not None]
    imbal_cvs = [per_market.get(lb, {}).get(m, {}).get("cv_pct")
                 for lb in [mk["label"] for mk in MARKETS]
                 for m in ["depth_imbalance_top5", "depth_imbalance_top10"]
                 if per_market.get(lb, {}).get(m, {}).get("cv_pct") is not None]
    level_cvs = [per_market.get(lb, {}).get(m, {}).get("cv_pct")
                 for lb in [mk["label"] for mk in MARKETS]
                 for m in ["number_of_bid_levels", "number_of_ask_levels"]
                 if per_market.get(lb, {}).get(m, {}).get("cv_pct") is not None]

    W("**Evidence:**")
    W("")
    if size_cvs:
        m_sz = statistics.mean(size_cvs)
        W(f"- Total bid/ask size CV%: mean {m_sz:.4f}%, max {max(size_cvs):.4f}%  ")
        if m_sz < CV_THRESHOLD:
            W(f"  → Book size is stable. Neither side adds or removes liquidity meaningfully over the observation window.")
        else:
            W(f"  → Book size varies beyond the {CV_THRESHOLD}% threshold.")
    if imbal_cvs:
        m_im = statistics.mean(imbal_cvs)
        W(f"- Depth imbalance CV%: mean {m_im:.4f}%, max {max(imbal_cvs):.4f}%  ")
        if m_im < CV_THRESHOLD:
            W(f"  → No directional pressure detected. Both sides move together if they move at all.")
        else:
            W(f"  → Directional imbalance detected beyond {CV_THRESHOLD}% threshold.")
    if level_cvs:
        m_lv = statistics.mean(level_cvs)
        W(f"- Level count CV%: mean {m_lv:.4f}%, max {max(level_cvs):.4f}%  ")
        if m_lv < CV_THRESHOLD:
            W(f"  → Number of resting price levels is constant throughout the observation window.")
        else:
            W(f"  → Number of price levels varies.")

    if overall == "DEPTH STATIC":
        W("")
        W("All seven metrics are statistically stable across all 12 markets for the full observation period.")
        W("The order book is structurally inert: depth, imbalance, and level count do not vary in any")
        W("market despite the constant mid-price. This is consistent with a fully automated market maker")
        W("maintaining a fixed symmetric book with no external order flow.")
    elif overall == "DEPTH CHANGING WITH STRUCTURE":
        W("")
        W("Depth changes with directional structure: book size and imbalance both vary, indicating")
        W("real order placement or cancellation activity with directional bias.")
    else:
        W("")
        W("Depth changes but without directional structure: book size varies while imbalance remains")
        W("near zero, consistent with symmetric AMM rebalancing rather than directional order flow.")

    W("")
    W("*All data collected live from the Polymarket CLOB API. No synthetic or cached values used.*")

    REPORT_OUT.write_text("\n".join(L))
    print(f"Report written → {REPORT_OUT}  ({len(L)} lines)", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

async def collect_chunk(offset):
    existing = []
    if RAW_OUT.exists():
        existing = json.loads(RAW_OUT.read_text())
    rounds_done = (max(r["round"] for r in existing if not r.get("error")) + 1) if existing else 0
    new_records = []
    async with httpx.AsyncClient() as client:
        for i in range(ROUNDS_PER_RUN):
            t0 = time.monotonic()
            r_idx = rounds_done + i
            recs = await collect_round(client, r_idx)
            new_records.extend(recs)
            ok = sum(1 for r in recs if not r.get("error"))
            print(f"  Round {r_idx+1}: {ok}/12 ok", flush=True)
            elapsed = time.monotonic() - t0
            sleep_s = max(0, INTERVAL_S - elapsed)
            if i < ROUNDS_PER_RUN - 1:
                await asyncio.sleep(sleep_s)
    all_records = existing + new_records
    RAW_OUT.write_text(json.dumps(all_records))
    total_rounds = (max(r["round"] for r in all_records if not r.get("error")) + 1) if all_records else 0
    print(f"Total rounds stored: {total_rounds}", flush=True)
    return all_records


def main():
    if "--report" in sys.argv:
        all_records = json.loads(RAW_OUT.read_text()) if RAW_OUT.exists() else []
    else:
        all_records = asyncio.run(collect_chunk(0))
    per_market = analyze(all_records)
    started_at = (datetime.fromtimestamp(min(r["ts"] for r in all_records if not r.get("error")), tz=timezone.utc)
                  .strftime("%Y-%m-%d %H:%M:%S") if all_records else "unknown")
    write_report(all_records, per_market, started_at)


if __name__ == "__main__":
    main()
