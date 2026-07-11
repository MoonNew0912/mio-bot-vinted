import logging, threading, json, os, requests, time, random, sys
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --- CONFIGURAZIONE ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "387028237"
SEEN_FILE = "seen_items.json"

# --- STRUTTURE DATI ---
id_automatici_visti = set()
lock_auto = threading.Lock()

# --- FUNZIONI DI SUPPORTO ---
def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": messaggio}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def check_articolo_valido(item, parola_chiave, prezzo_massimo):
    titolo = item.get('title', '').lower()
    brand = item.get('brand_title', '').lower()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    # Logica filtri
    if prezzo > prezzo_massimo: return False
    # Filtri Nike/Adidas/Ralph/Lacoste come concordato
    is_scarpe = any(x in titolo for x in ['scarpe', 'sneakers', 'jordan', 'nike', 'adidas'])
    if not is_scarpe and ("nike" in brand or "adidas" in brand): return False
    if any(b in brand for b in ["ralph lauren", "lacoste"]):
        if not any(x in titolo for x in ["felpa", "maglia", "t-shirt", "camicia", "polo"]): return False
    return True

# --- COMANDI TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot operativo!")

async def cerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ricerca manuale non disponibile in questa modalità, usa il monitoraggio automatico.")

# --- MOTORE BACKGROUND ---
def monitora_vinted_background(session, lista_ricerche):
    while True:
        for ricerca in lista_ricerche:
            try:
                res = session.get("https://www.vinted.it/api/v2/catalog/items", 
                                  params={'search_text': ricerca["nome"], 'order': 'newest_first'}, timeout=10)
                if res.status_code == 200:
                    for item in res.json().get('items', []):
                        if item['id'] not in id_automatici_visti and check_articolo_valido(item, ricerca["nome"], ricerca["prezzo_max"]):
                            invia_notifica_telegram(f"🔥 {ricerca['nome']}: {item['price']['amount']}€\n{item['url']}")
                            with lock_auto: id_automatici_visti.add(item['id'])
            except: pass
            time.sleep(5)

# --- AVVIO ---
if __name__ == '__main__':
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0...'})
    
    # DEFINIZIONE VARIABILE MANCANTE
    MIE_RICERCHE = [{"nome": "Stussy", "prezzo_max": 40.0}, {"nome": "Nike", "prezzo_max": 65.0}]

    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE), daemon=True).start()
    
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("cerca", cerca))
    app_bot.run_polling(drop_pending_updates=True)
