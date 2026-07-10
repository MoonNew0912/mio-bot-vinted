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

# Set globali persistenti per evitare QUALSIASI doppione (Mai ripuliti durante l'esecuzione)
id_visti_assoluti = set()
lock_id = threading.Lock()

def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": ID_CHAT_TELEGRAM, "text": messaggio, "disable_web_page_preview": False}
    try:
        # Gestione interna degli errori di invio
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 429:
            retry_after = res.json().get('parameters', {}).get('retry_after', 2)
            time.sleep(retry_after)
            requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRORE TELEGRAM] {e}")

def check_articolo_valido(item, brand_cercato, prezzo_massimo_default, prezzo_minimo_custom=0.0):
    """
    Applica filtri rigidi su disponibilità, brand, sesso, categorie, taglie e keyword replica.
    """
    # --- 0. DISPONIBILITÀ (Solo articoli realmente acquistabili) ---
    # Vinted usa 'status_id' o campi specifici. Verifichiamo lo stato dell'oggetto.
    if item.get('is_closed') or item.get('is_sold') or item.get('is_reserved') or item.get('is_hidden'):
        return False

    titolo = item.get('title', '').lower().strip()
    descrizione = item.get('description', '').lower().strip()
    brand_reale = item.get('brand_title', '').lower().strip()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    taglia = item.get('size_title', '').lower().strip()

    # --- 1. VERIFICA BRAND REALE ED ESCLUSIVO ---
    brand_cercato_clean = brand_cercato.lower().strip()
    if brand_cercato_clean == "erd":
        brand_cercato_clean = "enfants riches"

    # Se brand_title esiste, deve contenere il brand cercato
    if brand_reale:
        if brand_cercato_clean not in brand_reale:
            # Per ERD gestiamo la corrispondenza incrociata abbreviata/estesa
            if brand_cercato_clean == "enfants riches" and "erd" in brand_reale:
                pass
            else:
                return False
    else:
        # Se brand_title è vuoto, controlliamo in ordine titolo e descrizione
        if brand_cercato_clean in titolo:
            pass
        elif brand_cercato_clean in descrizione:
            pass
        else:
            return False

    # --- 2. FILTRO REPLICA / FAKE (Scarto immediato) ---
    parole_replica = [
        'inspired', 'inspired by', 'replica', 'replica 1:1', 'aaa', 'ua', 
        'fake', 'style', 'tipo', 'stile', 'simile', 'look', 'lookalike', 'inspired style'
    ]
    # Se cerchiamo brand che contengono queste parole per coincidenza (raro), evitiamo il filtro
    if any(p in titolo or p in descrizione for p in parole_replica):
        # Eccezione se la parola fa parte del brand cercato stesso
        if not any(p in brand_cercato_clean for p in parole_replica):
            return False

    # --- 3. SOLO ARTICOLI UOMO ---
    parole_bannate_sesso = [
        'woman', 'women', 'female', 'femme', 'donna', 'ladies', 'damen',
        'kid', 'kids', 'baby', 'junior', 'girl', 'boy', 'bambino', 'bambina', 
        'neonato', 'years', 'ans', 'anni'
    ]
    if any(p in titolo or p in descrizione or p in taglia for p in parole_bannate_sesso):
        # Accetta solo se è esplicitamente indicato uomo/men per contrastare falsi positivi nella descrizione
        if 'uomo' not in titolo and 'men' not in titolo and 'man' not in titolo:
            return False

    # --- 4. SOLO ABBIGLIAMENTO E SCARPE (Rigido) ---
    categorie_ammesse = [
        't-shirt', 'shirt', 'long sleeve', 'tank top', 'polo', 'felpa', 'hoodie', 
        'crewneck', 'sweater', 'maglia', 'maglione', 'jeans', 'cargo', 'pantaloni', 
        'shorts', 'jacket', 'bomber', 'coat', 'sneakers', 'scarpe', 'boots', 'loafers'
    ]
    if not any(cat in titolo or cat in descrizione for cat in categorie_ammesse):
        return False

    parole_bannate_categoria = [
        'libri', 'book', 'magazine', 'poster', 'profumi', 'perfume', 'beauty', 
        'skincare', 'makeup', 'cover', 'custodie', 'phone', 'iphone', 'airpods', 
        'console', 'videogiochi', 'accessori', 'accessories', 'bag', 'borsa', 
        'wallet', 'portafoglio', 'collane', 'bracciali', 'anelli', 'orologi', 
        'occhiali', 'cinture', 'cappelli', 'arredamento', 'casa', 'furniture', 
        'decorazioni', 'giocattoli', 'toys'
    ]
    if any(p in titolo or p in descrizione for p in parole_bannate_categoria):
        return False

    # --- 5. FILTRO TAGLIE OBBLIGATORIE ---
    vestiti_ok = {'m', 'l', 'xl'}
    pantaloni_ok = {'33', '34', '36', 'w33', 'w34', 'w36'}
    scarpe_ok = {'42.5', '42 1/2', '42½', '43', '43 1/3', '43⅓'}
    
    # Pulizia token taglia per match esatto ed evitare che 'xl' passi se la taglia è 'xxl' o 's' se è 'xs'
    token_taglia = set(re.split(r'[\s/(),.-]+', taglia))
    
    passa_taglia = False
    if any(s in taglia for s in scarpe_ok):
        passa_taglia = True
    elif any(p in token_taglia for p in pantaloni_ok):
        passa_taglia = True
    elif token_taglia.intersection(vestiti_ok):
        # Protezione ulteriore per escludere taglie composte sballate (es. 'xs' o 'xxl')
        if 'xs' not in token_taglia and 'xxl' not in token_taglia and 's' not in token_taglia:
            passa_taglia = True

    if not passa_taglia:
        return False

    # --- 6. FILTRO PREZZO ---
    return prezzo_minimo_custom <= prezzo <= prezzo_massimo_default

