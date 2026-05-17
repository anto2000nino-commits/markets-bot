import asyncio
import logging
import os
import requests
import yfinance as yf
import pytz
from datetime import datetime, timedelta
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("markets-bot")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
FMP_API_KEY = os.environ.get("FMP_API_KEY")

ITALY_TZ = pytz.timezone("Europe/Rome")
bot = Bot(token=BOT_TOKEN)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DISCLAIMER = "\n\n⚠️ <i>Contenuto generato da AI. Potrebbe contenere errori. Non costituisce consiglio finanziario. Fai sempre le tue valutazioni personali.</i>"

SYMBOLS_WEEKDAY = {
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

SYMBOLS_WEEKEND = {
    "metalli": {
        "Oro (XAU/USD)": "GC=F",
        "Argento (XAG/USD)": "SI=F",
        "Platino": "PL=F",
        "Rame": "HG=F",
    },
}

def is_weekend():
    return datetime.now(ITALY_TZ).weekday() >= 5

def get_symbols():
    return SYMBOLS_WEEKEND if is_weekend() else SYMBOLS_WEEKDAY

def get_market_data():
    data = {}
    symbols = get_symbols()
    for category, syms in symbols.items():
        for name, ticker in syms.items():
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

def get_economic_events():
    try:
        today = datetime.now(ITALY_TZ).strftime("%Y-%m-%d")
        url = f"https://financialmodelingprep.com/api/v3/economic_calendar?from={today}&to={today}&apikey={FMP_API_KEY}"
        resp = requests.get(url, timeout=10)
        events = resp.json()
        filtered = []
        for e in events:
            if e.get("impact") in ["High", "Medium"]:
                filtered.append(e)
        return filtered
    except Exception as e:
        logger.error(f"Error fetching economic events: {e}")
        return []

def format_market_summary(market_data, crypto_data):
    lines = []
    symbols = get_symbols()
    emoji_map = {"metalli": "🥇", "forex": "💱", "indici": "📊"}
    name_map = {"metalli": "METALLI", "forex": "FOREX", "indici": "INDICI"}
    for category in symbols:
        lines.append(f"\n{emoji_map[category]} <b>{name_map[category]}</b>")
        for name in symbols[category]:
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
    weekend_note = "\nNota: è weekend, i mercati forex e gli indici sono chiusi. Concentrati su metalli e crypto." if is_weekend() else ""

    istruzioni = f"""Sei un analista finanziario senior che scrive per trader professionisti su Telegram.
Usa SOLO dati reali forniti qui sotto. NON inventare prezzi, livelli o previsioni non supportate dai dati.
Scrivi in italiano corretto e professionale.
Usa ESCLUSIVAMENTE tag HTML Telegram: <b>grassetto</b>, <i>corsivo</i>. NON usare asterischi ** né cancelletti #.
Ogni titolo sezione in <b>grassetto</b>.
Sii preciso, concreto e utile. Cita i livelli numerici reali dai dati forniti.
Concludi SEMPRE con <b>💡 Osservazione Chiave</b>: un'analisi tecnica o macro originale basata sui dati reali.{weekend_note}"""

    prompts = {
        "morning": f"""{istruzioni}

Dati di mercato attuali:
{summary}

Analizza l'apertura dei mercati europei con queste sezioni:
<b>📊 Sentiment e Contesto Macro</b>
Analisi del sentiment basata sui movimenti reali dei dati sopra. Cita i valori numerici specifici.

<b>🥇 Metalli Preziosi</b>
Analisi tecnica di oro e argento con i livelli attuali. Supporti e resistenze chiave.

<b>💱 Forex</b>
I movimenti forex più significativi con i livelli esatti. Cosa guida i movimenti.

<b>🪙 Crypto</b>
Sentiment crypto e correlazioni con il risk-on/risk-off generale.

<b>💡 Osservazione Chiave</b>
Un'analisi originale e concreta basata sui numeri reali.

Massimo 280 parole. Zero generalità, solo analisi basata sui dati.""",

        "wallstreet": f"""{istruzioni}

Dati di mercato attuali:
{summary}

Analizza l'apertura di Wall Street con queste sezioni:
<b>🇺🇸 Sentiment Pre-Market</b>
Analisi basata sui futures e sugli indici europei già aperti. Cita i valori.

<b>📈 Indici e Livelli Chiave</b>
S&P 500, Nasdaq, FTSE, DAX — analisi tecnica con i livelli attuali dai dati.

<b>🥇 Metalli e Dollaro</b>
Come si stanno muovendo oro e forex rispetto all'apertura americana.

<b>💡 Osservazione Chiave</b>
Pattern tecnico o correlazione macro concreta basata sui dati reali.

Massimo 280 parole. Zero generalità, solo analisi basata sui dati.""",

        "recap": f"""{istruzioni}

Dati di mercato attuali:
{summary}

Recap pomeridiano con queste sezioni:
<b>🌍 Sessione Europea — Bilancio</b>
Come ha chiuso la sessione europea. Cita i valori numerici dei movimenti.

<b>🥇 Metalli e Materie Prime</b>
Analisi dei movimenti di oro, argento, platino e rame con i livelli attuali.

<b>🪙 Crypto nel Pomeriggio</b>
Situazione crypto con i prezzi reali e le variazioni percentuali.

<b>💡 Osservazione Chiave</b>
Cosa dicono i dati sulla direzione del mercato per la chiusura e domani.

Massimo 280 parole. Zero generalità, solo analisi basata sui dati.""",

        "close": f"""{istruzioni}

Dati di mercato attuali:
{summary}

Analisi di chiusura con queste sezioni:
<b>🌙 Bilancio della Giornata</b>
Recap numerico preciso: chi ha guadagnato, chi ha perso e quanto.

<b>🏆 Asset del Giorno</b>
Il miglior e il peggior asset della giornata con dati reali e motivazione.

<b>🔭 Outlook per Domani</b>
Cosa monitorare domani basandosi sui livelli tecnici attuali reali.

<b>💡 Osservazione Chiave</b>
Un pattern o una correlazione emersa oggi dai dati che vale la pena tenere a mente.

Massimo 280 parole. Zero generalità, solo analisi basata sui dati.""",

        "weekend": f"""{istruzioni}

Dati di mercato (weekend — solo metalli e crypto attivi):
{summary}

Analisi weekend con queste sezioni:
<b>🥇 Metalli Preziosi — Situazione Attuale</b>
Analisi tecnica di oro e argento con i livelli reali. Dove si trovano rispetto ai supporti chiave.

<b>🪙 Crypto Weekend</b>
Analisi del mercato crypto con prezzi e variazioni reali. Trend in atto.

<b>🔭 Cosa Monitorare Lunedì</b>
I livelli tecnici chiave e gli eventi macro della prossima settimana da tenere d'occhio.

<b>💡 Osservazione Chiave</b>
Un'analisi originale basata sui movimenti del weekend.

Massimo 280 parole. Zero generalità, solo analisi basata sui dati.""",
    }

    session = "weekend" if is_weekend() else session_type

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompts[session]}],
        )
        return resp.content[0].text
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return "<i>Analisi AI temporaneamente non disponibile.</i>"

