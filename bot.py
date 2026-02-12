import requests
import pandas as pd
import time
import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8090941115:AAEC9vEBPwbl6sQr0kubMv1lKlam1-vuUDI"
CHAT_ID = "8255900012"

PAIRS = ["EURUSDT", "GBPUSDT", "USDJPY", "NZDUSDT"]
TIMEFRAME = "15m"

PIP_TARGET = 0.0100
SL_BUFFER = 0.0015

wins = 0
losses = 0
signals_sent = 0


# SESSION FILTER — London & NY
def session_open():
    now = datetime.datetime.now(pytz.utc).hour
    return (7 <= now <= 11) or (12 <= now <= 20)


def get_candles(pair):
    url = f"https://api.binance.com/api/v3/klines?symbol={pair}&interval={TIMEFRAME}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        "time","open","high","low","close","volume","_","_","_","_","_","_"
    ])
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    return df


def detect_levels(df):
    support = df["low"].tail(30).min()
    resistance = df["high"].tail(30).max()
    return support, resistance


# AI CONFIDENCE ENGINE
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


async def send_signal(context, pair, direction, entry, sl, tp, analysis, confidence):
    global signals_sent
    signals_sent += 1

    msg = f"""
👑👑👑 SIGNAL

💱 Pair: {pair.replace("USDT","/USD")}
⏱ Timeframe: 15M
📈 Direction: {direction}

🤖 AI Confidence: {confidence}%

🔍 AI Analysis:
{analysis}

🏹 Entry: {entry:.5f}
🛑 Stop Loss: {sl:.5f}
🎯 Take Profit: {tp:.5f} (100 pips)
"""

    await context.bot.send_message(chat_id=CHAT_ID, text=msg)


async def scan_markets(context: ContextTypes.DEFAULT_TYPE):
    if not session_open():
        return

    for pair in PAIRS:
        df = get_candles(pair)
        support, resistance = detect_levels(df)
        price = df["close"].iloc[-1]

        recent_low = df["low"].tail(10).min()
        recent_high = df["high"].tail(10).max()

        # PRE-BREAKOUT WARNING
        if price > resistance * 0.999:
            await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {pair} breakout soon!")

        if price < support * 1.001:
            await context.bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {pair} breakdown soon!")

        # SELL BREAKOUT
        if price < support:
            confidence = ai_confidence_score(df, "SELL")
            if confidence < 70:
                continue

            entry = price
            sl = recent_high + SL_BUFFER
            tp = entry - PIP_TARGET

            analysis = "Support broken with strong bearish momentum and volatility expansion."

            await send_signal(context, pair, "SELL ⬇️", entry, sl, tp, analysis, confidence)

        # BUY BREAKOUT
        if price > resistance:
            confidence = ai_confidence_score(df, "BUY")
            if confidence < 70:
                continue

            entry = price
            sl = recent_low - SL_BUFFER
            tp = entry + PIP_TARGET

            analysis = "Resistance breakout confirmed with strong bullish pressure and momentum."

            await send_signal(context, pair, "BUY ⬆️", entry, sl, tp, analysis, confidence)


# TELEGRAM MENU
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🧠 Strategy", callback_data="strategy")],
        [InlineKeyboardButton("⚙ Settings", callback_data="settings")],
        [InlineKeyboardButton("🤖 AI Explain", callback_data="ai")],
        [InlineKeyboardButton("📡 Scan Now", callback_data="scan")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🚀 Trading Bot Menu", reply_markup=reply_markup)


async def menu_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "stats":
        await query.edit_message_text(
            f"📊 STATS\n\nSignals Sent: {signals_sent}\nWins: {wins}\nLosses: {losses}"
        )

    if query.data == "strategy":
        await query.edit_message_text(
            "📈 Strategy:\nBreakout Trading\nSupport/Resistance\nLondon + NY Sessions\nAI Confidence Filter"
        )

    if query.data == "settings":
        await query.edit_message_text("⚙ Settings coming soon")

    if query.data == "ai":
        await query.edit_message_text("🤖 AI explains every signal with confidence scoring")

    if query.data == "scan":
        await query.edit_message_text("📡 Manual Scan Started")
        await scan_markets(context)


# COMMANDS
async def alive(update: Update, context):
    await update.message.reply_text("🚀 Bot is Alive and Running")

async def ping(update: Update, context):
    start = time.time()
    await update.message.reply_text("🏓 Pong!")
    latency = round((time.time() - start) * 1000, 2)
    await update.message.reply_text(f"Ping: {latency} ms")


def run():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("alive", alive))
    app_bot.add_handler(CommandHandler("ping", ping))
    app_bot.add_handler(CallbackQueryHandler(menu_handler))

    app_bot.job_queue.run_repeating(scan_markets, interval=20)

    print("BOT LIVE 🚀")
    app_bot.run_polling()


if __name__ == "__main__":
    run()