import asyncio
import json
import websockets
import pandas as pd
import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8090941115:AAEC9vEBPwbl6sQr0kubMv1lKlam1-vuUDI"
CHAT_ID = "8255900012"

DERIV_TOKEN = "cYsrjk5OZQ9C7Wf"
DERIV_WS = "wss://ws.derivws.com/websockets/v3?app_id=1089"

PAIRS = ["frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD"]
TIMEFRAME = 60  # 1-minute candles

PIP_TARGET = 0.0100
SL_BUFFER = 0.0015

wins = 0
losses = 0
signals_sent = 0


# ✅ SESSION FILTER (London + NY)
def session_open():
    hour = datetime.datetime.now(pytz.utc).hour
    return (7 <= hour <= 11) or (12 <= hour <= 20)


# ✅ AI CONFIDENCE SCORING
def ai_confidence_score(df, direction):
    recent_range = df["high"].tail(10).max() - df["low"].tail(10).min()
    avg_range = df["high"].tail(30).max() - df["low"].tail(30).min()
    strength = recent_range / avg_range if avg_range != 0 else 0

    score = 50
    if strength > 0.6:
        score += 20
    if strength > 0.8:
        score += 30

    if direction == "BUY" and df["close"].iloc[-1] > df["close"].iloc[-2]:
        score += 10
    if direction == "SELL" and df["close"].iloc[-1] < df["close"].iloc[-2]:
        score += 10

    return min(score, 100)


# ✅ GET LIVE CANDLES FROM DERIV
async def get_candles(symbol):
    async with websockets.connect(DERIV_WS) as ws:
        await ws.send(json.dumps({"authorize": DERIV_TOKEN}))
        await ws.recv()

        await ws.send(json.dumps({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": 100,
            "end": "latest",
            "style": "candles",
            "granularity": TIMEFRAME
        }))

        data = json.loads(await ws.recv())
        candles = data["candles"]

        df = pd.DataFrame(candles)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        return df


# ✅ SUPPORT / RESISTANCE
def detect_levels(df):
    support = df["low"].tail(30).min()
    resistance = df["high"].tail(30).max()
    return support, resistance


# ✅ SEND SIGNAL
async def send_signal(context, pair, direction, entry, sl, tp, analysis, confidence):
    global signals_sent
    signals_sent += 1

    msg = f"""
👑👑👑 REAL SIGNAL

💱 Pair: {pair.replace("frx","")}
⏱ Timeframe: 1M
📊 Confidence: {confidence}%

📈 Direction: {direction}

🔍 Analysis:
{analysis}

🏹 Entry: {entry:.5f}
🛑 Stop Loss: {sl:.5f}
🎯 Take Profit: {tp:.5f} (100 pips)
"""

    await context.bot.send_message(chat_id=CHAT_ID, text=msg)


# ✅ LIVE MARKET SCANNER
async def scan_markets(context):
    if not session_open():
        return

    for pair in PAIRS:
        df = await get_candles(pair)

        support, resistance = detect_levels(df)
        price = df["close"].iloc[-1]

        recent_low = df["low"].tail(10).min()
        recent_high = df["high"].tail(10).max()

        # ⚠️ BREAKOUT WARNING
        if price > resistance * 0.999:
            await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {pair} breakout soon!")

        if price < support * 1.001:
            await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {pair} breakdown soon!")

        # 🔴 SELL BREAKOUT
        if price < support:
            confidence = ai_confidence_score(df, "SELL")
            if confidence < 70:
                continue

            entry = price
            sl = recent_high + SL_BUFFER
            tp = entry - PIP_TARGET

            analysis = "Support broken with strong bearish pressure."

            await send_signal(context, pair, "SELL ⬇️", entry, sl, tp, analysis, confidence)

        # 🟢 BUY BREAKOUT
        if price > resistance:
            confidence = ai_confidence_score(df, "BUY")
            if confidence < 70:
                continue

            entry = price
            sl = recent_low - SL_BUFFER
            tp = entry + PIP_TARGET

            analysis = "Resistance breakout confirmed. Buyers dominate."

            await send_signal(context, pair, "BUY ⬆️", entry, sl, tp, analysis, confidence)


# ✅ TELEGRAM MENU
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🧠 Strategy", callback_data="strategy")],
        [InlineKeyboardButton("🤖 AI Explain", callback_data="ai")],
        [InlineKeyboardButton("📡 Scan Now", callback_data="scan")]
    ]
    await update.message.reply_text("🚀 Deriv Trading Bot Menu", reply_markup=InlineKeyboardMarkup(keyboard))


async def menu_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "stats":
        await query.edit_message_text(f"📊 Stats\nSignals: {signals_sent}\nWins: {wins}\nLosses: {losses}")

    if query.data == "strategy":
        await query.edit_message_text("📈 Breakout Strategy\nSupport/Resistance\nLondon + NY\nAI Confidence")

    if query.data == "ai":
        await query.edit_message_text("🤖 AI filters weak trades & boosts accuracy")

    if query.data == "scan":
        await query.edit_message_text("📡 Manual scan started")
        await scan_markets(context)


# ✅ COMMANDS
async def alive(update: Update, context):
    await update.message.reply_text("🚀 Bot is Alive")

async def ping(update: Update, context):
    start = asyncio.get_event_loop().time()
    await update.message.reply_text("🏓 Pong!")
    latency = round((asyncio.get_event_loop().time() - start) * 1000, 2)
    await update.message.reply_text(f"Ping: {latency} ms")


# ✅ RUN BOT
def run():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alive", alive))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CallbackQueryHandler(menu_handler))

    app.job_queue.run_repeating(scan_markets, interval=30)

    print("DERIV REAL SIGNAL BOT LIVE 🚀")
    app.run_polling()


if __name__ == "__main__":
    run()