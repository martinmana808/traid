// No-network smoke test for the TRaid bot webhook's pure logic.
// Run: node scripts/telegram-smoke-test.mjs
import assert from "node:assert";
import { ownerMessage, buildUserPrompt, summarizeChart } from "../api/telegram.mjs";

const OWNER = "12345";

// 1. Owner's message with text → accepted.
const ok = ownerMessage({ message: { chat: { id: 12345 }, text: "hi" } }, OWNER);
assert(ok && ok.text === "hi", "owner text message should be accepted");

// 2. Stranger → rejected.
assert(
  ownerMessage({ message: { chat: { id: 999 }, text: "hi" } }, OWNER) === null,
  "stranger should be rejected",
);

// 3. Owner but no text (e.g. a sticker) → rejected.
assert(
  ownerMessage({ message: { chat: { id: 12345 } } }, OWNER) === null,
  "non-text should be rejected",
);

// 4. Garbage update → rejected, no throw.
assert(ownerMessage({}, OWNER) === null, "empty update should be rejected");

// 5. Prompt includes the quoted digest when replying, plus portfolio.
const prompt = buildUserPrompt(
  {
    text: "is the dip a buy?",
    reply_to_message: { text: "📊 TRaid Daily — RKLB -6%" },
  },
  '{"holdings":[{"ticker":"RKLB"}]}',
);
assert(prompt.includes("RKLB -6%"), "prompt should include the quoted digest");
assert(prompt.includes("is the dip a buy?"), "prompt should include his question");
assert(prompt.includes("portfolio"), "prompt should include portfolio context");

// 6. Prompt works with no quote and no portfolio.
const bare = buildUserPrompt({ text: "hey" }, undefined);
assert(bare.includes("hey") && !bare.includes("replying"), "bare prompt ok");

// 7. summarizeChart computes price, change %, and moving averages.
const fixture = {
  chart: {
    result: [
      {
        meta: { symbol: "TEST", currency: "USD", regularMarketPrice: 110, fiftyTwoWeekHigh: 120, fiftyTwoWeekLow: 80 },
        indicators: { quote: [{ close: Array(200).fill(100) }] },
      },
    ],
  },
};
const q = summarizeChart(fixture, "test");
assert(q.ticker === "TEST", "ticker from meta.symbol");
assert(q.price === 110, "price from regularMarketPrice");
assert(q.ma50 === 100 && q.ma200 === 100, "moving averages computed");
assert(q.change_pct === 10, "change % vs previous close"); // (110-100)/100*100
assert(q.high_52w === 120 && q.low_52w === 80, "52-week range passed through");

// 8. summarizeChart degrades gracefully on a bad payload.
const bad = summarizeChart({}, "xyz");
assert(bad.ticker === "XYZ" && bad.error === "no data", "bad payload → error, no throw");

console.log("✓ all smoke tests passed");
