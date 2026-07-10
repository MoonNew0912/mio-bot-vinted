import time
import random
import requests
import sys

# ================= CONFIGURAZIONE TELEGRAM =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"  # Il tuo token BotFather
ID_CHAT_TELEGRAM = "387028237"    # Il tuo ID numerico
# ===========================================================

def invia_notifica_telegram(messaggio):
    """Invia un messaggio di testo al tuo smartphone tramite Telegram"""
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

def check_articolo_valido(item, parola_chiave, prezzo_massimo_default):
    """Controlla se l'articolo rispetta i filtri di prezzo e anti-spam avanzati"""
    titolo = item.get('title', '').lower()
    descrizione = item.get('description', '').lower()
    brand = item.get('brand_title', '').lower()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    
    # 1. FILTRO PREZZO MINIMO GENERALE
    if prezzo < 3.0:
        return False

    # 2. FILTRO ANTI-ESCA SUI BRAND ALTA MODA
    brand_vuoto = brand in ['', 'senza marca', 'no brand', 'anonyme', 'unknown']
    parole_esca = ['tipo', 'stile', 'style', 'inspired', 'look', 'aesthetic', 'simile', 'lookalike']
    alta_moda_spam = ['rick owens', 'enfants riches', 'erd']
    
    if any(k in brand or k in titolo or k in descrizione for k in alta_moda_spam):
        if brand_vuoto and any(p in titolo or p in descrizione for p in parole_esca):
            return False  

    # 3. CONTROLLO PREZZI MASSIMI DINAMICI PER BRAND E CATEGORIA
    
    # --- CARHARTT ---
    if 'carhartt' in brand or 'carhartt' in titolo or 'carhartt' in parola_chiave.lower():
        if any(p in titolo or p in descrizione for p in ['pant', 'jeans', 'cargo', 'pantaloni', 'pantalone']):
            return prezzo <= 40.0
        elif any(m in titolo or m in descrizione for m in ['t-shirt', 'maglietta', 'tee', 'maglia']):
            return prezzo <= 15.0
        else:
            return prezzo <= 30.0

    # --- NIKE, JORDAN, ADIDAS (Scarpe e Abbigliamento) ---
    modelli_scarpe = ['jordan', 'dunk', 'air force', 'af1', 'campus', 'gazelle', 'samba', 'yeezy', 'scarpe', 'sneakers', 'jordan 5', 'jordan 11', 'jordan 12', 'jordan 13']
    brand_sportivi = ['nike', 'jordan', 'adidas']
    
    if any(b in brand or b in titolo or b in parola_chiave.lower() for b in brand_sportivi) or any(m in titolo or m in descrizione for m in modelli_scarpe):
        if any(m in titolo or m in descrizione for m in modelli_scarpe):
            return prezzo <= 65.0  
        elif any(m in titolo or m in descrizione for m in ['t-shirt', 'maglietta', 'tee']):
            return prezzo <= 15.0
        else:
            return prezzo <= 35.0

    # --- RICK OWENS / ENFANTS RICHES DÉPRIMÉS (ERD) ---
    if any(k in brand or k in titolo or k in descrizione or k in parola_chiave.lower() for k in alta_moda_spam):
        if any(p in titolo or p in descrizione for p in ['scarpe', 'stivali', 'boots', 'sneakers', 'ramones', 'geobasket']):
            return prezzo <= 80.0
        else:
            return prezzo <= 50.0

    return prezzo <= prezzo_massimo_default


