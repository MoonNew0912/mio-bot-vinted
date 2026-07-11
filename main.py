import time
import random
import requests
import threading
import sys

# ================= CONFIGURAZIONE =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"
ID_CHAT_TELEGRAM = "387028237"

id_automatici_visti = set()
id_manuali_visti = set()
lock_auto = threading.Lock()
lock_manual = threading.Lock()

def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": ID_CHAT_TELEGRAM, "text": messaggio, "disable_web_page_preview": False}
    try:
        requests.post(url, json=payload, timeout=5)
    except: pass

def check_articolo_valido(item, parola_chiave, prezzo_massimo_default, prezzo_minimo_custom=3.0):
    titolo = item.get('title', '').lower()
    descrizione = item.get('description', '').lower()
    brand = item.get('brand_title', '').lower()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    taglia = item.get('size_title', '').lower().strip()

    # --- FILTRI TAGLIE ---
    taglie_ammesse_vestiti = ['m', 'l', 'xl', 'l/xl']
    taglie_ammesse_scarpe = ['42.5', '42 1/2', '43', '43 1/3']
    if taglia not in (taglie_ammesse_vestiti + taglie_ammesse_scarpe):
        return False

    # --- LOGICA INTELLIGENTE: SCARPE VS ABBIGLIAMENTO ---
    is_scarpe = any(x in titolo for x in ['scarpe', 'sneakers', 'jordan', 'nike', 'adidas', 'yeezy'])
    
    # 1. Nike/Adidas: solo se scarpe
    if not is_scarpe and ("nike" in brand or "adidas" in brand):
        return False

    # 2. Ralph Lauren / Lacoste: solo parte superiore
    if any(b in brand for b in ["ralph lauren", "lacoste"]):
        if not any(x in titolo for x in ["felpa", "maglia", "t-shirt", "camicia", "polo", "giacca", "hoodie"]):
            return False

    # --- FILTRI BASE ---
    if prezzo < prezzo_minimo_custom or prezzo > prezzo_massimo_default:
        return False

    return True

# ... [Mantenere invariate le funzioni esegui_ricerca_manuale e gestisci_comandi_telegram] ...

def monitora_vinted_background(session, lista_ricerche):
    url_base_sicuro = "https://www.vinted.it/api/v2/catalog/items"
    
    while True:
        random.shuffle(lista_ricerche)
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_max = ricerca["prezzo_max"]

            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 10,
                'catalog_ids[]': [5, 123]
            }
            
            try:
                risposta = session.get(url_base_sicuro, params=parametri, timeout=7)
                if risposta.status_code == 200:
                    for item in risposta.json().get('items', []):
                        item_id = item.get('id')
                        with lock_auto:
                            if item_id in id_automatici_visti: continue
                        
                        if check_articolo_valido(item, parola_chiave, prezzo_max):
                            invia_notifica_telegram(f"⚡ TROVATO: {parola_chiave}\n{item.get('title')}\n{item.get('price', {}).get('amount')}€\n{item.get('url')}")
                            with lock_auto: id_automatici_visti.add(item_id)
                elif risposta.status_code == 429:
                    time.sleep(60)
            except: pass
            time.sleep(random.uniform(2.0, 4.0))

if __name__ == "__main__":
    session = requests.Session()
    # User-Agent molto realistico per tentare di aggirare il 403
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'})
    
    # ... [Mantenere il resto dell'avvio e la lista MIE_RICERCHE] ...
    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE)).start()
    gestisci_comandi_telegram(session)
