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
  html,body{margin:0;height:100dvh;background:#0e0e12;color:#d1d4dc;font:13px/1.4 -apple-system,Segoe UI,Roboto,sans-serif}
  body{display:flex;flex-direction:column;overflow:hidden}
  #header{padding:10px 14px;border-bottom:1px solid #1c1f2b}
  #title{font-weight:600;font-size:15px}
  #subtitle{color:#9aa0ad;margin-left:8px}
  .label{padding:2px 14px;color:#787b86;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .pane + .label{border-top: 1px solid #c8ccd4;padding-top:4px}
  .pane{width:100%;min-height:0;position:relative}
  .pane.collapsed{flex:0 0 0;min-height:0;height:0;overflow:hidden}
  .tog-cluster{position:absolute;top:4px;left:4px;z-index:5;display:flex;gap:4px}
  .tog{background:#1c1f2b;color:#9aa0ad;border:1px solid #2a2e39;border-radius:3px;
    padding:2px 6px;cursor:pointer;font-size:11px;user-select:none}
  .tog.off{color:#454851;border-color:#1c1f2b}
  #timeframe{padding:6px 14px;display:flex;gap:6px;border-bottom:1px solid #1c1f2b}
  #timeframe button{background:#1c1f2b;color:#9aa0ad;border:1px solid #2a2e39;border-radius:4px;
    padding:3px 10px;cursor:pointer;font-size:12px}
  #timeframe button.active{background:#2a2e39;color:#d1d4dc;border-color:#5b8def}
  #legend{padding:10px 14px;color:#787b86;border-top:1px solid #1c1f2b}
  #legend b{color:#9aa0ad}
  #layout{display:flex;flex-direction:row;flex:1;min-height:0}
  #charts-col{flex:1;min-width:0;display:flex;flex-direction:column}
  #price{flex:3;min-height:220px}
  #rsi,#macd,#stoch{flex:1;min-height:90px}
  #panel{width:230px;flex-shrink:0;background:#0b0d14;border-left:1px solid #1c1f2b;
    padding:10px 12px;overflow-y:auto;font-size:12px;line-height:1.6;color:#9aa0ad}
  #panel h3{margin:0 0 6px;font-size:12px;color:#d1d4dc;text-transform:uppercase;letter-spacing:.05em}
  #panel .row{display:flex;justify-content:space-between;margin:2px 0}
  #panel .key{color:#787b86}
  #panel .val{color:#d1d4dc;font-weight:600}
  #panel .read{display:block;color:#e0a73e;font-size:11px;white-space:normal;margin:1px 0 4px}
  #panel .sep{border-top:1px solid #1c1f2b;margin:8px 0}
  #panel .note{color:#787b86;font-size:11px;margin-top:8px}
  #panel .bull{color:#26a69a}
  #panel .bear{color:#ef5350}
  #tip{position:absolute;background:#1c1f2b;color:#d1d4dc;border:1px solid #2a2e39;
    border-radius:4px;padding:7px 10px;max-width:260px;font-size:11px;line-height:1.5;
    pointer-events:none;display:none;z-index:100;white-space:normal}
  .label.hidden{display:none}
  .dim-mask{position:absolute;top:0;bottom:0;background:rgba(14,14,18,0.6);pointer-events:none;z-index:3;display:none}
</style></head><body>
<div id="header"><span id="title">__TITLE__</span><span id="subtitle">__SUBTITLE__</span></div>
<div id="timeframe">__TIMEFRAME__</div>
<div id="layout">
<div id="charts-col">
<div class="label">Price · Bollinger · Volume</div>
<div class="pane" id="price"><div class="tog-cluster"><span class="tog" data-toggle="bb">BB</span><span class="tog" data-toggle="vol">Vol</span></div><div id="mask-left" class="dim-mask"></div><div id="mask-right" class="dim-mask"></div></div>
<div class="label" data-label-for="rsi">RSI (14)</div>
<div class="pane" id="rsi"><div class="tog-cluster"><span class="tog" data-toggle="rsi">RSI</span></div></div>
<div class="label" data-label-for="macd">MACD (12,26,9)</div>
<div class="pane" id="macd"><div class="tog-cluster"><span class="tog" data-toggle="macd">MACD</span></div></div>
<div class="label" data-label-for="stoch">Stochastic (14,3)</div>
<div class="pane" id="stoch"><div class="tog-cluster"><span class="tog" data-toggle="stoch">STOCH</span></div></div>
</div>
<div id="panel"><h3>Info</h3><div id="panel-body">Loading…</div></div>
</div>
<div id="legend">__LEGEND__</div>
<div id="tip"></div>
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

// Per-pane on/off state (price is always on)
const paneState = {rsi:true, macd:true, stoch:true};
function visibleCharts(){
  const active = [price];
  if(paneState.rsi)  active.push(rsiC);
  if(paneState.macd) active.push(macdC);
  if(paneState.stoch) active.push(stoch);
  return active;
}

let syncing = false;
let sel = null;
let dragging = false;
let dragStartX = 0;

function hideMasks(){
  document.getElementById('mask-left').style.display='none';
  document.getElementById('mask-right').style.display='none';
}
function positionMasks(){
  const mL = document.getElementById('mask-left');
  const mR = document.getElementById('mask-right');
  if(!sel){ hideMasks(); return; }
  const paneEl = document.getElementById('price');
  const paneWidth = paneEl.offsetWidth;
  let fromX = price.timeScale().timeToCoordinate(sel.from);
  let toX   = price.timeScale().timeToCoordinate(sel.to);
  if(fromX == null) fromX = 0;
  if(toX   == null) toX   = paneWidth;
  fromX = Math.max(0, Math.min(paneWidth, fromX));
  toX   = Math.max(0, Math.min(paneWidth, toX));
  mL.style.left = '0';
  mL.style.width = fromX + 'px';
  mL.style.display = 'block';
  mR.style.left = toX + 'px';
  mR.style.width = (paneWidth - toX) + 'px';
  mR.style.display = 'block';
}
function clearSelection(){
  sel = null;
  hideMasks();
  updateSummaryPanel();
}

// Subscribe all 4 charts; handlers use visibleCharts() to avoid touching collapsed panes
[price,rsiC,macdC,stoch].forEach(src => src.timeScale().subscribeVisibleLogicalRangeChange(range => {
  if(syncing) return;
  if(!range) return;
  syncing = true;
  visibleCharts().forEach(dst => {
    if(dst !== src){ try{ dst.timeScale().setVisibleLogicalRange(range); }catch(e){} }
  });
  syncing = false;
  updateSummaryPanel();
  positionMasks();
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
  let canArr = d.candles;
  let lo=0, hi=canArr.length-1;
  let panelHeader = '';
  if(sel){
    let fromIdx = canArr.findIndex(p => p.time >= sel.from);
    let toIdx = -1;
    for(let i=canArr.length-1; i>=0; i--){ if(canArr[i].time <= sel.to){ toIdx=i; break; } }
    if(fromIdx < 0) fromIdx = 0;
    if(toIdx < 0) toIdx = canArr.length-1;
    lo = fromIdx;
    hi = toIdx;
    panelHeader = `<div class="row"><span class="key" style="text-transform:uppercase;color:#e0a73e">Selection</span><span class="val" style="color:#e0a73e">${sel.from} → ${sel.to}</span></div>`;
  } else {
    const range = price.timeScale().getVisibleLogicalRange();
    if(range){ lo=Math.max(0,Math.floor(range.from)); hi=Math.min(canArr.length-1,Math.ceil(range.to)); }
  }
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
  // Derived stats
  const pctBelowHigh = (H>0)?((H-C)/H*100):null;
  const volArr = d.volume||[];
  const lastVolIdx = Math.min(hi, volArr.length-1);
  const lastVol = (lastVolIdx>=0 && volArr[lastVolIdx] && volArr[lastVolIdx].value!=null)?volArr[lastVolIdx].value:null;
  const wnd = Math.min(20, lastVolIdx+1);
  let vSum=0, vCnt=0;
  for(let i=Math.max(0,lastVolIdx-wnd+1);i<=lastVolIdx;i++){
    if(volArr[i]&&volArr[i].value!=null){vSum+=volArr[i].value;vCnt++;}
  }
  const volAvg = vCnt>0?vSum/vCnt:null;
  const volRatio = (lastVol!=null&&volAvg!=null&&volAvg>0)?(lastVol/volAvg):null;
  const atrV = lastDefined(d.atr);
  const atrPct = (atrV!=null&&C>0)?(atrV/C*100):null;
  const bbPctB = (bbUV!=null&&bbLV!=null&&(bbUV-bbLV)>0)?((C-bbLV)/(bbUV-bbLV)):null;
  const distS = (d.support!=null&&C>0)?((d.support/C-1)*100):null;
  const distR = (d.resistance!=null&&C>0)?((d.resistance/C-1)*100):null;
  document.getElementById('panel-body').innerHTML=panelHeader+`
<div class="row"><span class="key">Range</span><span class="val">${first.time} → ${last.time}</span></div>
<div class="row"><span class="key">O</span><span class="val">${fmt(O)}</span></div>
<div class="row"><span class="key">H (vis)</span><span class="val">${fmt(H)}</span></div>
<div class="row"><span class="key">L (vis)</span><span class="val">${fmt(L)}</span></div>
<div class="row"><span class="key">C</span><span class="val">${fmt(C)}</span></div>
<div class="row" data-tip="change"><span class="key">Change</span><span class="val ${cls(chg)}">${chg>=0?'+':''}${fmt(chg,2)}%</span></div>
<div class="row" data-tip="fromhigh"><span class="key">% below high</span><span class="val">${pctBelowHigh!=null?fmt(pctBelowHigh,1)+'%':'—'}</span></div>
<div class="row" data-tip="volume"><span class="key">Vol/AvgVol</span><span class="val">${volRatio!=null?fmt(volRatio,2)+'×':'—'}</span></div>
<div class="row" data-tip="atr"><span class="key">ATR</span><span class="val">${atrV!=null ? `${fmt(atrV)} (${atrPct!=null?fmt(atrPct,1)+'%':'—'})` : '—'}</span></div>
<div class="sep"></div>
<div class="row" data-tip="rsi"><span class="key">RSI</span><span class="val">${fmt(rsiV)}</span><span class="read">${rsiRead(rsiV)}</span></div>
<div class="row" data-tip="macd"><span class="key">MACD</span><span class="val">${fmt(macdV)}</span><span class="read ${cls(histV)}">${macdRead(histV)}</span></div>
<div class="row"><span class="key">Signal</span><span class="val">${fmt(sigV)}</span></div>
<div class="row"><span class="key">Hist</span><span class="val ${cls(histV)}">${fmt(histV)}</span></div>
<div class="row" data-tip="stochastic"><span class="key">Stoch K</span><span class="val">${fmt(kV)}</span><span class="read">${stochRead(kV)}</span></div>
<div class="row"><span class="key">Stoch D</span><span class="val">${fmt(dV)}</span></div>
<div class="row" data-tip="bollinger"><span class="key">BB</span><span class="read">${bbR}</span></div>
<div class="row"><span class="key">BB U/M/L</span><span class="val">${fmt(bbUV)}/${fmt(bbMV)}/${fmt(bbLV)}</span></div>
<div class="row" data-tip="percentb"><span class="key">%B</span><span class="val">${bbPctB!=null?fmt(bbPctB,2):'—'}</span></div>
<div class="sep"></div>
<div class="row" data-tip="sr"><span class="key">S/R</span><span class="val">${sr}</span></div>
<div class="row"><span class="key">→ Support</span><span class="val ${distS!=null?cls(distS):''}">${distS!=null?(distS>=0?'+':'')+fmt(distS,1)+'%':'—'}</span></div>
<div class="row"><span class="key">→ Resist</span><span class="val ${distR!=null?cls(distR):''}">${distR!=null?(distR>=0?'+':'')+fmt(distR,1)+'%':'—'}</span></div>
<div class="row"><span class="key">Call</span><span class="val">${call}</span></div>
__FUND_BLOCK__
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
  const volV=(d.volume[idx]&&d.volume[idx].value!=null)?d.volume[idx].value:null;
  const atrV=(d.atr&&d.atr[idx]&&d.atr[idx].value!=null)?d.atr[idx].value:null;
  const chg=c.open&&c.close?((c.close/c.open-1)*100):null;
  const bbR=bbRead(c.close,bbUV,bbLV);
  const bbPctB=(bbUV!=null&&bbLV!=null&&(bbUV-bbLV)>0)?((c.close-bbLV)/(bbUV-bbLV)):null;
  document.getElementById('panel-body').innerHTML=`
<div class="row"><span class="key">Date</span><span class="val">${time}</span></div>
<div class="row"><span class="key">O</span><span class="val">${fmt(c.open)}</span></div>
<div class="row"><span class="key">H</span><span class="val">${fmt(c.high)}</span></div>
<div class="row"><span class="key">L</span><span class="val">${fmt(c.low)}</span></div>
<div class="row"><span class="key">C</span><span class="val">${fmt(c.close)}</span></div>
<div class="row" data-tip="change"><span class="key">Change</span><span class="val ${chg!=null?cls(chg):''}">${chg!=null?(chg>=0?'+':'')+fmt(chg,2)+'%':'—'}</span></div>
<div class="row" data-tip="volume"><span class="key">Vol</span><span class="val">${volV!=null?Math.round(volV).toLocaleString():'—'}</span></div>
<div class="row" data-tip="atr"><span class="key">ATR</span><span class="val">${fmt(atrV)}</span></div>
<div class="sep"></div>
<div class="row" data-tip="rsi"><span class="key">RSI</span><span class="val">${fmt(rsiV)}</span><span class="read">${rsiRead(rsiV)}</span></div>
<div class="row" data-tip="macd"><span class="key">MACD</span><span class="val">${fmt(macdV)}</span><span class="read ${cls(histV)}">${macdRead(histV)}</span></div>
<div class="row"><span class="key">Signal</span><span class="val">${fmt(sigV)}</span></div>
<div class="row"><span class="key">Hist</span><span class="val ${cls(histV)}">${fmt(histV)}</span></div>
<div class="row" data-tip="stochastic"><span class="key">Stoch K</span><span class="val">${fmt(kV)}</span><span class="read">${stochRead(kV)}</span></div>
<div class="row"><span class="key">Stoch D</span><span class="val">${fmt(dV)}</span></div>
<div class="row" data-tip="bollinger"><span class="key">BB</span><span class="read">${bbR}</span></div>
<div class="row"><span class="key">BB U/M/L</span><span class="val">${fmt(bbUV)}/${fmt(bbMV)}/${fmt(bbLV)}</span></div>
<div class="row" data-tip="percentb"><span class="key">%B</span><span class="val">${bbPctB!=null?fmt(bbPctB,2):'—'}</span></div>
__FUND_BLOCK__
<div class="note">Context for timing — not financial advice.</div>`;
}

// Linked crosshair
let chsyncing = false;
const allPaneEntries = [
  {chart: price,  series: candles,  map: ()=>_resMaps.candle,   pane:'price'},
  {chart: rsiC,   series: rsiS,     map: ()=>_resMaps.rsi,      pane:'rsi'},
  {chart: macdC,  series: macdLine, map: ()=>_resMaps.macdLine, pane:'macd'},
  {chart: stoch,  series: kS,       map: ()=>_resMaps.k,        pane:'stoch'},
];
function activePaneEntries(){
  return allPaneEntries.filter(e => e.pane==='price' || paneState[e.pane]);
}
allPaneEntries.forEach(entry => {
  entry.chart.subscribeCrosshairMove(param => {
    if(chsyncing) return;
    chsyncing = true;
    const active = activePaneEntries();
    if(param && param.time){
      showHoverPanel(param.time);
      active.forEach(({chart:dst,series:ds,map}) => {
        if(dst === entry.chart) return;
        const v = map().get(param.time);
        if(v!=null){ try{ dst.setCrosshairPosition(v,param.time,ds); }catch(e){} }
        else { try{ dst.clearCrosshairPosition(); }catch(e){} }
      });
    } else {
      updateSummaryPanel();
      active.forEach(({chart:dst}) => {
        if(dst === entry.chart) return;
        try{ dst.clearCrosshairPosition(); }catch(e){}
      });
    }
    chsyncing = false;
  });
});

// Indicator toggle chips
document.querySelectorAll('.tog').forEach(chip => {
  chip.addEventListener('click', () => {
    const t = chip.dataset.toggle;
    if(t === 'bb'){
      chip.classList.toggle('off');
      const on = !chip.classList.contains('off');
      [bbU,bbM,bbL].forEach(s => s.applyOptions({visible:on}));
    } else if(t === 'vol'){
      chip.classList.toggle('off');
      const on = !chip.classList.contains('off');
      vol.applyOptions({visible:on});
    } else {
      // sub-pane collapse toggle (rsi / macd / stoch)
      const paneEl = document.getElementById(t);
      const nowCollapsed = paneEl.classList.toggle('collapsed');
      paneState[t] = !nowCollapsed;
      chip.classList.toggle('off', nowCollapsed);
      const labelEl = document.querySelector(`[data-label-for="${t}"]`);
      if(labelEl) labelEl.classList.toggle('hidden', nowCollapsed);
      visibleCharts().forEach(c => c.timeScale().fitContent());
    }
  });
});

function loadResolution(res){
  clearSelection();
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
  visibleCharts().forEach(c => c.timeScale().fitContent());
  positionMasks();
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

// Shift+drag range selection on price pane
(function(){
  const priceEl = document.getElementById('price');
  priceEl.addEventListener('mousedown', function(e){
    if(e.target.closest('.tog')) return;  // indicator toggle chip — don't touch selection
    if(e.shiftKey){
      dragging = true;
      dragStartX = e.clientX - priceEl.getBoundingClientRect().left;
      // suppress the chart's own pressed-mouse pan so the drag only selects
      price.applyOptions({handleScroll:{pressedMouseMove:false}, handleScale:{axisPressedMouseMove:false}});
      e.preventDefault();
    } else {
      clearSelection();
    }
  });
  document.addEventListener('mousemove', function(e){
    if(!dragging) return;
    const rect = priceEl.getBoundingClientRect();
    const curX = e.clientX - rect.left;
    const minX = Math.min(dragStartX, curX);
    const maxX = Math.max(dragStartX, curX);
    const canArr = DATA.resolutions[_currentRes] ? DATA.resolutions[_currentRes].candles : [];
    let fromTime = price.timeScale().coordinateToTime(minX);
    let toTime   = price.timeScale().coordinateToTime(maxX);
    if(fromTime == null) fromTime = canArr.length ? canArr[0].time : null;
    if(toTime   == null) toTime   = canArr.length ? canArr[canArr.length-1].time : null;
    if(fromTime && toTime){ sel = {from: fromTime, to: toTime}; positionMasks(); }
  });
  document.addEventListener('mouseup', function(e){
    if(!dragging) return;
    const rect = priceEl.getBoundingClientRect();
    const curX = e.clientX - rect.left;
    const dist = Math.abs(curX - dragStartX);
    dragging = false;
    // restore the chart's normal pan/scale after the selection drag
    price.applyOptions({handleScroll:{pressedMouseMove:true}, handleScale:{axisPressedMouseMove:true}});
    if(dist < 3){
      clearSelection();
    } else {
      updateSummaryPanel();
    }
  });
})();

// Educational tooltips
const TIPS = {
  rsi: "RSI (Relative Strength Index) measures momentum on a 0–100 scale. Above 70 suggests overbought conditions; below 30 suggests oversold. It's context, not a predictor — stocks can stay overbought for weeks in strong trends.",
  macd: "MACD (Moving Average Convergence Divergence) tracks momentum by comparing two EMAs. When the MACD line crosses above its signal line it suggests rising momentum; below suggests fading momentum. It lags price and works best in trending markets.",
  bollinger: "Bollinger Bands are volatility envelopes plotted ±2 standard deviations around a 20-period moving average. Price touching the upper band is 'stretched high'; lower band is 'stretched low'. Bands expand during volatile periods and contract during quiet ones.",
  percentb: "%B shows where price sits within the Bollinger Bands: 1.0 = at the upper band, 0.0 = at the lower band, 0.5 = at the middle. Values above 1 or below 0 mean price has moved outside the bands — notable but not a reliable sell/buy signal on its own.",
  stochastic: "Stochastic Oscillator compares the closing price to the recent high–low range (0–100). Above 80 is overbought; below 20 is oversold. The %K line is the raw reading; %D is a 3-period smoothing. Context matters — trending markets can sustain extremes.",
  atr: "ATR (Average True Range) measures average daily price movement (volatility). A higher ATR means bigger typical swings. Useful for sizing positions and setting stops — not a direction signal.",
  volume: "Volume/AvgVol compares the most recent bar's volume to its 20-bar average. A ratio above 1× means heavier-than-usual activity; below 1× is lighter. Spikes on big price moves can confirm the move; spikes on flat price can signal indecision.",
  sr: "Support and Resistance are price levels where buying or selling pressure has historically been strong. Support = a floor the price has bounced from; Resistance = a ceiling it's struggled to break. They're guides, not guarantees.",
  pe: "P/E (Price-to-Earnings) ratio compares the share price to annual earnings per share. A higher P/E implies the market expects strong future growth. It's most useful when compared to the company's peers and historical average — a high P/E isn't inherently bad.",
  forwardpe: "Forward P/E uses analyst estimates for next year's earnings instead of reported figures. It reflects expectations. If forward P/E is much lower than trailing P/E, the market anticipates strong earnings growth ahead — but estimates can be wrong.",
  peg: "PEG (Price/Earnings-to-Growth) divides the P/E by the expected earnings growth rate. A PEG below 1 is often seen as undervalued relative to growth; above 2 may be expensive. It's a rough heuristic, not a precise signal.",
  margin: "Profit margin (net income ÷ revenue) shows what fraction of sales becomes profit. Higher is better, and trend matters more than a single snapshot. Industry context is key — software companies typically have higher margins than retailers.",
  growth: "Revenue growth shows how fast the company's sales are expanding year-over-year. Consistent, accelerating growth is a positive sign. Slowing growth in a high-P/E stock can trigger sharp sell-offs.",
  change: "Change% is the price move from the open of the first visible candle to the close of the last — it reflects the performance over the visible window, not necessarily a single day.",
  fromhigh: "% below high shows how far the current close sits below the highest price in the visible window. It gives a quick sense of how much of a recent rally has given back — useful context but not a reversal signal on its own.",
};
const tipEl = document.getElementById('tip');
document.getElementById('panel').addEventListener('mouseover', e => {
  const row = e.target.closest('[data-tip]');
  if(!row) return;
  const key = row.dataset.tip;
  if(!TIPS[key]) return;
  tipEl.textContent = TIPS[key];
  tipEl.style.display = 'block';
  const vw = window.innerWidth, vh = window.innerHeight;
  let x = e.pageX + 12, y = e.pageY + 12;
  if(e.clientX + 270 > vw) x = e.pageX - 270;
  if(e.clientY + tipEl.offsetHeight + 10 > vh) y = e.pageY - tipEl.offsetHeight - 8;
  tipEl.style.left = x + 'px';
  tipEl.style.top  = y + 'px';
});
document.getElementById('panel').addEventListener('mouseout', e => {
  const row = e.target.closest('[data-tip]');
  if(!row) return;
  if(row.contains(e.relatedTarget)) return;
  tipEl.style.display = 'none';
});
</script>
</body></html>"""

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


def _make_fund_block_html(f):
    """Generate the fundamentals sidebar HTML block on the Python side.

    Returns an empty string when *f* is None/falsy so the rendered HTML never
    contains the 'Fundamentals (snapshot)' heading when data is absent.
    """
    if not f:
        return ''

    v = f.get('valuation') or {}
    g = f.get('growth') or {}
    p = f.get('profitability') or {}

    def _fmt(val, dec=2):
        if val is None:
            return '—'  # —
        return f'{val:.{dec}f}'

    def _strip_prefix(reading):
        """Strip redundant 'label value — ' prefix from a reading string."""
        if reading and ' — ' in reading:
            return reading.split(' — ', 1)[1]
        return reading

    def frow(label, val, reading=None, tip_key=None):
        v_str = '—' if val is None else val
        tip_attr = f' data-tip="{tip_key}"' if tip_key else ''
        row = (
            f'<div class="row"{tip_attr}>'
            f'<span class="key">{label}</span>'
            f'<span class="val">{v_str}</span>'
            f'</div>'
        )
        if reading:
            tail = _strip_prefix(reading)
            row += f'\n<div class="read">{tail}</div>'
        return row

    pe = v.get('trailing_pe')
    fpe = v.get('forward_pe')
    peg = v.get('peg')
    mrg = p.get('profit_margin_pct')
    rev = g.get('revenue_growth_pct')

    name = f.get('name') or '—'
    sector = f.get('sector') or '—'

    lines = [
        '<div class="sep"></div>',
        '<h3>Fundamentals (snapshot)</h3>',
        f'<div class="row"><span class="key">{name}</span><span class="val">{sector}</span></div>',
        frow('P/E', _fmt(pe) if pe is not None else None, v.get('reading'), 'pe'),
        frow('Forward P/E', _fmt(fpe) if fpe is not None else None, None, 'forwardpe'),
        frow('PEG', _fmt(peg) if peg is not None else None, None, 'peg'),
        frow('Margin', (_fmt(mrg, 1) + '%') if mrg is not None else None, p.get('reading'), 'margin'),
        frow('Rev growth', (_fmt(rev, 1) + '%') if rev is not None else None, g.get('reading'), 'growth'),
    ]
    return '\n'.join(lines)


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

    fund_block_html = _make_fund_block_html(payload.get("fundamentals"))
    # Harden: this HTML is injected into a JS template literal, so neutralize any
    # backtick / ${ that could break it (defensive — real fundamentals data is clean).
    fund_block_html = fund_block_html.replace("`", "&#96;").replace("${", "&#36;{")

    return (
        _TEMPLATE
        .replace("__CDN__", CDN)
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__LEGEND__", _LEGEND)
        .replace("__TIMEFRAME__", timeframe_html)
        .replace("__DATA__", json.dumps(payload))
        .replace("__FUND_BLOCK__", fund_block_html)
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
