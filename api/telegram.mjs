// TRaid two-way Telegram bot — webhook (v2: live quotes + portfolio).
//
// Free stack: Groq (free LLM, the same brain the daily digest uses) + Vercel
// Hobby (free hosting) + Yahoo Finance's free chart endpoint (no key) for LIVE
// prices. The OUTBOUND digest still runs from tools/watchdog.py on GitHub
// Actions — this file is the INBOUND half so Martin can chat with TRaid anywhere.
// Heavy/deep work (full optimization, tax, prediction ledger) stays in Claude Code.
//
// How it answers price questions: Groq calls the get_quote tool, this function
// fetches live data from Yahoo and computes 50/200-day moving averages, feeds it
// back, and Groq answers with REAL numbers — never prices from memory.
//
// Context per message (no database): his portfolio (PORTFOLIO_JSON, a Vercel
// SECRET env var — never the public repo) + the digest he replied to (Telegram
// hands us the quoted text). Locked to his chat id + a webhook secret.
//
// Required Vercel env vars (set in the dashboard, NOT in the repo):
//   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_WEBHOOK_SECRET,
//   GROQ_API_KEY (or GROK_API_KEY)
// Optional: GROQ_MODEL (default llama-3.3-70b-versatile), PORTFOLIO_JSON

const GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
const YAHOO_CHART = (t) =>
  `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(t)}?range=1y&interval=1d`;
const TELEGRAM_API = (token, method) =>
  `https://api.telegram.org/bot${token}/${method}`;

const SYSTEM_PROMPT =
  "You are TRaid, Martin's sharp, honest personal investment analyst, replying " +
  "in his Telegram chat while he's on the go. Martin is an NZ investor (base " +
  "currency NZD, high risk tolerance); his current portfolio is included in the " +
  "user message when available — use it. You have a get_quote tool that returns " +
  "LIVE market data (current price, today's % change, 50- and 200-day moving " +
  "averages, 52-week range). ALWAYS call get_quote for any question about a " +
  "stock's price, levels, trend, moving averages, or buy/sell timing — never " +
  "state prices or levels from memory, they will be wrong. Keep replies short " +
  "and skimmable for mobile (a few lines, no essays). Be direct and honest: no " +
  "hype, never blind buy/sell signals, flag uncertainty plainly. For genuinely " +
  "deep work (full portfolio optimization, tax/FIF, his prediction ledger), tell " +
  "him to open TRaid in Claude Code at home.";

const QUOTE_TOOL = {
  type: "function",
  function: {
    name: "get_quote",
    description:
      "Get LIVE market data for one stock ticker: current price, today's % " +
      "change, 50-day and 200-day moving averages, and 52-week high/low. Call " +
      "this whenever Martin asks about any stock's price, level, trend, moving " +
      "averages, or whether it's a buy/dip. Call it once per ticker mentioned.",
    parameters: {
      type: "object",
      properties: {
        ticker: { type: "string", description: "Stock ticker symbol, e.g. NVDA, TSLA, RKLB" },
      },
      required: ["ticker"],
    },
  },
};

// --- pure helpers (exported for testing) -----------------------------------

function round(x, n = 2) {
  if (x == null || Number.isNaN(Number(x))) return null;
  const p = 10 ** n;
  return Math.round(Number(x) * p) / p;
}

// Is this update from the owner, and does it carry usable text?
function ownerMessage(update, allowedChatId) {
  const msg = update && update.message;
  const chatId = msg && msg.chat && msg.chat.id;
  if (chatId == null || String(chatId) !== String(allowedChatId)) return null;
  if (!msg.text || !msg.text.trim()) return null;
  return msg;
}

// Build the Groq user prompt from the message + optional context.
function buildUserPrompt(msg, portfolioJson) {
  const quoted = msg.reply_to_message && msg.reply_to_message.text;
  const parts = [];
  if (portfolioJson) parts.push(`Martin's portfolio (NZD base):\n${portfolioJson}`);
  if (quoted) parts.push(`He is replying to this TRaid message:\n"""${quoted}"""`);
  parts.push(`Martin says: ${msg.text.trim()}`);
  return parts.join("\n\n");
}

