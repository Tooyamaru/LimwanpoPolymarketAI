import { useEffect, useRef, useState } from "react";

const C = {
  bg: "#03050A", panel: "#06090F",
  b1: "#0b1320", b2: "#111d2e",
  ng: "#39FF14", nc: "#00E5FF", np: "#C000FF",
  nm: "#FF2D95", ny: "#FFE600", nb: "#4488FF",
  tw: "#dff0ff", tm: "#6b8fa8", td: "#3a5570",
  red: "#ff3355",
};

type Status = "WAIT" | "WATCH" | "READY" | "TRACKING" | "WIN" | "LOSS";
type Pos = "YES" | "NO" | "NONE";
interface MCard { asset: string; tf: string; countdown: string; resolveTime: string; targetPrice: string; currentPrice: string; prediction: "YES" | "NO"; confidence: number; position: Pos; entries: number; capital: number; pnl: number | null; status: Status; isTarget?: boolean; }

const MARKETS: MCard[] = [
  { asset:"BTC", tf:"5M",  countdown:"04:12", resolveTime:"14:55 UTC", targetPrice:"107,310", currentPrice:"107,182", prediction:"NO",  confidence:89, position:"NO",   entries:3, capital:125, pnl:8.6,  status:"TRACKING" },
  { asset:"BTC", tf:"15M", countdown:"11:42", resolveTime:"15:15 UTC", targetPrice:"107,310", currentPrice:"107,182", prediction:"YES", confidence:72, position:"NONE", entries:0, capital:0,   pnl:null, status:"WATCH", isTarget:true },
  { asset:"BTC", tf:"1H",  countdown:"38:05", resolveTime:"16:00 UTC", targetPrice:"107,500", currentPrice:"107,182", prediction:"YES", confidence:41, position:"NONE", entries:0, capital:0,   pnl:null, status:"WAIT" },
  { asset:"ETH", tf:"5M",  countdown:"02:47", resolveTime:"14:55 UTC", targetPrice:"3,520",   currentPrice:"3,487",   prediction:"NO",  confidence:78, position:"NO",   entries:2, capital:75,  pnl:-3.2, status:"TRACKING" },
  { asset:"ETH", tf:"15M", countdown:"09:33", resolveTime:"15:15 UTC", targetPrice:"3,520",   currentPrice:"3,487",   prediction:"NO",  confidence:63, position:"NONE", entries:0, capital:0,   pnl:null, status:"READY" },
  { asset:"ETH", tf:"1H",  countdown:"41:18", resolveTime:"16:00 UTC", targetPrice:"3,550",   currentPrice:"3,487",   prediction:"YES", confidence:34, position:"NONE", entries:0, capital:0,   pnl:null, status:"WAIT" },
  { asset:"SOL", tf:"5M",  countdown:"03:55", resolveTime:"14:55 UTC", targetPrice:"148.20",  currentPrice:"148.45",  prediction:"YES", confidence:81, position:"YES",  entries:4, capital:200, pnl:12.4, status:"TRACKING" },
  { asset:"SOL", tf:"15M", countdown:"10:21", resolveTime:"15:15 UTC", targetPrice:"148.20",  currentPrice:"148.45",  prediction:"YES", confidence:55, position:"NONE", entries:0, capital:0,   pnl:null, status:"WATCH" },
  { asset:"SOL", tf:"1H",  countdown:"39:44", resolveTime:"16:00 UTC", targetPrice:"150.00",  currentPrice:"148.45",  prediction:"YES", confidence:47, position:"NONE", entries:0, capital:0,   pnl:null, status:"WAIT" },
  { asset:"XRP", tf:"5M",  countdown:"01:30", resolveTime:"14:55 UTC", targetPrice:"0.5820",  currentPrice:"0.5791",  prediction:"NO",  confidence:66, position:"NONE", entries:0, capital:0,   pnl:null, status:"READY" },
  { asset:"XRP", tf:"15M", countdown:"08:50", resolveTime:"15:15 UTC", targetPrice:"0.5820",  currentPrice:"0.5791",  prediction:"NO",  confidence:44, position:"NONE", entries:0, capital:0,   pnl:null, status:"WAIT" },
  { asset:"XRP", tf:"1H",  countdown:"37:10", resolveTime:"16:00 UTC", targetPrice:"0.5900",  currentPrice:"0.5791",  prediction:"YES", confidence:29, position:"NONE", entries:0, capital:0,   pnl:null, status:"WAIT" },
];

const ASSETS = ["BTC","ETH","SOL","XRP"];
const ICONS: Record<string,string> = { BTC:"₿", ETH:"Ξ", SOL:"◎", XRP:"✕" };

function cardBorder(m: MCard) {
  if (m.isTarget)                                    return { b:"rgba(0,229,255,.45)",  bg:"rgba(0,229,255,.03)",  glow:"0 0 10px rgba(0,229,255,.15)" };
  if (m.position !== "NONE" && (m.pnl ?? 0) > 0)   return { b:"rgba(57,255,20,.38)",   bg:"rgba(57,255,20,.025)", glow:"0 0 8px rgba(57,255,20,.12)" };
  if (m.position !== "NONE" && (m.pnl ?? 0) < 0)   return { b:"rgba(255,51,85,.35)",   bg:"rgba(255,51,85,.025)", glow:"0 0 8px rgba(255,51,85,.1)" };
  if (m.status === "WATCH" || m.status === "READY") return { b:"rgba(255,230,0,.28)",   bg:"rgba(255,230,0,.018)", glow:"none" };
  return { b:C.b2, bg:"rgba(0,0,0,.15)", glow:"none" };
}
function statusColor(s: Status) {
  if (s === "TRACKING") return C.nc; if (s === "WIN") return C.ng;
  if (s === "LOSS")     return C.red; if (s === "READY") return C.ng;
  if (s === "WATCH")    return C.ny;  return C.td;
}
function confColor(c: number) {
  if (c >= 85) return C.ng;  if (c >= 70) return "#22ee55";
  if (c >= 55) return C.nc;  if (c >= 40) return C.ny; return C.td;
}
function Dot({ color, size=5, pulse=false }: { color:string; size?:number; pulse?:boolean }) {
  return (
    <span style={{ position:"relative", display:"inline-block", width:size, height:size, flexShrink:0 }}>
      <span style={{ position:"absolute", inset:0, borderRadius:"50%", background:color, opacity:.9 }} />
      {pulse && <span style={{ position:"absolute", inset:-2, borderRadius:"50%", border:`1px solid ${color}`, animation:"ledPulse 2s ease-out infinite", opacity:.6 }} />}
    </span>
  );
}
function PanelLabel({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div style={{ fontSize:7.5, letterSpacing:3, color:C.td, padding:"5px 12px 4px", borderBottom:`1px solid ${C.b1}`, textTransform:"uppercase", display:"flex", alignItems:"center", justifyContent:"space-between", background:"rgba(0,0,0,.2)", flexShrink:0 }}>
      <div style={{ display:"flex", alignItems:"center", gap:6 }}>
        <span style={{ display:"inline-block", width:2, height:8, borderRadius:1, background:C.nc, opacity:.6 }} />
        {children}
      </div>
      {right && <span style={{ fontSize:6.5, color:C.nc, letterSpacing:1.5, opacity:.7 }}>{right}</span>}
    </div>
  );
}

