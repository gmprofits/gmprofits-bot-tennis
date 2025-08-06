import os
import requests
import logging
import time
from datetime import datetime
from flask import Flask
from telegram import Bot, ParseMode
import threading

# --- Configurazione ---
TOKEN = os.getenv("BOT_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID", "-1002086576103"))  # default supergroup

bot = Bot(token=TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
notificati = set()

headers = {"User-Agent": "Mozilla/5.0"}

logging.info(f"🔌 Bot avviato con CHAT_ID={CHAT_ID}")

# --- Funzione per determinare il favorito ---
def get_favorite(match):
    home = match.get('homeTeam', {}).get('name', 'Sconosciuto')
    away = match.get('awayTeam', {}).get('name', 'Sconosciuto')
    logging.info(f"📱 Quote per: {home} vs {away}")
    try:
        url = f"https://api.the-odds-api.com/v4/sports/tennis/events?regions=eu&markets=h2h&apiKey={ODDS_API_KEY}"
        data = requests.get(url).json()
        for ev in data:
            if home.lower() in ev['home_team'].lower() and away.lower() in ev['away_team'].lower():
                out = ev['bookmakers'][0]['markets'][0]['outcomes']
                favorito = out[0]['name'] if out[0]['price'] < out[1]['price'] else out[1]['name']
                logging.info(f"📈 Favorito quote: {favorito}")
                return favorito
    except Exception as e:
        logging.warning(f"OddsAPI non disponibile: {e}")
    # Fallback ranking
    hr = match.get('homeTeam', {}).get('ranking', {}).get('currentRank', 9999)
    ar = match.get('awayTeam', {}).get('ranking', {}).get('currentRank', 9999)
    favorito = home if hr < ar else away
    logging.info(f"🏷️ Favorito ranking: {favorito} | {hr} vs {ar}")
    return favorito

# --- Recupero match dal proxy ---
def get_live_matches():
    try:
        url = "https://<TUO_PROXY>/matches"
        ev = requests.get(url, headers=headers).json()
        return ev.get("events", [])
    except Exception as e:
        logging.error(f"Errore SofaScore: {e}")
        return []

# --- Controllo match e notifiche ---
def check_matches():
    global notificati
    matches = get_live_matches()
    logging.info(f"🔍 Trovati {len(matches)} match in diretta")
    logging.info("✅ Esecuzione check_matches()")
    for match in matches:
        mid = match.get('id')
        if not mid or mid in notificati:
            continue
        try:
            home = match.get('homeTeam', {}).get('name', 'Sconosciuto')
            away = match.get('awayTeam', {}).get('name', 'Sconosciuto')
            raw_h = match.get('homeScore', 0)
            raw_a = match.get('awayScore', 0)
            home_score = raw_h.get('period1', raw_h) if isinstance(raw_h, dict) else raw_h
            away_score = raw_a.get('period1', raw_a) if isinstance(raw_a, dict) else raw_a
            status = match.get('status', {}).get('description', '').lower()
            if 'set' not in status:
                continue
            favorito = get_favorite(match)
            logging.info(f"🎾 Match: {home} vs {away} | Set 1: {home_score}-{away_score} | Favorito: {favorito}")
            sf_condition = (favorito == home and away_score >= 5 and away_score > home_score) or \
                           (favorito == away and home_score >= 5 and home_score > away_score)
            if sf_condition:
                logging.info("🚨 CONDIZIONE ALERT RAGGIUNTA 🚨")
                msg = (
                    f"🚨 {home} vs {away}\n"
                    f"Set 1: {home_score}-{away_score}\n"
                    f"🏅 Il favorito {favorito} sta perdendo! 🚨"
                )
                try:
                    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
                    logging.info("✅ Messaggio inviato con successo")
                except Exception as e:
                    logging.error(f"❌ Errore invio messaggio: {e}")
                notificati.add(mid)
        except Exception as e:
            logging.error(f"Errore match {mid}: {e}")

# --- Loop di polling ---
def start_loop():
    logging.info("🏁 Inizio loop di polling")
    while True:
        try:
            check_matches()
        except Exception as e:
            logging.error(f"Errore nel loop di controllo: {e}")
        if datetime.now().minute == 0:
            notificati.clear()
            logging.info("🔁 Reset notifiche")
        time.sleep(60)

@app.route("/")
def home():
    return "Tennis Bot attivo su Render!"

if __name__ == '__main__':
    threading.Thread(target=start_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)
