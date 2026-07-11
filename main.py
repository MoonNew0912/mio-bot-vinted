import logging, threading, json, os, requests, time
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler

# --- CONFIGURAZIONE ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL") 
CHAT_ID = "387028237"

# --- SESSIONE ---
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
if PROXY_URL: session.proxies = {"http": PROXY_URL, "https": PROXY_URL}

def check_articolo_valido(item, parola_chiave, prezzo_massimo):
    titolo = item.get('title', '').lower()
    brand = item.get('brand_title', '').lower() or ""
    prezzo = float(item.get('price', {}).get('amount', '0'))
    if prezzo > prezzo_massimo: return False
    # Logica filtri
    is_scarpe = any(x in titolo for x in ['scarpe', 'sneakers', 'jordan', 'nike', 'adidas', 'yeezy'])
    if not is_scarpe and ("nike" in brand or "adidas" in brand): return False
    if any(b in brand for b in ["ralph lauren", "lacoste"]):
        if not any(x in titolo for x in ["felpa", "maglia", "t-shirt", "camicia", "polo"]): return False
    return True

id_automatici_visti = set()

def monitora_vinted_background(session, lista_ricerche):
    while True:
        for ricerca in lista_ricerche:
            try:
                res = session.get("https://www.vinted.it/api/v2/catalog/items", params={'search_text': ricerca["nome"], 'order': 'newest_first', 'per_page': 5}, timeout=10)
                if res.status_code == 200:
                    for item in res.json().get('items', []):
                        if item['id'] not in id_automatici_visti and check_articolo_valido(item, ricerca["nome"], ricerca["prezzo_max"]):
                            msg = f"🔥 {ricerca['nome'].upper()}: {item['price']['amount']}€\n{item['title']}\n{item['url']}"
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
                            id_automatici_visti.add(item['id'])
            except: pass
            time.sleep(10)

if __name__ == '__main__':
    # Server Flask per Render
    threading.Thread(target=lambda: Flask(__name__).run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    
    # Lista ricerche
    MIE_RICERCHE = [{"nome": "Stussy", "prezzo_max": 40.0}, {"nome": "Nike", "prezzo_max": 65.0}, {"nome": "Ralph Lauren", "prezzo_max": 40.0}]
    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE), daemon=True).start()
    
    # Bot Telegram
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot operativo!")))
    app_bot.add_handler(CommandHandler("test", lambda u, c: u.message.reply_text("Il bot è vivo e riceve i comandi!")))
    
    print("Bot in ascolto...")
    app_bot.run_polling(drop_pending_updates=True)
