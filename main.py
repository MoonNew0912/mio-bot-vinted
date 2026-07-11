import logging, threading, json, os, requests, time, random, sys
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Configurazione
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "387028237"
SEEN_FILE = "seen_items.json"

# Inizializzazione sessione per persistenza cookie
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
})

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- FUNZIONI DI SUPPORTO ---
def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r') as f: return set(json.load(f))
        except: return set()
    return set()

def save_seen(seen_ids):
    with open(SEEN_FILE, 'w') as f: json.dump(list(seen_ids), f)

seen_items = load_seen()

# --- DEFINIZIONE COMANDI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="Bot operativo. Usa /cerca [testo] [prezzo_max]")

async def cerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /cerca [testo] [prezzo_max]")
        return
    
    query = " ".join(context.args[:-1])
    max_price = context.args[-1]
    
    url = "https://www.vinted.it/api/v2/catalog/items"
    params = {"search_text": query, "price_to": max_price, "order": "price_asc", "currency": "EUR"}
    
    try:
        response = session.get(url, params=params, timeout=10)
        if response.status_code != 200:
            await update.message.reply_text(f"Errore Vinted ({response.status_code})")
            return
            
        items = response.json().get('items', [])
        count = 0
        for item in items:
            item_id = str(item['id'])
            if item_id in seen_items: continue
            
            seen_items.add(item_id)
            price = item.get('price', {}).get('amount', 'N/D')
            msg = f"🛒 {item.get('title')}\n💰 {price}€\n🔗 {item.get('url')}"
            await context.bot.send_message(chat_id=CHAT_ID, text=msg)
            count += 1
            if count >= 3: break
            
        save_seen(seen_items)
        if count == 0: await update.message.reply_text("Nessun nuovo articolo trovato.")
    except Exception as e:
        await update.message.reply_text(f"Errore: {str(e)}")

# --- AVVIO SERVER WEB E BOT ---
@app.route('/')
def home(): return "Bot is running!"

def run_web_server(): 
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # 1. Avvia server web
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # 2. Configura bot
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("cerca", cerca))
    
    # 3. Avvia polling
    print("Avvio bot...")
    app_bot.run_polling(drop_pending_updates=True)
