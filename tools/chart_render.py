"""Renders self-contained interactive HTML charts (Phase 7).

Pure string rendering — no network, no filesystem. Embeds the chart data as
JSON and loads TradingView lightweight-charts from a pinned CDN URL.
"""
import json

CDN = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"

_LABEL_MAP = {"1h": "1H", "1d": "1D", "1wk": "1W", "1mo": "1M"}
_RES_ORDER = ["1h", "1d", "1wk", "1mo"]

_TEMPLATE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — TRaid</title>
<script src="__CDN__"></script>
<style>
  html,body{margin:0;background:#0e0e12;color:#d1d4dc;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
  #header{padding:10px 14px;border-bottom:1px solid #1c1f2b}
  #title{font-weight:600;font-size:15px}
  #subtitle{color:#9aa0ad;margin-left:8px}
  .label{padding:2px 14px;color:#787b86;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .pane + .label{border-top: 1px solid #c8ccd4;padding-top:4px}
  .pane{width:100%;min-height:0}
  #timeframe{padding:6px 14px;display:flex;gap:6px;border-bottom:1px solid #1c1f2b}
  #timeframe button{background:#1c1f2b;color:#9aa0ad;border:1px solid #2a2e39;border-radius:4px;
    padding:3px 10px;cursor:pointer;font-size:12px}
  #timeframe button.active{background:#2a2e39;color:#d1d4dc;border-color:#5b8def}
  #legend{padding:10px 14px;color:#787b86;border-top:1px solid #1c1f2b}
  #legend b{color:#9aa0ad}
  #layout{display:flex;flex-direction:row;min-height:100vh}
  #charts-col{flex:1;min-width:0;display:flex;flex-direction:column}
  #price{flex:3;min-height:220px}
  #rsi,#macd,#stoch{flex:1;min-height:90px}
  #panel{width:230px;flex-shrink:0;background:#0b0d14;border-left:1px solid #1c1f2b;
    padding:10px 12px;overflow-y:auto;font-size:12px;line-height:1.6;color:#9aa0ad}
  #panel h3{margin:0 0 6px;font-size:12px;color:#d1d4dc;text-transform:uppercase;letter-spacing:.05em}
  #panel .row{display:flex;justify-content:space-between;margin:2px 0}
  #panel .key{color:#787b86}
  #panel .val{color:#d1d4dc;font-weight:600}
  #panel .read{color:#e0a73e;font-size:11px}
  #panel .sep{border-top:1px solid #1c1f2b;margin:8px 0}
  #panel .note{color:#787b86;font-size:11px;margin-top:8px}
  #panel .bull{color:#26a69a}
  #panel .bear{color:#ef5350}
</style></head><body>
<div id="header"><span id="title">__TITLE__</span><span id="subtitle">__SUBTITLE__</span></div>
<div id="timeframe">__TIMEFRAME__</div>
<div id="layout">
<div id="charts-col">
<div class="label">Price · Bollinger · Volume</div><div class="pane" id="price"></div>
<div class="label">RSI (14)</div><div class="pane" id="rsi"></div>
<div class="label">MACD (12,26,9)</div><div class="pane" id="macd"></div>
<div class="label">Stochastic (14,3)</div><div class="pane" id="stoch"></div>
</div>
<div id="panel"><h3>Info</h3><div id="panel-body">Loading…</div></div>
</div>
<div id="legend">__LEGEND__</div>
<script>
const DATA = __DATA__;
const LWC = LightweightCharts;
const dark = {layout:{background:{color:'#0e0e12'},textColor:'#d1d4dc'},
  grid:{vertLines:{color:'#15171f'},horzLines:{color:'#15171f'}},
  rightPriceScale:{borderColor:'#2a2e39',minimumWidth:72},
  crosshair:{mode:0}};
function mk(id,h,showTime){
  const opts = Object.assign({},dark,{height:h,autoSize:true,
    timeScale:{visible:showTime,borderColor:'#2a2e39'}});
  return LWC.createChart(document.getElementById(id),opts);
}

const price = mk('price',380,false);
const rsiC  = mk('rsi',140,false);
const macdC = mk('macd',140,false);
const stoch = mk('stoch',140,true);

// Series created once
const candles = price.addCandlestickSeries({upColor:'#26a69a',downColor:'#ef5350',
  borderVisible:false,wickUpColor:'#26a69a',wickDownColor:'#ef5350'});
const bbU = price.addLineSeries({color:'#5b8def',lineWidth:1});
const bbM = price.addLineSeries({color:'#787b86',lineWidth:1});
const bbL = price.addLineSeries({color:'#5b8def',lineWidth:1});
const vol  = price.addHistogramSeries({priceScaleId:'',priceFormat:{type:'volume'},color:'#2b3145'});
vol.priceScale().applyOptions({scaleMargins:{top:0.82,bottom:0}});

const rsiS = rsiC.addLineSeries({color:'#e0a73e',lineWidth:1});
rsiS.createPriceLine({price:70,color:'#ef5350',lineStyle:2,title:'70'});
rsiS.createPriceLine({price:30,color:'#26a69a',lineStyle:2,title:'30'});

const macdHist = macdC.addHistogramSeries({});
const macdLine = macdC.addLineSeries({color:'#5b8def',lineWidth:1});
const macdSig  = macdC.addLineSeries({color:'#e0a73e',lineWidth:1});

const kS = stoch.addLineSeries({color:'#5b8def',lineWidth:1});
const dS = stoch.addLineSeries({color:'#e0a73e',lineWidth:1});
kS.createPriceLine({price:80,color:'#ef5350',lineStyle:2,title:'80'});
kS.createPriceLine({price:20,color:'#26a69a',lineStyle:2,title:'20'});

const charts = [price,rsiC,macdC,stoch];
let syncing = false;
charts.forEach(src => src.timeScale().subscribeVisibleLogicalRangeChange(range => {
  if(syncing) return;
  if(!range) return;
  syncing = true;
  charts.forEach(dst => {
    if(dst !== src){ try{ dst.timeScale().setVisibleLogicalRange(range); }catch(e){} }
  });
  syncing = false;
  updateSummaryPanel();
}));

let srLines = [];
function clearSR(){ srLines.forEach(l => candles.removePriceLine(l)); srLines = []; }

// Per-resolution time→value maps for crosshair linking
// [candleMap, rsiMap, macdLineMap, kMap]
let _resMaps = {candle:new Map(),rsi:new Map(),macdLine:new Map(),k:new Map()};
let _currentRes = null;

function buildResMaps(res){
  const d = DATA.resolutions[res];
  const cm = new Map(); d.candles.forEach(p=>{ if(p.close!=null) cm.set(p.time,p.close); });
  const rm = new Map(); d.rsi.forEach(p=>{ if(p.value!=null) rm.set(p.time,p.value); });
  const mm = new Map(); d.macd.macd.forEach(p=>{ if(p.value!=null) mm.set(p.time,p.value); });
  const km = new Map(); d.stochastic.k.forEach(p=>{ if(p.value!=null) km.set(p.time,p.value); });
  _resMaps = {candle:cm, rsi:rm, macdLine:mm, k:km};
}

// Reading helpers
function rsiRead(v){ return v==null?'—':v>70?'Overbought':v<30?'Oversold':'Neutral'; }
function stochRead(v){ return v==null?'—':v>80?'Overbought':v<20?'Oversold':'Neutral'; }
function macdRead(hist){ return hist==null?'—':hist>=0?'Bullish':'Bearish'; }
function bbRead(p,upper,lower){
  if(p==null||upper==null||lower==null) return '—';
  return p>upper?'Stretched high':p<lower?'Stretched low':'Within bands';
}

function fmt(v,dec){ return v==null?'—':v.toFixed(dec==null?2:dec); }
function cls(v){ return v==null?'':v>=0?'bull':'bear'; }

function lastDefined(arr){
  if(!arr) return null;
  for(let i=arr.length-1;i>=0;i--){ if(arr[i].value!=null) return arr[i].value; }
  return null;
}
function lastDefinedInRange(arr,fromIdx,toIdx){
  if(!arr) return null;
  const lo=Math.max(0,Math.floor(fromIdx)), hi=Math.min(arr.length-1,Math.ceil(toIdx));
  for(let i=hi;i>=lo;i--){ if(arr[i]&&arr[i].value!=null) return arr[i].value; }
  return null;
}

function updateSummaryPanel(){
  const res = _currentRes;
  if(!res) return;
  const d = DATA.resolutions[res];
  const range = price.timeScale().getVisibleLogicalRange();
  let canArr = d.candles;
  let lo=0, hi=canArr.length-1;
  if(range){ lo=Math.max(0,Math.floor(range.from)); hi=Math.min(canArr.length-1,Math.ceil(range.to)); }
  const vis = canArr.slice(lo,hi+1).filter(p=>p.open!=null);
  if(!vis.length){ document.getElementById('panel-body').innerHTML='<span>No visible candles.</span>'; return; }
  const first=vis[0], last=vis[vis.length-1];
  const O=first.open, C=last.close;
  const H=Math.max(...vis.map(p=>p.high));
  const L=Math.min(...vis.map(p=>p.low));
  const chg=((C/O-1)*100);
  const rsiV=lastDefinedInRange(d.rsi,lo,hi);
  const macdV=lastDefinedInRange(d.macd.macd,lo,hi);
  const sigV=lastDefinedInRange(d.macd.signal,lo,hi);
  const histV=lastDefinedInRange(d.macd.hist,lo,hi);
  const kV=lastDefinedInRange(d.stochastic.k,lo,hi);
  const dV=lastDefinedInRange(d.stochastic.d,lo,hi);
  const bbUV=lastDefinedInRange(d.bollinger.upper,lo,hi);
  const bbMV=lastDefinedInRange(d.bollinger.middle,lo,hi);
  const bbLV=lastDefinedInRange(d.bollinger.lower,lo,hi);
  const bbR=bbRead(C,bbUV,bbLV);
  const sr=d.support!=null?`S ${fmt(d.support)} / R ${fmt(d.resistance)}`:'—';
  const call=DATA.call||(DATA.meta&&DATA.meta.call)||'—';
  document.getElementById('panel-body').innerHTML=`
<div class="row"><span class="key">Range</span><span class="val">${first.time} → ${last.time}</span></div>
<div class="row"><span class="key">O</span><span class="val">${fmt(O)}</span></div>
<div class="row"><span class="key">H</span><span class="val">${fmt(H)}</span></div>
<div class="row"><span class="key">L</span><span class="val">${fmt(L)}</span></div>
<div class="row"><span class="key">C</span><span class="val">${fmt(C)}</span></div>
<div class="row"><span class="key">Change</span><span class="val ${cls(chg)}">${chg>=0?'+':''}${fmt(chg,2)}%</span></div>
<div class="sep"></div>
<div class="row"><span class="key">RSI</span><span class="val">${fmt(rsiV)}</span><span class="read">${rsiRead(rsiV)}</span></div>
<div class="row"><span class="key">MACD</span><span class="val">${fmt(macdV)}</span><span class="read ${cls(histV)}">${macdRead(histV)}</span></div>
<div class="row"><span class="key">Signal</span><span class="val">${fmt(sigV)}</span></div>
<div class="row"><span class="key">Hist</span><span class="val ${cls(histV)}">${fmt(histV)}</span></div>
<div class="row"><span class="key">Stoch K</span><span class="val">${fmt(kV)}</span><span class="read">${stochRead(kV)}</span></div>
<div class="row"><span class="key">Stoch D</span><span class="val">${fmt(dV)}</span></div>
<div class="row"><span class="key">BB</span><span class="read">${bbR}</span></div>
<div class="row"><span class="key">BB U/M/L</span><span class="val">${fmt(bbUV)}/${fmt(bbMV)}/${fmt(bbLV)}</span></div>
<div class="sep"></div>
<div class="row"><span class="key">S/R</span><span class="val">${sr}</span></div>
<div class="row"><span class="key">Call</span><span class="val">${call}</span></div>
<div class="note">Context for timing — not financial advice.</div>`;
}

function showHoverPanel(time){
  const res = _currentRes;
  if(!res) return;
  const d = DATA.resolutions[res];
  const idx = d.candles.findIndex(p=>p.time===time);
  if(idx<0){ updateSummaryPanel(); return; }
  const c=d.candles[idx];
  const rsiV=(d.rsi[idx]&&d.rsi[idx].value!=null)?d.rsi[idx].value:null;
  const macdV=(d.macd.macd[idx]&&d.macd.macd[idx].value!=null)?d.macd.macd[idx].value:null;
  const sigV=(d.macd.signal[idx]&&d.macd.signal[idx].value!=null)?d.macd.signal[idx].value:null;
  const histV=(d.macd.hist[idx]&&d.macd.hist[idx].value!=null)?d.macd.hist[idx].value:null;
  const kV=(d.stochastic.k[idx]&&d.stochastic.k[idx].value!=null)?d.stochastic.k[idx].value:null;
  const dV=(d.stochastic.d[idx]&&d.stochastic.d[idx].value!=null)?d.stochastic.d[idx].value:null;
  const bbUV=(d.bollinger.upper[idx]&&d.bollinger.upper[idx].value!=null)?d.bollinger.upper[idx].value:null;
  const bbMV=(d.bollinger.middle[idx]&&d.bollinger.middle[idx].value!=null)?d.bollinger.middle[idx].value:null;
  const bbLV=(d.bollinger.lower[idx]&&d.bollinger.lower[idx].value!=null)?d.bollinger.lower[idx].value:null;
  const vol=(d.volume[idx]&&d.volume[idx].value!=null)?d.volume[idx].value:null;
  const chg=c.open&&c.close?((c.close/c.open-1)*100):null;
  const bbR=bbRead(c.close,bbUV,bbLV);
  document.getElementById('panel-body').innerHTML=`
<div class="row"><span class="key">Date</span><span class="val">${time}</span></div>
<div class="row"><span class="key">O</span><span class="val">${fmt(c.open)}</span></div>
<div class="row"><span class="key">H</span><span class="val">${fmt(c.high)}</span></div>
<div class="row"><span class="key">L</span><span class="val">${fmt(c.low)}</span></div>
<div class="row"><span class="key">C</span><span class="val">${fmt(c.close)}</span></div>
<div class="row"><span class="key">Change</span><span class="val ${chg!=null?cls(chg):''}">${chg!=null?(chg>=0?'+':'')+fmt(chg,2)+'%':'—'}</span></div>
<div class="row"><span class="key">Vol</span><span class="val">${vol!=null?Math.round(vol).toLocaleString():'—'}</span></div>
<div class="sep"></div>
<div class="row"><span class="key">RSI</span><span class="val">${fmt(rsiV)}</span><span class="read">${rsiRead(rsiV)}</span></div>
<div class="row"><span class="key">MACD</span><span class="val">${fmt(macdV)}</span><span class="read ${cls(histV)}">${macdRead(histV)}</span></div>
<div class="row"><span class="key">Signal</span><span class="val">${fmt(sigV)}</span></div>
<div class="row"><span class="key">Hist</span><span class="val ${cls(histV)}">${fmt(histV)}</span></div>
<div class="row"><span class="key">Stoch K</span><span class="val">${fmt(kV)}</span><span class="read">${stochRead(kV)}</span></div>
<div class="row"><span class="key">Stoch D</span><span class="val">${fmt(dV)}</span></div>
<div class="row"><span class="key">BB</span><span class="read">${bbR}</span></div>
<div class="row"><span class="key">BB U/M/L</span><span class="val">${fmt(bbUV)}/${fmt(bbMV)}/${fmt(bbLV)}</span></div>
<div class="note">Context for timing — not financial advice.</div>`;
}

// Linked crosshair
let chsyncing = false;
const paneEntries = [
  {chart: price,  series: candles,  map: ()=>_resMaps.candle},
  {chart: rsiC,   series: rsiS,     map: ()=>_resMaps.rsi},
  {chart: macdC,  series: macdLine, map: ()=>_resMaps.macdLine},
  {chart: stoch,  series: kS,       map: ()=>_resMaps.k},
];
paneEntries.forEach(({chart,series},i) => {
  chart.subscribeCrosshairMove(param => {
    if(chsyncing) return;
    chsyncing = true;
    if(param && param.time){
      showHoverPanel(param.time);
      paneEntries.forEach(({chart:dst,series:ds,map},j) => {
        if(j===i) return;
        const v = map().get(param.time);
        if(v!=null){ try{ dst.setCrosshairPosition(v,param.time,ds); }catch(e){} }
      });
    } else {
      updateSummaryPanel();
      paneEntries.forEach(({chart:dst},j) => {
        if(j===i) return;
        try{ dst.clearCrosshairPosition(); }catch(e){}
      });
    }
    chsyncing = false;
  });
});

function loadResolution(res){
  _currentRes = res;
  buildResMaps(res);
  const d = DATA.resolutions[res];
  candles.setData(d.candles);
  bbU.setData(d.bollinger.upper);
  bbM.setData(d.bollinger.middle);
  bbL.setData(d.bollinger.lower);
  vol.setData(d.volume);
  rsiS.setData(d.rsi);
  macdHist.setData(d.macd.hist.map(p =>
    (p.value == null) ? {time:p.time} : {time:p.time,value:p.value,color:p.value>=0?'#26a69a':'#ef5350'}
  ));
  macdLine.setData(d.macd.macd);
  macdSig.setData(d.macd.signal);
  kS.setData(d.stochastic.k);
  dS.setData(d.stochastic.d);
  clearSR();
  if(d.support != null){ srLines.push(candles.createPriceLine({price:d.support,color:'#26a69a',
    lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'S '+d.support})); }
  if(d.resistance != null){ srLines.push(candles.createPriceLine({price:d.resistance,color:'#ef5350',
    lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'R '+d.resistance})); }
  charts.forEach(c => c.timeScale().fitContent());
  updateSummaryPanel();
}

// Timeframe toggle
const buttons = document.querySelectorAll('#timeframe button');
buttons.forEach(btn => btn.addEventListener('click', () => {
  buttons.forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadResolution(btn.dataset.res);
}));
const defBtn = document.querySelector('#timeframe button[data-res="'+DATA.default+'"]');
if(defBtn){ defBtn.classList.add('active'); }
loadResolution(DATA.default);
</script></body></html>"""

_LEGEND = (
    "<b>How to read this:</b> scroll to zoom, drag to pan, hover for values. "
    "<b>Candles</b> green=up/red=down. <b>Bollinger</b> bands = volatility envelope "
    "(price near upper=stretched high, near lower=stretched low). "
    "<b>RSI</b> &gt;70 overbought / &lt;30 oversold. "
    "<b>MACD</b> line crossing its signal = momentum shift; histogram = the gap. "
    "<b>Stochastic</b> &gt;80 overbought / &lt;20 oversold. "
    "Dashed <b>S/R</b> lines = nearest support/resistance. "
    "Context for timing — not a buy/sell trigger. Not financial advice."
)


def render_chart_html(payload, meta=None):
    meta = meta or {}
    ticker = payload.get("ticker", "?")
    price = payload.get("price", "")
    as_of = payload.get("as_of", "")
    title = f"{ticker} · {price}"
    sub_bits = [f"as of {as_of}"]
    if meta.get("call"):
        call_bit = f"TRaid call: {meta['call']}"
        if meta.get("confidence"):
            call_bit += f" ({meta['confidence']})"
        if meta.get("call_date"):
            call_bit += f" — {meta['call_date']}"
        sub_bits.insert(0, call_bit)
    subtitle = "  ·  ".join(b for b in sub_bits if b)

    # Build timeframe buttons from present resolution keys
    resolutions = payload.get("resolutions", {})
    timeframe_html = "".join(
        f'<button data-res="{r}">{_LABEL_MAP.get(r, r)}</button>'
        for r in _RES_ORDER if r in resolutions
    )

    return (
        _TEMPLATE
        .replace("__CDN__", CDN)
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__LEGEND__", _LEGEND)
        .replace("__TIMEFRAME__", timeframe_html)
        .replace("__DATA__", json.dumps(payload))
    )


def render_session_index(date, entries):
    rows = []
    for e in entries:
        label = e["ticker"]
        if e.get("call"):
            label += f' <span style="color:#787b86">— {e["call"]}</span>'
        rows.append(f'<li><a href="{e["filename"]}">{label}</a></li>')
    items = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>TRaid charts — {date}</title>
<style>
 html,body{{margin:0;background:#0e0e12;color:#d1d4dc;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
 h1{{font-size:16px;padding:14px;border-bottom:1px solid #1c1f2b;margin:0}}
 ul{{list-style:none;padding:14px;margin:0}} li{{padding:6px 0}}
 a{{color:#5b8def;text-decoration:none}} a:hover{{text-decoration:underline}}
 .note{{padding:0 14px 14px;color:#787b86;font-size:12px}}
</style></head><body>
<h1>TRaid charts — session {date}</h1>
<ul>
{items}
</ul>
<div class="note">Decision-support, not financial advice.</div>
</body></html>"""
