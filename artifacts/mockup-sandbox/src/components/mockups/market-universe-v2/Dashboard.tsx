import { useEffect, useRef, useState } from "react";

const C = {
  bg: "#03050A",
  panel: "#06090F",
  panel2: "#080c13",
  b1: "#0b1320",
  b2: "#111d2e",
  b3: "#1a2c40",
  ng: "#39FF14",
  nc: "#00E5FF",
  np: "#C000FF",
  nm: "#FF2D95",
  ny: "#FFE600",
  tw: "#dff0ff",
  tm: "#6b8fa8",
  td: "#3a5570",
  red: "#ff3355",
};

type Status = "WAIT" | "WATCH" | "READY" | "TRACKING" | "WIN" | "LOSS";
type Pos = "YES" | "NO" | "NONE";

interface MarketCard {
  asset: string;
  tf: string;
  countdown: string;
  resolveTime: string;
  targetPrice: string;
  currentPrice: string;
  prediction: "YES" | "NO";
  confidence: number;
  position: Pos;
  entries: number;
  capital: number;
  pnl: number | null;
  status: Status;
  isTarget?: boolean;
}

const MARKETS: MarketCard[] = [
  { asset: "BTC", tf: "5M",  countdown: "04:12", resolveTime: "14:55 UTC", targetPrice: "107,310", currentPrice: "107,182", prediction: "NO",  confidence: 89, position: "NO",   entries: 3, capital: 125, pnl: 8.6,  status: "TRACKING" },
  { asset: "BTC", tf: "15M", countdown: "11:42", resolveTime: "15:15 UTC", targetPrice: "107,310", currentPrice: "107,182", prediction: "YES", confidence: 72, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WATCH", isTarget: true },
  { asset: "BTC", tf: "1H",  countdown: "38:05", resolveTime: "16:00 UTC", targetPrice: "107,500", currentPrice: "107,182", prediction: "YES", confidence: 41, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WAIT" },
  { asset: "ETH", tf: "5M",  countdown: "02:47", resolveTime: "14:55 UTC", targetPrice: "3,520",   currentPrice: "3,487",   prediction: "NO",  confidence: 78, position: "NO",   entries: 2, capital: 75,  pnl: -3.2, status: "TRACKING" },
  { asset: "ETH", tf: "15M", countdown: "09:33", resolveTime: "15:15 UTC", targetPrice: "3,520",   currentPrice: "3,487",   prediction: "NO",  confidence: 63, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "READY" },
  { asset: "ETH", tf: "1H",  countdown: "41:18", resolveTime: "16:00 UTC", targetPrice: "3,550",   currentPrice: "3,487",   prediction: "YES", confidence: 34, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WAIT" },
  { asset: "SOL", tf: "5M",  countdown: "03:55", resolveTime: "14:55 UTC", targetPrice: "148.20",  currentPrice: "148.45",  prediction: "YES", confidence: 81, position: "YES",  entries: 4, capital: 200, pnl: 12.4, status: "TRACKING" },
  { asset: "SOL", tf: "15M", countdown: "10:21", resolveTime: "15:15 UTC", targetPrice: "148.20",  currentPrice: "148.45",  prediction: "YES", confidence: 55, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WATCH" },
  { asset: "SOL", tf: "1H",  countdown: "39:44", resolveTime: "16:00 UTC", targetPrice: "150.00",  currentPrice: "148.45",  prediction: "YES", confidence: 47, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WAIT" },
  { asset: "XRP", tf: "5M",  countdown: "01:30", resolveTime: "14:55 UTC", targetPrice: "0.5820",  currentPrice: "0.5791",  prediction: "NO",  confidence: 66, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "READY" },
  { asset: "XRP", tf: "15M", countdown: "08:50", resolveTime: "15:15 UTC", targetPrice: "0.5820",  currentPrice: "0.5791",  prediction: "NO",  confidence: 44, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WAIT" },
  { asset: "XRP", tf: "1H",  countdown: "37:10", resolveTime: "16:00 UTC", targetPrice: "0.5900",  currentPrice: "0.5791",  prediction: "YES", confidence: 29, position: "NONE", entries: 0, capital: 0,   pnl: null, status: "WAIT" },
];

const ASSET_ICONS: Record<string, string> = { BTC: "₿", ETH: "Ξ", SOL: "◎", XRP: "✕" };

function cardColors(m: MarketCard): { border: string; bg: string; glow: string } {
  if (m.isTarget) return { border: `1px solid rgba(0,229,255,.55)`, bg: "rgba(0,229,255,.04)", glow: "0 0 14px rgba(0,229,255,.2)" };
  if (m.position !== "NONE" && m.pnl !== null && m.pnl > 0) return { border: `1px solid rgba(57,255,20,.45)`, bg: "rgba(57,255,20,.04)", glow: "0 0 12px rgba(57,255,20,.15)" };
  if (m.position !== "NONE" && m.pnl !== null && m.pnl < 0) return { border: `1px solid rgba(255,51,85,.4)`, bg: "rgba(255,51,85,.04)", glow: "0 0 12px rgba(255,51,85,.12)" };
  if (m.status === "WATCH" || m.status === "READY") return { border: `1px solid rgba(255,230,0,.35)`, bg: "rgba(255,230,0,.025)", glow: "0 0 10px rgba(255,230,0,.1)" };
  return { border: `1px solid ${C.b2}`, bg: "rgba(0,0,0,.2)", glow: "none" };
}

function statusColor(s: Status): string {
  if (s === "TRACKING") return C.nc;
  if (s === "WIN") return C.ng;
  if (s === "LOSS") return C.red;
  if (s === "READY") return C.ng;
  if (s === "WATCH") return C.ny;
  return C.td;
}

function confColor(c: number): string {
  if (c >= 85) return C.ng;
  if (c >= 70) return "#22ee55";
  if (c >= 55) return C.nc;
  if (c >= 40) return C.ny;
  return C.td;
}

function assetAvgConf(asset: string): number {
  const cards = MARKETS.filter(m => m.asset === asset);
  return Math.round(cards.reduce((a, m) => a + m.confidence, 0) / cards.length);
}

function assetPositions(asset: string): number {
  return MARKETS.filter(m => m.asset === asset && m.position !== "NONE").length;
}

function assetCapital(asset: string): number {
  return MARKETS.filter(m => m.asset === asset).reduce((a, m) => a + m.capital, 0);
}

function Dot({ color, size = 6 }: { color: string; size?: number }) {
  return (
    <span style={{
      display: "inline-block", width: size, height: size, borderRadius: "50%",
      background: color, boxShadow: `0 0 6px ${color}`,
      flexShrink: 0
    }} />
  );
}

function PanelTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 7.5, letterSpacing: 3, color: C.tm, padding: "5px 12px 4px",
      borderBottom: `1px solid ${C.b1}`, textTransform: "uppercase",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      background: "linear-gradient(90deg,rgba(0,0,0,.25),transparent)",
      flexShrink: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{
          display: "inline-block", width: 2, height: 8, borderRadius: 1,
          background: `linear-gradient(180deg,${C.nc},rgba(0,229,255,.2))`,
          boxShadow: `0 0 6px ${C.nc}`,
        }} />
        {children}
      </div>
      {right && <span style={{ fontSize: 7, color: C.nc, letterSpacing: 1.5, opacity: .8 }}>{right}</span>}
    </div>
  );
}

function AssetHeader({ asset }: { asset: string }) {
  const conf = assetAvgConf(asset);
  const pos = assetPositions(asset);
  const cap = assetCapital(asset);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "4px 10px", background: `linear-gradient(90deg,rgba(0,229,255,.06),transparent)`,
      borderBottom: `1px solid rgba(0,229,255,.12)`,
      borderTop: `1px solid rgba(0,229,255,.08)`, flexShrink: 0,
    }}>
      <span style={{ fontSize: 11, fontWeight: "bold", color: C.nc, letterSpacing: 1, minWidth: 28 }}>
        {ASSET_ICONS[asset]} {asset}
      </span>
      <span style={{ color: C.td, fontSize: 8 }}>│</span>
      <span style={{ fontSize: 8, color: C.tm, letterSpacing: .5 }}>
        AI Conf <span style={{ color: confColor(conf), fontWeight: "bold" }}>{conf}%</span>
      </span>
      <span style={{ color: C.td, fontSize: 8 }}>│</span>
      <span style={{ fontSize: 8, color: C.tm, letterSpacing: .5 }}>
        Positions <span style={{ color: pos > 0 ? C.nc : C.td, fontWeight: "bold" }}>{pos}</span>
      </span>
      <span style={{ color: C.td, fontSize: 8 }}>│</span>
      <span style={{ fontSize: 8, color: C.tm, letterSpacing: .5 }}>
        Capital <span style={{ color: cap > 0 ? C.tw : C.td, fontWeight: "bold" }}>${cap}</span>
      </span>
    </div>
  );
}