// ── PORTFOLIO SUMMARY ─────────────────────────────────────────────────────────
function PortfolioSummary() {
  const stats = [
    { l:"TOTAL VALUE",  v:"$4,280",  c:C.nc,  sub:"↑ $120 today" },
    { l:"OPEN POS",     v:"3",       c:C.tw,  sub:"BTC · SOL · ETH" },
    { l:"TOTAL PnL",    v:"+$17.8",  c:C.ng,  sub:"+0.42%" },
    { l:"WIN RATE",     v:"71%",     c:C.ng,  sub:"22 / 31 trades" },
    { l:"DAILY LOSS",   v:"3.2%",    c:C.ny,  sub:"Limit 10%" },
    { l:"CAPITAL",      v:"$400",    c:C.tm,  sub:"$4k available" },
  ];
  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <PanelLabel>Portfolio</PanelLabel>
      <div style={{ flex:1, display:"grid", gridTemplateColumns:"1fr 1fr", gap:1, padding:"8px 8px 6px", overflow:"hidden" }}>
        {stats.map(({ l, v, c, sub }) => (
          <div key={l} style={{ background:C.panel, border:`1px solid ${C.b2}`, borderRadius:2, padding:"6px 8px" }}>
            <div style={{ fontSize:6, color:C.td, letterSpacing:1.5, marginBottom:2 }}>{l}</div>
            <div style={{ fontSize:14, fontWeight:"bold", color:c, lineHeight:1, marginBottom:2 }}>{v}</div>
            <div style={{ fontSize:6.5, color:C.tm }}>{sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── LIVE MARKET CHART (candlestick) ──────────────────────────────────────────
interface Candle { o:number; h:number; l:number; c:number; v:number; }
function genCandles(n:number): Candle[] {
  const out:Candle[] = []; let price = 107182;
  for (let i=0; i<n; i++) {
    const o = price; const d = (Math.random()-0.485)*80;
    const c = o + d; const rng = Math.abs(d)*1.8 + Math.random()*30;
    const h = Math.max(o,c) + Math.random()*rng*0.5;
    const l = Math.min(o,c) - Math.random()*rng*0.5;
    const v = 200 + Math.random()*800;
    out.push({ o:Math.round(o), h:Math.round(h), l:Math.round(l), c:Math.round(c), v:Math.round(v) });
    price = c;
  }
  return out;
}

function LiveChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef  = useRef<number>(0);
  const candlesRef = useRef<Candle[]>([]);
  const tickRef   = useRef(0);
  const [livePrice, setLivePrice] = useState(107182);
  const H24_OPEN = 106540;

  useEffect(() => {
    candlesRef.current = genCandles(60);
    let blinkOn = true; let blinkT = 0;

    function draw() {
      const canvas = canvasRef.current; if (!canvas) return;
      const ctx = canvas.getContext("2d"); if (!ctx) return;
      const W = canvas.width, H = canvas.height;
      const VOLS = 28; const chartH = H - VOLS - 2;
      const PAD_L = 52, PAD_R = 8, PAD_T = 8;

      tickRef.current++;
      blinkT++; if (blinkT > 30) { blinkOn = !blinkOn; blinkT = 0; }
      if (tickRef.current % 60 === 0) {
        const candles = candlesRef.current;
        const last = candles[candles.length-1];
        const o = last.c; const d = (Math.random()-0.485)*70;
        const c = o+d; const rng = Math.abs(d)*1.6+Math.random()*25;
        candles.push({ o:Math.round(o), h:Math.round(Math.max(o,c)+Math.random()*rng*0.5), l:Math.round(Math.min(o,c)-Math.random()*rng*0.5), c:Math.round(c), v:Math.round(200+Math.random()*700) });
        if (candles.length > 70) candles.shift();
        setLivePrice(Math.round(c));
      }

      ctx.clearRect(0, 0, W, H);
      const candles = candlesRef.current;
      const prices = candles.flatMap(c=>[c.h,c.l]);
      const mn = Math.min(...prices), mx = Math.max(...prices), prng = mx-mn||200;
      const vols = candles.map(c=>c.v), mvol = Math.max(...vols);
      const cw = (W - PAD_L - PAD_R) / candles.length;
      const py = (v:number) => PAD_T + (1-(v-mn)/prng)*(chartH-PAD_T);

      // Session H/L
      const sHigh = Math.max(...candles.slice(-20).map(c=>c.h));
      const sLow  = Math.min(...candles.slice(-20).map(c=>c.l));
      ctx.setLineDash([2,6]); ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(57,255,20,.35)"; ctx.beginPath(); ctx.moveTo(PAD_L,py(sHigh)); ctx.lineTo(W-PAD_R,py(sHigh)); ctx.stroke();
      ctx.strokeStyle = "rgba(255,51,85,.35)"; ctx.beginPath(); ctx.moveTo(PAD_L,py(sLow));  ctx.lineTo(W-PAD_R,py(sLow));  ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = "7px Courier New"; ctx.textAlign = "right";
      ctx.fillStyle = "rgba(57,255,20,.65)"; ctx.fillText("H "+sHigh.toLocaleString(), PAD_L-3, py(sHigh)+3);
      ctx.fillStyle = "rgba(255,51,85,.65)"; ctx.fillText("L "+sLow.toLocaleString(),  PAD_L-3, py(sLow)+3);

      // Grid lines
      ctx.textAlign = "right";
      for (let i=0; i<=4; i++) {
        const val = mx - (i/4)*prng; const y = py(val);
        ctx.strokeStyle = "rgba(17,29,46,.9)"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(PAD_L,y); ctx.lineTo(W-PAD_R,y); ctx.stroke();
        ctx.fillStyle = "rgba(107,143,168,.55)"; ctx.font = "7px Courier New";
        ctx.fillText(Math.round(val).toLocaleString(), PAD_L-4, y+2.5);
      }

      // Volume bars
      candles.forEach((c,i) => {
        const x = PAD_L + i*cw; const bh = (c.v/mvol)*VOLS;
        ctx.fillStyle = c.c >= c.o ? "rgba(57,255,20,.22)" : "rgba(255,51,85,.22)";
        ctx.fillRect(x+1, H-bh, cw-2, bh);
      });

      // Candlesticks
      candles.forEach((c,i) => {
        const x = PAD_L + i*cw + cw/2; const oh=py(c.o), ch=py(c.c), hh=py(c.h), lh=py(c.l);
        const bull = c.c >= c.o; const color = bull ? C.ng : C.red;
        ctx.strokeStyle = color+"99"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x,hh); ctx.lineTo(x,lh); ctx.stroke();
        const bodyTop=Math.min(oh,ch), bodyH=Math.max(1,Math.abs(oh-ch));
        ctx.fillStyle = i===candles.length-1 ? color : (bull ? color+"66" : color+"55");
        ctx.fillRect(x-cw*0.35, bodyTop, cw*0.7, bodyH);
        if (i===candles.length-1) {
          ctx.strokeStyle = color; ctx.lineWidth = 1;
          ctx.strokeRect(x-cw*0.35, bodyTop, cw*0.7, bodyH);
        }
      });

      // Last price dashed line + label
      const lastClose = candles[candles.length-1].c; const ly = py(lastClose);
      ctx.setLineDash([3,5]); ctx.strokeStyle = "rgba(0,229,255,.4)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PAD_L,ly); ctx.lineTo(W-PAD_R,ly); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = blinkOn ? C.nc : "rgba(0,229,255,.3)";
      ctx.fillRect(W-PAD_R+2, ly-6, 1, 12);
      ctx.textAlign = "left"; ctx.font = "bold 8px Courier New"; ctx.fillStyle = C.nc;
      ctx.fillText(lastClose.toLocaleString(), W-PAD_R+4, ly+3);

      frameRef.current = requestAnimationFrame(draw);
    }
    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, []);

  const delta = livePrice - H24_OPEN;
  const deltaPct = ((delta/H24_OPEN)*100).toFixed(2);
  const up = delta >= 0; const dc = up ? C.ng : C.red;

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <PanelLabel right="BTC/USD · 5M">Live Market Chart</PanelLabel>
      <div style={{ flex:1, position:"relative", padding:"2px 2px 2px" }}>
        <canvas ref={canvasRef} style={{ width:"100%", height:"100%", display:"block" }} width={900} height={220} />

        {/* Bloomberg info panel */}
        <div style={{ position:"absolute", top:6, left:58, background:"rgba(3,5,10,.9)", border:`1px solid ${C.b2}`, borderRadius:2, padding:"6px 10px", minWidth:130, boxShadow:"0 2px 12px rgba(0,0,0,.7)" }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:3 }}>
            <span style={{ fontSize:7, color:C.td, letterSpacing:2 }}>BTC / USD</span>
            <span style={{ fontSize:6, color:C.ng, letterSpacing:1, animation:"liveBlink 1.4s ease-in-out infinite" }}>● LIVE</span>
          </div>
          <div style={{ fontSize:20, fontWeight:"bold", color:C.nc, lineHeight:1, letterSpacing:.5, marginBottom:3, textShadow:`0 0 12px rgba(0,229,255,.5)` }}>
            {livePrice.toLocaleString()}
          </div>
          <div style={{ display:"flex", gap:5, marginBottom:5 }}>
            <span style={{ fontSize:9, fontWeight:"bold", color:dc }}>{up?"+":""}{delta.toLocaleString()}</span>
            <span style={{ fontSize:8, color:dc }}>{up?"+":""}{deltaPct}%</span>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"2px 8px" }}>
            {[{ l:"24H H", v:"108,440" },{ l:"24H L", v:"106,120" },{ l:"VOLUME", v:"28.4B" },{ l:"SESSION", v:"7.2H" }].map(({ l, v }) => (
              <div key={l}><div style={{ fontSize:5.5, color:C.td }}>{l}</div><div style={{ fontSize:7, color:C.tm, fontWeight:"bold" }}>{v}</div></div>
            ))}
          </div>
        </div>

        {/* TF tabs */}
        <div style={{ position:"absolute", top:6, right:6, display:"flex", gap:3 }}>
          {["5M","15M","1H"].map((tf,i) => (
            <div key={tf} style={{ fontSize:7, padding:"2px 6px", border:`1px solid ${i===0?C.nc:C.b2}`, color:i===0?C.nc:C.td, borderRadius:1, background:i===0?"rgba(0,229,255,.07)":"transparent" }}>{tf}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── SYSTEM HEALTH ─────────────────────────────────────────────────────────────
function SystemHealth() {
  const engines = [
    { name:"Universe",    val:"99.8%" }, { name:"Signal",     val:"98.7%" },
    { name:"Opportunity", val:"98.9%" }, { name:"Strategy",   val:"99.6%" },
    { name:"Risk",        val:"99.5%" }, { name:"Execution",  val:"99.1%" },
    { name:"Exit",        val:"99.4%" }, { name:"Analytics",  val:"98.5%" },
    { name:"Portfolio",   val:"99.3%" }, { name:"Capital",    val:"100%" },
  ];
  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <PanelLabel right="10/10">System Health</PanelLabel>
      <div style={{ flex:1, overflowY:"auto", padding:"6px 8px", display:"flex", flexDirection:"column", gap:2 }}>
        {engines.map(({ name, val }) => (
          <div key={name} style={{ display:"flex", alignItems:"center", gap:6, padding:"4px 8px", background:"rgba(6,9,15,.8)", border:`1px solid ${C.b1}`, borderRadius:2, borderLeft:`2px solid ${C.ng}` }}>
            <Dot color={C.ng} size={4} pulse />
            <span style={{ fontSize:7.5, color:C.tm, flex:1, letterSpacing:.3 }}>{name}</span>
            <span style={{ fontSize:7.5, fontWeight:"bold", color:C.ng }}>{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── ASSET HEADER ─────────────────────────────────────────────────────────────
function AssetHeader({ asset }: { asset: string }) {
  const cards = MARKETS.filter(m => m.asset === asset);
  const conf = Math.round(cards.reduce((a,m)=>a+m.confidence,0)/cards.length);
  const pos  = cards.filter(m=>m.position!=="NONE").length;
  const cap  = cards.reduce((a,m)=>a+m.capital,0);
  const pnl  = cards.reduce((a,m)=>a+(m.pnl??0),0);
  const pc   = pnl>0?C.ng:pnl<0?C.red:C.td;
  const cc   = confColor(conf);
  const r    = 13; const circ = 2*Math.PI*r;
  const dash = circ - (conf/100)*circ;
  return (
    <div style={{ background:`linear-gradient(90deg,rgba(0,229,255,.06),transparent)`, borderBottom:`1px solid rgba(0,229,255,.14)`, borderTop:`1px solid ${C.b1}`, marginBottom:3 }}>
      <div style={{ height:1.5, background:`linear-gradient(90deg,${cc},transparent)` }} />
      <div style={{ padding:"7px 10px 8px" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:5 }}>
          <div style={{ display:"flex", alignItems:"center", gap:7 }}>
            <span style={{ fontSize:14, color:C.nc }}>{ICONS[asset]}</span>
            <div>
              <div style={{ fontSize:12, fontWeight:"bold", color:C.nc, letterSpacing:1.5, lineHeight:1 }}>{asset}</div>
              <div style={{ fontSize:6, color:C.td, letterSpacing:.5, marginTop:1 }}>3 MARKETS{pos>0?` · ${pos} ACTIVE`:""}</div>
            </div>
          </div>
          <div style={{ position:"relative", width:32, height:32 }}>
            <svg width="32" height="32" style={{ transform:"rotate(-90deg)" }}>
              <circle cx="16" cy="16" r={r} fill="none" stroke={`${cc}20`} strokeWidth="2"/>
              <circle cx="16" cy="16" r={r} fill="none" stroke={cc} strokeWidth="2" strokeDasharray={circ} strokeDashoffset={dash} strokeLinecap="round" style={{ filter:`drop-shadow(0 0 2px ${cc})` }}/>
            </svg>
            <div style={{ position:"absolute", inset:0, display:"flex", alignItems:"center", justifyContent:"center", flexDirection:"column" }}>
              <span style={{ fontSize:7.5, fontWeight:"bold", color:cc, lineHeight:1 }}>{conf}</span>
            </div>
          </div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:3 }}>
          {[
            { l:"POS",     v:pos>0?`${pos}`:"—",             c:pos>0?C.nc:C.td },
            { l:"CAPITAL", v:cap>0?`$${cap}`:"—",             c:cap>0?C.tw:C.td },
            { l:"PnL",     v:pnl!==0?(pnl>0?`+$${pnl.toFixed(1)}`:`-$${Math.abs(pnl).toFixed(1)}`):"—", c:pc },
          ].map(({ l, v, c }) => (
            <div key={l} style={{ textAlign:"center", background:"rgba(0,0,0,.2)", borderRadius:2, padding:"3px 0", border:`1px solid ${C.b1}` }}>
              <div style={{ fontSize:5.5, color:C.td, letterSpacing:.8 }}>{l}</div>
              <div style={{ fontSize:9, fontWeight:"bold", color:c }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── CONFIDENCE RING ──────────────────────────────────────────────────────────
function ConfRing({ conf, size=38 }: { conf:number; size?:number }) {
  const r = size/2 - 4; const circ = 2*Math.PI*r; const cc = confColor(conf);
  const dash = circ - (conf/100)*circ;
  return (
    <div style={{ position:"relative", width:size, height:size, flexShrink:0 }}>
      <svg width={size} height={size} style={{ transform:"rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={`${cc}18`} strokeWidth="2"/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={cc} strokeWidth="2" strokeDasharray={circ} strokeDashoffset={dash} strokeLinecap="round" style={{ filter:`drop-shadow(0 0 2px ${cc})` }}/>
      </svg>
      <div style={{ position:"absolute", inset:0, display:"flex", alignItems:"center", justifyContent:"center", flexDirection:"column" }}>
        <span style={{ fontSize:8, fontWeight:"bold", color:cc, lineHeight:1 }}>{conf}</span>
        <span style={{ fontSize:5, color:C.td, lineHeight:1 }}>%</span>
      </div>
    </div>
  );
}

// ── MARKET CARD ──────────────────────────────────────────────────────────────
function MarketCardComp({ m }: { m: MCard }) {
  const { b, bg, glow } = cardBorder(m);
  const predColor = m.prediction === "YES" ? C.ng : C.nm;
  const posColor  = m.position === "YES" ? C.ng : m.position === "NO" ? C.nm : C.td;
  const pnlColor  = m.pnl===null ? C.td : m.pnl>0 ? C.ng : C.red;
  const pnlStr    = m.pnl===null ? "—" : m.pnl>0 ? `+${m.pnl}%` : `${m.pnl}%`;
  const sc        = statusColor(m.status);
  return (
    <div style={{ border:`1px solid ${b}`, background:bg, boxShadow:glow, borderRadius:2, padding:"7px 8px 6px", marginBottom:4, position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", left:0, top:0, bottom:0, width:2, background:b, opacity:.7 }} />

      {/* ① Countdown + TF + Conf ring */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:5, paddingLeft:4 }}>
        <div>
          <div style={{ fontSize:7, color:C.td, letterSpacing:1.5, marginBottom:1 }}>{m.tf}</div>
          <div style={{ fontSize:19, fontWeight:"bold", color:sc, lineHeight:1, letterSpacing:.5 }}>{m.countdown}</div>
          <div style={{ fontSize:6, color:C.td, marginTop:1 }}>{m.resolveTime}</div>
        </div>
        <ConfRing conf={m.confidence} size={38} />
      </div>

      {/* ② YES / NO banner */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", background:`${predColor}12`, border:`1px solid ${predColor}44`, borderRadius:2, padding:"5px 9px", marginBottom:5 }}>
        <div style={{ display:"flex", alignItems:"center", gap:7 }}>
          <span style={{ fontSize:15, fontWeight:"bold", color:predColor, letterSpacing:2, textShadow:`0 0 10px ${predColor}` }}>{m.prediction}</span>
          <span style={{ fontSize:6.5, color:predColor, opacity:.65, letterSpacing:.5 }}>AI PREDICTS</span>
        </div>
        {m.isTarget && <span style={{ fontSize:6, color:C.nc, border:`1px solid rgba(0,229,255,.3)`, padding:"1px 5px", borderRadius:1, letterSpacing:.5 }}>TARGET</span>}
      </div>

      {/* ③ Prices */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:3, marginBottom:4 }}>
        {[{ l:"TARGET", v:m.targetPrice, c:C.td },{ l:"CURRENT", v:m.currentPrice, c:C.tw }].map(({ l, v, c }) => (
          <div key={l} style={{ background:"rgba(0,0,0,.18)", borderRadius:1, padding:"3px 5px", border:`1px solid ${C.b1}` }}>
            <div style={{ fontSize:5.5, color:C.td, letterSpacing:.8 }}>{l}</div>
            <div style={{ fontSize:7.5, fontWeight:"bold", color:c }}>{v}</div>
          </div>
        ))}
      </div>

      {/* ④ Portfolio */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:2, background:"rgba(0,0,0,.18)", border:`1px solid ${C.b1}`, borderRadius:1, padding:"3px 4px", marginBottom:4 }}>
        {[
          { l:"POS",  v:m.position,                       c:posColor },
          { l:"BUYS", v:`${m.entries}`,                   c:m.entries>0?C.tw:C.td },
          { l:"CAP",  v:m.capital>0?`$${m.capital}`:"—", c:m.capital>0?C.tw:C.td },
          { l:"PNL",  v:pnlStr,                           c:pnlColor },
        ].map(({ l, v, c }) => (
          <div key={l} style={{ textAlign:"center" }}>
            <div style={{ fontSize:5.5, color:C.td, letterSpacing:.3 }}>{l}</div>
            <div style={{ fontSize:7.5, fontWeight:"bold", color:c }}>{v}</div>
          </div>
        ))}
      </div>

      {/* ⑤ Status */}
      <div style={{ display:"flex", alignItems:"center", gap:4, paddingLeft:4 }}>
        <Dot color={sc} size={5} pulse={m.status==="TRACKING"} />
        <span style={{ fontSize:6.5, fontWeight:"bold", color:sc, letterSpacing:2 }}>{m.status}</span>
      </div>
    </div>
  );
}

// ── AI PIPELINE ───────────────────────────────────────────────────────────────
const NODE_COLORS: Record<string,string> = {
  Universe:"#00E5FF", Signal:"#4488FF", Opportunity:"#C000FF",
  Strategy:"#FFE600", Risk:"#39FF14",  Execution:"#ff3355",
};

function PipelineNode({ name, count, active, icon }: { name:string; count:string; active:boolean; icon:React.ReactNode }) {
  const col = NODE_COLORS[name] ?? C.nc;
  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:7, flex:1 }}>
      <div style={{ position:"relative", width:64, height:64 }}>
        <div style={{ position:"absolute", inset:0, borderRadius:"50%", border:`1px solid ${col}${active?"44":"18"}`, animation:active?"nodeRing 5s linear infinite":"none", boxShadow:active?`0 0 18px ${col}33`:"none" }} />
        {active && <div style={{ position:"absolute", inset:5, borderRadius:"50%", border:`1px solid ${col}22`, animation:"nodeRingRev 7s linear infinite" }} />}
        <div style={{ position:"absolute", inset:9, borderRadius:"50%", background:active?`radial-gradient(circle,${col}30 0%,${col}08 60%,transparent 100%)`:"rgba(0,0,0,.35)", border:`1px solid ${col}${active?"40":"14"}`, display:"flex", alignItems:"center", justifyContent:"center", boxShadow:active?`0 0 10px ${col}30`:"none", animation:active?"nodeGlow 2.5s ease-in-out infinite":"none" }}>
          {icon}
        </div>
        {active && <div style={{ position:"absolute", inset:-5, borderRadius:"50%", border:`1px solid ${col}44`, animation:"pulseRing 2.5s ease-out infinite" }} />}
      </div>
      <div style={{ textAlign:"center" }}>
        <div style={{ fontSize:7.5, fontWeight:"bold", color:col, letterSpacing:2, textShadow:active?`0 0 8px ${col}66`:"none" }}>{name.toUpperCase()}</div>
        <div style={{ fontSize:8, color:active?C.tw:C.td, marginTop:2 }}>{count}</div>
      </div>
    </div>
  );
}

function FlowConnector({ left, right, active }: { left:string; right:string; active:boolean }) {
  const col = active ? left : C.b2;
  return (
    <div style={{ flex:1, display:"flex", alignItems:"center", paddingBottom:28 }}>
      <div style={{ flex:1, height:2, position:"relative", background:`${col}18`, borderRadius:1, overflow:"hidden" }}>
        <div style={{ position:"absolute", inset:0, backgroundImage:`repeating-linear-gradient(90deg,${col}20 0,${col}20 1px,transparent 1px,transparent 10px)` }} />
        {active && <>
          <div style={{ position:"absolute", top:0, height:"100%", width:"30%", background:`linear-gradient(90deg,transparent,${left},transparent)`, animation:"flowEnergy 1.6s linear infinite" }} />
          <div style={{ position:"absolute", top:0, height:"100%", width:"20%", background:`linear-gradient(90deg,transparent,${right}88,transparent)`, animation:"flowEnergy 1.6s linear infinite .8s" }} />
        </>}
      </div>
    </div>
  );
}

function AIPipeline() {
  const [active, setActive] = useState(2);
  useEffect(() => {
    const t = setInterval(() => setActive(n => (n+1)%6), 2800);
    return () => clearInterval(t);
  }, []);

  const nodes = [
    { name:"Universe",    count:"12 markets", icon:<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke={active===0?"#00E5FF":C.td} strokeWidth="1" opacity=".7"/><ellipse cx="12" cy="12" rx="9" ry="3.5" stroke={active===0?"#00E5FF":C.td} strokeWidth=".8" style={{animationName:"orbitRing",animationDuration:"6s",animationIterationCount:"infinite",animationTimingFunction:"linear"}}/><circle cx="12" cy="12" r="2" fill={active===0?"#00E5FF":C.td} opacity=".9"/></svg> },
    { name:"Signal",      count:"3 active",   icon:<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="2.5" fill={active===1?"#4488FF":C.td}/>{[6,9.5,13].map((r,i)=><circle key={r} cx="12" cy="12" r={r} stroke={active===1?"#4488FF":C.td} strokeWidth=".7" opacity={.7-i*.18}/>)}</svg> },
    { name:"Opportunity", count:"2 scored",   icon:<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><polygon points="12,3 19.5,8.5 19.5,15.5 12,21 4.5,15.5 4.5,8.5" stroke={active===2?"#C000FF":C.td} strokeWidth="1" fill={active===2?"rgba(192,0,255,.12)":"none"}/><polygon points="12,7.5 16.5,10.5 16.5,13.5 12,16.5 7.5,13.5 7.5,10.5" stroke={active===2?"#C000FF":C.td} strokeWidth=".7" fill="none"/><circle cx="12" cy="12" r="1.8" fill={active===2?"#C000FF":C.td}/></svg> },
    { name:"Strategy",    count:"1 queued",   icon:<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><polygon points="12,4 20,8.5 20,15.5 12,20 4,15.5 4,8.5" stroke={active===3?"#FFE600":C.td} strokeWidth="1" fill={active===3?"rgba(255,230,0,.08)":"none"}/><circle cx="12" cy="12" r="2.5" fill={active===3?"#FFE600":C.td} opacity=".9"/></svg> },
    { name:"Risk",        count:"1 approved", icon:<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M12 3L20 7v7q0 4-8 7q-8-3-8-7V7Z" stroke={active===4?"#39FF14":C.td} strokeWidth="1" fill={active===4?"rgba(57,255,20,.07)":"none"}/><path d="M8.5 12l2.5 2.5 4.5-4.5" stroke={active===4?"#39FF14":C.td} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg> },
    { name:"Execution",   count:"3 trades",   icon:<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8" stroke={active===5?"#ff3355":C.td} strokeWidth="1" fill="none"/><circle cx="12" cy="12" r="4.5" stroke={active===5?"#ff3355":C.td} strokeWidth=".8" fill={active===5?"rgba(255,51,85,.1)":"none"}/><circle cx="12" cy="12" r="1.8" fill={active===5?"#ff3355":C.td} opacity=".95"/></svg> },
  ];
  const nodeNames = nodes.map(n=>n.name);

  return (
    <div style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <PanelLabel right={`${nodeNames[active]} ACTIVE`}>AI Decision Engine</PanelLabel>
      <div style={{ padding:"14px 16px 10px", display:"flex", alignItems:"center" }}>
        {nodes.map((n,i) => (
          <div key={n.name} style={{ display:"contents" }}>
            <PipelineNode {...n} active={active===i} />
            {i < nodes.length-1 && (
              <FlowConnector left={NODE_COLORS[n.name]} right={NODE_COLORS[nodes[i+1].name]} active={active===i || active===i+1} />
            )}
          </div>
        ))}
      </div>
      {/* Status + operational bar */}
      <div style={{ margin:"0 16px 10px", display:"flex", gap:6 }}>
        <div style={{ flex:1, padding:"4px 10px", background:"rgba(0,0,0,.25)", border:`1px solid ${C.b1}`, borderLeft:`2px solid ${NODE_COLORS[nodeNames[active]]}`, borderRadius:2, display:"flex", alignItems:"center", gap:7 }}>
          <Dot color={NODE_COLORS[nodeNames[active]]} size={4} pulse />
          <span style={{ fontSize:7.5, color:NODE_COLORS[nodeNames[active]], fontWeight:"bold", letterSpacing:1.5 }}>{nodeNames[active].toUpperCase()}</span>
          <span style={{ fontSize:7.5, color:C.tm }}>BTC 15M YES · confidence 72% · awaiting next stage…</span>
        </div>
        {/* Operational stats */}
        <div style={{ display:"flex", gap:4, alignItems:"center" }}>
          {[
            { l:"LAT",  v:"12ms",  c:C.ng },
            { l:"WS",   v:"OK",    c:C.ng },
            { l:"CPU",  v:"8%",    c:C.ng },
            { l:"MEM",  v:"42%",   c:C.ny },
            { l:"PING", v:"4ms",   c:C.ng },
          ].map(({ l, v, c }) => (
            <div key={l} style={{ textAlign:"center", padding:"3px 7px", background:"rgba(0,0,0,.25)", border:`1px solid ${C.b1}`, borderRadius:2 }}>
              <div style={{ fontSize:5.5, color:C.td, letterSpacing:.5 }}>{l}</div>
              <div style={{ fontSize:7.5, fontWeight:"bold", color:c }}>{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── BADGE COLORS ──────────────────────────────────────────────────────────────
const BADGE: Record<string, string> = {
  INFO:"#00E5FF", SYS:"#6b8fa8", SYSTEM:"#6b8fa8", SIGNAL:"#4488FF",
  ENTRY:"#39FF14", EXIT:"#FFE600", WARNING:"#FFE600", RISK:"#ff3355",
  OPP:"#C000FF", EXEC:"#FF2D95", EXECUTED:"#FF2D95", SUCCESS:"#39FF14",
  BLOCKED:"#ff3355", STRAT:"#FFE600",
};

function ThinkingFeed() {
  const items = [
    { time:"14:44:02", tag:"SIGNAL", msg:"BTC 15M — mid=0.505 move=+0.004 — confidence 74%→72% — Decision: WATCH" },
    { time:"14:43:55", tag:"SYS",    msg:"SOL 5M — Position TRACKING +12.4% — monitoring for exit trigger" },
    { time:"14:43:41", tag:"RISK",   msg:"ETH 5M — Position TRACKING -3.2% — stop-loss threshold -15% — holding" },
    { time:"14:43:30", tag:"OPP",    msg:"XRP 5M — Opportunity score 78 — READY threshold reached" },
    { time:"14:43:15", tag:"SYS",    msg:"Universe sync complete — 12 markets active · 4 assets" },
    { time:"14:43:00", tag:"ENTRY",  msg:"BTC 5M — NO position opened @ 0.505 — $42 — paper trade" },
    { time:"14:42:44", tag:"INFO",   msg:"ETH 15M — Exposure check PASSED — DAILY_LOSS 3.2% < 10%" },
    { time:"14:42:30", tag:"STRAT",  msg:"SOL 1H — confidence 47% below threshold — market SKIPPED" },
  ];
  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <PanelLabel right="LIVE">AI Thinking Feed</PanelLabel>
      <div style={{ flex:1, overflowY:"auto", padding:"2px 0" }}>
        {items.map((item,i) => {
          const bc = BADGE[item.tag] ?? C.td;
          return (
            <div key={i} style={{ padding:"4px 10px", borderBottom:`1px solid rgba(11,19,32,.6)`, display:"flex", gap:6, alignItems:"flex-start" }}>
              <span style={{ fontSize:6.5, color:C.td, flexShrink:0, marginTop:1, minWidth:46 }}>{item.time}</span>
              <span style={{ fontSize:6, fontWeight:"bold", color:bc, background:`${bc}14`, border:`1px solid ${bc}28`, padding:"0 4px", borderRadius:1, flexShrink:0, letterSpacing:.5 }}>{item.tag}</span>
              <span style={{ fontSize:7.5, color:C.tm, lineHeight:1.45 }}>{item.msg}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
function LiveFeed() {
  const items = [
    { tag:"SIGNAL",   msg:"BTC 15M mid=0.505 move=+0.004 → signal generated" },
    { tag:"EXECUTED", msg:"SOL 5M YES filled @ 0.505 — $50 — paper" },
    { tag:"INFO",     msg:"ETH 5M risk approved — exposure within limits" },
    { tag:"SYS",      msg:"12 markets price-refreshed in 847ms" },
    { tag:"OPP",      msg:"XRP 5M opportunity score 78 — READY threshold" },
    { tag:"EXIT",     msg:"BTC 5M NO monitored — profit +8.6% — hold" },
    { tag:"RISK",     msg:"Daily loss 3.2% — within parameters — OK" },
    { tag:"STRAT",    msg:"ETH 15M READY — queued for execution engine" },
  ];
  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden", borderLeft:`1px solid ${C.b1}` }}>
      <PanelLabel right="LIVE">AI Live Feed</PanelLabel>
      <div style={{ flex:1, overflowY:"auto", padding:"2px 0" }}>
        {items.map((item,i) => {
          const bc = BADGE[item.tag] ?? C.td;
          return (
            <div key={i} style={{ padding:"4px 10px", borderBottom:`1px solid rgba(11,19,32,.6)`, display:"flex", gap:6, alignItems:"center" }}>
              <span style={{ fontSize:6, fontWeight:"bold", color:bc, background:`${bc}14`, border:`1px solid ${bc}28`, padding:"0 4px", borderRadius:1, flexShrink:0, letterSpacing:.5 }}>{item.tag}</span>
              <span style={{ fontSize:7.5, color:C.tm }}>{item.msg}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── FOOTER ───────────────────────────────────────────────────────────────────
function CryptoTicker() {
  const prices = [
    { sym:"BTC", p:"107,182", d:"+0.32%", up:true }, { sym:"ETH", p:"3,487",  d:"+0.81%", up:true },
    { sym:"SOL", p:"148.45",  d:"+1.24%", up:true }, { sym:"XRP", p:"0.5791", d:"-0.38%", up:false },
    { sym:"BNB", p:"612.30",  d:"+0.54%", up:true }, { sym:"DOGE",p:"0.1821", d:"-1.12%", up:false },
  ];
  return (
    <div style={{ display:"flex", alignItems:"center", flex:1, overflow:"hidden" }}>
      <span style={{ fontSize:6.5, color:C.nc, letterSpacing:2, flexShrink:0, padding:"0 8px", borderRight:`1px solid ${C.b1}` }}>CRYPTO</span>
      <div style={{ flex:1, overflow:"hidden" }}>
        <div style={{ display:"flex", animation:"tickerScroll 22s linear infinite", whiteSpace:"nowrap" }}>
          {[...prices,...prices].map((p,i) => (
            <span key={i} style={{ display:"inline-flex", gap:5, alignItems:"center", padding:"0 12px", borderRight:`1px solid ${C.b1}` }}>
              <span style={{ fontSize:7.5, fontWeight:"bold", color:C.tw }}>{p.sym}</span>
              <span style={{ fontSize:7.5, color:C.tm }}>{p.p}</span>
              <span style={{ fontSize:7, color:p.up?C.ng:C.red }}>{p.d}</span>
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
    <div style={{ display:"flex", alignItems:"center", flex:1.5, borderLeft:`1px solid ${C.b1}`, overflow:"hidden" }}>
      <span style={{ fontSize:6.5, color:C.nm, letterSpacing:2, flexShrink:0, padding:"0 8px", borderRight:`1px solid ${C.b1}` }}>NEWS</span>
      <div style={{ flex:1, overflow:"hidden" }}>
        <div style={{ display:"flex", animation:"tickerScroll 38s linear infinite", whiteSpace:"nowrap" }}>
          {[...news,...news].map((n,i) => (
            <span key={i} style={{ display:"inline-block", fontSize:7.5, color:C.tm, padding:"0 18px", borderRight:`1px solid ${C.b1}` }}>{n}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── MAIN DASHBOARD ────────────────────────────────────────────────────────────
export function Dashboard() {
  const [time, setTime] = useState(() => new Date().toUTCString().slice(17,25)+" UTC");
  useEffect(() => {
    const t = setInterval(() => setTime(new Date().toUTCString().slice(17,25)+" UTC"), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div style={{ width:"100vw", height:"100vh", overflow:"hidden", background:C.bg, fontFamily:"'Courier New',Courier,monospace", fontSize:11, color:C.tm, display:"grid", gridTemplateRows:"40px 1fr 26px" }}>
      <style>{`
        @keyframes nodeRing    { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes nodeRingRev { from{transform:rotate(0deg)} to{transform:rotate(-360deg)} }
        @keyframes nodeGlow    { 0%,100%{opacity:1} 50%{opacity:.65} }
        @keyframes pulseRing   { 0%{transform:scale(1);opacity:.6} 100%{transform:scale(1.7);opacity:0} }
        @keyframes flowEnergy  { 0%{left:-35%} 100%{left:115%} }
        @keyframes feedIn      { from{opacity:0;transform:translateY(-5px)} to{opacity:1;transform:translateY(0)} }
        @keyframes tickerScroll{ 0%{transform:translateX(0)} 100%{transform:translateX(-50%)} }
        @keyframes orbitRing   { from{transform:rotateX(66deg) rotate(0deg)} to{transform:rotateX(66deg) rotate(360deg)} }
        @keyframes liveBlink   { 0%,100%{opacity:1} 50%{opacity:.2} }
        @keyframes ledPulse    { 0%{transform:scale(1);opacity:.6} 100%{transform:scale(2.2);opacity:0} }
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:2px} ::-webkit-scrollbar-track{background:transparent} ::-webkit-scrollbar-thumb{background:#111d2e;border-radius:2px}
      `}</style>

      {/* BG ambient */}
      <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:0, background:"radial-gradient(ellipse 80% 40% at 50% 0%,rgba(0,229,255,.025) 0%,transparent 55%),radial-gradient(ellipse 35% 40% at 85% 65%,rgba(192,0,255,.015) 0%,transparent 50%)" }} />
      {/* Scanlines */}
      <div style={{ position:"fixed", inset:0, pointerEvents:"none", zIndex:9999, background:"repeating-linear-gradient(transparent,transparent 2px,rgba(0,0,0,.025) 2px,rgba(0,0,0,.025) 4px)" }} />

      {/* ── HEADER ────────────────────────────────────────────────────── */}
      <header style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0 20px", zIndex:100, position:"relative", borderBottom:`1px solid rgba(0,229,255,.1)`, background:"rgba(6,9,15,.98)", boxShadow:"0 1px 0 rgba(0,229,255,.06),0 4px 20px rgba(0,0,0,.5)" }}>
        <div style={{ fontSize:16, fontWeight:"bold", letterSpacing:8, color:C.nc, textShadow:`0 0 16px rgba(0,229,255,.4)` }}>
          LIMWANPO <span style={{ color:C.td, letterSpacing:4, fontSize:12 }}>//</span> <span style={{ color:C.nm, textShadow:`0 0 16px rgba(255,45,149,.4)` }}>POLYMARKET AI</span>
        </div>
        <div style={{ display:"flex", gap:5, alignItems:"center" }}>
          <div style={{ fontSize:8.5, padding:"3px 10px", border:`1px solid rgba(0,229,255,.35)`, borderRadius:2, color:C.nc, background:"rgba(0,229,255,.06)", letterSpacing:1.5 }}>PAPER MODE</div>
          {[
            { label:"9 ENGINES", dot:C.ng },
            { label:"12 MARKETS", dot:C.nc },
            { label:"3 SIGNALS", dot:C.np },
            { label:"1 POSITION", dot:C.np },
            { label:"CAPITAL OK", dot:C.ng },
          ].map(({ label, dot }, i) => (
            <div key={i} style={{ display:"flex", alignItems:"center", gap:4, padding:"3px 9px", border:`1px solid ${C.b2}`, borderRadius:2, fontSize:8.5, color:C.tm, background:"rgba(0,0,0,.3)", letterSpacing:.8 }}>
              <Dot color={dot} size={4} />
              {label}
            </div>
          ))}
          <div style={{ fontSize:8, color:C.td, letterSpacing:.5, marginLeft:4 }}>{time}</div>
        </div>
      </header>

      {/* ── BODY ─────────────────────────────────────────────────────── */}
      <div style={{ overflowY:"auto", overflowX:"hidden", zIndex:1, position:"relative" }}>

        {/* ROW 1 */}
        <div style={{ display:"grid", gridTemplateColumns:"260px 1fr 220px", gap:0, borderBottom:`1px solid ${C.b1}`, height:228 }}>
          <div style={{ borderRight:`1px solid ${C.b1}` }}><PortfolioSummary /></div>
          <div style={{ borderRight:`1px solid ${C.b1}` }}><LiveChart /></div>
          <SystemHealth />
        </div>

        {/* ROW 2 — Market Universe */}
        <div style={{ borderBottom:`1px solid ${C.b1}` }}>
          <PanelLabel right="12 MARKETS · 4 ASSETS">Market Universe</PanelLabel>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)" }}>
            {ASSETS.map((asset,ai) => (
              <div key={asset} style={{ borderRight:ai<3?`1px solid ${C.b1}`:"none", paddingBottom:6 }}>
                <AssetHeader asset={asset} />
                {MARKETS.filter(m=>m.asset===asset).map((m,i) => (
                  <div key={i} style={{ padding:"0 7px" }}><MarketCardComp m={m} /></div>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ROW 3 — Pipeline */}
        <div style={{ borderBottom:`1px solid ${C.b1}` }}>
          <AIPipeline />
        </div>

        {/* ROW 4 — Feeds */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", height:230, borderBottom:`1px solid ${C.b1}` }}>
          <ThinkingFeed />
          <LiveFeed />
        </div>
      </div>

      {/* ── FOOTER ───────────────────────────────────────────────────── */}
      <footer style={{ display:"flex", alignItems:"stretch", zIndex:100, borderTop:`1px solid ${C.b1}`, background:"rgba(3,5,10,.97)", overflow:"hidden" }}>
        <CryptoTicker />
        <NewsTicker />
      </footer>
    </div>
  );
}
