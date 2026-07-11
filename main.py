import logging, threading, json, os, requests, time, random
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --- CONFIGURAZIONE ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL") # Formato: http://user:pass@ip:porta
CHAT_ID = "387028237"
SEEN_FILE = "seen_items.json"

# --- INIZIALIZZAZIONE SESSIONE ---
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
})

if PROXY_URL:
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}

# --- FUNZIONI DI FILTRO (LOGICA) ---
def check_articolo_valido(item, parola_chiave, prezzo_massimo):
    titolo = item.get('title', '').lower()
    brand = item.get('brand_title', '').lower() or ""
    prezzo = float(item.get('price', {}).get('amount', '0'))
    
    if prezzo > prezzo_massimo: return False
    
    # Logica intelligente: Nike/Adidas solo per scarpe
    is_scarpe = any(x in titolo for x in ['scarpe', 'sneakers', 'jordan', 'nike', 'adidas', 'yeezy'])
    if not is_scarpe and ("nike" in brand or "adidas" in brand): return False
    
    # Logica Ralph Lauren/Lacoste: solo parte superiore
    if any(b in brand for b in ["ralph lauren", "lacoste"]):
        if not any(x in titolo for x in ["felpa", "maglia", "t-shirt", "camicia", "polo", "giacca"]): return False
        
    return True

# --- MOTORE BACKGROUND ---
id_automatici_visti = set()
lock_auto = threading.Lock()

def monitora_vinted_background(session, lista_ricerche):
    while True:
        for ricerca in lista_ricerche:
            try:
                res = session.get("https://www.vinted.it/api/v2/catalog/items", 
                                  params={'search_text': ricerca["nome"], 'order': 'newest_first', 'per_page': 10}, timeout=10)
                if res.status_code == 200:
                    for item in res.json().get('items', []):
                        if item['id'] not in id_automatici_visti and check_articolo_valido(item, ricerca["nome"], ricerca["prezzo_max"]):
                            msg = f"🔥 {ricerca['nome'].upper()}: {item['price']['amount']}€\n{item['title']}\n{item['url']}"
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
                            with lock_auto: id_automatici_visti.add(item['id'])
            except: pass
            time.sleep(5)

# --- WEB SERVER (Per mantenere Render attivo) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot attivo!"

# --- AVVIO BOT ---
if __name__ == '__main__':
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    
    MIE_RICERCHE = [
        {"nome": "Stussy", "prezzo_max": 40.0}, {"nome": "Nike", "prezzo_max": 65.0}, 
        {"nome": "Ralph Lauren", "prezzo_max": 40.0}, {"nome": "Lacoste", "prezzo_max": 40.0}
    ]
    
    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE), daemon=True).start()
    
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.run_polling()
