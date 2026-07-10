import time, random, requests, threading, os
from flask import Flask

TOKEN = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"
CHAT_ID = "387028237"

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online", 200

def invia_notifica(msg):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    except: pass

def esegui_ricerca(brand):
    # User-agent più aggiornato e headers completi
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://www.vinted.it/'
    }
    
    # Parametri base (senza forzare catalog_ids che spesso blocca tutto)
    params = {'search_text': brand, 'order': 'newest_first', 'per_page': 20}
    
    try:
        session = requests.Session()
        # Richiesta iniziale per ottenere i cookie di sessione
        session.get("https://www.vinted.it/", headers=headers)
        
        # Chiamata API
        r = session.get("https://www.vinted.it/api/v2/catalog/items", params=params, headers=headers, timeout=10)
        
        for item in r.json().get('items', []):
            prezzo = float(item.get('price', {}).get('amount', 0))
            titolo = item.get('title', '').lower()
            brand_titolo = item.get('brand_title', '').lower()
            
            # FILTRI RIGIDI LATO BOT
            if prezzo > 50: continue # Prezzo fisso massimo
            if any(parola in titolo for parola in ['donna', 'femme', 'bikini', 'costume', 'scarpe donna']): continue
            if any(taglia in item.get('size_title', '').lower() for taglia in ['xs', 's', 'xxl']): continue
            
            msg = f"🔥 {brand_titolo} | {titolo}\n💰 {prezzo}€\n🔗 {item['url']}"
            invia_notifica(msg)
            
    except Exception as e: print(f"Errore: {e}")

def monitora():
    brand_list = ["Carhartt", "Stone Island", "CP Company", "Dickies"]
    while True:
        for b in brand_list:
            esegui_ricerca(b)
            time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()
    threading.Thread(target=monitora, daemon=True).start()
    while True: time.sleep(60)