function MarketCardComp({ m }: { m: MarketCard }) {
  const { border, bg, glow } = cardColors(m);
  const predColor = m.prediction === "YES" ? C.ng : C.nm;
  const posColor = m.position === "YES" ? C.ng : m.position === "NO" ? C.nm : C.td;
  const pnlColor = m.pnl === null ? C.td : m.pnl > 0 ? C.ng : C.red;
  const pnlStr = m.pnl === null ? "—" : m.pnl > 0 ? `+${m.pnl}%` : `${m.pnl}%`;

  return (
    <div style={{
      border, background: bg, boxShadow: glow,
      margin: "4px 8px", borderRadius: 2, padding: "7px 9px",
      position: "relative", flexShrink: 0,
      transition: "box-shadow .3s, border-color .3s",
    }}>
      {m.isTarget && (
        <div style={{
          position: "absolute", top: 0, right: 0,
          fontSize: 7, letterSpacing: 1, color: C.nc,
          background: "rgba(0,229,255,.12)", padding: "1px 5px",
          borderBottomLeftRadius: 2,
        }}>TARGET</div>
      )}

      {/* Header Row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 5 }}>
        <span style={{ fontSize: 10, fontWeight: "bold", color: C.tw, letterSpacing: 1 }}>
          {m.asset} • {m.tf}
        </span>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 14, fontWeight: "bold", color: C.nc, letterSpacing: 1, lineHeight: 1 }}>{m.countdown}</div>
          <div style={{ fontSize: 7, color: C.tm, letterSpacing: .5, marginTop: 1 }}>{m.resolveTime}</div>
        </div>
      </div>

      {/* Price row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, marginBottom: 5 }}>
        <div>
          <div style={{ fontSize: 7, color: C.td, letterSpacing: 1, marginBottom: 1 }}>TARGET</div>
          <div style={{ fontSize: 9, fontWeight: "bold", color: C.tm }}>{m.targetPrice}</div>
        </div>
        <div>
          <div style={{ fontSize: 7, color: C.td, letterSpacing: 1, marginBottom: 1 }}>CURRENT</div>
          <div style={{ fontSize: 9, fontWeight: "bold", color: C.tw }}>{m.currentPrice}</div>
        </div>
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: `linear-gradient(90deg,${C.b2},transparent)`, marginBottom: 5 }} />

      {/* AI Decision */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, marginBottom: 5 }}>
        <div>
          <div style={{ fontSize: 7, color: C.td, letterSpacing: 1, marginBottom: 2 }}>PREDICTION</div>
          <div style={{
            display: "inline-block", fontSize: 9, fontWeight: "bold", color: predColor,
            border: `1px solid ${predColor}44`, background: `${predColor}11`,
            padding: "1px 6px", borderRadius: 1,
            textShadow: `0 0 6px ${predColor}`,
          }}>{m.prediction}</div>
        </div>
        <div>
          <div style={{ fontSize: 7, color: C.td, letterSpacing: 1, marginBottom: 2 }}>CONFIDENCE</div>
          <div style={{ fontSize: 13, fontWeight: "bold", color: confColor(m.confidence), lineHeight: 1 }}>
            {m.confidence}%
          </div>
        </div>
      </div>

      {/* Portfolio */}
      <div style={{ background: `rgba(0,0,0,.2)`, border: `1px solid ${C.b1}`, borderRadius: 1, padding: "4px 6px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 3 }}>
          <div>
            <div style={{ fontSize: 6.5, color: C.td, letterSpacing: .5, marginBottom: 1 }}>POS</div>
            <div style={{ fontSize: 8, fontWeight: "bold", color: posColor }}>{m.position}</div>
          </div>
          <div>
            <div style={{ fontSize: 6.5, color: C.td, letterSpacing: .5, marginBottom: 1 }}>BUYS</div>
            <div style={{ fontSize: 8, fontWeight: "bold", color: m.entries > 0 ? C.tw : C.td }}>{m.entries}</div>
          </div>
          <div>
            <div style={{ fontSize: 6.5, color: C.td, letterSpacing: .5, marginBottom: 1 }}>CAP</div>
            <div style={{ fontSize: 8, fontWeight: "bold", color: m.capital > 0 ? C.tw : C.td }}>
              {m.capital > 0 ? `$${m.capital}` : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 6.5, color: C.td, letterSpacing: .5, marginBottom: 1 }}>PNL</div>
            <div style={{ fontSize: 8, fontWeight: "bold", color: pnlColor }}>{pnlStr}</div>
          </div>
        </div>
      </div>

      {/* Status */}
      <div style={{ marginTop: 5, display: "flex", alignItems: "center", gap: 5 }}>
        <Dot color={statusColor(m.status)} size={5} />
        <span style={{ fontSize: 7.5, fontWeight: "bold", color: statusColor(m.status), letterSpacing: 2 }}>
          {m.status}
        </span>
      </div>
    </div>
  );
}

