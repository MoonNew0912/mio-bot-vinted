import logging
import threading
import json
import os
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from vinted_api import Vinted

# CONFIGURAZIONE
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "387028237"
SEEN_FILE = "seen_items.json"

app = Flask(__name__)
vinted = Vinted()
logging.basicConfig(level=logging.INFO)

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f: return set(json.load(f))
    return set()

def save_seen(seen_ids):
    with open(SEEN_FILE, 'w') as f: json.dump(list(seen_ids), f)

seen_items = load_seen()

@app.route('/')
def home(): return "Bot is running!"

def run_web_server(): 
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="Bot operativo. Usa /cerca [testo] [prezzo_max]")

async def cerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /cerca [testo] [prezzo_max]")
        return
    
    query = context.args[0]
    max_price = context.args[1]
    
    try:
        # Ricerca su Vinted
        items = vinted.items.search(query, price_to=max_price, currency="EUR", order="price_asc")
        
        count = 0
        for item in items:
            # Filtro: Condizioni (1=Nuovo con etichetta, 2=Nuovo, 3=Ottimo, 4=Buono)
            if item.condition_id not in [1, 2, 3, 4]: continue
            
            # Filtro: Esclusione Nike/Adidas
            if "nike" in item.brand.lower() or "adidas" in item.brand.lower(): continue
            
            # Filtro: Evita duplicati
            if str(item.id) in seen_items: continue
            
            # Filtro: Categorie e Taglie (Logica base)
            # Nota: vinted-api filtra le categorie tramite il catalogo di Vinted.
            
            seen_items.add(str(item.id))
            msg = f"🛒 {item.title}\n💰 {item.price}€\n🏷 {item.brand}\n🔗 {item.url}"
            await context.bot.send_message(chat_id=CHAT_ID, text=msg)
            
            count += 1
            if count >= 10: break
        
        save_seen(seen_items)
        if count == 0: await update.message.reply_text("Nessun nuovo articolo trovato.")
    except Exception as e:
        await update.message.reply_text(f"Errore: {str(e)}")

if __name__ == '__main__':
    threading.Thread(target=run_web_server).start()
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("cerca", cerca))
    app_bot.run_polling()
