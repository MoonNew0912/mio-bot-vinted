import logging
import asyncio
import os
from telegram.ext import ApplicationBuilder, CommandHandler
from vinted_unofficial.client import VintedClient
import sqlite3
import time

# --- CONFIGURAZIONE ---
TOKEN = os.getenv("8948272794:AAEjodIDu_-WDIeby8WB2I6N_baki-h-rSo") # Impostalo nelle Environment Variables di Render
CHAT_ID = "387028237"
DB_PATH = "vinted_bot.db"

# --- DB SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS processed (item_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

# --- LOGICA BOT ---
async def start(update, context):
    await update.message.reply_text("Bot monitoraggio Vinted attivo e operativo!")

async def monitor_vinted(context):
    """Funzione di loop per il monitoraggio"""
    client = VintedClient()
    # Esempio di ricerca base (modifica i parametri a piacere)
    try:
        items = client.items.search({"search_text": "stone island", "order": "newest_first"})
        for item in items:
            conn = sqlite3.connect(DB_PATH)
            exists = conn.execute("SELECT 1 FROM processed WHERE item_id = ?", (item.id,)).fetchone()
            
            if not exists:
                # Invia notifica
                msg = f"🔥 NUOVO ARTICOLO: {item.title}\nPrezzo: {item.price}€\nLink: {item.url}"
                await context.bot.send_message(chat_id=CHAT_ID, text=msg)
                
                # Salva nel DB
                conn.execute("INSERT INTO processed (item_id) VALUES (?)", (item.id,))
                conn.commit()
            conn.close()
    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == '__main__':
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Aggiungi job per il monitoraggio (ogni 60 secondi)
    job_queue = application.job_queue
    job_queue.run_repeating(monitor_vinted, interval=60, first=10)
    
    application.add_handler(CommandHandler("start", start))
    
    print("Bot avviato su Render...")
    application.run_polling()
