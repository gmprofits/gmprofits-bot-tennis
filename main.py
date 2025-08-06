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
CHAT_ID = int(os.getenv("CHAT_ID", "-1002086576103"))  # puoi sovrascrivere da Render
TOPIC_ID = int(os.getenv("TOPIC_ID", "998"))  # idem

bot = Bot(token=TOKEN)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
notificati = set()

headers = {
    "User-Agent": "Mozilla/5.0"
}

# --- Funzione per determinare il favorito ---
def get_favorite(match):
    home_team = match.get('homeTeam', {})
    away_team = match.get('awayTeam', {})
    home = home_team.get('name', 'Sconosciuto')
    away = away_team.get('name', 'Sconosciuto')

    logging.info(f"📱 Tentativo quote per: {home} vs {away}")

    try:
        url = f"https://api.the-odds-api.com/v4/sports/tennis/events?regions=eu&markets=h2h&apiKey={ODDS_API_KEY}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        for event in data:
            if home.lower() in event['home_team'].lower() and away.lower() in event['away_team'].lower():
                bookmakers = event.get('bookmakers', [])
                if bookmakers:
                    markets = bookmakers[0].get('markets', [])
                    if markets:
                        outcomes = markets[0].get('outcomes', [])
                        if len(outcomes) == 2:
                            favorito = outcomes[0]['name'] if outcomes[0]['price'] < outcomes[1]['price'] else outcomes[1]['name']
                            logging.info(f"📈 Favorito da quote: {favorito}")
                            return favorito
    except Exception as e:
        logging.warning(f"OddsAPI non disponibile: {e}")

    # Fallback su ranking
    home_rank = home_team.get('ranking', {}).get('currentRank') if isinstance(home_team.get('ranking'), dict) else 9999
    away_rank = away_team.get('ranking', {}).get('currentRank') if isinstance(away_team.get('ranking'), dict) else 9999
    favorito = home if home_rank < away_rank else away
    logging.info(f"🏷️ Favorito da ranking: {favorito} | Rank: {home_rank} vs {away_rank}")
    return favorito

# --- API SofaScore ---
def get_live_matches():
    try:
        url = "https://b645c9da-fdd1-4ffc-a3db-0ebdcdf6daac-00-2l841urwih42l.kirk.replit.dev:5000/matches"  # Inserisci l'URL del tuo proxy Replit
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get("events", [])
    except Exception as e:
        logging.error(f"Errore richiesta SofaScore: {e}")
        return []

# --- Funzione principale ---
def check_matches():
    global notificati
    logging.info("✅ check_matches() eseguito")
    matches = get_live_matches()
    logging.info(f"🔍 Trovati {len(matches)} match in diretta")

    for match in matches:
        if not isinstance(match, dict):
            continue
        try:
            match_id = match.get('id')
            if not match_id or match_id in notificati:
                continue

            home_team = match.get('homeTeam', {})
            away_team = match.get('awayTeam', {})
            home = home_team.get('name', 'Sconosciuto')
            away = away_team.get('name', 'Sconosciuto')

            hs = match.get('homeScore') or {}
            as_ = match.get('awayScore') or {}
            home_score = hs.get('period1', 0) if isinstance(hs, dict) else 0
            away_score = as_.get('period1', 0) if isinstance(as_, dict) else 0

            status = match.get('status', {}).get('description', '').lower()
            if 'set' not in status:
                continue

            favorite = get_favorite(match)

            logging.info(f"🎯 {home} vs {away} | Set1: {home_score}-{away_score} | 🏅 Favorito: {favorite}")

            sfavorito_avanti = (favorite == home and away_score >= 5 and away_score > home_score) or \
                               (favorite == away and home_score >= 5 and home_score > away_score)

            if sfavorito_avanti:
                logging.info("🚨 CONDIZIONE ALERT RAGGIUNTA 🚨")
                msg = (
                    f"🚨 {home} vs {away}\n"
                    f"Set 1: {home_score}-{away_score}\n"
                    f"🏅 Favorito: {favorite} sta perdendo il primo set 🚨"
                )
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=msg,
                    message_thread_id=TOPIC_ID,
                    parse_mode=ParseMode.MARKDOWN
                )
                notificati.add(match_id)

        except Exception as e:
            logging.error(f"Errore match: {e}")

# --- Loop ---
def start_loop():
    while True:
        check_matches()
        time.sleep(60)
        if datetime.now().minute == 0:
            notificati.clear()
            logging.info("🔁 Reset notifiche effettuato.")

# --- Flask app (per tenerlo vivo su Render) ---
@app.route("/")
def home():
    return "Tennis Bot attivo su Render!"

if __name__ == '__main__':
    threading.Thread(target=start_loop).start()
    app.run(host='0.0.0.0', port=8080)
