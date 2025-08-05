import requests
import logging
import time
import threading
from datetime import datetime
from flask import Flask
from telegram import Bot
from telegram.constants import ParseMode

# --- Config ---
TOKEN = "INSERISCI_IL_TUO_TOKEN_TELEGRAM"
CHAT_ID = -1002086576103
TOPIC_ID = 998
ODDS_API_KEY = "INSERISCI_LA_TUA_API_KEY_ODDSAPI"

bot = Bot(token=TOKEN)
app = Flask(__name__)
notificati = set()

# Log
logging.basicConfig(level=logging.INFO)
headers = {"User-Agent": "Mozilla/5.0"}

@app.route('/')
def home():
    return "Tennis Bot attivo!"

def start_flask():
    app.run(host='0.0.0.0', port=8080)

def get_live_matches():
    try:
        url = "https://api.sofascore.com/api/v1/sport/tennis/events/live"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get("events", [])
    except Exception as e:
        logging.error(f"Errore richiesta SofaScore: {e}")
        return []

def get_favorite(match):
    home_team = match.get('homeTeam', {})
    away_team = match.get('awayTeam', {})
    home = home_team.get('name', 'Sconosciuto')
    away = away_team.get('name', 'Sconosciuto')
    logging.info(f"📱 Quote per: {home} vs {away}")

    try:
        url = f"https://api.the-odds-api.com/v4/sports/tennis/events?regions=eu&markets=h2h&apiKey={ODDS_API_KEY}"
        res = requests.get(url)
        res.raise_for_status()
        data = res.json()

        for event in data:
            if home.lower() in event['home_team'].lower() and away.lower() in event['away_team'].lower():
                markets = event.get('bookmakers', [])[0].get('markets', [])
                if markets:
                    outcomes = markets[0].get('outcomes', [])
                    if len(outcomes) == 2:
                        favorito = outcomes[0]['name'] if outcomes[0]['price'] < outcomes[1]['price'] else outcomes[1]['name']
                        return favorito
    except Exception as e:
        logging.warning(f"OddsAPI non disponibile: {e}")

    home_rank = home_team.get('ranking', {}).get('currentRank') if isinstance(home_team.get('ranking'), dict) else 9999
    away_rank = away_team.get('ranking', {}).get('currentRank') if isinstance(away_team.get('ranking'), dict) else 9999
    return home if home_rank < away_rank else away

def check_matches():
    global notificati
    matches = get_live_matches()
    logging.info(f"📡 {len(matches)} match live")
    for match in matches:
        try:
            match_id = match.get('id')
            if not match_id or match_id in notificati:
                continue

            home_team = match.get('homeTeam', {}).get('name', 'Sconosciuto')
            away_team = match.get('awayTeam', {}).get('name', 'Sconosciuto')
            hs = match.get('homeScore', {})
            as_ = match.get('awayScore', {})
            home_score = hs.get('period1', 0)
            away_score = as_.get('period1', 0)

            status = match.get('status', {}).get('description', '').lower()
            if 'set' not in status:
                continue

            favorite = get_favorite(match)
            logging.info(f"🎾 {home_team} vs {away_team} | Set1: {home_score}-{away_score} | 🏅 Favorito: {favorite}")

            sfavorito_avanti = (favorite == home_team and away_score >= 5 and away_score > home_score) or                                (favorite == away_team and home_score >= 5 and home_score > away_score)

            if sfavorito_avanti:
                msg = (
                    f"🚨 {home_team} vs {away_team}\n"
                    f"Set 1: {home_score}-{away_score}\n"
                    f"🏅 Favorito: {favorite} sta perdendo il primo set 🚨"
                )
                bot.send_message(chat_id=CHAT_ID, text=msg, message_thread_id=TOPIC_ID, parse_mode=ParseMode.MARKDOWN)
                notificati.add(match_id)
        except Exception as e:
            logging.error(f"Errore nel match: {e}")

def loop_bot():
    while True:
        try:
            check_matches()
            time.sleep(60)
            if datetime.now().minute == 0:
                notificati.clear()
        except Exception as e:
            logging.error(f"Errore nel loop: {e}")
            time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=start_flask, daemon=True).start()
    threading.Thread(target=loop_bot, daemon=True).start()
    while True:
        time.sleep(60)