// Pure: turn a Yahoo chart JSON payload into a compact quote summary.
function summarizeChart(data, ticker) {
  const res = data && data.chart && data.chart.result && data.chart.result[0];
  if (!res) return { ticker: String(ticker).toUpperCase(), error: "no data" };
  const m = res.meta || {};
  const closes = (
    (res.indicators && res.indicators.quote && res.indicators.quote[0] && res.indicators.quote[0].close) || []
  ).filter((c) => c != null);
  const price = m.regularMarketPrice != null ? m.regularMarketPrice : closes[closes.length - 1];
  const prev = closes.length >= 2 ? closes[closes.length - 2] : null;
  const ma = (n) => (closes.length >= n ? closes.slice(-n).reduce((a, b) => a + b, 0) / n : null);
  return {
    ticker: m.symbol || String(ticker).toUpperCase(),
    currency: m.currency || null,
    price: round(price),
    change_pct: price != null && prev ? round(((price - prev) / prev) * 100) : null,
    ma50: round(ma(50)),
    ma200: round(ma(200)),
    high_52w: round(m.fiftyTwoWeekHigh),
    low_52w: round(m.fiftyTwoWeekLow),
  };
}

// --- network -----------------------------------------------------------------

async function getQuote(ticker) {
  const t = String(ticker || "").trim();
  if (!t) return { ticker: "", error: "no ticker given" };
  try {
    const r = await fetch(YAHOO_CHART(t), { headers: { "User-Agent": "Mozilla/5.0 (TRaid bot)" } });
    if (!r.ok) return { ticker: t.toUpperCase(), error: `lookup failed (${r.status})` };
    return summarizeChart(await r.json(), t);
  } catch (e) {
    return { ticker: t.toUpperCase(), error: e.message };
  }
}

async function callGroq(apiKey, model, messages) {
  return fetch(GROQ_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      "User-Agent": "TRaid/1.0 (+https://github.com/martinmana808/traid)",
    },
    body: JSON.stringify({
      model,
      messages,
      tools: [QUOTE_TOOL],
      tool_choice: "auto",
      temperature: 0.5,
      max_tokens: 600,
    }),
  });
}

// Run the Groq chat loop, executing get_quote tool calls against live data.
async function groqChat(userPrompt) {
  const apiKey = process.env.GROQ_API_KEY || process.env.GROK_API_KEY;
  const model = process.env.GROQ_MODEL || "llama-3.3-70b-versatile";
  if (!apiKey) return "⚠️ TRaid bot isn't configured yet (missing Groq key).";

  const messages = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: userPrompt },
  ];

  try {
    for (let step = 0; step < 4; step++) {
      const r = await callGroq(apiKey, model, messages);
      if (!r.ok) return `⚠️ TRaid couldn't reach Groq (${r.status}). Try again shortly.`;
      const d = await r.json();
      const choice = d.choices && d.choices[0] && d.choices[0].message;
      if (!choice) return "⚠️ TRaid got an empty reply — try rephrasing.";

      messages.push(choice);
      const calls = choice.tool_calls || [];
      if (calls.length === 0) {
        return (choice.content || "").trim() || "⚠️ TRaid got an empty reply — try rephrasing.";
      }

      // Execute each requested tool call and feed the results back to Groq.
      for (const c of calls) {
        let args = {};
        try { args = JSON.parse(c.function.arguments || "{}"); } catch { /* leave empty */ }
        const result = c.function.name === "get_quote"
          ? await getQuote(args.ticker)
          : { error: `unknown tool ${c.function.name}` };
        messages.push({ role: "tool", tool_call_id: c.id, content: JSON.stringify(result) });
      }
    }
    return "⚠️ TRaid got stuck fetching data — try asking again in a moment.";
  } catch (e) {
    return `⚠️ TRaid hit a network error: ${e.message}`;
  }
}

async function sendTelegram(token, chatId, text) {
  try {
    await fetch(TELEGRAM_API(token, "sendMessage"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
  } catch (_e) {
    /* best-effort; nothing we can do if Telegram is unreachable */
  }
}

// --- handler -----------------------------------------------------------------

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(200).send("TRaid bot up");

  const secret = process.env.TELEGRAM_WEBHOOK_SECRET;
  if (secret && req.headers["x-telegram-bot-api-secret-token"] !== secret) {
    return res.status(401).send("unauthorized");
  }

  let update = req.body;
  if (!update || typeof update === "string") {
    try { update = JSON.parse(update || "{}"); } catch { update = {}; }
  }

  const msg = ownerMessage(update, process.env.TELEGRAM_CHAT_ID);
  if (!msg) return res.status(200).send("ignored");

  const reply = await groqChat(buildUserPrompt(msg, process.env.PORTFOLIO_JSON));
  await sendTelegram(process.env.TELEGRAM_BOT_TOKEN, msg.chat.id, reply);
  return res.status(200).send("ok");
}

// Exported for local smoke tests (see scripts/telegram-smoke-test.mjs).
export { ownerMessage, buildUserPrompt, summarizeChart, getQuote, groqChat };
