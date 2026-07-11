import logging, threading, json, os, requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Configurazione
BOT_TOKEN = os.getenv("8948272794:AAEjodIDu_-WDIeby8WB2I6N_baki-h-rSo")
CHAT_ID = "387028237"
SEEN_FILE = "seen_items.json"

app = Flask(__name__)
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
        await update.message.reply_text("Uso corretto: /cerca [testo] [prezzo_max]")
        return
    
    query = context.args[0]
    max_price = context.args[1]
    
    # URL di ricerca Vinted
    url = f"https://www.vinted.it/api/v2/catalog/items?search_text={query}&price_to={max_price}&order=price_asc"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        items = data.get('items', [])
        
        count = 0
        for item in items:
            item_id = str(item['id'])
            # Filtro duplicati
            if item_id in seen_items: continue
            
            # Filtro brand (esclusione Nike/Adidas)
            brand = item.get('brand_title', '') or ''
            if "nike" in brand.lower() or "adidas" in brand.lower(): continue
            
            seen_items.add(item_id)
            price = item.get('price', {}).get('amount', 'N/D')
            link = item.get('url', '#')
            
            msg = f"🛒 {item.get('title')}\n💰 {price}€\n🏷 {brand}\n🔗 {link}"
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
