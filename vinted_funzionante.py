import time
import random
import requests
import threading
import sys

# ================= CONFIGURAZIONE TELEGRAM =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"  # Il tuo token BotFather
ID_CHAT_TELEGRAM = "387028237"    # Il tuo ID numerico
# ===========================================================

# Strutture di memoria separate per evitare interferenze tra i due motori
id_automatici_visti = set()
id_manuali_visti = set()

lock_auto = threading.Lock()
lock_manual = threading.Lock()

def invia_notifica_telegram(messaggio):
    """Invia un messaggio di testo su Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {
        "chat_id": ID_CHAT_TELEGRAM,
        "text": messaggio,
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRORE TELEGRAM] Impossibile inviare la notifica: {e}")

def check_articolo_valido(item, parola_chiave, prezzo_massimo_default, prezzo_minimo_custom=3.0):
    """Controlla se l'articolo rispetta i filtri con LOGICA WHITELIST rigorosa per le tue taglie"""
    titolo = item.get('title', '').lower()
    descrizione = item.get('description', '').lower()
    brand = item.get('brand_title', '').lower()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    taglia = item.get('size_title', '').lower().strip()

    # Whitelist rigida delle tue taglie personali
    taglie_ammesse_vestiti = ['m', 'l', 'xl', 'l/xl']
    taglie_ammesse_pantaloni = ['33', '34', '36', 'w33', 'w34', 'w36']
    taglie_ammesse_scarpe = ['42.5', '42 1/2', '43', '43 1/3']
    tutte_le_taglie_ok = taglie_ammesse_vestiti + taglie_ammesse_pantaloni + taglie_ammesse_scarpe

    if taglia not in tutte_le_taglie_ok:
        if not any(t_ok in taglia for t_ok in tutte_le_taglie_ok):
            return False
        if any(vietata in taglia for vietata in ['xs', 's', '35', '36', '37', '38', '39', '40', '41']) and not ('42.5' in taglia or '43' in taglia):
            return False

    # Esclusione categorie non maschili o infantili
    parole_bannate_categoria = ['donna', 'woman', 'femme', 'giocattolo', 'gioco', 'toy', 'joc', 'juguete', 'bambino', 'bambina', 'neonata', 'neonato', 'kid', 'kids', 'baby']
    if any(p in titolo or p in descrizione for p in parole_bannate_categoria):
        if 'uomo' not in titolo and 'men' not in titolo:
            return False

    if prezzo < prezzo_minimo_custom:
        return False

    # Filtro anti-esca repliche
    brand_vuoto = brand in ['', 'senza marca', 'no brand', 'anonyme', 'unknown']
    parole_esca = ['tipo', 'stile', 'style', 'inspired', 'look', 'aesthetic', 'simile', 'lookalike']
    if any(k in brand or k in titolo or k in descrizione for k in ['rick owens', 'enfants riches', 'erd']):
        if brand_vuoto and any(p in titolo or p in descrizione for p in parole_esca):
            return False  

    return prezzo <= prezzo_massimo_default

def esegui_ricerca_manuale(session, brand_cercato, p_min, p_max):
    """Esegue una ricerca istantanea ordinata dal prezzo più basso, usando la memoria dedicata manuale"""
    url_base = "https://www.vinted.it/api/v2/catalog/items"
    
    parametri = {
        'search_text': brand_cercato,
        'order': 'price_low_to_high',
        'per_page': 50,
        'catalog_ids[]': [5, 123],
        'size_ids[]': [207, 208, 209, 778, 779, 363, 364, 366]
    }
    
    try:
        invia_notifica_telegram(f"🔍 Cerco su Vinted: {brand_cercato.upper()} (da {p_min}€ a {p_max}€) ordinato dal prezzo più basso...")
        risposta = session.get(url_base, params=parametri, timeout=10)
        
        if risposta.status_code == 200:
            articoli = risposta.json().get('items', [])
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
                    taglia_vinted = item.get('size_title', '').lower().strip()
                    
                    testo_notifica = (
                        f"🔎 RICERCA MANUALE: {brand_cercato.upper()}\n"
                        f"💰 Prezzo: {prezzo} € (Più basso trovato)\n"
                        f"👕 Articolo: {titolo}\n"
                        f"📏 Taglia: {taglia_vinted.upper()}\n\n"
                        f"🔗 LINK:\n{link}"
                    )
                    invia_notifica_telegram(testo_notifica)
                    
                    with lock_manual:
                        id_manuali_visti.add(item_id)
                    inviati += 1
                    time.sleep(1.0)
                    
            if inviati == 0:
                invia_notifica_telegram(f"❌ Nessun nuovo articolo trovato per '{brand_cercato}' in quel range di prezzo o con le tue taglie.")
        else:
            invia_notifica_telegram("⚠️ Errore di connessione con i server Vinted durante la ricerca manuale.")
    except Exception as e:
        print(f"Errore ricerca manuale: {e}")

