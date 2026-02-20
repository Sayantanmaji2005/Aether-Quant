from __future__ import annotations

import hmac
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import uuid4

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aetherquant.backtest import BacktestEngine
from aetherquant.config import Settings
from aetherquant.data.yfinance_provider import YFinanceProvider
from aetherquant.execution.base import Broker
from aetherquant.execution.live_broker import LiveBroker
from aetherquant.execution.paper_broker import PaperBroker
from aetherquant.execution.trading_engine import TradingEngine
from aetherquant.optimization import (
    OptimizerConstraints,
    mean_variance_weights,
    risk_parity_weights,
)
from aetherquant.portfolio import PortfolioConfig
from aetherquant.rate_limit import InMemoryRateLimiter
from aetherquant.storage import RunStorage
from aetherquant.strategy import default_momentum_strategy

logger = logging.getLogger(__name__)


class BacktestRequest(BaseModel):
    symbol: str = "SPY"
    period: str = "1y"
    interval: str = "1d"


class PaperTradeRequest(BaseModel):
    symbol: str = "SPY"
    period: str = "6mo"
    interval: str = "1d"
    broker: Literal["paper", "live"] = "paper"
    broker_provider: Literal["generic-rest", "alpaca"] | None = None
    broker_endpoint: str | None = None
    broker_key_id: str | None = None
    broker_token: str | None = None
    slippage_bps: float | None = Field(default=None, ge=0.0)


class OptimizeRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "TLT"])
    period: str = "1y"
    interval: str = "1d"
    method: Literal["risk-parity", "mean-variance"] = "risk-parity"
    allow_short: bool = False
    max_weight: float = Field(default=1.0, gt=0.0)
    risk_aversion: float = Field(default=3.0, gt=0.0)


