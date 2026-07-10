import time, requests, threading, os
from flask import Flask

TOKEN = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"
CHAT_ID = "387028237"

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online", 200

# Memoria per evitare notifiche doppie
articoli_gia_inviati = set()

def invia_notifica(msg):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    except: pass

def esegui_ricerca(brand):
    global articoli_gia_inviati
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Referer': 'https://www.vinted.it/'
    }
    params = {'search_text': brand, 'order': 'newest_first', 'per_page': 20}
    
    try:
        session = requests.Session()
        session.get("https://www.vinted.it/", headers=headers, timeout=10)
        r = session.get("https://www.vinted.it/api/v2/catalog/items", params=params, headers=headers, timeout=10)
        
        if r.status_code != 200: return

        for item in r.json().get('items', []):
            item_id = str(item.get('id'))
            if item_id in articoli_gia_inviati: continue
            
            # Estrazione dati
            prezzo = float(item.get('price', {}).get('amount', 0))
            taglia = str(item.get('size_title', '')).lower()
            titolo = item.get('title', '').lower()
            
            # FILTRO TAGLIE: ACCETTIAMO SOLO QUESTE ESATTE
            taglie_ok = ['m', 'l', 'xl', '46', '48', '50', '52']
            if taglia not in taglie_ok: continue

            # FILTRO PREZZO
            if prezzo == 0 or prezzo > 50: continue
            
            # FILTRO ANTI-ROBA DONNA
            if any(parola in titolo for parola in ['donna', 'femme', 'bikini', 'costume']): continue
            
            # Invio
            msg = f"🔥 {item.get('brand_title')} | {titolo}\n💰 {prezzo}€\n🔗 {item.get('url')}"
            invia_notifica(msg)
            articoli_gia_inviati.add(item_id)
            
            # Pulizia memoria
            if len(articoli_gia_inviati) > 200: articoli_gia_inviati.clear()
            
            time.sleep(2)
            
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
    invia_notifica("🚀 BOT FILTRI ATTIVO E BLINDATO")
    while True: time.sleep(60)
