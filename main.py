import time
import random
import requests
import threading
import re
import os
from flask import Flask

TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"
ID_CHAT_TELEGRAM = "387028237"

# ID Categorie Uomo Vinted (Solo Abbigliamento e Scarpe Uomo)
CAT_UOMO_ID = "5,79,80,81,2050,2054,2056,2058,2060,2062,2064"

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online", 200

def avvia_server_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def invia_notifica(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", 
                      json={"chat_id": ID_CHAT_TELEGRAM, "text": msg}, timeout=5)
    except: pass

def esegui_ricerca(brand, p_max):
    # Forziamo i parametri direttamente nella chiamata API
    params = {
        'search_text': brand,
        'catalog_ids': CAT_UOMO_ID,
        'price_to': p_max,
        'order': 'newest_first',
        'per_page': 20
    }
    try:
        r = requests.get("https://www.vinted.it/api/v2/catalog/items", params=params, timeout=10)
        for item in r.json().get('items', []):
            # Filtro taglia extra lato bot
            size = item.get('size_title', '').lower()
            if any(x in size for x in ['xs', 's', 'xxl', '3xl']): continue
            
            msg = f"🔥 {item['brand_title']} | {item['title']}\n💰 {item['price']['amount']}€\n🔗 {item['url']}"
            invia_notifica(msg)
    except: pass

def monitora():
    brand_nicchia = [
        "Rick Owens", "Enfants Riches Déprimés", "ERD", "Raf Simons", 
        "Margiela", "Chrome Hearts", "Corteiz", "Denim Tears", 
        "Cactus Plant", "Off-White", "Helmut Lang", "Yohji Yamamoto",
        "Comme des Garçons", "Undercover", "CP Company", "Stone Island"
    ]
    while True:
        for b in brand_nicchia:
            # Budget dinamico: 80 per i pezzi rari, 40 per gli altri
            limit = 80 if b in ["Rick Owens", "Enfants Riches Déprimés", "ERD"] else 40
            esegui_ricerca(b, limit)
            time.sleep(random.uniform(5, 10))

if __name__ == "__main__":
    threading.Thread(target=avvia_server_web, daemon=True).start()
    threading.Thread(target=monitora, daemon=True).start()
    invia_notifica("🛡️ CENTRALINA NICCHIA ATTIVA (Filtri API Nativi)")
    # Loop vuoto per mantenere il bot vivo
    while True: time.sleep(60)
