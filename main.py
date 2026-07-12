import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Recupero token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Funzione ricerca (più semplice possibile)
async def cerca_su_vinted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /cerca [marca]")
        return
    
    query = context.args[0]
    await update.message.reply_text(f"Cerco {query}...")
    
    url = f"https://www.vinted.it/api/v2/catalog/items?search_text={query}&order=newest_first&per_page=3"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            items = res.json().get('items', [])
            if not items:
                await update.message.reply_text("Nessun risultato.")
                return
            for item in items:
                prezzo = item.get('price', {}).get('amount')
                await update.message.reply_text(f"🔥 {item['title']}\n💰 {prezzo}€\n🔗 {item['url']}")
        else:
            await update.message.reply_text(f"Errore Vinted: {res.status_code}")
    except Exception as e:
        await update.message.reply_text(f"Errore: {e}")

if __name__ == '__main__':
    print("Avvio del bot in modalità polling...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("cerca", cerca_su_vinted))
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("Bot attivo! Usa /cerca [marca]")))
    
    print("Bot pronto.")
    app.run_polling()
