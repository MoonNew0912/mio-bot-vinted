import time
import random
import requests
import threading
import sys
import re
import os
from flask import Flask

TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"
ID_CHAT_TELEGRAM = "387028237"

id_visti_assoluti = set()
lock_id = threading.Lock()

CATEGORIE_UOMO_AMMESSE = {5, 79, 80, 81, 2050, 2054, 2056, 2058, 2060, 2062, 2064}
CAT_PANTALONI = {80, 81, 2058, 2060}
CAT_SCARPE = {5}

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Online", 200

def avvia_server_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    try:
        requests.post(url, json={"chat_id": ID_CHAT_TELEGRAM, "text": messaggio}, timeout=5)
    except: pass

def check_articolo_valido(item, brand_cercato, p_max_imposto, stats=None):
    if stats is None: stats = {}
    
    # 1. Filtro Prezzo (Priorità Assoluta al limite imposto)
    prezzo = float(item.get('price', {}).get('amount', '0'))
    if prezzo > p_max_imposto:
        return False
        
    # 2. Filtro Taglie (Rigido)
    taglia = item.get('size_title', '').lower().strip()
    token_taglia = set(re.split(r'[\s/(),.-]+', taglia))
    
    taglie_vietate = {'xs', 's', 'xxl', '3xl', '4xl'}
    if token_taglia.intersection(taglie_vietate):
        return False
        
    # 3. Filtro Categorie/Sesso
    catalog_id = item.get('catalog_id')
    if catalog_id and catalog_id not in CATEGORIE_UOMO_AMMESSE:
        return False
        
    return True

def esegui_ricerca_manuale(session, brand_cercato, p_min, p_max):
    url_base = "https://www.vinted.it/api/v2/catalog/items"
    articoli_validi = []
    
    try:
        r = session.get(url_base, params={'search_text': brand_cercato, 'order': 'newest_first', 'per_page': 30}, timeout=10)
        for item in r.json().get('items', []):
            if item['id'] in id_visti_assoluti: continue
            
            if check_articolo_valido(item, brand_cercato, p_max):
                id_visti_assoluti.add(item['id'])
                articoli_validi.append(item)
                if len(articoli_validi) >= 5: break
                
        for item in articoli_validi:
            msg = f"🔥 {item['brand_title']} | {item['title']}\n💰 {item['price']['amount']}€\n📏 {item['size_title']}\n🔗 {item['url']}"
            invia_notifica_telegram(msg)
    except: pass

def gestisci_comandi_telegram(session):
    last_id = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates", params={'offset': last_id, 'timeout': 10}).json()
            for up in r.get('result', []):
                last_id = up['update_id'] + 1
                text = up.get('message', {}).get('text', '')
                if text.lower().startswith('cerca '):
                    p = [x.strip() for x in text[6:].split(',')]
                    if len(p) == 3:
                        threading.Thread(target=esegui_ricerca_manuale, args=(session, p[0], float(p[1]), float(p[2])), daemon=True).start()
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=avvia_server_web, daemon=True).start()
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    gestisci_comandi_telegram(session)
