import threading, os, requests, time
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL") 
CHAT_ID = "387028237"

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
if PROXY_URL: session.proxies = {"http": PROXY_URL, "https": PROXY_URL}

# Funzione di ricerca istantanea (comando /cerca)
def cerca_su_vinted(update, context):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("Uso: /cerca [marca] [prezzo_max]")
        return
    
    parts = query.split()
    nome = parts[0]
    prezzo_max = float(parts[1]) if len(parts) > 1 else 50.0
    
    update.message.reply_text(f"🔍 Cerco {nome} a max {prezzo_max}€...")
    
    res = session.get("https://www.vinted.it/api/v2/catalog/items", params={'search_text': nome, 'order': 'newest_first', 'per_page': 3})
    
    if res.status_code == 200:
        items = res.json().get('items', [])
        if not items:
            update.message.reply_text("Non ho trovato nulla con questi parametri.")
        for item in items:
            prezzo = float(item.get('price', {}).get('amount', '0'))
            msg = f"🔥 {item['title']}\nPrezzo: {prezzo}€\n{item['url']}"
            update.message.reply_text(msg)
    else:
        update.message.reply_text(f"Errore: {res.status_code}. Il proxy potrebbe bloccare la richiesta.")

if __name__ == '__main__':
    # Server Flask
    threading.Thread(target=lambda: Flask(__name__).run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    
    # Bot Telegram
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot operativo!")))
    app_bot.add_handler(CommandHandler("test", lambda u, c: u.message.reply_text("Vivo!")))
    app_bot.add_handler(CommandHandler("cerca", cerca_su_vinted))
    
    print("Bot in ascolto...")
    app_bot.run_polling(drop_pending_updates=True)
