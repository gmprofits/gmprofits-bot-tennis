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
CHAT_ID = int(os.getenv("CHAT_ID", "-1002086576103"))
TOPIC_ID = os.getenv("TOPIC_ID")  # opzionale

# --- Inizializzazione Bot e Flask ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(token=TOKEN)
app = Flask(__name__)
notificati = set()
headers = {"User-Agent": "Mozilla/5.0"}

# --- Test di avvio immediato ---
logging.info(f"🔌 Config: CHAT_ID={CHAT_ID}, TOPIC_ID={TOPIC_ID}")
try:
    args = {"chat_id": CHAT_ID, "text": "🤖 Bot start!", "parse_mode": ParseMode.MARKDOWN}
    if TOPIC_ID:
        args["message_thread_id"] = int(TOPIC_ID)
    bot.send_message(**args)
    logging.info("✅ Messaggio di start inviato con successo")
except Exception as e:
    logging.error(f"❌ Errore invio messaggio di start: {e}")

# --- Ottieni match live ---
def get_live_matches():
    try:
        url = "https://<TUO_PROXY>/matches"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception as e:
        logging.error(f"Errore recupero match: {e}")
        return []

# --- Determina favorito ---
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
                fav = out[0]['name'] if out[0]['price'] < out[1]['price'] else out[1]['name']
                logging.info(f"📈 Favorito quote: {fav}")
                return fav
    except Exception as e:
        logging.warning(f"OddsAPI error: {e}")
    hr = match.get('homeTeam', {}).get('ranking', {}).get('currentRank', 9999)
    ar = match.get('awayTeam', {}).get('ranking', {}).get('currentRank', 9999)
    fav = home if hr < ar else away
    logging.info(f"🏷️ Favorito ranking: {fav}")
    return fav

# --- Controllo match e invio notifiche ---
def check_matches():
    matches = get_live_matches()
    logging.info(f"🔍 {len(matches)} match in diretta")
    for m in matches:
        mid = m.get('id')
        if not mid or mid in notificati:
            continue
        try:
            home = m.get('homeTeam', {}).get('name', 'Sconosciuto')
            away = m.get('awayTeam', {}).get('name', 'Sconosciuto')
            raw_h = m.get('homeScore', 0)
            raw_a = m.get('awayScore', 0)
            hs = raw_h.get('period1', raw_h) if isinstance(raw_h, dict) else raw_h
            as_ = raw_a.get('period1', raw_a) if isinstance(raw_a, dict) else raw_a
            st = m.get('status', {}).get('description', '').lower()
            if 'set' not in st:
                continue
            fav = get_favorite(m)
            logging.info(f"🎾 {home} vs {away} | Set1: {hs}-{as_} | Fav: {fav}")
            cond = (fav == home and as_ >= 5 and as_ > hs) or (fav == away and hs >= 5 and hs > as_)
            if cond:
                logging.info("🚨 ALERT TRIGGER")
                text = f"🚨 {home} vs {away}\nSet1: {hs}-{as_}\nFav {fav} sta perdendo!"
                args = {"chat_id": CHAT_ID, "text": text, "parse_mode": ParseMode.MARKDOWN}
                if TOPIC_ID:
                    args["message_thread_id"] = int(TOPIC_ID)
                try:
                    bot.send_message(**args)
                    logging.info("✅ Alert inviato")
                except Exception as e:
                    logging.error(f"❌ Errore invio alert: {e}")
                notificati.add(mid)
        except Exception as e:
            logging.error(f"Errore match {mid}: {e}")

# --- Loop continuativo ---

def start_loop():
    logging.info("🏁 Loop avviato")
    while True:
        check_matches()
        if datetime.now().minute == 0:
            notificati.clear()
            logging.info("🔁 Notify reset")
        time.sleep(60)

@app.route("/")
def home():
    return "Bot tennis attivo!"

# --- Avvio applicazione ---
if __name__ == '__main__':
    threading.Thread(target=start_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=8080)
