import time, requests, threading, os
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
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.vinted.it/'
    }
    try:
        session = requests.Session()
        # Ottieni i cookie necessari
        session.get("https://www.vinted.it/", headers=headers, timeout=10)
        
        url = f"https://www.vinted.it/api/v2/catalog/items?search_text={brand}&order=newest_first&per_page=20"
        r = session.get(url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            print(f"Bloccati da Vinted (Status {r.status_code})")
            time.sleep(300) # Dormiamo 5 minuti se ci bloccano
            return

        for item in r.json().get('items', []):
            try:
                prezzo = float(item.get('price', {}).get('amount', 0))
                taglia = str(item.get('size_title', '')).lower()
                titolo = item.get('title', '').lower()
                
                # FILTRI REALI
                if prezzo == 0 or prezzo > 50: continue
                if any(t in taglia for t in ['xs', 's', 'xxl', '3xl']): continue
                if any(p in titolo for p in ['donna', 'femme', 'bikini']): continue
                
                msg = f"🔥 {item.get('brand_title')} | {titolo}\n💰 {prezzo}€\n🔗 {item.get('url')}"
                invia_notifica(msg)
                time.sleep(2) # Piccola pausa tra notifiche per non spammare Telegram
            except: continue
            
    except Exception as e: print(f"Errore: {e}")

def monitora():
    brand_list = ["Carhartt", "Stone Island", "CP Company", "Dickies"]
    while True:
        for b in brand_list:
            esegui_ricerca(b)
            time.sleep(30) # Pausa più lunga tra un brand e l'altro per essere meno visibili

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()
    threading.Thread(target=monitora, daemon=True).start()
    while True: time.sleep(60)
