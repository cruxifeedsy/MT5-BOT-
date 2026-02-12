
import requests
import pandas as pd
import time
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from datetime import datetime

BOT_TOKEN = "YOUR_BOT_TOKEN"

PAIRS = {
    "EUR/USD": "EURUSDT",
    "GBP/USD": "GBPUSDT",
    "NZD/JPY": "NZDUSDT"
}

TIMEFRAME = "15m"
PIP_TARGET = 0.0100
SL_BUFFER = 0.0015

user_balance = {}
user_risk = {}
waiting_balance = {}
waiting_risk = {}

bot = Bot(token=BOT_TOKEN)

def in_trading_session():
    hour = datetime.now().hour
    return (9 <= hour <= 18) or (14 <= hour <= 23)

def get_candles(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={TIMEFRAME}&limit=100"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=["time","open","high","low","close","volume","_","_","_","_","_","_"])
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    return df

def detect_support_resistance(df):
    support = df["low"].tail(30).min()
    resistance = df["high"].tail(30).max()
    return support, resistance

def calculate_lot(balance, risk_percent, sl_pips):
    risk_amount = balance * (risk_percent / 100)
    pip_value = 10
    lot = risk_amount / (sl_pips * pip_value)
    return round(lot, 2)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🤖 Multi-Pair Trading Bot Activated!")

def handle_message(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    if waiting_balance.get(chat_id):
        user_balance[chat_id] = float(text)
        waiting_balance[chat_id] = False
        waiting_risk[chat_id] = True
        update.message.reply_text("📊 Enter risk % (example: 2):")
        return

    if waiting_risk.get(chat_id):
        user_risk[chat_id] = float(text)
        waiting_risk[chat_id] = False
        update.message.reply_text("✅ Risk saved. Waiting for breakout...")

def breakout_watcher():
    sent_warning = {}
    sent_signal = {}

    while True:
        if not in_trading_session():
            time.sleep(30)
            continue

        for pair_name, symbol in PAIRS.items():
            df = get_candles(symbol)
            support, resistance = detect_support_resistance(df)
            price = df["close"].iloc[-1]

            recent_low = df["low"].tail(10).min()
            recent_high = df["high"].tail(10).max()

            for chat_id in user_balance.keys():

                # WARNING ALERT
                if resistance - price < 0.0003 and not sent_warning.get((chat_id, symbol)):
                    bot.send_message(chat_id, f"⚠️ {pair_name} breakout soon — standby!")
                    bot.send_message(chat_id, "💰 Enter your account balance:")
                    waiting_balance[chat_id] = True
                    sent_warning[(chat_id, symbol)] = True

                # SELL SIGNAL
                if price < support and not sent_signal.get((chat_id, symbol)):
                    entry = price
                    sl = recent_high + SL_BUFFER
                    tp = entry - PIP_TARGET
                    sl_pips = abs(entry - sl) * 10000
                    lot = calculate_lot(user_balance[chat_id], user_risk[chat_id], sl_pips)

                    message = f"""
👑👑👑👑👑👑 SIGNAL

💱 Pair: {pair_name}
⏱ Timeframe: 15M
⬇️ Direction: SELL

🏹 Entry: {entry:.5f}
🛑 Stop Loss: {sl:.5f}
🎯 Take Profit: {tp:.5f}

💰 Lot Size: {lot}
📊 Risk: {user_risk[chat_id]}%
"""

                    bot.send_message(chat_id, message)
                    sent_signal[(chat_id, symbol)] = True

                # BUY SIGNAL
                if price > resistance and not sent_signal.get((chat_id, symbol)):
                    entry = price
                    sl = recent_low - SL_BUFFER
                    tp = entry + PIP_TARGET
                    sl_pips = abs(entry - sl) * 10000
                    lot = calculate_lot(user_balance[chat_id], user_risk[chat_id], sl_pips)

                    message = f"""
👑👑👑👑👑👑 SIGNAL

💱 Pair: {pair_name}
⏱ Timeframe: 15M
⬆️ Direction: BUY

🏹 Entry: {entry:.5f}
🛑 Stop Loss: {sl:.5f}
🎯 Take Profit: {tp:.5f}

💰 Lot Size: {lot}
📊 Risk: {user_risk[chat_id]}%
"""

                    bot.send_message(chat_id, message)
                    sent_signal[(chat_id, symbol)] = True

        time.sleep(20)

updater = Updater(BOT_TOKEN)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

updater.start_polling()
breakout_watcher()