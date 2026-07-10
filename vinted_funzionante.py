import time
import random
import requests
import threading
import sys
import re

# ================= CONFIGURAZIONE TELEGRAM =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"  # Il tuo token BotFather
ID_CHAT_TELEGRAM = "387028237"    # Il tuo ID numerico
# ===========================================================

id_automatici_visti = set()
id_manuali_visti = set()

lock_auto = threading.Lock()
lock_manual = threading.Lock()

def pulisci_cache_se_piena():
    global id_automatici_visti, id_manuali_visti
    with lock_auto:
        if len(id_automatici_visti) > 5000:
            id_automatici_visti = set(list(id_automatici_visti)[-2000:])
    with lock_manual:
        if len(id_manuali_visti) > 5000:
            id_manuali_visti = set(list(id_manuali_visti)[-2000:])

def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": ID_CHAT_TELEGRAM, "text": messaggio, "disable_web_page_preview": False}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRORE TELEGRAM] {e}")

def check_articolo_valido(item, brand_cercato, prezzo_massimo_default, prezzo_minimo_custom=3.0):
    titolo = item.get('title', '').lower()
    descrizione = item.get('description', '').lower()
    brand_reale = item.get('brand_title', '').lower().strip()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    taglia = item.get('size_title', '').lower().strip()

    # --- 1. VERIFICA BRAND ---
    brand_cercato_clean = brand_cercato.lower().strip()
    if brand_cercato_clean == "erd":
        brand_cercato_clean = "enfants riches"

    if brand_cercato_clean not in brand_reale:
        brand_vuoto = brand_reale in ['', 'senza marca', 'no brand', 'anonyme', 'unknown']
        if not brand_vuoto:
            return False
        if brand_cercato_clean not in titolo and brand_cercato_clean not in descrizione:
            return False

    # --- 2. BLOCCO ANNI / BAMBINI ---
    if any(b in taglia for b in ['ans', 'years', 'anni', 'bambin', 'kid', 'mounat']):
        return False

    # --- 3. FILTRO TAGLIE INTELLIGENTE ---
    vestiti_ok = ['m', 'l', 'xl', 'l/xl']
    pantaloni_ok = ['33', '34', '36', 'w33', 'w34', 'w36']
    scarpe_ok = ['42.5', '42 1/2', '43', '43 1/3']
    
    passa_taglia = False

    if any(s in taglia for s in scarpe_ok):
        passa_taglia = True
    elif any(p == taglia or f"w{p}" in taglia for p in ['33', '34', '36']):
        passa_taglia = True
    else:
        token_taglia = re.split(r'[\s/(),.-]+', taglia)
        if any(v in token_taglia for v in vestiti_ok):
            if 'xs' in token_taglia or ('s' in token_taglia and 'xl' not in token_taglia):
                passa_taglia = False
            else:
                passa_taglia = True

    if not passa_taglia:
        return False

    # --- 4. CATEGORIE SVIATE ---
    parole_bannate_categoria = ['donna', 'woman', 'femme', 'giocattolo', 'gioco', 'baby', 'neonat']
    if any(p in titolo or p in descrizione for p in parole_bannate_categoria):
        if 'uomo' not in titolo and 'men' not in titolo:
            return False

    if prezzo < prezzo_minimo_custom:
        return False

    parole_esca = ['tipo', 'stile', 'style', 'inspired', 'look', 'simile', 'lookalike']
    if any(k in brand_reale or k in titolo for k in ['rick owens', 'enfants riches']):
        if any(p in titolo or p in descrizione for p in parole_esca):
            return False  

    return prezzo <= prezzo_massimo_default

