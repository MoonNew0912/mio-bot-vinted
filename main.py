import threading, os, requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Recupero variabili
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL") 
CHAT_ID = "387028237"

# Sessione richieste
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
if PROXY_URL: 
    session.proxies = {"http": PROXY_URL, "https": PROXY_URL}

# Funzione comando /cerca
async def cerca_su_vinted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /cerca [marca] [prezzo_max]")
        return
    
    nome = context.args[0]
    prezzo_max = float(context.args[1]) if len(context.args) > 1 else 50.0
    
    await update.message.reply_text(f"🔍 Cerco {nome} a max {prezzo_max}€...")
    
    try:
        res = session.get("https://www.vinted.it/api/v2/catalog/items", params={'search_text': nome, 'order': 'newest_first', 'per_page': 3}, timeout=10)
        if res.status_code == 200:
            items = res.json().get('items', [])
            if not items:
                await update.message.reply_text("Non ho trovato nulla.")
            for item in items:
                prezzo = float(item.get('price', {}).get('amount', '0'))
                if prezzo <= prezzo_max:
                    msg = f"🔥 {item['title']}\nPrezzo: {prezzo}€\n{item['url']}"
                    await update.message.reply_text(msg)
                else:
                    await update.message.reply_text(f"Articolo trovato ma supera il prezzo: {item['title']} - {prezzo}€")
        else:
            await update.message.reply_text(f"Errore Vinted: {res.status_code}")
    except Exception as e:
        await update.message.reply_text(f"Errore connessione: {str(e)}")

if __name__ == '__main__':
    # Flask in thread separato
    app_flask = Flask(__name__)
    @app_flask.route('/')
    def home(): return "Bot Attivo"
    threading.Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    # Bot Telegram nel thread principale
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot operativo!")))
    app_bot.add_handler(CommandHandler("test", lambda u, c: u.message.reply_text("Vivo e vegeto!")))
    app_bot.add_handler(CommandHandler("cerca", cerca_su_vinted))
    
    print("Bot in ascolto...")
    app_bot.run_polling()
