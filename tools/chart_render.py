"""Renders self-contained interactive HTML charts (Phase 7).

Pure string rendering — no network, no filesystem. Embeds the chart data as
JSON and loads TradingView lightweight-charts from a pinned CDN URL.
"""
import json

CDN = "https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"

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
  #legend{padding:10px 14px;color:#787b86;border-top:1px solid #1c1f2b}
  #legend b{color:#9aa0ad}
</style></head><body>
<div id="header"><span id="title">__TITLE__</span><span id="subtitle">__SUBTITLE__</span></div>
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
  rightPriceScale:{borderColor:'#2a2e39'},timeScale:{borderColor:'#2a2e39'},
  crosshair:{mode:0}};
function mk(id,h){return LWC.createChart(document.getElementById(id),
  Object.assign({height:h,autoSize:true},dark));}

const price = mk('price',380);
const candles = price.addCandlestickSeries({upColor:'#26a69a',downColor:'#ef5350',
  borderVisible:false,wickUpColor:'#26a69a',wickDownColor:'#ef5350'});
candles.setData(DATA.candles);
const bbU=price.addLineSeries({color:'#5b8def',lineWidth:1});bbU.setData(DATA.bollinger.upper);
const bbM=price.addLineSeries({color:'#787b86',lineWidth:1});bbM.setData(DATA.bollinger.middle);
const bbL=price.addLineSeries({color:'#5b8def',lineWidth:1});bbL.setData(DATA.bollinger.lower);
const vol=price.addHistogramSeries({priceScaleId:'',priceFormat:{type:'volume'},color:'#2b3145'});
vol.priceScale().applyOptions({scaleMargins:{top:0.82,bottom:0}});vol.setData(DATA.volume);
if(DATA.support){candles.createPriceLine({price:DATA.support,color:'#26a69a',lineWidth:1,
  lineStyle:2,axisLabelVisible:true,title:'S '+DATA.support});}
if(DATA.resistance){candles.createPriceLine({price:DATA.resistance,color:'#ef5350',lineWidth:1,
  lineStyle:2,axisLabelVisible:true,title:'R '+DATA.resistance});}

const rsi=mk('rsi',140);
const rsiS=rsi.addLineSeries({color:'#e0a73e',lineWidth:1});rsiS.setData(DATA.rsi);
rsiS.createPriceLine({price:70,color:'#ef5350',lineStyle:2,title:'70'});
rsiS.createPriceLine({price:30,color:'#26a69a',lineStyle:2,title:'30'});

const macd=mk('macd',140);
const macdHist=macd.addHistogramSeries({});
macdHist.setData(DATA.macd.hist.map(p=>({time:p.time,value:p.value,
  color:p.value>=0?'#26a69a':'#ef5350'})));
const macdLine=macd.addLineSeries({color:'#5b8def',lineWidth:1});macdLine.setData(DATA.macd.macd);
const macdSig=macd.addLineSeries({color:'#e0a73e',lineWidth:1});macdSig.setData(DATA.macd.signal);

const stoch=mk('stoch',140);
const kS=stoch.addLineSeries({color:'#5b8def',lineWidth:1});kS.setData(DATA.stochastic.k);
const dS=stoch.addLineSeries({color:'#e0a73e',lineWidth:1});dS.setData(DATA.stochastic.d);
kS.createPriceLine({price:80,color:'#ef5350',lineStyle:2,title:'80'});
kS.createPriceLine({price:20,color:'#26a69a',lineStyle:2,title:'20'});

const charts=[price,rsi,macd,stoch];let syncing=false;
charts.forEach(src=>src.timeScale().subscribeVisibleLogicalRangeChange(range=>{
  if(syncing||!range)return;syncing=true;
  charts.forEach(dst=>{if(dst!==src)dst.timeScale().setVisibleLogicalRange(range);});
  syncing=false;}));
price.timeScale().fitContent();
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


def render_chart_html(chart_data, meta=None):
    meta = meta or {}
    ticker = chart_data.get("ticker", "?")
    price = chart_data.get("price", "")
    as_of = chart_data.get("as_of", "")
    title = f"{ticker} · {price}"
    sub_bits = [f"as of {as_of}", f"period {chart_data.get('period', '')}"]
    if meta.get("call"):
        call_bit = f"TRaid call: {meta['call']}"
        if meta.get("confidence"):
            call_bit += f" ({meta['confidence']})"
        if meta.get("call_date"):
            call_bit += f" — {meta['call_date']}"
        sub_bits.insert(0, call_bit)
    subtitle = "  ·  ".join(b for b in sub_bits if b)
    return (
        _TEMPLATE
        .replace("__CDN__", CDN)
        .replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__LEGEND__", _LEGEND)
        .replace("__DATA__", json.dumps(chart_data))
    )