def esegui_ricerca_manuale(session, brand_cercato, p_min, p_max):
    """
    Esegue la ricerca manuale estraendo finché necessario gli articoli più recenti,
    li filtra rigidamente, li ordina per prezzo crescente e restituisce ESATTAMENTE 10 pezzi diversi.
    """
    url_base = "https://www.vinted.it/api/v2/catalog/items"
    invia_notifica_telegram(f"🔍 [RICERCA] Sguinzaglio i cani su Vinted per: {brand_cercato.upper()} ({p_min}€ - {p_max}€)...")
    
    articoli_validi_trovati = []
    page = 1
    max_pagine_tentativi = 5  # Evita loop infiniti se i risultati totali reali terminano
    
    while len(articoli_validi_trovati) < 10 and page <= max_pagine_tentativi:
        parametri = {
            'search_text': brand_cercato,
            'order': 'newest_first',
            'per_page': 50,
            'page': page
        }
        
        try:
            risposta = session.get(url_base, params=parametri, timeout=10)
            
            if risposta.status_code == 429:
                time.sleep(15)
                continue
                
            if risposta.status_code != 200:
                break
                
            articoli = risposta.json().get('items', [])
            if not articoli:
                break  # Fine dei risultati disponibili su Vinted
                
            for item in articoli:
                item_id = item.get('id')
                
                # Controllo unicità assoluta thread-safe
                with lock_id:
                    if item_id in id_visti_assoluti:
                        continue
                
                if check_articolo_valido(item, brand_cercato, p_max, p_min):
                    articoli_validi_trovati.append(item)
                    if len(articoli_validi_trovati) == 10:
                        break
                        
            page += 1
            time.sleep(1.0) # Protezione rate limit tra le pagine
            
        except Exception as e:
            print(f"Errore pagina ricerca manuale: {e}")
            break

    if not articoli_validi_trovati:
        invia_notifica_telegram(f"❌ Nessun nuovo pezzo idoneo trovato per '{brand_cercato}' nella fascia di prezzo indicata.")
        return

    # --- ORDINAMENTO PER PREZZO CRESCENTE (Dal meno costoso al più costoso) ---
    articoli_validi_trovati.sort(key=lambda x: float(x.get('price', {}).get('amount', '0')))

    # --- INVIO DEI RISULTATI (Fino a un massimo esatto di 10) ---
    for item in articoli_validi_trovati:
        item_id = item.get('id')
        
        # Registrazione definitiva dell'ID per evitare duplicati futuri
        with lock_id:
            id_visti_assoluti.add(item_id)
            
        titolo = item.get('title', 'Nessun titolo')
        prezzo = float(item.get('price', {}).get('amount', '0'))
        link = item.get('url', '')
        taglia_vinted = item.get('size_title', '').upper().strip()
        brand_effettivo = item.get('brand_title', 'Non specificato').upper()
        
        testo_notifica = (
            f"🔥 Brand: {brand_effettivo}\n\n"
            f"👕 Articolo:\n{titolo}\n\n"
            f"📏 Taglia:\n{taglia_vinted}\n\n"
            f"💰 Prezzo:\n{prezzo} €\n\n"
            f"🔗 Link:\n{link}"
        )
        invia_notifica_telegram(testo_notifica)
        time.sleep(0.5)

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
                            # Avvio del thread dedicato per mantenere reattivo il bot
                            threading.Thread(
                                target=esegui_ricerca_manuale, 
                                args=(session, brand_cercato, prezzo_min, prezzo_max), 
                                name=f"Manual-{brand_cercato}-{random.randint(100,999)}"
                            ).start()
                        except ValueError:
                            invia_notifica_telegram("⚠️ Prezzi non validi. Formato: cerca Stussy, 10, 40")
                    else:
                        invia_notifica_telegram("⚠️ Formato richiesto: cerca Brand, Min, Max")
        except Exception:
            time.sleep(5)

