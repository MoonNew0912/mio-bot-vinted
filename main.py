import time, requests, threading, os
from flask import Flask

# CONFIGURAZIONE
TOKEN = "8948272794:AAEjodIDu_-WDIeby8WB2I6N_baki-h-rSo"
CHAT_ID = "387028237"
BRAND_LIST = ["Carhartt", "Stone Island", "CP Company", "Dickies"]
TAGLIE_OK = ['m', 'l', 'xl', '46', '48', '50', '52']

# MEMORIA ANTI-SPAM
articoli_gia_inviati = set()

# SERVER WEB PER MANTENERE IL BOT ATTIVO
app = Flask(__name__)
@app.route('/')
def home(): return "Bot attivo", 200

def invia_notifica(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": msg}, timeout=5)
    except: pass

def esegui_ricerca(brand):
    global articoli_gia_inviati
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Referer': 'https://www.vinted.it/'
    }
    
    try:
        session = requests.Session()
        session.get("https://www.vinted.it/", headers=headers, timeout=10)
        r = session.get(f"https://www.vinted.it/api/v2/catalog/items?search_text={brand}&order=newest_first&per_page=20", 
                        headers=headers, timeout=10)
        
        if r.status_code != 200: return

        for item in r.json().get('items', []):
            item_id = str(item.get('id'))
            if item_id in articoli_gia_inviati: continue
            
            # FILTRI
            prezzo = float(item.get('price', {}).get('amount', 0))
            taglia = str(item.get('size_title', '')).lower()
            titolo = item.get('title', '').lower()
            
            if prezzo == 0 or prezzo > 50: continue
            if taglia not in TAGLIE_OK: continue
            if any(p in titolo for p in ['donna', 'femme', 'bikini', 'costume']): continue
            
            # NOTIFICA
            msg = f"🔥 {item.get('brand_title')} | {titolo}\n💰 {prezzo}€\n🔗 {item.get('url')}"
            invia_notifica(msg)
            articoli_gia_inviati.add(item_id)
            if len(articoli_gia_inviati) > 300: articoli_gia_inviati.clear()
            
    except: pass

def monitora():
    while True:
        for b in BRAND_LIST:
            esegui_ricerca(b)
            time.sleep(30)

if __name__ == "__main__":
    # Avvia server web
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()
    
    # Notifica di avvio
    invia_notifica("🚀 BOT LIVE! Sto scansionando Carhartt, Stone Island, CP Company e Dickies...")
    
    # Avvia monitoraggio
    monitora()
