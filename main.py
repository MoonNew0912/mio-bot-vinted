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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Referer': 'https://www.vinted.it/'
    }
    params = {'search_text': brand, 'order': 'newest_first', 'per_page': 20}
    
    try:
        session = requests.Session()
        session.get("https://www.vinted.it/", headers=headers)
        r = session.get("https://www.vinted.it/api/v2/catalog/items", params=params, headers=headers, timeout=10)
        
        for item in r.json().get('items', []):
            # ESTRAZIONE FORZATA: qui prendiamo i dati esatti
            prezzo_str = item.get('price', {}).get('amount', '0')
            prezzo = float(prezzo_str) if prezzo_str else 0
            taglia = str(item.get('size_title', '')).lower()
            titolo = item.get('title', '').lower()
            
            # --- FILTRI REALI (DEBUG) ---
            # 1. Prezzo: deve essere minore di 50
            if prezzo == 0 or prezzo > 50: continue
            
            # 2. Taglie: deve escludere xs, s, xxl, 3xl
            if any(t in taglia for t in ['xs', 's', 'xxl', '3xl']): continue
            
            # 3. Categorie indesiderate
            if any(parola in titolo for parola in ['donna', 'femme', 'bikini', 'costume']): continue
            
            msg = f"🔥 {item.get('brand_title', 'No Brand')} | {titolo}\n💰 {prezzo}€\n🔗 {item.get('url')}"
            invia_notifica(msg)
            
    except Exception as e: print(f"Errore: {e}")

def monitora():
    brand_list = ["Carhartt", "Stone Island", "CP Company", "Dickies"]
    while True:
        for b in brand_list:
            esegui_ricerca(b)
            time.sleep(15)

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()
    threading.Thread(target=monitora, daemon=True).start()
    while True: time.sleep(60)