def monitora_vinted_background(session, lista_ricerche):
    url_base_sicuro = "https://www.vinted.it/api/v2/catalog/items"
    parole_bannate_reali = ["rotto", "rotta", "rovinato", "rovinata", "bucato", "bucata", "usurato"]

    while True:
        random.shuffle(lista_ricerche)
        
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_massimo = ricerca["prezzo_max"]

            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 20
            }
            
            try:
                risposta = session.get(url_base_sicuro, params=parametri, timeout=7)
                
                if risposta.status_code == 429:
                    time.sleep(30)
                    continue
                    
                if risposta.status_code == 200:
                    articoli = risposta.json().get('items', [])
                    for item in articoli:
                        item_id = item.get('id')
                        
                        with lock_id:
                            if item_id in id_visted_assoluti or item_id in id_visti_assoluti:
                                continue
                            # Verifica filtri rigidi prima di notificare e salvare
                            if not check_articolo_valido(item, parola_chiave, prezzo_massimo):
                                continue
                            
                            titolo = item.get('title', 'Nessun titolo')
                            if any(parola in titolo.lower() for parola in parole_bannate_reali):
                                continue
                                
                            id_visti_assoluti.add(item_id)

                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').upper().strip()
                        brand_rilevato = item.get('brand_title', 'Generico').upper()

                        testo_notifica = (
                            f"🔥 Brand: {brand_rilevato}\n\n"
                            f"👕 Articolo:\n{titolo}\n\n"
                            f"📏 Taglia:\n{taglia_vinted}\n\n"
                            f"💰 Prezzo:\n{prezzo} €\n\n"
                            f"🔗 Link:\n{link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        time.sleep(0.5)
                        
                time.sleep(random.uniform(2.0, 3.5))
            except Exception:
                pass
        time.sleep(2)

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

    invia_notifica_telegram("🚀 Centralina Vinted Professionale Avviata.\n• Filtri Uomo, Categorie e Taglie attivi.\n• Controllo Replica e Unicità ID permanente.")

    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE)).start()
    gestisci_comandi_telegram(session)
