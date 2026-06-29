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
  .pane{width:100%}
  #timeframe{padding:6px 14px;display:flex;gap:6px;border-bottom:1px solid #1c1f2b}
  #timeframe button{background:#1c1f2b;color:#9aa0ad;border:1px solid #2a2e39;border-radius:4px;
    padding:3px 10px;cursor:pointer;font-size:12px}
  #timeframe button.active{background:#2a2e39;color:#d1d4dc;border-color:#5b8def}
  #legend{padding:10px 14px;color:#787b86;border-top:1px solid #1c1f2b}
  #legend b{color:#9aa0ad}
</style></head><body>
<div id="header"><span id="title">__TITLE__</span><span id="subtitle">__SUBTITLE__</span></div>
<div id="timeframe">__TIMEFRAME__</div>
<div class="label">Price · Bollinger · Volume</div><div class="pane" id="price"></div>
<div class="label">RSI (14)</div><div class="pane" id="rsi"></div>
<div class="label">MACD (12,26,9)</div><div class="pane" id="macd"></div>
<div class="label">Stochastic (14,3)</div><div class="pane" id="stoch"></div>
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
}));

let srLines = [];
function clearSR(){ srLines.forEach(l => candles.removePriceLine(l)); srLines = []; }

function loadResolution(res){
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