def monitora_vinted_istantaneo(lista_ricerche, secondi_attesa_giro=10):
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
        'Accept': 'application/json, text/plain, */*',
        'Connection': 'keep-alive',
        'Referer': 'https://www.vinted.it/catalog'
    }
    session.headers.update(headers)
    
    print("Inizializzazione connessione...")
    try:
        session.get("https://www.vinted.it/catalog", timeout=10)
        print("Connessione stabilita con successo.\n")
        invia_notifica_telegram("🔒 BOT BLINDATO! Attivati i filtri nativi Vinted: SOLO UOMO e SOLO TAGLIE M/L/XL, 42.5/43, W33/34/36.")
    except Exception as e:
        print(f"Errore connessione iniziale: {e}")
        return

    url_base_sicuro = "https://www.vinted.it"
    percorso_api = "/api/v2/catalog/items"
    id_annunci_visti = set()
    
    parole_bannate_reali = ["rotto", "rotta", "rovinato", "rovinata", "bucato", "bucata", "usurato"]

    print(f"⚡ BOT AVVIATO SU {len(lista_ricerche)} RICERCHE UOMO SELEZIONATE.")
    print("="*60)

    while True:
        random.shuffle(lista_ricerche)
        
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_massimo = ricerca["prezzo_max"]

            # PARAMETRI NATIVI VINTED: Forza il server a risponderci solo con roba da uomo e taglie specifiche
            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 20,
                'status_ids[]': [1, 2, 3, 6],
                # 5 == Abbigliamento Uomo, 123 == Scarpe Uomo
                'catalog_ids[]': [5, 123],
                # ID Taglie Vinted ufficiali: 207=M, 208=L, 209=XL, 778=42.5, 779=43, 363=W33, 364=W34, 366=W36
                'size_ids[]': [207, 208, 209, 778, 779, 363, 364, 366]
            }
            
            try:
                risposta = session.get(url_base_sicuro + percorso_api, params=parametri, timeout=7)
                
                if risposta.status_code == 200:
                    articoli = risposta.json().get('items', [])
                    print(f"[DEBUG] '{parola_chiave}' -> Trovati {len(articoli)} articoli filtrati uomo.")
                    
                    for item in articoli:
                        item_id = item.get('id')
                        if item_id in id_annunci_visti:
                            continue
                            
                        titolo = item.get('title', 'Nessun titolo')
                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').lower().strip()

                        # 1. Filtro Prezzo Avanzato
                        if not check_articolo_valido(item, parola_chiave, prezzo_massimo):
                            id_annunci_visti.add(item_id)
                            continue

                        # 2. Controllo Parole Bandite residue
                        if any(parola in titolo.lower() for parola in parole_bannate_reali):
                            id_annunci_visti.add(item_id)
                            continue

                        # === COSTRUZIONE NOTIFICA TELEGRAM ===
                        testo_notifica = (
                            f"🎯 AFFARE UOMO TROVATO!\n"
                            f"🔥 Brand Cercato: {parola_chiave.upper()}\n"
                            f"👕 Articolo: {titolo}\n"
                            f"📏 Taglia: {taglia_vinted.upper()}\n"
                            f"💰 Prezzo: {prezzo} €\n\n"
                            f"🔗 LINK:\n{link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        
                        id_annunci_visti.add(item_id)
                        continue  
                        
                elif risposta.status_code == 429:
                    print("\n[!] Rate limit (429)! Attesa 60 secondi...")
                    time.sleep(60)
                    
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass
            
        print(f"--- Giro completato. Pausa... ---")
        time.sleep(secondi_attesa_giro)

# LISTA DELLE TUE RICERCHE (Prezzi tarati per taglie M/L/XL/42.5/43/W33-34-36)
MIE_RICERCHE = [
    {"nome": "Stussy", "prezzo_max": 40.0},
    {"nome": "Supreme", "prezzo_max": 40.0},
    {"nome": "Palace", "prezzo_max": 40.0},
    {"nome": "Burberry", "prezzo_max": 40.0},
    {"nome": "Prada", "prezzo_max": 40.0},
    {"nome": "Corteiz", "prezzo_max": 40.0},
    {"nome": "Fear of God Essentials", "prezzo_max": 40.0},
    {"nome": "Denim Tears", "prezzo_max": 40.0},
    {"nome": "Cactus Plant", "prezzo_max": 40.0},
    {"nome": "Off-White", "prezzo_max": 40.0},
    {"nome": "Raf Simons", "prezzo_max": 40.0},
    {"nome": "Rick Owens", "prezzo_max": 80.0},
    {"nome": "Enfants Riches Déprimés", "prezzo_max": 80.0},
    {"nome": "ERD", "prezzo_max": 40.0},
    {"nome": "Helmut Lang", "prezzo_max": 40.0},
    {"nome": "Margiela", "prezzo_max": 40.0},
    {"nome": "Yohji Yamamoto", "prezzo_max": 40.0},
    {"nome": "Comme des Garçons", "prezzo_max": 40.0},
    {"nome": "Undercover", "prezzo_max": 40.0},
    {"nome": "CP Company", "prezzo_max": 40.0},
    {"nome": "Stone Island", "prezzo_max": 40.0},
    {"nome": "Carhartt", "prezzo_max": 40.0},
    {"nome": "Nike", "prezzo_max": 65.0},
    {"nome": "Jordan", "prezzo_max": 65.0},
    {"nome": "Jordan 5", "prezzo_max": 65.0},
    {"nome": "Jordan 11", "prezzo_max": 65.0},
    {"nome": "Jordan 12", "prezzo_max": 65.0},
    {"nome": "Jordan 13", "prezzo_max": 65.0},
    {"nome": "Adidas", "prezzo_max": 65.0},
    {"nome": "Chrome Hearts", "prezzo_max": 40.0},
    {"nome": "Hellstar", "prezzo_max": 40.0},
    {"nome": "Sp5der", "prezzo_max": 40.0},
    {"nome": "Syna World", "prezzo_max": 40.0},
    {"nome": "Trapstar", "prezzo_max": 40.0},
    {"nome": "Sicko Born", "prezzo_max": 40.0},
    {"nome": "Gallery Dept", "prezzo_max": 40.0},
    {"nome": "RRR123", "prezzo_max": 40.0},
    {"nome": "Balenciaga", "prezzo_max": 40.0},
    {"nome": "Vetements", "prezzo_max": 40.0},
    {"nome": "Evisu", "prezzo_max": 65.0},
    {"nome": "True Religion", "prezzo_max": 30.0},
    {"nome": "Vicinity", "prezzo_max": 35.0},
    {"nome": "Acne Studios", "prezzo_max": 65.0},
    {"nome": "derschutze", "prezzo_max": 35.0},
    {"nome": "Cold Culture", "prezzo_max": 35.0}
]

monitora_vinted_istantaneo(MIE_RICERCHE, secondi_attesa_giro=10)
