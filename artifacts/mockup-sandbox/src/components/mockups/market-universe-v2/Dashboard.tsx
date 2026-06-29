import { useEffect, useRef, useState, useCallback } from "react";

const C = {
  bg: "#03050A", panel: "#06090F", panel2: "#080c13",
  b1: "#0b1320", b2: "#111d2e", b3: "#1a2c40",
  ng: "#39FF14", nc: "#00E5FF", np: "#C000FF",
  nm: "#FF2D95", ny: "#FFE600", tw: "#dff0ff",
  tm: "#6b8fa8", td: "#3a5570", red: "#ff3355",
};

type Status = "WAIT" | "WATCH" | "READY" | "TRACKING" | "WIN" | "LOSS";
type Pos = "YES" | "NO" | "NONE";
interface MarketCard { asset: string; tf: string; countdown: string; resolveTime: string; targetPrice: string; currentPrice: string; prediction: "YES" | "NO"; confidence: number; position: Pos; entries: number; capital: number; pnl: number | null; status: Status; isTarget?: boolean; }

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

const ASSETS = ["BTC", "ETH", "SOL", "XRP"];
const ICONS: Record<string, string> = { BTC: "₿", ETH: "Ξ", SOL: "◎", XRP: "✕" };

function cardBorder(m: MarketCard) {
  if (m.isTarget)                                          return { b: `rgba(0,229,255,.55)`,  bg: "rgba(0,229,255,.045)", glow: "0 0 16px rgba(0,229,255,.22)" };
  if (m.position !== "NONE" && (m.pnl ?? 0) > 0)         return { b: `rgba(57,255,20,.45)`,   bg: "rgba(57,255,20,.035)",  glow: "0 0 14px rgba(57,255,20,.18)" };
  if (m.position !== "NONE" && (m.pnl ?? 0) < 0)         return { b: `rgba(255,51,85,.4)`,    bg: "rgba(255,51,85,.035)",  glow: "0 0 14px rgba(255,51,85,.15)" };
  if (m.status === "WATCH" || m.status === "READY")       return { b: `rgba(255,230,0,.35)`,   bg: "rgba(255,230,0,.022)",  glow: "0 0 12px rgba(255,230,0,.12)" };
  return { b: C.b2, bg: "rgba(0,0,0,.2)", glow: "none" };
}
function statusColor(s: Status) {
  if (s === "TRACKING") return C.nc; if (s === "WIN") return C.ng;
  if (s === "LOSS") return C.red;    if (s === "READY") return C.ng;
  if (s === "WATCH") return C.ny;    return C.td;
}
function confColor(c: number) {
  if (c >= 85) return C.ng; if (c >= 70) return "#22ee55";
  if (c >= 55) return C.nc; if (c >= 40) return C.ny; return C.td;
}
function Dot({ color, size = 6 }: { color: string; size?: number }) {
  return <span style={{ display:"inline-block", width:size, height:size, borderRadius:"50%", background:color, boxShadow:`0 0 6px ${color}`, flexShrink:0 }} />;
}
function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div style={{ fontSize:8, letterSpacing:3.5, color:C.tm, padding:"6px 16px 5px", borderBottom:`1px solid ${C.b1}`, textTransform:"uppercase", display:"flex", alignItems:"center", justifyContent:"space-between", background:"linear-gradient(90deg,rgba(0,0,0,.35),transparent)", flexShrink:0 }}>
      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
        <span style={{ display:"inline-block", width:2, height:9, borderRadius:1, background:`linear-gradient(180deg,${C.nc},rgba(0,229,255,.15))`, boxShadow:`0 0 7px ${C.nc}` }} />
        {children}
      </div>
      {right && <span style={{ fontSize:7, color:C.nc, letterSpacing:2, opacity:.8 }}>{right}</span>}
    </div>
  );
}