function ThinkingFeed() {
  const items = [
    { time: "14:44:02", tag: "INFO", msg: "BTC 15M — Confidence increased 74% → 81% — price moving away from target — Decision: OPEN NO", color: C.nc },
    { time: "14:43:55", tag: "SYS",  msg: "SOL 5M — Position TRACKING +12.4% — monitoring for exit trigger",                             color: C.tm },
    { time: "14:43:41", tag: "INFO", msg: "ETH 5M — Position TRACKING -3.2% — stop-loss threshold at -15%",                              color: C.ny },
    { time: "14:43:30", tag: "SYS",  msg: "XRP 5M — Confidence 66% reached READY threshold — awaiting confirmation",                     color: C.ng },
    { time: "14:43:15", tag: "SYS",  msg: "Universe sync complete — 12 markets active across 4 assets",                                  color: C.tm },
    { time: "14:43:00", tag: "INFO", msg: "BTC 5M — NO position profitable — PnL +8.6% — holding",                                      color: C.ng },
  ];
  return (
    <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <PanelTitle right="LIVE">AI Thinking Feed</PanelTitle>
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
        {items.map((item, i) => (
          <div key={i} style={{
            padding: "4px 10px", borderBottom: `1px solid rgba(11,19,32,.6)`,
            display: "flex", gap: 6, alignItems: "flex-start",
            animation: i === 0 ? "feedIn .4s ease" : undefined,
          }}>
            <span style={{ fontSize: 7, color: C.td, flexShrink: 0, marginTop: 1 }}>{item.time}</span>
            <span style={{
              fontSize: 6.5, fontWeight: "bold", color: item.color, letterSpacing: 1,
              background: `${item.color}18`, padding: "0 3px", borderRadius: 1, flexShrink: 0,
            }}>{item.tag}</span>
            <span style={{ fontSize: 8, color: C.tm, lineHeight: 1.4 }}>{item.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LiveFeed() {
  const items = [
    { tag: "SYS",  msg: "SIGNAL: BTC 15M mid=0.505 move=+0.004 → signal generated",   color: C.nc },
    { tag: "EXEC", msg: "EXECUTION: SOL 5M YES filled @ 0.505 — $50 — paper",          color: C.ng },
    { tag: "RISK", msg: "RISK: ETH 5M approved — exposure within limits",              color: C.ny },
    { tag: "SYS",  msg: "PRICE: 12 markets refreshed in 847ms",                        color: C.tm },
    { tag: "OPP",  msg: "OPPORTUNITY: XRP 5M score 78 — READY threshold met",          color: C.nc },
    { tag: "EXIT", msg: "EXIT: BTC 5M NO monitored — 8.6% profit — hold signal",       color: C.ng },
  ];
  return (
    <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column", borderTop: `1px solid ${C.b1}` }}>
      <PanelTitle right="LIVE">AI Live Feed</PanelTitle>
      <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
        {items.map((item, i) => (
          <div key={i} style={{
            padding: "3px 10px", borderBottom: `1px solid rgba(11,19,32,.6)`,
            display: "flex", gap: 6, alignItems: "center",
          }}>
            <span style={{
              fontSize: 6.5, fontWeight: "bold", color: item.color, letterSpacing: 1,
              background: `${item.color}18`, padding: "0 3px", borderRadius: 1, flexShrink: 0,
            }}>{item.tag}</span>
            <span style={{ fontSize: 7.5, color: C.tm }}>{item.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AITarget() {
  const target = MARKETS.find(m => m.isTarget)!;
  return (
    <div style={{
      flexShrink: 0, borderBottom: `1px solid rgba(0,229,255,.12)`,
      background: "linear-gradient(135deg,rgba(0,229,255,.025) 0%,transparent 45%),#06090F",
      position: "relative", overflow: "hidden",
    }}>
      {/* scan line */}
      <div style={{
        position: "absolute", left: 0, right: 0, height: 60, pointerEvents: "none",
        background: "linear-gradient(to bottom,transparent,rgba(0,229,255,.05),transparent)",
        animation: "tgtScan 5s linear infinite",
      }} />
      <PanelTitle right="PRIORITY 1">AI Current Target</PanelTitle>
      <div style={{ padding: "10px 14px", position: "relative", zIndex: 1 }}>
        {/* Market name + dir */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            {/* radar rings mini */}
            <div style={{ position: "relative", width: 48, height: 48 }}>
              {[48,34,20,8].map((s, i) => (
                <div key={i} style={{
                  position: "absolute",
                  top: (48 - s) / 2, left: (48 - s) / 2,
                  width: s, height: s, borderRadius: "50%",
                  border: `1px solid rgba(0,229,255,${.12 + i * .06})`,
                }} />
              ))}
              <div style={{
                position: "absolute", top: "50%", left: "50%",
                transform: "translate(-50%,-50%)",
                width: 8, height: 8, borderRadius: "50%",
                background: C.nc, boxShadow: `0 0 10px ${C.nc}`,
              }} />
            </div>
          </div>
          <div>
            <div style={{ fontSize: 20, fontWeight: "bold", color: C.nc, letterSpacing: 3, lineHeight: 1 }}>
              {target.asset} {target.tf}
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 4, alignItems: "center" }}>
              <span style={{
                fontSize: 10, fontWeight: "bold", color: C.ng, letterSpacing: 2,
                border: `1px solid rgba(57,255,20,.4)`, background: "rgba(57,255,20,.08)",
                padding: "2px 9px", borderRadius: 2,
              }}>YES</span>
              <span style={{ fontSize: 11, color: C.ng, fontWeight: "bold" }}>{target.confidence}%</span>
              <span style={{ fontSize: 8, color: C.tm }}>confidence</span>
            </div>
          </div>
        </div>

        {/* Data grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          {[
            { l: "ODDS", v: "51.0 / 49.0" },
            { l: "SPREAD", v: "0.010" },
            { l: "EDGE", v: "+2.1%" },
            { l: "BEST BID", v: "0.505" },
            { l: "BEST ASK", v: "0.515" },
            { l: "EXP MIN", v: target.countdown },
          ].map(({ l, v }) => (
            <div key={l}>
              <div style={{ fontSize: 6.5, color: C.td, letterSpacing: 1, marginBottom: 1 }}>{l}</div>
              <div style={{ fontSize: 9, fontWeight: "bold", color: C.tw }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Status bar */}
        <div style={{
          marginTop: 8, display: "flex", alignItems: "center", gap: 6,
          background: "rgba(0,229,255,.05)", border: `1px solid rgba(0,229,255,.15)`,
          padding: "4px 8px", borderRadius: 2,
        }}>
          <Dot color={C.nc} size={5} />
          <span style={{ fontSize: 8, color: C.nc, letterSpacing: 1.5, fontWeight: "bold" }}>SCANNING</span>
          <span style={{ fontSize: 7, color: C.tm, marginLeft: "auto" }}>Waiting for signal confirmation…</span>
        </div>

        {/* Top 3 row */}
        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
          {["#1 BTC 15M", "#2 SOL 5M", "#3 XRP 5M"].map((label, i) => (
            <div key={i} style={{
              flex: 1, border: `1px solid ${i === 0 ? "rgba(0,229,255,.35)" : C.b2}`,
              background: i === 0 ? "rgba(0,229,255,.06)" : "rgba(0,0,0,.2)",
              padding: "3px 6px", borderRadius: 1, textAlign: "center",
              fontSize: 8, color: i === 0 ? C.nc : C.tm, fontWeight: i === 0 ? "bold" : "normal",
            }}>
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HealthPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <Dot color={color} size={5} />
      <span style={{ fontSize: 7.5, color: C.tm, letterSpacing: .5 }}>{label}</span>
      <span style={{ fontSize: 8, fontWeight: "bold", color, marginLeft: "auto" }}>{value}</span>
    </div>
  );
}

export function Dashboard() {
  const [time, setTime] = useState(() => new Date().toUTCString().slice(17, 25) + " UTC");

  useEffect(() => {
    const t = setInterval(() => {
      setTime(new Date().toUTCString().slice(17, 25) + " UTC");
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const assets = ["BTC", "ETH", "SOL", "XRP"];

  return (
    <div style={{
      width: "100vw", height: "100vh", overflow: "hidden",
      background: C.bg, fontFamily: "'Courier New', Courier, monospace",
      fontSize: 11, color: C.tm,
      display: "grid", gridTemplateRows: "42px 1fr 22px",
      position: "relative",
    }}>
      <style>{`
        @keyframes tgtScan { 0% { top: -60px; } 100% { top: 120%; } }
        @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:.15; } }
        @keyframes feedIn { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:translateY(0); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 3px; } ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #111d2e; border-radius: 2px; }
      `}</style>

      {/* Background glow */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: `
          radial-gradient(ellipse 70% 50% at 50% 0%, rgba(0,229,255,.028) 0%, transparent 65%),
          radial-gradient(ellipse 40% 40% at 80% 70%, rgba(192,0,255,.018) 0%, transparent 55%),
          radial-gradient(ellipse 35% 35% at 15% 55%, rgba(57,255,20,.013) 0%, transparent 50%)
        `,
      }} />

      {/* Scanlines */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 9999,
        background: "repeating-linear-gradient(transparent,transparent 2px,rgba(0,0,0,.03) 2px,rgba(0,0,0,.03) 4px)",
      }} />

      {/* ── HEADER ── */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 20px", zIndex: 100, position: "relative",
        borderBottom: `1px solid rgba(0,229,255,.1)`,
        background: "linear-gradient(135deg,rgba(0,229,255,.03) 0%,transparent 55%),rgba(6,9,15,.98)",
        boxShadow: `0 1px 0 rgba(0,229,255,.06),0 4px 24px rgba(0,0,0,.6)`,
      }}>
        <div>
          <div style={{
            fontSize: 15, fontWeight: "bold", letterSpacing: 7, color: C.nc,
            textShadow: `0 0 14px ${C.nc},0 0 32px rgba(0,229,255,.22)`,
          }}>LIMWANPO // <span style={{ color: C.nm, textShadow: `0 0 14px ${C.nm}` }}>POLYMARKET AI</span></div>
          <div style={{ fontSize: 7, letterSpacing: 5, color: C.tm, marginTop: 1 }}>AI MISSION CONTROL · MARKET UNIVERSE V2</div>
        </div>

        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {[
            { label: "PAPER MODE", color: C.nc },
            { label: "9 ENGINES LIVE", dot: C.ng },
            { label: "12 MARKETS", dot: C.nc },
            { label: "3 SIGNALS", dot: C.np },
            { label: "1 OPEN", dot: C.np },
            { label: "CAPITAL OK", dot: C.ng },
          ].map(({ label, color, dot }, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 5, padding: "3px 10px",
              border: `1px solid ${color ? "rgba(0,229,255,.3)" : C.b2}`,
              borderRadius: 2, fontSize: 9, letterSpacing: 1.5,
              color: color || C.tm, background: color ? "rgba(0,229,255,.06)" : "rgba(0,0,0,.3)",
            }}>
              {dot && <Dot color={dot} />}
              {label}
            </div>
          ))}
          <div style={{ fontSize: 9, color: C.tm, letterSpacing: 1 }}>{time}</div>
        </div>
      </header>

      {/* ── MAIN ── */}
      <main style={{
        display: "grid", gridTemplateColumns: "320px 1fr 260px",
        overflow: "hidden", position: "relative", zIndex: 1,
      }}>
        {/* ═══ LEFT — MARKET UNIVERSE ═══ */}
        <div style={{
          borderRight: `1px solid rgba(0,229,255,.07)`,
          display: "flex", flexDirection: "column", overflow: "hidden",
        }}>
          <PanelTitle right="12 MARKETS">Market Universe</PanelTitle>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {assets.map(asset => (
              <div key={asset} style={{ marginBottom: 2 }}>
                <AssetHeader asset={asset} />
                {MARKETS.filter(m => m.asset === asset).map((m, i) => (
                  <MarketCardComp key={i} m={m} />
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ═══ CENTER ═══ */}
        <div style={{
          display: "flex", flexDirection: "column", overflow: "hidden",
          borderRight: `1px solid rgba(0,229,255,.07)`,
          background: "linear-gradient(180deg,rgba(0,229,255,.015) 0%,transparent 20%)",
        }}>
          <AITarget />

          {/* Decision Engine Status */}
          <div style={{ flexShrink: 0, borderBottom: `1px solid ${C.b1}` }}>
            <PanelTitle right="LAST UPDATE: {time}">AI Decision Engine</PanelTitle>
            <div style={{ padding: "8px 12px", display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
              {[
                { label: "UNIVERSE", value: "4", sub: "4 assets", color: C.nc, pct: "100%" },
                { label: "SIGNALS",  value: "3", sub: "3 active", color: C.nc, pct: "100%" },
                { label: "OPPS",     value: "2", sub: "2 scored", color: C.nc, pct: "67%" },
                { label: "STRATEGY", value: "1", sub: "1 queued",  color: C.ny, pct: "50%" },
                { label: "RISK",     value: "1", sub: "1 approved",color: C.ng, pct: "100%" },
              ].map(({ label, value, sub, color, pct }) => (
                <div key={label} style={{
                  background: C.panel, border: `1px solid ${C.b2}`, borderRadius: 2, padding: "8px 10px",
                  textAlign: "center", position: "relative", overflow: "hidden",
                }}>
                  <div style={{ fontSize: 6.5, color: C.td, letterSpacing: 2, marginBottom: 4 }}>{label}</div>
                  <div style={{ fontSize: 22, fontWeight: "bold", color, lineHeight: 1 }}>{value}</div>
                  <div style={{ fontSize: 7, color: C.tm, marginTop: 3 }}>{sub}</div>
                  <div style={{ marginTop: 5, height: 2, background: C.b1, borderRadius: 1 }}>
                    <div style={{ width: pct, height: "100%", background: color, borderRadius: 1 }} />
                  </div>
                  <div style={{ fontSize: 6.5, color: C.td, marginTop: 2 }}>{pct}</div>
                </div>
              ))}
            </div>
            <div style={{
              margin: "0 12px 8px", padding: "4px 8px",
              background: "rgba(0,229,255,.04)", border: `1px solid rgba(0,229,255,.12)`,
              borderRadius: 2, display: "flex", alignItems: "center", gap: 6,
            }}>
              <Dot color={C.nc} size={5} />
              <span style={{ fontSize: 7.5, color: C.nc, letterSpacing: 1, fontWeight: "bold" }}>SYSTEM THINKING</span>
              <span style={{ fontSize: 7, color: C.tm, marginLeft: "auto" }}>
                LAST UPDATE: {time}
              </span>
            </div>
          </div>

          {/* System Health */}
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <PanelTitle>System Health</PanelTitle>
            <div style={{ flex: 1, overflowY: "auto", padding: "8px 12px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px" }}>
                {[
                  { l: "UNIVERSE",    v: "99.8%", c: C.ng },
                  { l: "EXECUTION",   v: "99.1%", c: C.ng },
                  { l: "SIGNAL",      v: "98.7%", c: C.ng },
                  { l: "POSITION",    v: "99.3%", c: C.ng },
                  { l: "OPPORTUNITY", v: "98.9%", c: C.ng },
                  { l: "EXIT",        v: "99.4%", c: C.ng },
                  { l: "STRATEGY",    v: "99.6%", c: C.ng },
                  { l: "ANALYTICS",   v: "98.5%", c: C.ng },
                  { l: "RISK",        v: "99.5%", c: C.ng },
                  { l: "CAPITAL",     v: "100%",  c: C.ng },
                ].map(({ l, v, c }) => (
                  <HealthPill key={l} label={l} value={v} color={c} />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ═══ RIGHT ═══ */}
        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <ThinkingFeed />
          <LiveFeed />
        </div>
      </main>

      {/* ── FOOTER ── */}
      <footer style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 16px", zIndex: 100, position: "relative",
        borderTop: `1px solid ${C.b1}`,
        background: "rgba(3,5,10,.95)", fontSize: 7, color: C.td, letterSpacing: .5,
      }}>
        <div style={{ display: "flex", gap: 12 }}>
          {[
            { l: "BTC", v: "107,182", d: "+0.3%" },
            { l: "ETH", v: "3,487",   d: "+0.8%" },
            { l: "SOL", v: "148.45",  d: "+1.2%" },
            { l: "XRP", v: "0.5791",  d: "-0.4%" },
          ].map(({ l, v, d }) => (
            <span key={l} style={{ display: "flex", gap: 4, alignItems: "center" }}>
              <span style={{ color: C.tm, fontWeight: "bold" }}>{l}</span>
              <span style={{ color: C.tw }}>{v}</span>
              <span style={{ color: d.startsWith("+") ? C.ng : C.red }}>{d}</span>
            </span>
          ))}
        </div>
        <span>LIMWANPO // POLYMARKET AI · V2.0 · PAPER MODE</span>
        <span style={{ color: C.nc }}>REFRESHED {time}</span>
      </footer>
    </div>
  );
}