PAGE = """
<!doctype html>
<html>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>AetherQuant Web</title>
<style>
:root{
  --bg-a:#e8f2ff;
  --bg-b:#ffe7d2;
  --ink:#10213a;
  --muted:#4d5f7b;
  --card:#ffffffd9;
  --card-border:#a8bad8;
  --run-a:#0f75d8;
  --run-b:#10b1a2;
  --run-shadow:#0d7fc74d;
  --soft-bg:#edf4ff;
  --soft-border:#b8c9e2;
  --soft-ink:#1f3658;
  --out-bg:#06142b;
  --out-ink:#dbeafe;
}
*{box-sizing:border-box}
body{
  font-family:"Avenir Next","Segoe UI","Trebuchet MS",Verdana,sans-serif;
  max-width:1100px;
  margin:0 auto;
  padding:20px 14px 32px;
  color:var(--ink);
  min-height:100vh;
  position:relative;
  overflow-x:hidden;
  background:
    radial-gradient(1400px 700px at -20% -20%, #b4d6ff 0%, transparent 58%),
    radial-gradient(900px 560px at 120% -10%, #ffd8b2 0%, transparent 60%),
    linear-gradient(120deg, var(--bg-a), var(--bg-b));
}
body::before,
body::after{
  content:"";
  position:fixed;
  pointer-events:none;
  z-index:-1;
}
body::before{
  inset:0;
  background:
    repeating-linear-gradient(
      -20deg,
      transparent 0 22px,
      #ffffff26 22px 24px
    );
  opacity:.32;
}
body::after{
  width:460px;
  height:460px;
  right:-160px;
  bottom:-150px;
  border-radius:50%;
  background:radial-gradient(circle at 30% 30%, #3fa5ff66, transparent 70%);
  filter:blur(14px);
  animation:floatBlob 8s ease-in-out infinite alternate;
}
h1{
  margin:0;
  font-size:46px;
  line-height:1.06;
  letter-spacing:0.2px;
  text-wrap:balance;
}
h3{
  margin:0 0 12px;
  font-size:30px;
  line-height:1.12;
  letter-spacing:0.2px;
}
.hero{
  margin-bottom:12px;
  padding:18px 18px 14px;
  border-radius:20px;
  border:1px solid #b4c5de;
  background:
    linear-gradient(160deg, #ffffffd4, #eaf4ffd9 62%, #fff4e6d4);
  box-shadow:
    0 20px 40px -32px #12213c,
    inset 0 1px 0 #ffffffcc;
  animation:rise .45s ease both;
}
.subtitle{
  margin:8px 0 0;
  color:var(--muted);
  font-size:24px;
  line-height:1.35;
}
.card{
  background:var(--card);
  border:1px solid var(--card-border);
  border-radius:20px;
  padding:16px;
  margin:14px 0;
  backdrop-filter:blur(6px);
  box-shadow:
    0 24px 50px -38px #183259,
    inset 0 1px 0 #ffffffd4;
  animation:rise .48s ease both;
  position:relative;
  overflow:hidden;
}
.card::before{
  content:"";
  position:absolute;
  inset:-40% auto auto -20%;
  width:220px;
  height:220px;
  border-radius:50%;
  background:radial-gradient(circle, #7dc0ff3f, transparent 70%);
  pointer-events:none;
}
.card:nth-of-type(2){animation-delay:.05s}
.card:nth-of-type(3){animation-delay:.1s}
.card:nth-of-type(4){animation-delay:.15s}
.card:nth-of-type(5){animation-delay:.2s}
.row{display:flex;gap:8px;flex-wrap:wrap}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.chip{
  padding:6px 10px;
  border:1px solid var(--soft-border);
  border-radius:999px;
  background:linear-gradient(180deg, #f6faff, #ebf3ff);
  color:var(--soft-ink);
  font-size:12px;
  cursor:pointer;
  transition:transform .14s ease, background .14s ease, border-color .14s ease;
}
.chip:hover{
  background:#dfebff;
  border-color:#8fb2db;
  transform:translateY(-1px);
}
input,select,button{
  padding:10px 12px;
  border:1px solid #b4c3da;
  border-radius:10px;
  font-size:15px;
}
input,select{
  background:#ffffffd9;
  color:#112444;
}
input:focus,select:focus{
  outline:none;
  border-color:#1f7bd9;
  box-shadow:0 0 0 3px #1578dd2e;
}
button{
  cursor:pointer;
  transition:transform .16s ease, filter .16s ease, box-shadow .16s ease;
}
.btn-run{
  background:linear-gradient(135deg, var(--run-a), var(--run-b));
  color:#fff;
  border:none;
  box-shadow:0 10px 16px -12px var(--run-shadow);
}
.btn-soft{
  background:var(--soft-bg);
  color:var(--soft-ink);
  border:1px solid var(--soft-border);
}
button:hover{
  filter:brightness(1.03);
  transform:translateY(-1px);
}
button:active{transform:translateY(0)}
pre{
  background:linear-gradient(180deg, var(--out-bg), #050f1f);
  color:var(--out-ink);
  padding:14px;
  border-radius:14px;
  overflow:auto;
  border:1px solid #1f3355;
  box-shadow:inset 0 0 30px #0f2141;
  min-height:98px;
  animation:fadeIn .5s ease both;
}
.status{
  display:inline-block;
  font-size:13px;
  padding:4px 10px;
  border-radius:999px;
  background:#d6fbf4;
  color:#0a6b5d;
  margin-left:10px;
  vertical-align:middle;
}
.card .subtitle{
  font-size:16px;
  margin:8px 0 0;
}
.hint-box{
  margin-top:10px;
  padding:10px 12px;
  border-radius:10px;
  border:1px dashed #7fa9d9;
  background:#e8f2ff;
  color:#0d2f57;
  font-size:13px;
  font-family:Consolas,"Courier New",monospace;
  overflow-wrap:anywhere;
}
.hint-row{
  display:flex;
  gap:8px;
  align-items:center;
  flex-wrap:wrap;
}
#hint_key_value{
  min-width:340px;
  max-width:100%;
  font-family:Consolas,"Courier New",monospace;
}
.corner-tag{
  position:fixed;
  right:12px;
  bottom:10px;
  padding:6px 10px;
  border-radius:999px;
  border:1px solid #9cb2d2;
  background:#ffffffdb;
  color:#1f3658;
  font-size:11px;
  letter-spacing:.3px;
  z-index:30;
  box-shadow:0 8px 20px -16px #0f223f;
}
@media (max-width: 760px){
  h1{font-size:38px}
  h3{font-size:28px}
  .subtitle{font-size:21px}
  .hero{padding:16px 14px 12px}
  .card{padding:14px}
  .corner-tag{
    right:8px;
    bottom:8px;
    font-size:10px;
  }
}
@keyframes rise{
  from{opacity:0; transform:translateY(8px)}
  to{opacity:1; transform:translateY(0)}
}
@keyframes fadeIn{
  from{opacity:.6}
  to{opacity:1}
}
@keyframes floatBlob{
  from{transform:translateY(0)}
  to{transform:translateY(-24px)}
}
</style>
</head>
<body>
<div class='hero'>
<h1>AetherQuant Dashboard</h1>
<p class='subtitle'>Quant workflows for backtesting, paper/live execution, and optimization.
<span class='status'>Live UI</span></p>
</div>
<div class='card'>
<h3>API Security</h3>
<div class='row'>
<input id='api_key' placeholder='X-API-Key (optional)' style='min-width:260px'/>
<button type='button' class='btn-soft' onclick='clearApiKey()'>Clear Key</button>
<button type='button' class='btn-soft' onclick='useHintKey()'>Use Hint Key</button>
</div>
<p class='subtitle'>Use the trader/admin API key shared by your deployment owner.</p>
<div class='hint-box' id='hint_key_box'>
<div>Hint key (protected):</div>
<div class='hint-row'>
<input id='hint_key_value' type='password' readonly
value='F15E3458EC2562D0545E14F435AF2BC58BE0FD23EF3730D8FAAC4722A44E6B56'/>
<button type='button' class='btn-soft' onclick='toggleHintKey()' id='hint_toggle_btn'>Show</button>
<button type='button' class='btn-soft' onclick='copyHintKey()'>Copy</button>
</div>
</div>
</div>
<div class='card'>
<h3>Backtest</h3>
<div class='row'>
<input id='b_symbol' value='SPY' placeholder='Symbol' list='symbol_list'/>
<select id='b_symbol_pick' onchange='pickSymbol("b_symbol", this.value)'>
<option value=''>Popular ETFs</option>
<option value='SPY'>SPY</option>
<option value='QQQ'>QQQ</option>
<option value='DIA'>DIA</option>
<option value='IWM'>IWM</option>
<option value='VTI'>VTI</option>
<option value='VOO'>VOO</option>
<option value='IVV'>IVV</option>
<option value='TLT'>TLT</option>
<option value='IEF'>IEF</option>
<option value='GLD'>GLD</option>
<option value='SLV'>SLV</option>
<option value='USO'>USO</option>
<option value='XLF'>XLF</option>
<option value='XLK'>XLK</option>
<option value='XLE'>XLE</option>
</select>
<input id='b_period' value='1y' placeholder='Period'/>
<input id='b_interval' value='1d' placeholder='Interval'/>
<button class='btn-run' onclick='runBacktest()'>Run</button>
<button type='button' class='btn-soft' onclick='resetBacktestDefaults()'>Use Defaults</button>
</div>
<div class='chips'>
<button type='button' class='chip' onclick='setBacktestSymbol("SPY")'>SPY</button>
<button type='button' class='chip' onclick='setBacktestSymbol("QQQ")'>QQQ</button>
<button type='button' class='chip' onclick='setBacktestSymbol("DIA")'>DIA</button>
<button type='button' class='chip' onclick='setBacktestSymbol("IWM")'>IWM</button>
<button type='button' class='chip' onclick='setBacktestSymbol("GLD")'>GLD</button>
</div>
</div>
<div class='card'>
<h3>Paper Trade</h3>
<div class='row'>
<input id='p_symbol' value='SPY' list='symbol_list'/>
<select id='p_symbol_pick' onchange='pickSymbol("p_symbol", this.value)'>
<option value=''>Popular ETFs</option>
<option value='SPY'>SPY</option>
<option value='QQQ'>QQQ</option>
<option value='DIA'>DIA</option>
<option value='IWM'>IWM</option>
<option value='VTI'>VTI</option>
<option value='VOO'>VOO</option>
<option value='IVV'>IVV</option>
<option value='TLT'>TLT</option>
<option value='IEF'>IEF</option>
<option value='GLD'>GLD</option>
<option value='SLV'>SLV</option>
<option value='USO'>USO</option>
<option value='XLF'>XLF</option>
<option value='XLK'>XLK</option>
<option value='XLE'>XLE</option>
</select>
<input id='p_period' value='6mo'/>
<input id='p_interval' value='1d'/>
<select id='p_broker'>
<option value='paper'>paper</option>
<option value='live'>live</option>
</select>
<select id='p_provider'>
<option value='generic-rest'>generic-rest</option>
<option value='alpaca'>alpaca</option>
</select>
<input id='p_endpoint' placeholder='Broker Endpoint' style='min-width:220px'/>
<input id='p_key_id' placeholder='Broker Key ID (alpaca)'/>
<input id='p_token' placeholder='Broker Token/Secret' style='min-width:220px'/>
<button class='btn-run' onclick='runPaper()'>Run</button>
<button type='button' class='btn-soft' onclick='resetPaperDefaults()'>Use Defaults</button>
</div>
<div class='chips'>
<button type='button' class='chip' onclick='setPaperSymbol("SPY")'>SPY</button>
<button type='button' class='chip' onclick='setPaperSymbol("QQQ")'>QQQ</button>
<button type='button' class='chip' onclick='setPaperSymbol("DIA")'>DIA</button>
<button type='button' class='chip' onclick='setPaperSymbol("IWM")'>IWM</button>
<button type='button' class='chip' onclick='setPaperSymbol("TLT")'>TLT</button>
</div>
</div>
<div class='card'>
<h3>Optimize</h3>
<div class='row'>
<input id='o_symbols' value='SPY,QQQ,TLT' style='min-width:220px'/>
<select id='o_add_symbol' onchange='addOptimizeSymbol(this.value)'>
<option value=''>Add Symbol</option>
<option value='SPY'>SPY</option>
<option value='QQQ'>QQQ</option>
<option value='DIA'>DIA</option>
<option value='IWM'>IWM</option>
<option value='VTI'>VTI</option>
<option value='VOO'>VOO</option>
<option value='IVV'>IVV</option>
<option value='TLT'>TLT</option>
<option value='IEF'>IEF</option>
<option value='GLD'>GLD</option>
<option value='SLV'>SLV</option>
<option value='USO'>USO</option>
<option value='XLF'>XLF</option>
<option value='XLK'>XLK</option>
<option value='XLE'>XLE</option>
</select>
<select id='o_method'>
<option value='risk-parity'>risk-parity</option>
<option value='mean-variance'>mean-variance</option>
</select>
<button class='btn-run' onclick='runOptimize()'>Run</button>
<button type='button' class='btn-soft' onclick='clearOptimizeSymbols()'>Clear</button>
<button type='button' class='btn-soft' onclick='resetOptimizeDefaults()'>Use Defaults</button>
</div>
<div class='chips'>
<button type='button' class='chip' onclick='setOptimizeSymbols("SPY,QQQ,TLT")'>SPY,QQQ,TLT</button>
<button type='button' class='chip' onclick='setOptimizeSymbols("SPY,IEF,GLD")'>SPY,IEF,GLD</button>
<button type='button' class='chip' onclick='setOptimizeSymbols("QQQ,XLK,XLF")'>QQQ,XLK,XLF</button>
<button type='button' class='chip' onclick='setOptimizeSymbols("VOO,IWM,TLT")'>VOO,IWM,TLT</button>
</div>
</div>
<datalist id='symbol_list'>
<option value='SPY'></option>
<option value='QQQ'></option>
<option value='DIA'></option>
<option value='IWM'></option>
<option value='VTI'></option>
<option value='VOO'></option>
<option value='IVV'></option>
<option value='TLT'></option>
<option value='IEF'></option>
<option value='GLD'></option>
<option value='SLV'></option>
<option value='USO'></option>
<option value='XLF'></option>
<option value='XLK'></option>
<option value='XLE'></option>
</datalist>
<pre id='out'>Ready.</pre>
<script>
const apiKeyInput = document.getElementById('api_key');
const bSymbolInput = document.getElementById('b_symbol');
const bPeriodInput = document.getElementById('b_period');
const bIntervalInput = document.getElementById('b_interval');
const pSymbolInput = document.getElementById('p_symbol');
const pPeriodInput = document.getElementById('p_period');
const pIntervalInput = document.getElementById('p_interval');
const pBrokerSelect = document.getElementById('p_broker');
const pProviderSelect = document.getElementById('p_provider');
const pEndpointInput = document.getElementById('p_endpoint');
const pKeyIdInput = document.getElementById('p_key_id');
const pTokenInput = document.getElementById('p_token');
const oSymbolsInput = document.getElementById('o_symbols');
const oAddSymbolSelect = document.getElementById('o_add_symbol');
const oMethodSelect = document.getElementById('o_method');
const STORAGE_KEYS = {
  apiKey: 'aetherq.api_key',
  backtestSymbol: 'aetherq.backtest.symbol',
  paperSymbol: 'aetherq.paper.symbol',
  optimizeSymbols: 'aetherq.optimize.symbols'
};

function readStorage(key){
  try { return localStorage.getItem(key); } catch (_) { return null; }
}
function writeStorage(key, value){
  try { localStorage.setItem(key, value); } catch (_) {}
}
function removeStorage(key){
  try { localStorage.removeItem(key); } catch (_) {}
}
function bindPersist(inputEl, key){
  const saved = readStorage(key);
  if (saved) inputEl.value = saved;
  inputEl.addEventListener('input', () => writeStorage(key, inputEl.value.trim()));
}
function clearApiKey(){
  apiKeyInput.value = '';
  removeStorage(STORAGE_KEYS.apiKey);
}
function useHintKey(){
  const hint = 'F15E3458EC2562D0545E14F435AF2BC58BE0FD23EF3730D8FAAC4722A44E6B56';
  apiKeyInput.value = hint;
  writeStorage(STORAGE_KEYS.apiKey, hint);
}
function toggleHintKey(){
  const hintInput = document.getElementById('hint_key_value');
  const btn = document.getElementById('hint_toggle_btn');
  if (!hintInput || !btn) return;
  if (hintInput.type === 'password') {
    hintInput.type = 'text';
    btn.textContent = 'Hide';
  } else {
    hintInput.type = 'password';
    btn.textContent = 'Show';
  }
}
function copyHintKey(){
  const hintInput = document.getElementById('hint_key_value');
  if (!hintInput) return;
  const value = hintInput.value;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(value);
    return;
  }
  hintInput.type = 'text';
  hintInput.select();
  document.execCommand('copy');
  hintInput.type = 'password';
}
function resetBacktestDefaults(){
  bSymbolInput.value = 'SPY';
  bPeriodInput.value = '1y';
  bIntervalInput.value = '1d';
  writeStorage(STORAGE_KEYS.backtestSymbol, bSymbolInput.value);
}
function setBacktestSymbol(symbol){
  bSymbolInput.value = symbol;
  writeStorage(STORAGE_KEYS.backtestSymbol, symbol);
}
function resetPaperDefaults(){
  pSymbolInput.value = 'SPY';
  pPeriodInput.value = '6mo';
  pIntervalInput.value = '1d';
  pBrokerSelect.value = 'paper';
  pProviderSelect.value = 'generic-rest';
  pEndpointInput.value = '';
  pKeyIdInput.value = '';
  pTokenInput.value = '';
  writeStorage(STORAGE_KEYS.paperSymbol, pSymbolInput.value);
}
function setPaperSymbol(symbol){
  pSymbolInput.value = symbol;
  writeStorage(STORAGE_KEYS.paperSymbol, symbol);
}
function clearOptimizeSymbols(){
  oSymbolsInput.value = '';
  removeStorage(STORAGE_KEYS.optimizeSymbols);
}
function resetOptimizeDefaults(){
  oSymbolsInput.value = 'SPY,QQQ,TLT';
  oMethodSelect.value = 'risk-parity';
  oAddSymbolSelect.value = '';
  writeStorage(STORAGE_KEYS.optimizeSymbols, oSymbolsInput.value);
}
function setOptimizeSymbols(value){
  oSymbolsInput.value = value;
  writeStorage(STORAGE_KEYS.optimizeSymbols, value);
}

async function post(url, payload){
  const apiKey = apiKeyInput.value.trim();
  const headers = {'Content-Type':'application/json'};
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
    headers['Authorization'] = `Bearer ${apiKey}`;
  }
  const r = await fetch(url,{
    method:'POST',
    headers,
    body:JSON.stringify(payload)
  });
  const j = await r.json();
  const out = document.getElementById('out');
  out.textContent = JSON.stringify(j,null,2);
  out.animate(
    [{opacity:.7, transform:'translateY(2px)'},{opacity:1, transform:'translateY(0)'}],
    {duration:220, easing:'ease-out'}
  );
}
function runBacktest(){
  post('/api/backtest',{symbol:bSymbolInput.value,period:bPeriodInput.value,interval:bIntervalInput.value});
}
function pickSymbol(targetId, value){
  if (!value) return;
  const el = document.getElementById(targetId);
  if (el) el.value = value;
}
function addOptimizeSymbol(value){
  if (!value) return;
  const parts = oSymbolsInput.value.split(',').map(x => x.trim().toUpperCase()).filter(Boolean);
  if (!parts.includes(value)) parts.push(value);
  oSymbolsInput.value = parts.join(',');
  oAddSymbolSelect.value = '';
}
function runPaper(){
  post('/api/papertrade',{
    symbol:pSymbolInput.value,
    period:pPeriodInput.value,
    interval:pIntervalInput.value,
    broker:pBrokerSelect.value,
    broker_provider:pProviderSelect.value || null,
    broker_endpoint:pEndpointInput.value.trim() || null,
    broker_key_id:pKeyIdInput.value.trim() || null,
    broker_token:pTokenInput.value.trim() || null
  });
}
function runOptimize(){
  post('/api/optimize',{symbols:oSymbolsInput.value.split(',').map(x=>x.trim()).filter(Boolean),method:oMethodSelect.value});
}
bindPersist(apiKeyInput, STORAGE_KEYS.apiKey);
bindPersist(bSymbolInput, STORAGE_KEYS.backtestSymbol);
bindPersist(pSymbolInput, STORAGE_KEYS.paperSymbol);
bindPersist(oSymbolsInput, STORAGE_KEYS.optimizeSymbols);
</script>
<div class='corner-tag'>THIS WEBSITE IS MADE BY SAYANTAN MAJI</div>
</body>
</html>
"""