// ── PORTFOLIO SUMMARY ──────────────────────────────────────────────────────────
function PortfolioSummary() {
  const stats = [
    { l:"TOTAL VALUE",  v:"$4,280",  c:C.nc,  sub:"↑ $120 today" },
    { l:"OPEN POS",     v:"3",       c:C.nc,  sub:"BTC·SOL·ETH" },
    { l:"TOTAL PnL",    v:"+$17.8",  c:C.ng,  sub:"+0.42%" },
    { l:"WIN RATE",     v:"71%",     c:C.ng,  sub:"22/31 trades" },
    { l:"DAILY LOSS",   v:"3.2%",    c:C.ny,  sub:"Limit: 10%" },
    { l:"CAPITAL USED", v:"$400",    c:C.tm,  sub:"$4k available" },
  ];
  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <SectionTitle>Portfolio Summary</SectionTitle>
      <div style={{ flex:1, display:"grid", gridTemplateColumns:"1fr 1fr", gap:1, padding:10, overflow:"hidden" }}>
        {stats.map(({ l, v, c, sub }) => (
          <div key={l} style={{ background:C.panel, border:`1px solid ${C.b2}`, borderRadius:2, padding:"7px 10px", position:"relative", overflow:"hidden" }}>
            <div style={{ position:"absolute", bottom:0, right:0, width:30, height:30, borderRadius:"50%", background:c, opacity:.04, filter:"blur(10px)" }} />
            <div style={{ fontSize:6.5, color:C.td, letterSpacing:1.5, marginBottom:3 }}>{l}</div>
            <div style={{ fontSize:15, fontWeight:"bold", color:c, lineHeight:1, marginBottom:2, textShadow:`0 0 10px ${c}55` }}>{v}</div>
            <div style={{ fontSize:7, color:C.tm }}>{sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── LIVE MARKET CHART ──────────────────────────────────────────────────────────
function LiveChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const dataRef = useRef<number[]>([]);
  const tRef = useRef(0);

  useEffect(() => {
    const seed: number[] = [];
    let v = 107182;
    for (let i = 0; i < 120; i++) { v += (Math.random() - 0.49) * 60; seed.push(v); }
    dataRef.current = seed;

    function draw() {
      const canvas = canvasRef.current; if (!canvas) return;
      const ctx = canvas.getContext("2d"); if (!ctx) return;
      const w = canvas.width, h = canvas.height;

      tRef.current += 0.3;
      if (tRef.current > 2) {
        tRef.current = 0;
        const last = dataRef.current[dataRef.current.length - 1];
        dataRef.current.push(last + (Math.random() - 0.49) * 55);
        if (dataRef.current.length > 150) dataRef.current.shift();
      }

      ctx.clearRect(0, 0, w, h);
      const pts = dataRef.current;
      const mn = Math.min(...pts), mx = Math.max(...pts);
      const rng = mx - mn || 100;
      const px = (i: number) => (i / (pts.length - 1)) * w;
      const py = (v: number) => h - 8 - ((v - mn) / rng) * (h - 24);

      // Grid
      ctx.strokeStyle = "rgba(17,29,46,.8)"; ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = 8 + (i / 4) * (h - 24);
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        const val = mx - (i / 4) * rng;
        ctx.fillStyle = "rgba(107,143,168,.5)"; ctx.font = "9px Courier New";
        ctx.fillText(Math.round(val).toLocaleString(), 4, y - 2);
      }

      // Area fill
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, "rgba(0,229,255,.25)");
      grad.addColorStop(1, "rgba(0,229,255,.0)");
      ctx.beginPath(); ctx.moveTo(px(0), py(pts[0]));
      pts.forEach((v, i) => i > 0 && ctx.lineTo(px(i), py(v)));
      ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
      ctx.fillStyle = grad; ctx.fill();

      // Line
      ctx.beginPath(); ctx.moveTo(px(0), py(pts[0]));
      pts.forEach((v, i) => i > 0 && ctx.lineTo(px(i), py(v)));
      ctx.strokeStyle = C.nc; ctx.lineWidth = 1.5;
      ctx.shadowBlur = 6; ctx.shadowColor = C.nc;
      ctx.stroke(); ctx.shadowBlur = 0;

      // Last price dot
      const lx = px(pts.length - 1), ly = py(pts[pts.length - 1]);
      ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = C.nc; ctx.shadowBlur = 10; ctx.shadowColor = C.nc;
      ctx.fill(); ctx.shadowBlur = 0;

      // Price label
      ctx.fillStyle = C.nc; ctx.font = "bold 10px Courier New";
      ctx.fillText(Math.round(pts[pts.length - 1]).toLocaleString(), lx - 38, ly - 6);

      frameRef.current = requestAnimationFrame(draw);
    }
    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, []);

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <SectionTitle right="LIVE · BTC/USD">Live Market Chart</SectionTitle>
      <div style={{ flex:1, position:"relative", padding:"4px 6px 6px" }}>
        <canvas ref={canvasRef} style={{ width:"100%", height:"100%", display:"block" }}
          width={900} height={200} />
        {/* Overlays */}
        <div style={{ position:"absolute", top:10, right:16, display:"flex", gap:8 }}>
          {["5M","15M","1H"].map((tf, i) => (
            <div key={tf} style={{ fontSize:8, padding:"2px 7px", border:`1px solid ${i===0?C.nc:C.b2}`, color:i===0?C.nc:C.td, borderRadius:2, cursor:"pointer", background:i===0?"rgba(0,229,255,.08)":"transparent" }}>{tf}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── SYSTEM HEALTH ──────────────────────────────────────────────────────────────
function SystemHealth() {
  const engines = [
    { name:"Universe",    val:"99.8%", ok:true  },
    { name:"Signal",      val:"98.7%", ok:true  },
    { name:"Opportunity", val:"98.9%", ok:true  },
    { name:"Strategy",    val:"99.6%", ok:true  },
    { name:"Risk",        val:"99.5%", ok:true  },
    { name:"Execution",   val:"99.1%", ok:true  },
    { name:"Exit",        val:"99.4%", ok:true  },
    { name:"Analytics",   val:"98.5%", ok:true  },
    { name:"Portfolio",   val:"99.3%", ok:true  },
    { name:"Capital",     val:"100%",  ok:true  },
  ];
  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <SectionTitle right="10/10 OK">System Health</SectionTitle>
      <div style={{ flex:1, overflowY:"auto", padding:"8px 10px", display:"flex", flexDirection:"column", gap:4 }}>
        {engines.map(({ name, val, ok }) => (
          <div key={name} style={{
            display:"flex", alignItems:"center", gap:7, padding:"5px 9px",
            background:ok?"rgba(57,255,20,.028)":"rgba(255,51,85,.028)",
            border:`1px solid ${ok?"rgba(57,255,20,.18)":"rgba(255,51,85,.18)"}`,
            borderRadius:3, position:"relative", overflow:"hidden",
          }}>
            <div style={{ position:"absolute", left:0, top:0, bottom:0, width:2, background:ok?C.ng:C.red, boxShadow:`0 0 6px ${ok?C.ng:C.red}` }} />
            <Dot color={ok?C.ng:C.red} size={5} />
            <span style={{ fontSize:8, color:ok?C.tm:C.red, flex:1, letterSpacing:.5 }}>{name}</span>
            <span style={{ fontSize:8, fontWeight:"bold", color:ok?C.ng:C.red }}>{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ASSET HEADER ───────────────────────────────────────────────────────────────
function AssetHeader({ asset }: { asset: string }) {
  const cards = MARKETS.filter(m => m.asset === asset);
  const conf = Math.round(cards.reduce((a, m) => a + m.confidence, 0) / cards.length);
  const pos  = cards.filter(m => m.position !== "NONE").length;
  const cap  = cards.reduce((a, m) => a + m.capital, 0);
  const pnl  = cards.reduce((a, m) => a + (m.pnl ?? 0), 0);
  const pnlColor = pnl > 0 ? C.ng : pnl < 0 ? C.red : C.td;
  return (
    <div style={{ padding:"6px 10px 5px", background:`linear-gradient(90deg,rgba(0,229,255,.07),rgba(0,229,255,.02))`, borderBottom:`1px solid rgba(0,229,255,.14)`, borderTop:`1px solid rgba(0,229,255,.1)`, marginBottom:4 }}>
      <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
        <span style={{ fontSize:13, fontWeight:"bold", color:C.nc, letterSpacing:1.5 }}>{ICONS[asset]} {asset}</span>
        <div style={{ height:1, flex:1, background:`linear-gradient(90deg,rgba(0,229,255,.3),transparent)` }} />
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:4 }}>
        {[
          { l:"CONF",       v:`${conf}%`,                              c:confColor(conf) },
          { l:"POSITIONS",  v:`${pos}`,                                c:pos>0?C.nc:C.td },
          { l:"CAPITAL",    v:cap>0?`$${cap}`:"—",                     c:cap>0?C.tw:C.td },
          { l:"PnL",        v:pnl!==0?(pnl>0?`+$${pnl.toFixed(1)}`:`-$${Math.abs(pnl).toFixed(1)}`):"—", c:pnlColor },
        ].map(({ l, v, c }) => (
          <div key={l} style={{ textAlign:"center", background:"rgba(0,0,0,.2)", borderRadius:2, padding:"2px 4px" }}>
            <div style={{ fontSize:6, color:C.td, letterSpacing:1 }}>{l}</div>
            <div style={{ fontSize:9, fontWeight:"bold", color:c }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── MARKET CARD ────────────────────────────────────────────────────────────────
function MarketCardComp({ m }: { m: MarketCard }) {
  const { b, bg, glow } = cardBorder(m);
  const predColor = m.prediction === "YES" ? C.ng : C.nm;
  const posColor  = m.position === "YES" ? C.ng : m.position === "NO" ? C.nm : C.td;
  const pnlColor  = m.pnl === null ? C.td : m.pnl > 0 ? C.ng : C.red;
  const pnlStr    = m.pnl === null ? "—" : m.pnl > 0 ? `+${m.pnl}%` : `${m.pnl}%`;
  return (
    <div style={{ border:`1px solid ${b}`, background:bg, boxShadow:glow, borderRadius:2, padding:"7px 8px", marginBottom:4, position:"relative" }}>
      {m.isTarget && <div style={{ position:"absolute", top:0, right:0, fontSize:6.5, letterSpacing:1, color:C.nc, background:"rgba(0,229,255,.14)", padding:"1px 5px", borderBottomLeftRadius:2 }}>TARGET</div>}
      {/* Row 1: TF + countdown */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:5 }}>
        <span style={{ fontSize:10, fontWeight:"bold", color:C.tw, letterSpacing:.5 }}>{m.tf}</span>
        <div style={{ textAlign:"right" }}>
          <div style={{ fontSize:13, fontWeight:"bold", color:statusColor(m.status), lineHeight:1 }}>{m.countdown}</div>
          <div style={{ fontSize:6.5, color:C.td }}>{m.resolveTime}</div>
        </div>
      </div>
      {/* Price */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:4, marginBottom:5 }}>
        <div><div style={{ fontSize:6, color:C.td, letterSpacing:1 }}>TARGET</div><div style={{ fontSize:8, fontWeight:"bold", color:C.tm }}>{m.targetPrice}</div></div>
        <div><div style={{ fontSize:6, color:C.td, letterSpacing:1 }}>CURRENT</div><div style={{ fontSize:8, fontWeight:"bold", color:C.tw }}>{m.currentPrice}</div></div>
      </div>
      {/* Divider */}
      <div style={{ height:1, background:`linear-gradient(90deg,${C.b2},transparent)`, marginBottom:5 }} />
      {/* Prediction */}
      <div style={{ display:"grid", gridTemplateColumns:"auto 1fr", gap:6, alignItems:"center", marginBottom:5 }}>
        <div style={{ fontSize:9, fontWeight:"bold", color:predColor, border:`1px solid ${predColor}44`, background:`${predColor}11`, padding:"1px 7px", borderRadius:1 }}>{m.prediction}</div>
        <div style={{ display:"flex", alignItems:"baseline", gap:4 }}>
          <span style={{ fontSize:14, fontWeight:"bold", color:confColor(m.confidence), lineHeight:1 }}>{m.confidence}%</span>
          <span style={{ fontSize:7, color:C.td }}>conf</span>
        </div>
      </div>
      {/* Portfolio row */}
      <div style={{ background:"rgba(0,0,0,.25)", border:`1px solid ${C.b1}`, borderRadius:2, padding:"3px 5px" }}>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:2 }}>
          {[
            { l:"POS",  v:m.position,                        c:posColor },
            { l:"BUYS", v:`${m.entries}`,                    c:m.entries>0?C.tw:C.td },
            { l:"CAP",  v:m.capital>0?`$${m.capital}`:"—",  c:m.capital>0?C.tw:C.td },
            { l:"PNL",  v:pnlStr,                            c:pnlColor },
          ].map(({ l, v, c }) => (
            <div key={l} style={{ textAlign:"center" }}>
              <div style={{ fontSize:6, color:C.td, letterSpacing:.5 }}>{l}</div>
              <div style={{ fontSize:8, fontWeight:"bold", color:c }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
      {/* Status */}
      <div style={{ marginTop:5, display:"flex", alignItems:"center", gap:4 }}>
        <Dot color={statusColor(m.status)} size={5} />
        <span style={{ fontSize:7, fontWeight:"bold", color:statusColor(m.status), letterSpacing:2 }}>{m.status}</span>
      </div>
    </div>
  );
}

// ── AI PIPELINE NODE ───────────────────────────────────────────────────────────
function PipelineNode({ name, count, active, icon, colorOverride }: {
  name: string; count: string; active: boolean; icon: React.ReactNode; colorOverride?: string;
}) {
  const col = colorOverride ?? (active ? C.nc : C.td);
  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:8, flex:1 }}>
      {/* Node orb */}
      <div style={{ position:"relative", width:64, height:64 }}>
        {/* Outer ring */}
        <div style={{
          position:"absolute", inset:0, borderRadius:"50%",
          border:`1px solid ${col}${active?"66":"22"}`,
          animation:active?"nodeRing 3s linear infinite":"none",
          boxShadow:active?`0 0 20px ${col}44,inset 0 0 15px ${col}22`:"none",
        }} />
        {/* Inner fill */}
        <div style={{
          position:"absolute", inset:8, borderRadius:"50%",
          background:active?`radial-gradient(circle,${col}33 0%,${col}08 60%,transparent 100%)`:`rgba(0,0,0,.3)`,
          border:`1px solid ${col}${active?"44":"11"}`,
          display:"flex", alignItems:"center", justifyContent:"center",
          boxShadow:active?`0 0 12px ${col}33`:"none",
        }}>
          {icon}
        </div>
        {/* Pulse ring on active */}
        {active && (
          <div style={{
            position:"absolute", inset:-4, borderRadius:"50%",
            border:`1px solid ${col}44`,
            animation:"pulseRing 2s ease-out infinite",
          }} />
        )}
      </div>
      {/* Label */}
      <div style={{ textAlign:"center" }}>
        <div style={{ fontSize:8, fontWeight:"bold", color:col, letterSpacing:2, textShadow:active?`0 0 8px ${col}`:"none" }}>{name.toUpperCase()}</div>
        <div style={{ fontSize:9, color:active?C.tw:C.td, fontWeight:"bold", marginTop:2 }}>{count}</div>
      </div>
    </div>
  );
}

function FlowConnector({ active, color = C.nc }: { active: boolean; color?: string }) {
  return (
    <div style={{ flex:1, display:"flex", alignItems:"center", paddingBottom:22 }}>
      <div style={{ flex:1, height:2, position:"relative", background:`${color}18`, borderRadius:1 }}>
        {active && (
          <div style={{
            position:"absolute", top:0, height:"100%", width:"40%",
            background:`linear-gradient(90deg,transparent,${color},transparent)`,
            borderRadius:1, animation:"flowEnergy 1.8s linear infinite",
          }} />
        )}
      </div>
    </div>
  );
}

function AIPipeline() {
  const [activeNode, setActiveNode] = useState(2);
  useEffect(() => {
    const t = setInterval(() => setActiveNode(n => (n + 1) % 6), 3000);
    return () => clearInterval(t);
  }, []);

  const nodes = [
    { name:"Universe",    count:"12 markets", color:C.nc,  icon:<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke={activeNode===0?C.nc:C.td} strokeWidth="1" opacity=".6"/><ellipse cx="12" cy="12" rx="9" ry="4" stroke={activeNode===0?C.nc:C.td} strokeWidth="1" style={{animationName:"orbitRing",animationDuration:"8s",animationIterationCount:"infinite",animationTimingFunction:"linear"}}/><circle cx="12" cy="12" r="2.5" fill={activeNode===0?C.nc:C.td} opacity=".8"/></svg> },
    { name:"Signal",      count:"3 signals",  color:C.nc,  icon:<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="3" fill={activeNode===1?C.nc:C.td} opacity=".9"/>{[7,11,15].map((r,i)=><circle key={r} cx="12" cy="12" r={r} stroke={activeNode===1?C.nc:C.td} strokeWidth=".8" opacity={.6-i*.15}/>)}</svg> },
    { name:"Opportunity", count:"2 scored",   color:C.np,  icon:<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><polygon points="12,3 19,9 19,15 12,21 5,15 5,9" stroke={activeNode===2?C.np:C.td} strokeWidth="1" fill={activeNode===2?"rgba(192,0,255,.2)":"none"}/><polygon points="12,7 16,10 16,14 12,17 8,14 8,10" stroke={activeNode===2?C.np:C.td} strokeWidth=".8" fill={activeNode===2?"rgba(192,0,255,.1)":"none"}/><circle cx="12" cy="12" r="2" fill={activeNode===2?C.np:C.td}/></svg> },
    { name:"Strategy",    count:"1 queued",   color:C.ny,  icon:<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><polygon points="12,4 20,8.5 20,15.5 12,20 4,15.5 4,8.5" stroke={activeNode===3?C.ny:C.td} strokeWidth="1" fill={activeNode===3?"rgba(255,230,0,.1)":"none"}/><polygon points="12,8 17,10.7 17,15.3 12,18 7,15.3 7,10.7" stroke={activeNode===3?C.ny:C.td} strokeWidth=".8" fill="none"/><circle cx="12" cy="12" r="2.5" fill={activeNode===3?C.ny:C.td} opacity=".9"/></svg> },
    { name:"Risk",        count:"1 approved", color:C.ng,  icon:<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 3 L20 7 L20 14 Q20 18 12 21 Q4 18 4 14 L4 7 Z" stroke={activeNode===4?C.ng:C.td} strokeWidth="1" fill={activeNode===4?"rgba(57,255,20,.08)":"none"}/><path d="M8 12 L11 15 L16 10" stroke={activeNode===4?C.ng:C.td} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg> },
    { name:"Execution",   count:"3 trades",   color:C.nm,  icon:<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke={activeNode===5?C.nm:C.td} strokeWidth="1" fill="none"/><circle cx="12" cy="12" r="5" stroke={activeNode===5?C.nm:C.td} strokeWidth="1" fill={activeNode===5?"rgba(255,45,149,.08)":"none"}/><circle cx="12" cy="12" r="2" fill={activeNode===5?C.nm:C.td} opacity=".9"/>{activeNode===5&&[0,60,120,180,240,300].map(a=><line key={a} x1="12" y1="4" x2="12" y2="7" stroke={C.nm} strokeWidth=".8" style={{transformOrigin:"12px 12px",transform:`rotate(${a}deg)`}} opacity=".7"/>)}</svg> },
  ];

  return (
    <div style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <SectionTitle right={`NODE ${activeNode + 1}/6 ACTIVE`}>AI Decision Engine — Pipeline</SectionTitle>
      <div style={{ padding:"16px 20px 12px", display:"flex", alignItems:"center" }}>
        {nodes.map((n, i) => (
          <div key={n.name} style={{ display:"contents" }}>
            <PipelineNode name={n.name} count={n.count} active={activeNode===i} icon={n.icon} colorOverride={n.color} />
            {i < nodes.length - 1 && <FlowConnector active={activeNode===i || activeNode===i+1} color={nodes[i].color} />}
          </div>
        ))}
      </div>
      {/* Current decision banner */}
      <div style={{ margin:"0 20px 12px", padding:"6px 12px", background:"rgba(0,229,255,.04)", border:`1px solid rgba(0,229,255,.15)`, borderRadius:2, display:"flex", alignItems:"center", gap:8 }}>
        <Dot color={C.nc} />
        <span style={{ fontSize:8, color:C.nc, letterSpacing:1.5, fontWeight:"bold" }}>PROCESSING</span>
        <span style={{ fontSize:8, color:C.tm }}>BTC 15M YES · confidence 72% · awaiting risk approval…</span>
        <div style={{ marginLeft:"auto", display:"flex", gap:6 }}>
          {nodes.map((n, i) => (
            <div key={n.name} style={{ width:20, height:3, borderRadius:2, background:i<=activeNode?n.color:C.b2, boxShadow:i===activeNode?`0 0 6px ${n.color}`:"none", transition:"all .3s" }} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── AI FEEDS ───────────────────────────────────────────────────────────────────
function ThinkingFeed() {
  const items = [
    { time:"14:44:02", tag:"INFO",  msg:"BTC 15M — Confidence 74% → 72% — mid stable — Decision: WATCH", color:C.nc },
    { time:"14:43:55", tag:"SYS",   msg:"SOL 5M — Position TRACKING +12.4% — exit trigger monitoring",   color:C.tm },
    { time:"14:43:41", tag:"INFO",  msg:"ETH 5M — Position TRACKING -3.2% — stop-loss threshold at -15%", color:C.ny },
    { time:"14:43:30", tag:"OPP",   msg:"XRP 5M — Score 78 — READY threshold reached",                   color:C.ng },
    { time:"14:43:15", tag:"SYS",   msg:"Universe sync complete — 12 markets · 4 assets",                 color:C.tm },
    { time:"14:43:00", tag:"INFO",  msg:"BTC 5M — NO position profitable — PnL +8.6% — holding",         color:C.ng },
    { time:"14:42:44", tag:"RISK",  msg:"ETH 15M — Exposure check passed — DAILY_LOSS 3.2% < 10%",        color:C.tm },
    { time:"14:42:30", tag:"STRAT", msg:"SOL 1H confidence 47% — below threshold — skipping",             color:C.td },
  ];
  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <SectionTitle right="LIVE">AI Thinking Feed</SectionTitle>
      <div style={{ flex:1, overflowY:"auto", padding:"4px 0" }}>
        {items.map((item, i) => (
          <div key={i} style={{ padding:"4px 12px", borderBottom:`1px solid rgba(11,19,32,.7)`, display:"flex", gap:7, alignItems:"flex-start", animation:i===0?"feedIn .4s ease":undefined }}>
            <span style={{ fontSize:7, color:C.td, flexShrink:0, marginTop:1, minWidth:50 }}>{item.time}</span>
            <span style={{ fontSize:6.5, fontWeight:"bold", color:item.color, letterSpacing:1, background:`${item.color}18`, padding:"0 3px", borderRadius:1, flexShrink:0, height:"fit-content" }}>{item.tag}</span>
            <span style={{ fontSize:8, color:C.tm, lineHeight:1.45 }}>{item.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
function LiveFeed() {
  const items = [
    { tag:"SYS",  msg:"SIGNAL: BTC 15M mid=0.505 move=+0.004 → signal generated",    color:C.nc },
    { tag:"EXEC", msg:"EXECUTION: SOL 5M YES filled @ 0.505 — $50",                   color:C.ng },
    { tag:"RISK", msg:"RISK: ETH 5M approved — exposure within limits",               color:C.ny },
    { tag:"SYS",  msg:"PRICE: 12 markets refreshed in 847ms",                         color:C.tm },
    { tag:"OPP",  msg:"OPPORTUNITY: XRP 5M score 78 — READY",                         color:C.nc },
    { tag:"EXIT", msg:"EXIT: BTC 5M NO monitored — 8.6% profit — hold signal",        color:C.ng },
    { tag:"SYS",  msg:"RISK: daily loss 3.2% — within parameters",                    color:C.tm },
    { tag:"STRAT",msg:"STRATEGY: ETH 15M READY queued for execution",                 color:C.ny },
  ];
  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden", borderLeft:`1px solid ${C.b1}` }}>
      <SectionTitle right="LIVE">AI Live Feed</SectionTitle>
      <div style={{ flex:1, overflowY:"auto", padding:"4px 0" }}>
        {items.map((item, i) => (
          <div key={i} style={{ padding:"4px 12px", borderBottom:`1px solid rgba(11,19,32,.7)`, display:"flex", gap:7, alignItems:"center" }}>
            <span style={{ fontSize:6.5, fontWeight:"bold", color:item.color, letterSpacing:1, background:`${item.color}18`, padding:"0 3px", borderRadius:1, flexShrink:0 }}>{item.tag}</span>
            <span style={{ fontSize:8, color:C.tm }}>{item.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── FOOTER TICKERS ─────────────────────────────────────────────────────────────
function CryptoTicker() {
  const prices = [
    { sym:"BTC", price:"107,182", delta:"+0.32%", up:true },
    { sym:"ETH", price:"3,487",   delta:"+0.81%", up:true },
    { sym:"SOL", price:"148.45",  delta:"+1.24%", up:true },
    { sym:"XRP", price:"0.5791",  delta:"-0.38%", up:false },
    { sym:"BNB", price:"612.30",  delta:"+0.54%", up:true },
    { sym:"DOGE",price:"0.1821",  delta:"-1.12%", up:false },
  ];
  return (
    <div style={{ display:"flex", alignItems:"center", gap:2, overflow:"hidden", flex:1 }}>
      <span style={{ fontSize:7, color:C.nc, letterSpacing:2, flexShrink:0, padding:"0 8px" }}>CRYPTO</span>
      <div style={{ flex:1, overflow:"hidden", position:"relative" }}>
        <div style={{ display:"flex", gap:0, animation:"tickerScroll 20s linear infinite", whiteSpace:"nowrap" }}>
          {[...prices, ...prices].map((p, i) => (
            <span key={i} style={{ display:"inline-flex", gap:5, alignItems:"center", padding:"0 14px", borderRight:`1px solid ${C.b1}` }}>
              <span style={{ fontSize:8, fontWeight:"bold", color:C.tw }}>{p.sym}</span>
              <span style={{ fontSize:8, color:C.tm }}>{p.price}</span>
              <span style={{ fontSize:7, color:p.up?C.ng:C.red }}>{p.delta}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
function NewsTicker() {
  const news = [
    "REUTERS: Bitcoin breaks above $108k resistance — bulls target $112k",
    "BLOOMBERG: Fed signals rate hold — crypto markets rally 2.4%",
    "COINDESK: Polymarket volume hits $840M monthly record",
    "THE BLOCK: Ethereum ETF inflows reach $310M in 48 hours",
    "REUTERS: SOL surges 5% on Firedancer mainnet upgrade news",
  ];
  return (
    <div style={{ display:"flex", alignItems:"center", gap:2, flex:1.4, borderLeft:`1px solid ${C.b2}`, overflow:"hidden" }}>
      <span style={{ fontSize:7, color:C.nm, letterSpacing:2, flexShrink:0, padding:"0 8px" }}>NEWS</span>
      <div style={{ flex:1, overflow:"hidden" }}>
        <div style={{ display:"flex", gap:0, animation:"tickerScroll 35s linear infinite", whiteSpace:"nowrap" }}>
          {[...news, ...news].map((n, i) => (
            <span key={i} style={{ display:"inline-block", fontSize:8, color:C.tm, padding:"0 20px", borderRight:`1px solid ${C.b1}` }}>
              {n}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── MAIN DASHBOARD ─────────────────────────────────────────────────────────────
export function Dashboard() {
  const [time, setTime] = useState(() => new Date().toUTCString().slice(17, 25) + " UTC");
  useEffect(() => {
    const t = setInterval(() => setTime(new Date().toUTCString().slice(17, 25) + " UTC"), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{
      width:"100vw", height:"100vh", overflow:"hidden",
      background:C.bg, fontFamily:"'Courier New', Courier, monospace",
      fontSize:11, color:C.tm,
      display:"grid", gridTemplateRows:"42px 1fr 28px",
    }}>
      <style>{`
        @keyframes nodeRing    { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes pulseRing   { 0%{transform:scale(1);opacity:.6} 100%{transform:scale(1.6);opacity:0} }
        @keyframes flowEnergy  { 0%{left:-40%} 100%{left:100%} }
        @keyframes feedIn      { from{opacity:0;transform:translateY(-6px)} to{opacity:1;transform:translateY(0)} }
        @keyframes tickerScroll{ 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        @keyframes orbitRing   { from{transform:rotateX(70deg) rotate(0deg)} to{transform:rotateX(70deg) rotate(360deg)} }
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:2px} ::-webkit-scrollbar-track{background:transparent} ::-webkit-scrollbar-thumb{background:#111d2e;border-radius:2px}
      `}</style>

      {/* BG glows */}
      <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:0, background:`
        radial-gradient(ellipse 80% 40% at 50% 0%, rgba(0,229,255,.03) 0%, transparent 60%),
        radial-gradient(ellipse 40% 50% at 85% 60%, rgba(192,0,255,.018) 0%, transparent 50%),
        radial-gradient(ellipse 35% 40% at 12% 70%, rgba(57,255,20,.013) 0%, transparent 50%)
      ` }} />
      {/* Scanlines */}
      <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:9999, background:"repeating-linear-gradient(transparent,transparent 2px,rgba(0,0,0,.03) 2px,rgba(0,0,0,.03) 4px)" }} />

      {/* ── HEADER ────────────────────────────────────────────────────── */}
      <header style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0 20px", zIndex:100, position:"relative", borderBottom:`1px solid rgba(0,229,255,.1)`, background:"linear-gradient(135deg,rgba(0,229,255,.03) 0%,transparent 55%),rgba(6,9,15,.98)", boxShadow:`0 1px 0 rgba(0,229,255,.06),0 4px 24px rgba(0,0,0,.6)` }}>
        <div>
          <div style={{ fontSize:15, fontWeight:"bold", letterSpacing:7, color:C.nc, textShadow:`0 0 14px ${C.nc},0 0 32px rgba(0,229,255,.22)` }}>
            LIMWANPO // <span style={{ color:C.nm, textShadow:`0 0 14px ${C.nm}` }}>POLYMARKET AI</span>
          </div>
          <div style={{ fontSize:7, letterSpacing:5, color:C.tm, marginTop:1 }}>AI MISSION CONTROL · MARKET UNIVERSE V2</div>
        </div>
        <div style={{ display:"flex", gap:6, alignItems:"center" }}>
          {[
            { label:"PAPER MODE",     color:C.nc  },
            { label:"9 ENGINES LIVE", dot:C.ng    },
            { label:"12 MARKETS",     dot:C.nc    },
            { label:"3 SIGNALS",      dot:C.np    },
            { label:"1 OPEN",         dot:C.np    },
            { label:"CAPITAL OK",     dot:C.ng    },
          ].map(({ label, color, dot }, i) => (
            <div key={i} style={{ display:"flex", alignItems:"center", gap:5, padding:"3px 10px", border:`1px solid ${color?"rgba(0,229,255,.3)":C.b2}`, borderRadius:2, fontSize:9, letterSpacing:1.5, color:color||C.tm, background:color?"rgba(0,229,255,.06)":"rgba(0,0,0,.3)" }}>
              {dot && <Dot color={dot} />}
              {label}
            </div>
          ))}
          <div style={{ fontSize:9, color:C.tm, letterSpacing:1 }}>{time}</div>
        </div>
      </header>

      {/* ── BODY (scrollable) ─────────────────────────────────────────── */}
      <div style={{ overflowY:"auto", overflowX:"hidden", zIndex:1, position:"relative" }}>

        {/* ROW 1 — Portfolio | Chart | Health */}
        <div style={{ display:"grid", gridTemplateColumns:"260px 1fr 220px", gap:0, borderBottom:`1px solid ${C.b1}`, height:230 }}>
          <div style={{ borderRight:`1px solid ${C.b1}` }}><PortfolioSummary /></div>
          <div style={{ borderRight:`1px solid ${C.b1}` }}><LiveChart /></div>
          <SystemHealth />
        </div>

        {/* ROW 2 — Market Universe (THE HEART) */}
        <div style={{ borderBottom:`1px solid ${C.b1}` }}>
          <SectionTitle right="12 MARKETS · 4 ASSETS">Market Universe — Operational Center</SectionTitle>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:0 }}>
            {ASSETS.map((asset, ai) => (
              <div key={asset} style={{ borderRight:ai<3?`1px solid ${C.b1}`:"none", padding:"0 0 8px" }}>
                <AssetHeader asset={asset} />
                {MARKETS.filter(m => m.asset === asset).map((m, i) => (
                  <div key={i} style={{ padding:"0 8px" }}>
                    <MarketCardComp m={m} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ROW 3 — AI Decision Engine Pipeline */}
        <div style={{ borderBottom:`1px solid ${C.b1}` }}>
          <AIPipeline />
        </div>

        {/* ROW 4 — AI Feeds */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", height:240, borderBottom:`1px solid ${C.b1}` }}>
          <ThinkingFeed />
          <LiveFeed />
        </div>
      </div>

      {/* ── FOOTER ───────────────────────────────────────────────────── */}
      <footer style={{ display:"flex", alignItems:"stretch", zIndex:100, position:"relative", borderTop:`1px solid ${C.b1}`, background:"rgba(3,5,10,.97)", overflow:"hidden" }}>
        <CryptoTicker />
        <NewsTicker />
      </footer>
    </div>
  );
}