def esegui_ricerca_manuale(session, brand_cercato, p_min, p_max):
    """Ricerca manuale modificata con ordinamento 'più recenti' e contatore di debug"""
    url_base = "https://www.vinted.it/api/v2/catalog/items"
    pulisci_cache_se_piena()
    
    # Cambiato in 'newest_first' per evitare i blocchi degli annunci in evidenza obsoleti
    parametri = {
        'search_text': brand_cercato,
        'order': 'newest_first',
        'per_page': 50
    }
    
    try:
        invia_notifica_telegram(f"🔍 [RICERCA] Sguinzaglio i cani su Vinted per: {brand_cercato.upper()} ({p_min}€ - {p_max}€)...")
        risposta = session.get(url_base, params=parametri, timeout=10)
        
        if risposta.status_code == 200:
            articoli = risposta.json().get('items', [])
            totale_ricevuti = len(articoli)
            inviati = 0
            
            for item in articoli:
                if inviati >= 10:
                    break
                    
                item_id = item.get('id')
                
                with lock_manual:
                    if item_id in id_manuali_visti:
                        continue
                
                prezzo = float(item.get('price', {}).get('amount', '0'))
                
                if p_min <= prezzo <= p_max and check_articolo_valido(item, brand_cercato, p_max, p_min):
                    titolo = item.get('title', 'Nessun titolo')
                    link = item.get('url', '')
                    taglia_vinted = item.get('size_title', '').upper().strip()
                    brand_effettivo = item.get('brand_title', 'Non specificato').upper()
                    
                    testo_notifica = (
                        f"🔎 RICERCA MANUALE CHIESTA:\n"
                        f"🔥 Brand Rilevato: {brand_effettivo}\n"
                        f"👕 Articolo: {titolo}\n"
                        f"📏 Taglia: {taglia_vinted}\n"
                        f"💰 Prezzo: {prezzo} €\n\n"
                        f"🔗 LINK:\n{link}"
                    )
                    invia_notifica_telegram(testo_notifica)
                    
                    with lock_manual:
                        id_manuali_visti.add(item_id)
                    inviati += 1
                    time.sleep(0.8)
                    
            if inviati == 0:
                invia_notifica_telegram(f"❌ Nessun pezzo idoneo trovato. (Analizzati {totale_ricevuti} articoli scaricati da Vinted per '{brand_cercato}')")
        else:
            invia_notifica_telegram(f"⚠️ Errore di connessione Vinted (Status: {risposta.status_code}). Riprova.")
    except Exception as e:
        print(f"Errore ricerca manuale: {e}")

def gestisci_comandi_telegram(session):
    url_updates = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    last_update_id = 0
    
    try:
        r = requests.get(url_updates, params={'offset': -1}, timeout=5).json()
        if r.get('result'):
            last_update_id = r['result'][0]['update_id'] + 1
    except Exception:
        pass

    while True:
        try:
            r = requests.get(url_updates, params={'offset': last_update_id, 'timeout': 20}, timeout=25).json()
            for update in r.get('result', []):
                last_update_id = update['update_id'] + 1
                message = update.get('message', {})
                text = message.get('text', '').strip()
                chat_id = str(message.get('chat', {}).get('id', ''))
                
                if chat_id == ID_CHAT_TELEGRAM and text.lower().startswith('cerca '):
                    corpo = text[6:]
                    parti = [p.strip() for p in corpo.split(',')]
                    
                    if len(parti) == 3:
                        brand_cercato = parti[0]
                        try:
                            prezzo_min = float(parti[1])
                            prezzo_max = float(parti[2])
                            threading.Thread(target=esegui_riceline_manuale, args=(session, brand_cercato, prezzo_min, prezzo_max), name=f"Manual-{brand_cercato}").start()
                        except ValueError:
                            invia_notifica_telegram("⚠️ Prezzi non validi. Formato: cerca Stussy, 10, 40")
                    else:
                        invia_notifica_telegram("⚠️ Formato: cerca Brand, Min, Max")
        except Exception:
            time.sleep(5)