def _extract_api_key(request: Request) -> str | None:
    provided_key = request.headers.get("X-API-Key")
    if not provided_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header[:7].lower() == "bearer ":
            provided_key = auth_header[7:]
    if not provided_key:
        return None
    normalized = provided_key.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()
    return normalized or None


def _require_api_key(request: Request, settings: Settings) -> None:
    _require_role(request, settings, allowed_roles={"trader", "admin"})


def _request_role(request: Request, settings: Settings) -> str:
    if not settings.api_key and not settings.admin_api_key:
        return "anonymous"
    provided_key = _extract_api_key(request)
    if not provided_key:
        return ""
    if settings.admin_api_key and hmac.compare_digest(provided_key, settings.admin_api_key):
        return "admin"
    if settings.api_key and hmac.compare_digest(provided_key, settings.api_key):
        return "trader"
    return ""


def _require_role(request: Request, settings: Settings, allowed_roles: set[str]) -> str:
    role = _request_role(request, settings)
    if role == "anonymous":
        return role
    if not role:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    return role


def _get_storage(settings: Settings) -> RunStorage | None:
    if not settings.database_url:
        return None
    storage = RunStorage(settings.database_url)
    storage.init_schema()
    return storage


def create_app() -> FastAPI:
    app = FastAPI(title="AetherQuant Web", version="0.1.0")
    rate_limit_per_minute = int(getattr(Settings(), "rate_limit_per_minute", 120))
    limiter = InMemoryRateLimiter(rate_limit_per_minute)

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = Settings()
        storage = _get_storage(settings)
        actor_role = _request_role(request, settings) or "unauthenticated"
        principal = _extract_api_key(request) or (
            request.client.host if request.client else "unknown"
        )
        request_id = request.headers.get("X-Request-ID", uuid4().hex)
        started = time.perf_counter()
        if request.url.path.startswith("/api/"):
            allowed, retry_after = limiter.allow(principal)
            if not allowed:
                response = Response(status_code=429, content='{"detail":"Rate limit exceeded"}')
                response.headers["Content-Type"] = "application/json"
                response.headers["Retry-After"] = str(max(1, int(retry_after)))
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        logger.info(
            "%s %s status=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
        if storage is not None and request.url.path.startswith("/api/"):
            try:
                storage.record_audit_event(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    request_id=request_id,
                    actor_role=actor_role,
                )
            except ValueError:
                logger.exception("Failed to persist audit event")
        return response

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return PAGE

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        settings = Settings()
        return {"status": "ok", "env": settings.env, "app": settings.app_name}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/api/backtest")
    def backtest(req: BacktestRequest, request: Request) -> dict[str, float | int | str]:
        try:
            settings = Settings()
            _require_role(request, settings, allowed_roles={"trader", "admin"})
            storage = _get_storage(settings)
            provider = YFinanceProvider()
            frame = provider.fetch_ohlcv(req.symbol, period=req.period, interval=req.interval)

            engine = BacktestEngine(
                strategy=default_momentum_strategy(),
                portfolio_config=PortfolioConfig(
                    initial_cash=settings.initial_cash,
                    commission_bps=settings.commission_bps,
                ),
            )
            result = engine.run(frame)
            payload: dict[str, float | int | str] = {
                "symbol": req.symbol,
                "rows": int(len(frame)),
                "annual_return": round(result.annual_return, 6),
                "max_drawdown": round(result.max_drawdown, 6),
                "sharpe": round(result.sharpe, 6),
                "final_equity": round(float(result.equity.iloc[-1]), 2),
                "benchmark_annual_return": round(result.benchmark_annual_return, 6),
                "benchmark_max_drawdown": round(result.benchmark_max_drawdown, 6),
                "benchmark_sharpe": round(result.benchmark_sharpe, 6),
                "benchmark_final_equity": round(float(result.benchmark_equity.iloc[-1]), 2),
                "excess_annual_return": round(
                    result.annual_return - result.benchmark_annual_return,
                    6,
                ),
            }
            if storage is not None:
                run_id = storage.record_run(
                    run_type="backtest",
                    symbol=req.symbol,
                    period=req.period,
                    interval=req.interval,
                    payload=payload,
                    metrics={
                        "annual_return": result.annual_return,
                        "max_drawdown": result.max_drawdown,
                        "sharpe": result.sharpe,
                        "benchmark_annual_return": result.benchmark_annual_return,
                        "benchmark_max_drawdown": result.benchmark_max_drawdown,
                        "benchmark_sharpe": result.benchmark_sharpe,
                        "excess_annual_return": (
                            result.annual_return - result.benchmark_annual_return
                        ),
                    },
                )
                payload["run_id"] = run_id
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/papertrade")
    def papertrade(req: PaperTradeRequest, request: Request) -> dict[str, float | int | str]:
        try:
            settings = Settings()
            _require_role(request, settings, allowed_roles={"trader", "admin"})
            storage = _get_storage(settings)
            provider = YFinanceProvider()
            frame = provider.fetch_ohlcv(req.symbol, period=req.period, interval=req.interval)
            targets = default_momentum_strategy().generate_signals(frame).clip(lower=0.0)

            broker: Broker
            if req.broker == "paper":
                broker = PaperBroker(
                    starting_cash=settings.initial_cash,
                    commission_bps=settings.commission_bps,
                    slippage_bps=(
                        settings.slippage_bps if req.slippage_bps is None else req.slippage_bps
                    ),
                )
            else:
                broker_provider = req.broker_provider or settings.live_broker_provider
                endpoint = req.broker_endpoint or settings.live_broker_endpoint
                key_id = req.broker_key_id or settings.live_broker_key_id
                token = req.broker_token or settings.live_broker_token
                if not endpoint:
                    raise HTTPException(
                        status_code=400,
                        detail="broker_endpoint is required for live broker.",
                    )
                if not token:
                    raise HTTPException(
                        status_code=400,
                        detail="broker_token is required for live broker.",
                    )
                if broker_provider == "alpaca" and not key_id:
                    raise HTTPException(
                        status_code=400,
                        detail="broker_key_id is required for alpaca provider.",
                    )
                broker = LiveBroker(
                    endpoint=endpoint,
                    api_key_id=key_id,
                    api_token=token,
                    provider=broker_provider,
                    dry_run=settings.live_broker_dry_run,
                )
            run_result = TradingEngine(broker=broker, symbol=req.symbol).run(
                prices=frame["close"],
                target_positions=targets,
            )

            payload: dict[str, float | int | str] = {
                "symbol": req.symbol,
                "broker": req.broker,
                "orders_placed": run_result.orders_placed,
                "start_equity": round(float(run_result.equity_curve.iloc[0]), 2),
                "final_equity": round(float(run_result.equity_curve.iloc[-1]), 2),
            }
            if storage is not None:
                run_id = storage.record_run(
                    run_type="papertrade",
                    symbol=req.symbol,
                    period=req.period,
                    interval=req.interval,
                    payload=payload,
                    metrics={
                        "start_equity": float(run_result.equity_curve.iloc[0]),
                        "final_equity": float(run_result.equity_curve.iloc[-1]),
                    },
                    orders=run_result.orders,
                )
                payload["run_id"] = run_id
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/optimize")
    def optimize(req: OptimizeRequest, request: Request) -> dict[str, object]:
        try:
            settings = Settings()
            _require_role(request, settings, allowed_roles={"trader", "admin"})
            storage = _get_storage(settings)
            provider = YFinanceProvider()
            normalized = [s.strip().upper() for s in req.symbols if s.strip()]
            if len(normalized) < 2:
                raise HTTPException(status_code=400, detail="Provide at least two symbols.")
            if len(set(normalized)) != len(normalized):
                raise HTTPException(status_code=400, detail="symbols must be unique.")

            close_data: dict[str, pd.Series] = {}
            for symbol in normalized:
                frame = provider.fetch_ohlcv(symbol, period=req.period, interval=req.interval)
                close_data[symbol] = frame["close"]

            close = pd.DataFrame(close_data).dropna(how="any")
            returns = close.pct_change().dropna(how="any")
            if returns.empty:
                raise HTTPException(status_code=400, detail="No overlapping data to optimize.")

            constraints = OptimizerConstraints(
                allow_short=req.allow_short,
                max_weight=req.max_weight,
            )
            if req.method == "risk-parity":
                weights = risk_parity_weights(returns, constraints=constraints)
            else:
                weights = mean_variance_weights(
                    returns,
                    risk_aversion=req.risk_aversion,
                    constraints=constraints,
                )

            payload: dict[str, object] = {
                "method": req.method,
                "symbols": normalized,
                "weights": {k: round(float(v), 6) for k, v in weights.items()},
            }
            if storage is not None:
                run_id = storage.record_run(
                    run_type="optimize",
                    symbol=",".join(normalized),
                    period=req.period,
                    interval=req.interval,
                    payload=payload,
                    metrics={f"weight_{k}": float(v) for k, v in weights.items()},
                )
                payload["run_id"] = run_id
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/runs")
    def runs(request: Request, limit: int = 20) -> dict[str, object]:
        settings = Settings()
        _require_role(request, settings, allowed_roles={"admin"})
        storage = _get_storage(settings)
        if storage is None:
            raise HTTPException(status_code=400, detail="Persistence is not configured.")
        rows = storage.list_runs(limit=limit)
        return {
            "runs": [
                {
                    "run_id": row.run_id,
                    "created_at": row.created_at,
                    "run_type": row.run_type,
                    "symbol": row.symbol,
                    "final_equity": row.final_equity,
                    "orders_placed": row.orders_placed,
                }
                for row in rows
            ]
        }

    @app.get("/api/audit")
    def audit(request: Request, limit: int = 100) -> dict[str, object]:
        settings = Settings()
        _require_role(request, settings, allowed_roles={"admin"})
        storage = _get_storage(settings)
        if storage is None:
            raise HTTPException(status_code=400, detail="Persistence is not configured.")
        rows = storage.list_audit_events(limit=limit)
        return {
            "events": [
                {
                    "event_id": row.event_id,
                    "created_at": row.created_at,
                    "method": row.method,
                    "path": row.path,
                    "status_code": row.status_code,
                    "request_id": row.request_id,
                    "actor_role": row.actor_role,
                }
                for row in rows
            ]
        }

    return app


def run() -> None:
    uvicorn.run("aetherquant.web.app:create_app", factory=True, host="127.0.0.1", port=8000)


app = create_app()