def get_ai_event_analysis(event):
    nome = event.get("event", "Evento sconosciuto")
    paese = event.get("country", "")
    ora = event.get("date", "")
    actual = event.get("actual", "N/D")
    stima = event.get("estimate", "N/D")
    precedente = event.get("previous", "N/D")
    impatto = event.get("impact", "")

    prompt = f"""Sei un analista finanziario senior. Analizza questo evento economico reale per i trader.

Evento: {nome}
Paese: {paese}
Orario: {ora}
Valore attuale: {actual}
Stima consensus: {stima}
Valore precedente: {precedente}
Impatto: {impatto}

Scrivi in italiano corretto e professionale.
Usa SOLO tag HTML Telegram: <b>grassetto</b>, <i>corsivo</i>. NON usare asterischi né cancelletti.

Struttura:
<b>📌 Cos'è e Perché Conta</b>
Spiegazione concisa dell'indicatore e della sua rilevanza per i mercati.

<b>📊 Dato Reale vs Attese</b>
Commenta il dato uscito rispetto al consensus e al precedente. Sii preciso con i numeri.

<b>⚡ Impatto Atteso sui Mercati</b>
Come potrebbero reagire forex, indici e metalli. Sii specifico: quale direzione e perché.

<b>⚠️ Livelli da Monitorare</b>
Gli asset più sensibili a questo dato con i livelli tecnici chiave da tenere d'occhio.

Massimo 200 parole. Analisi concreta, niente generalità."""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        logger.error(f"AI event analysis error: {e}")
        return "<i>Analisi evento non disponibile.</i>"

async def send_market_update(session_type, header_emoji, header_text):
    if is_weekend() and session_type in ["wallstreet", "recap"]:
        logger.info(f"Skipping {session_type} — weekend")
        return

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
{analysis}{DISCLAIMER}

<i>AI MarketsAnalysis 📊</i>"""

        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
        logger.info(f"Sent {session_type} update")
    except Exception as e:
        logger.error(f"Error sending {session_type} update: {e}")

async def check_and_send_events():
    if is_weekend():
        return
    try:
        events = get_economic_events()
        if not events:
            return
        now = datetime.now(ITALY_TZ)
        for event in events:
            try:
                event_time_str = event.get("date", "")
                if not event_time_str:
                    continue
                event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00")).astimezone(ITALY_TZ)
                diff = (event_time - now).total_seconds()
                if event.get("actual") and abs(diff) < 3600:
                    analysis = get_ai_event_analysis(event)
                    impact_emoji = "🔴" if event.get("impact") == "High" else "🟡"
                    message = f"""{impact_emoji} <b>EVENTO ECONOMICO — {event.get('event', '').upper()}</b>
🌍 {event.get('country', '')} | 🕐 {event_time.strftime('%H:%M')}

{analysis}{DISCLAIMER}

<i>AI MarketsAnalysis 📊</i>"""
                    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
                    logger.info(f"Sent event: {event.get('event')}")
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    except Exception as e:
        logger.error(f"Error in check_and_send_events: {e}")

async def morning_update():
    await send_market_update("morning", "🌅", "APERTURA MERCATI EUROPEI")

async def wallstreet_update():
    await send_market_update("wallstreet", "🇺🇸", "APERTURA WALL STREET")

async def recap_update():
    await send_market_update("recap", "📋", "RECAP POMERIDIANO")

async def close_update():
    await send_market_update("close", "🌙", "CHIUSURA MERCATI & OUTLOOK")

async def main():
    logger.info("Starting AI MarketsAnalysis Bot...")
    scheduler = AsyncIOScheduler(timezone=ITALY_TZ)
    scheduler.add_job(morning_update, "cron", hour=8, minute=0)
    scheduler.add_job(wallstreet_update, "cron", hour=14, minute=30)
    scheduler.add_job(recap_update, "cron", hour=18, minute=0)
    scheduler.add_job(close_update, "cron", hour=22, minute=0)
    scheduler.add_job(check_and_send_events, "cron", minute="*/30")
    scheduler.start()
    logger.info("Scheduler started. Sending test message...")
    await send_market_update("morning", "🚀", "BOT AVVIATO - TEST MERCATI")
    logger.info("Bot running.")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