def monitora_vinted_background(session, lista_ricerche):
    url_base_sicuro = "https://www.vinted.it/api/v2/catalog/items"
    parole_bannate_reali = ["rotto", "rotta", "rovinato", "rovinata", "bucato", "bucata", "usurato"]

    while True:
        pulisci_cache_se_piena()
        random.shuffle(lista_ricerche)
        
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_massimo = ricerca["prezzo_max"]

            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 10,
                'status_ids[]': [1, 2, 3, 6]
            }
            
            try:
                risposta = session.get(url_base_sicuro, params=parametri, timeout=7)
                if risposta.status_code == 200:
                    articoli = risposta.json().get('items', [])
                    for item in articoli:
                        item_id = item.get('id')
                        
                        with lock_auto:
                            if item_id in id_automatici_visti:
                                continue
                            id_automatici_visti.add(item_id)

                        titolo = item.get('title', 'Nessun titolo')
                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').upper().strip()
                        brand_rilevato = item.get('brand_title', 'Generico').upper()

                        if not check_articolo_valido(item, parola_chiave, prezzo_massimo):
                            continue

                        if any(parola in titolo.lower() for parola in parole_bannate_reali):
                            continue

                        testo_notifica = (
                            f"⚡ APPENA PUBBLICATO ORA!\n"
                            f"🔥 Brand Reale: {brand_rilevato}\n"
                            f"👕 Articolo: {titolo}\n"
                            f"📏 Taglia: {taglia_vinted}\n"
                            f"💰 Prezzo: {prezzo} €\n\n"
                            f"🔗 LINK DIRETTO:\n{link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        
                elif risposta.status_code == 429:
                    time.sleep(45)
                time.sleep(random.uniform(2.5, 4.0))
            except Exception:
                pass
        time.sleep(5)

if __name__ == "__main__":
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
        'Accept': 'application/json, text/plain, */*',
        'Connection': 'keep-alive',
        'Referer': 'https://www.vinted.it/catalog'
    })
    
    try:
        session.get("https://www.vinted.it/catalog", timeout=10)
    except Exception:
        sys.exit(1)

    MIE_RICERCHE = [
        {"nome": "Stussy", "prezzo_max": 40.0}, {"nome": "Supreme", "prezzo_max": 40.0},
        {"nome": "Palace", "prezzo_max": 40.0}, {"nome": "Burberry", "prezzo_max": 40.0},
        {"nome": "Prada", "prezzo_max": 40.0}, {"nome": "Corteiz", "prezzo_max": 40.0},
        {"nome": "Fear of God Essentials", "prezzo_max": 40.0}, {"nome": "Denim Tears", "prezzo_max": 40.0},
        {"nome": "Cactus Plant", "prezzo_max": 40.0}, {"nome": "Off-White", "prezzo_max": 40.0},
        {"nome": "Raf Simons", "prezzo_max": 40.0}, {"nome": "Rick Owens", "prezzo_max": 80.0},
        {"nome": "Enfants Riches Déprimés", "prezzo_max": 80.0}, {"nome": "ERD", "prezzo_max": 40.0},
        {"nome": "Helmut Lang", "prezzo_max": 40.0}, {"nome": "Margiela", "prezzo_max": 40.0},
        {"nome": "Yohji Yamamoto", "prezzo_max": 40.0}, {"nome": "Comme des Garçons", "prezzo_max": 40.0},
        {"nome": "Undercover", "prezzo_max": 40.0}, {"nome": "CP Company", "prezzo_max": 40.0},
        {"nome": "Stone Island", "prezzo_max": 40.0}, {"nome": "Carhartt", "prezzo_max": 40.0},
        {"nome": "Nike", "prezzo_max": 65.0}, {"nome": "Jordan", "prezzo_max": 65.0},
        {"nome": "Jordan 5", "prezzo_max": 65.0}, {"nome": "Jordan 11", "prezzo_max": 65.0},
        {"nome": "Jordan 12", "prezzo_max": 65.0}, {"nome": "Jordan 13", "prezzo_max": 65.0},
        {"nome": "Adidas", "prezzo_max": 65.0}, {"nome": "Chrome Hearts", "prezzo_max": 40.0},
        {"nome": "Hellstar", "prezzo_max": 40.0}, {"nome": "Sp5der", "prezzo_max": 40.0},
        {"nome": "Syna World", "prezzo_max": 40.0}, {"nome": "Trapstar", "prezzo_max": 40.0},
        {"nome": "Sicko Born", "prezzo_max": 40.0}, {"nome": "Gallery Dept", "prezzo_max": 40.0},
        {"nome": "RRR123", "prezzo_max": 40.0}, {"nome": "Balenciaga", "prezzo_max": 40.0},
        {"nome": "Vetements", "prezzo_max": 40.0}, {"nome": "Evisu", "prezzo_max": 65.0},
        {"nome": "True Religion", "prezzo_max": 30.0}, {"nome": "Vicinity", "prezzo_max": 35.0},
        {"nome": "Acne Studios", "prezzo_max": 65.0}, {"nome": "derschutze", "prezzo_max": 35.0},
        {"nome": "Cold Culture", "prezzo_max": 35.0}
    ]

    invia_notifica_telegram("⚙️ AGGIORNAMENTO STRUTTURALE REALE:\n• Ottimizzato ordinamento manuale sui flussi live.\n• Log diagnostico attivo.")

    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE)).start()
    gestisci_comandi_telegram(session)
