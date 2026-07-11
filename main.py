import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from vinted_asc import Vinted

# CONFIGURAZIONE
BOT_TOKEN = "8948272794:AAEjodIDu_-WDIeby8WB2I6N_baki-h-rSo"
CHAT_ID = "387028237"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
vinted = Vinted()
last_items_ids = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="Bot attivo e pronto per la ricerca!")

async def cerca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Esempio comando: /cerca streetwear 20
    query = context.args[0]
    max_price = float(context.args[1])
    
    # Parametri filtrati
    params = {
        "search_text": query,
        "price_to": max_price,
        "currency": "EUR",
        "order": "price_asc",
        "condition_ids": "1,2", # Buono, Ottimo, Nuovo con etichetta
        "size_ids": "208,209,210,211", # M, L, L, XL (esempio ID)
        "catalog_ids": "1904,1242", # Uomo, Scarpe
    }
    
    items = vinted.search(params)
    
    # Filtro esclusione brand e duplicati
    results = [i for i in items if i.id not in last_items_ids and i.brand.lower() not in ['nike', 'adidas']]
    
    # Selezione primi 10
    output = results[:10]
    
    for item in output:
        last_items_ids.add(item.id)
        msg = f"{item.title}\nPrezzo: {item.price}\nBrand: {item.brand}\nLink: {item.url}"
        await context.bot.send_message(chat_id=CHAT_ID, text=msg)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cerca", cerca))
    app.run_polling()
