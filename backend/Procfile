import asyncio
import logging
import os
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
import yfinance as yf
import requests
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("markets-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ITALY_TZ = pytz.timezone("Europe/Rome")

bot = Bot(token=BOT_TOKEN)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYMBOLS = {
    "metalli": {
        "Oro (XAU/USD)": "GC=F",
        "Argento (XAG/USD)": "SI=F",
        "Platino (XPT/USD)": "PL=F",
        "Rame (HG=F)": "HG=F",
    },
    "forex": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "USD/CHF": "CHF=X",
    },
    "indici": {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "DAX": "^GDAXI",
        "FTSE 100": "^FTSE",
    },
}

def get_market_data():
    data = {}
    all_symbols = {}
    for category, symbols in SYMBOLS.items():
        all_symbols.update(symbols)
    
    for name, symbol in all_symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", interval="1d")
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                current = hist["Close"].iloc[-1]
                change = ((current - prev_close) / prev_close) * 100
                data[name] = {
                    "price": current,
                    "change": change,
                    "prev_close": prev_close,
                }
        except Exception as e:
            logger.error(f"Error fetching {name}: {e}")
    return data

def get_crypto_data():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,binancecoin,solana",
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        return {
            "Bitcoin (BTC)": {"price": data["bitcoin"]["usd"], "change": data["bitcoin"]["usd_24h_change"]},
            "Ethereum (ETH)": {"price": data["ethereum"]["usd"], "change": data["ethereum"]["usd_24h_change"]},
            "BNB": {"price": data["binancecoin"]["usd"], "change": data["binancecoin"]["usd_24h_change"]},
            "Solana (SOL)": {"price": data["solana"]["usd"], "change": data["solana"]["usd_24h_change"]},
        }
    except Exception as e:
        logger.error(f"Error fetching crypto: {e}")
        return {}

def format_market_summary(market_data, crypto_data):
    lines = []
    for category, symbols in SYMBOLS.items():
        emoji = {"metalli": "🏅", "forex": "💱", "indici": "📈"}[category]
        name_it = {"metalli": "METALLI", "forex": "FOREX", "indici": "INDICI"}[category]
        lines.append(f"\n{emoji} <b>{name_it}</b>")
        for name in symbols:
            if name in market_data:
                d = market_data[name]
                arrow = "🟢" if d["change"] >= 0 else "🔴"
                sign = "+" if d["change"] >= 0 else ""
                lines.append(f"{arrow} {name}: <b>{d['price']:.4f}</b> ({sign}{d['change']:.2f}%)")

    if crypto_data:
        lines.append(f"\n🪙 <b>CRYPTO</b>")
        for name, d in crypto_data.items():
            arrow = "🟢" if d["change"] >= 0 else "🔴"
            sign = "+" if d["change"] >= 0 else ""
            price_str = f"${d['price']:,.2f}" if d["price"] > 1 else f"${d['price']:.4f}"
            lines.append(f"{arrow} {name}: <b>{price_str}</b> ({sign}{d['change']:.2f}%)")
    
    return "\n".join(lines)

def get_ai_analysis(market_data, crypto_data, session_type):
    summary = format_market_summary(market_data, crypto_data)
    
    prompts = {
        "morning": f"""Sei un analista finanziario esperto. Analizza questi dati di mercato per l'apertura dei mercati europei:

{summary}

Fornisci in italiano:
1. Un'analisi breve (3-4 frasi) del sentiment generale del mercato
2. I metalli più importanti da monitorare oggi e perché
3. I movimenti forex più rilevanti
4. Cosa aspettarsi dalla sessione europea

Sii diretto, professionale e utile per trader. Max 200 parole.""",

        "wallstreet": f"""Sei un analista finanziario esperto. Analizza questi dati per l'apertura di Wall Street:

{summary}

Fornisci in italiano:
1. Come stanno performando gli indici USA rispetto a quelli europei
2. Il sentiment sui metalli preziosi (oro e argento soprattutto)
3. Le crypto più forti/deboli in questo momento
4. Cosa aspettarsi dalla sessione americana

Max 200 parole, tono professionale.""",

        "recap": f"""Sei un analista finanziario esperto. Fai un recap pomeridiano con questi dati:

{summary}

Fornisci in italiano:
1. Come è andata la sessione europea
2. Analisi metalli: oro, argento, platino e rame - tendenze
3. Situazione crypto: BTC e ETH in particolare
4. Outlook per la chiusura USA e domani mattina

Max 200 parole, conciso e professionale.""",

        "close": f"""Sei un analista finanziario esperto. Analizza la chiusura mercati:

{summary}

Fornisci in italiano:
1. Recap della giornata completa sui mercati
2. Performance metalli: vincitori e perdenti
3. Crypto: trend in atto
4. Cosa aspettarsi domani: notizie importanti, livelli chiave da monitorare

Max 200 parole, tono analitico e professionale."""
    }

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=500,
            messages=[{"role": "user", "content": prompts[session_type]}]
        )
        return resp.content[0].text
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return "Analisi AI temporaneamente non disponibile."

async def send_market_update(session_type, header_emoji, header_text):
    try:
        market_data = get_market_data()
        crypto_data = get_crypto_data()
        
        now = datetime.now(ITALY_TZ).strftime("%d/%m/%Y %H:%M")
        summary = format_market_summary(market_data, crypto_data)
        analysis = get_ai_analysis(market_data, crypto_data, session_type)
        
        message = f"""{header_emoji} <b>{header_text}</b>
📅 {now}
{summary}

🧠 <b>ANALISI AI</b>
{analysis}

<i>BullVision Markets Bot 📊</i>"""

        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="HTML"
        )
        logger.info(f"Sent {session_type} update")
    except Exception as e:
        logger.error(f"Error sending {session_type} update: {e}")

async def morning_update():
    await send_market_update("morning", "🌅", "APERTURA MERCATI EUROPEI")

async def wallstreet_update():
    await send_market_update("wallstreet", "🇺🇸", "APERTURA WALL STREET")

async def recap_update():
    await send_market_update("recap", "📊", "RECAP POMERIDIANO")

async def close_update():
    await send_market_update("close", "🌙", "CHIUSURA MERCATI & OUTLOOK")

async def main():
    logger.info("Starting BullVision Markets Bot...")
    
    scheduler = AsyncIOScheduler(timezone=ITALY_TZ)
    scheduler.add_job(morning_update, "cron", hour=8, minute=0)
    scheduler.add_job(wallstreet_update, "cron", hour=14, minute=30)
    scheduler.add_job(recap_update, "cron", hour=18, minute=0)
    scheduler.add_job(close_update, "cron", hour=22, minute=0)
    scheduler.start()
    
    logger.info("Scheduler started. Sending test message...")
    await send_market_update("morning", "🚀", "BOT AVVIATO - TEST MERCATI")
    
    logger.info("Bot running. Press Ctrl+C to stop.")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
