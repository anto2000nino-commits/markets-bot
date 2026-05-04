import asyncio
import logging
import os
import requests
import yfinance as yf
import pytz
from datetime import datetime
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("markets-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

ITALY_TZ = pytz.timezone("Europe/Rome")
bot = Bot(token=BOT_TOKEN)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYMBOLS = {
    "metalli": {
        "Oro (XAU/USD)": "GC=F",
        "Argento (XAG/USD)": "SI=F",
        "Platino": "PL=F",
        "Rame": "HG=F",
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
        "FTSE 100": "^FTSE",
        "DAX": "^GDAXI",
    },
}

def get_market_data():
    data = {}
    for category, symbols in SYMBOLS.items():
        for name, ticker in symbols.items():
            try:
                t = yf.Ticker(ticker)
                info = t.fast_info
                price = info.last_price
                prev_close = info.previous_close
                change = ((price - prev_close) / prev_close) * 100 if prev_close else 0
                data[name] = {"price": price, "change": change, "prev_close": prev_close}
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
    emoji_map = {"metalli": "🥇", "forex": "💱", "indici": "📊"}
    name_map = {"metalli": "METALLI", "forex": "FOREX", "indici": "INDICI"}
    for category, symbols in SYMBOLS.items():
        lines.append(f"\n{emoji_map[category]} <b>{name_map[category]}</b>")
        for name in symbols:
            if name in market_data:
                d = market_data[name]
                arrow = "🟢" if d["change"] >= 0 else "🔴"
                sign = "+" if d["change"] >= 0 else ""
                lines.append(f"{arrow} {name}: <b>{d['price']:.4f}</b> ({sign}{d['change']:.2f}%)")
    if crypto_data:
        lines.append("\n🪙 <b>CRYPTO</b>")
        for name, d in crypto_data.items():
            arrow = "🟢" if d["change"] >= 0 else "🔴"
            sign = "+" if d["change"] >= 0 else ""
            lines.append(f"{arrow} {name}: <b>${d['price']:,.2f}</b> ({sign}{d['change']:.2f}%)")
    return "\n".join(lines)

def get_ai_analysis(market_data, crypto_data, session_type):
    summary = format_market_summary(market_data, crypto_data)
    istruzioni_html = """Rispondi SOLO in italiano corretto e professionale.
Usa ESCLUSIVAMENTE tag HTML Telegram: <b>testo</b> per grassetto, <i>testo</i> per corsivo.
NON usare asterischi **, NON usare cancelletti #, NON usare markdown.
Ogni titolo di sezione deve essere in <b>grassetto</b>.
Concludi SEMPRE con una sezione <b>💡 Chicca del Giorno</b> con un'osservazione originale, un pattern tecnico o un dato poco noto utile per i trader oggi."""

    prompts = {
        "morning": f"""Sei un analista finanziario esperto che scrive per un canale Telegram di trading.
Analizza questi dati per l'apertura dei mercati europei:

{summary}

{istruzioni_html}

Struttura la risposta con queste sezioni:
<b>📊 Sentiment Generale</b>
<b>⚠️ Asset da Monitorare</b>
<b>💱 Forex in Evidenza</b>
<b>💡 Chicca del Giorno</b>

Massimo 220 parole.""",

        "wallstreet": f"""Sei un analista finanziario esperto che scrive per un canale Telegram di trading.
Analizza questi dati per l'apertura di Wall Street:

{summary}

{istruzioni_html}

Struttura la risposta con queste sezioni:
<b>🇺🇸 Apertura Wall Street</b>
<b>📈 Indici e Trend</b>
<b>⚠️ Livelli Chiave da Tenere d'Occhio</b>
<b>💡 Chicca del Giorno</b>

Massimo 220 parole.""",

        "recap": f"""Sei un analista finanziario esperto che scrive per un canale Telegram di trading.
Fai un recap pomeridiano con questi dati:

{summary}

{istruzioni_html}

Struttura la risposta con queste sezioni:
<b>🌍 Come è Andata la Sessione Europea</b>
<b>🥇 Metalli e Materie Prime</b>
<b>🪙 Crypto nel Pomeriggio</b>
<b>💡 Chicca del Giorno</b>

Massimo 220 parole.""",

        "close": f"""Sei un analista finanziario esperto che scrive per un canale Telegram di trading.
Analizza la chiusura mercati con questi dati:

{summary}

{istruzioni_html}

Struttura la risposta con queste sezioni:
<b>🌙 Recap della Giornata</b>
<b>🏆 Vincitori e Perdenti</b>
<b>🔭 Cosa Aspettarsi Domani</b>
<b>💡 Chicca del Giorno</b>

Massimo 220 parole.""",
    }

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompts[session_type]}],
        )
        return resp.content[0].text
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return "<i>Analisi AI temporaneamente non disponibile.</i>"

async def send_market_update(session_type, header_emoji, header_text):
    try:
        market_data = get_market_data()
        crypto_data = get_crypto_data()
        now = datetime.now(ITALY_TZ).strftime("%d/%m/%Y %H:%M")
        summary = format_market_summary(market_data, crypto_data)
        analysis = get_ai_analysis(market_data, crypto_data, session_type)

        message = f"""{header_emoji} <b>{header_text}</b>
🕐 {now}
{summary}

🤖 <b>ANALISI AI</b>
{analysis}

<i>BullVision Markets Bot 📊</i>"""

        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
        logger.info(f"Sent {session_type} update")
    except Exception as e:
        logger.error(f"Error sending {session_type} update: {e}")

async def morning_update():
    await send_market_update("morning", "🌅", "APERTURA MERCATI EUROPEI")

async def wallstreet_update():
    await send_market_update("wallstreet", "🇺🇸", "APERTURA WALL STREET")

async def recap_update():
    await send_market_update("recap", "📋", "RECAP POMERIDIANO")

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