def gestisci_comandi_telegram(session):
    """Resta in ascolto costante su Telegram per intercettare i tuoi messaggi 'cerca ...'"""
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
                            threading.Thread(target=esegui_ricerca_manuale, args=(session, brand_cercato, prezzo_min, prezzo_max)).start()
                        except ValueError:
                            invia_notifica_telegram("⚠️ Formato prezzi non valido. Usa i numeri, es: cerca Stussy, 10, 40")
                    else:
                        invia_notifica_telegram("⚠️ Formato errato! Scrivi esattamente così:\ncerca NomeBrand, PrezzoMin, PrezzoMax\n\nEsempio: cerca Supreme, 15, 50")
        except Exception:
            time.sleep(5)

def monitora_vinted_background(session, lista_ricerche):
    """Il vecchio motore automatico di monitoraggio continuo iper-veloce per i NUOVI ARRIVI PUBBLICATI AL MOMENTO"""
    url_base_sicuro = "https://www.vinted.it/api/v2/catalog/items"
    parole_bannate_reali = ["rotto", "rotta", "rovinato", "rovinata", "bucato", "bucata", "usurato"]

    while True:
        random.shuffle(lista_ricerche)
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_massimo = ricerca["prezzo_max"]

            # Ordine rigido 'newest_first' per beccare i secondi esatti del caricamento online
            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 10,
                'status_ids[]': [1, 2, 3, 6],
                'catalog_ids[]': [5, 123],
                'size_ids[]': [207, 208, 209, 778, 779, 363, 364, 366]
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
                        
                        titolo = item.get('title', 'Nessun titolo')
                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').lower().strip()

                        if not check_articolo_valido(item, parola_chiave, prezzo_massimo):
                            with lock_auto: id_automatici_visti.add(item_id)
                            continue

                        if any(parola in titolo.lower() for parola in parole_bannate_reali):
                            with lock_auto: id_automatici_visti.add(item_id)
                            continue

                        testo_notifica = (
                            f"⚡ RECENTISSIMO ABBIGLIAMENTO UOMO!\n"
                            f"🔥 Brand: {parola_chiave.upper()}\n"
                            f"👕 Articolo: {titolo}\n"
                            f"📏 Taglia: {taglia_vinted.upper()}\n"
                            f"💰 Prezzo: {prezzo} €\n\n"
                            f"🔗 LINK DIRETTO:\n{link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        
                        with lock_auto:
                            id_automatici_visti.add(item_id)
                            
                elif risposta.status_code == 429:
                    time.sleep(60)
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass
        time.sleep(5)

# Avvio del sistema
if __name__ == "__main__":
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
        'Accept': 'application/json, text/plain, */*',
        'Connection': 'keep-alive',
        'Referer': 'https://www.vinted.it/catalog'
    })
    
    print("Inizializzazione sessione...")
    try:
        session.get("https://www.vinted.it/catalog", timeout=10)
    except Exception as e:
        print(f"Errore connessione iniziale: {e}")
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

    print("Fase di riscaldamento iniziale...")
    for r in MIE_RICERCHE[:15]:
        try:
            res = session.get("https://www.vinted.it/api/v2/catalog/items", params={'search_text': r['nome'], 'order': 'newest_first', 'per_page': 20, 'catalog_ids[]': [5,123]}, timeout=5)
            if res.status_code == 200:
                for item in res.json().get('items', []):
                    id_automatici_visti.add(item.get('id'))
        except Exception: pass

    invia_notifica_telegram("🚀 BOT RESETTATO E FUNZIONANTE!\n• Monitoraggio automatico sincronizzato sui NUOVI arrivi millesimali.\n• Ricerche manuali separate al 100%.")

    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE)).start()
    gestisci_comandi_telegram(session)
