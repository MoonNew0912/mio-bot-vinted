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
    """Controlla se l'articolo rispetta i filtri con LOGICA WHITELIST (Solo quello che vuoi)"""
    titolo = item.get('title', '').lower()
    descrizione = item.get('description', '').lower()
    brand = item.get('brand_title', '').lower()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    
    # Estraiamo la taglia e puliamola da spazi extra
    taglia_originale = item.get('size_title', '')
    taglia = taglia_originale.lower().strip()

    # ================= FILTRO RIGIDO WHITELIST TAGLIE =================
    # Definiamo le uniche e sole taglie accettate per te
    taglie_ammesse_vestiti = ['m', 'l', 'xl', 'l/xl']
    taglie_ammesse_pantaloni = ['33', '34', '36', 'w33', 'w34', 'w36']
    taglie_ammesse_scarpe = ['42.5', '42 1/2', '43', '43 1/3']
    
    tutte_le_taglie_ok = taglie_ammesse_vestiti + taglie_ammesse_pantaloni + taglie_ammesse_scarpe

    # Se la taglia dell'articolo NON è nella tua whitelist, eliminalo subito
    if taglia not in tutte_le_taglie_ok:
        # Controllo di sicurezza per taglie scritte come "42.5 eu" o "m / 38"
        if not any(t_ok in taglia for t_ok in tutte_le_taglie_ok):
            return False
        # Se contiene una taglia ammessa ma contiene ANCHE una taglia vietata (es. "S/M" o "39"), blocca
        if any(vietata in taglia for vietata in ['xs', 's', '35', '36', '37', '38', '39', '40', '41']) and not ('42.5' in taglia or '43' in taglia):
            return False

    # ================= ANTI-SPAM DONNA / GIOCATTOLI =================
    # Se nel titolo o nella descrizione ci sono parole chiave da donna o infantili, blocca
    parole_bannate_categoria = [
        'donna', 'woman', 'femme', 'giocattolo', 'gioco', 'toy', 'joc', 'juguete', 
        'bambino', 'bambina', 'neonata', 'neonato', 'kid', 'kids', 'baby'
    ]
    if any(p in titolo or p in descrizione for p in parole_bannate_categoria):
        # Eccezione se specifica chiaramente uomo nel titolo per evitare falsi positivi
        if 'uomo' not in titolo and 'men' not in titolo:
            return False

    # ================= FILTRI PREZZO E QUALITÀ =================
    if prezzo < 3.0:
        return False

    # Filtro anti-esca (oggetti "tipo" o "stile" brand famosi)
    brand_vuoto = brand in ['', 'senza marca', 'no brand', 'anonyme', 'unknown']
    parole_esca = ['tipo', 'stile', 'style', 'inspired', 'look', 'aesthetic', 'simile', 'lookalike']
    alta_moda_spam = ['rick owens', 'enfants riches', 'erd']
    
    if any(k in brand or k in titolo or k in descrizione for k in alta_moda_spam):
        if brand_vuoto and any(p in titolo or p in descrizione for p in parole_esca):
            return False  

    # Controllo tetti massimi di budget
    if 'carhartt' in brand or 'carhartt' in titolo or 'carhartt' in parola_chiave.lower():
        if any(p in titolo or p in descrizione for p in ['pant', 'jeans', 'cargo', 'pantaloni', 'pantalone']):
            return prezzo <= 40.0
        elif any(m in titolo or m in descrizione for m in ['t-shirt', 'maglietta', 'tee', 'maglia']):
            return prezzo <= 15.0
        else:
            return prezzo <= 30.0

    modelli_scarpe = ['jordan', 'dunk', 'air force', 'af1', 'campus', 'gazelle', 'samba', 'yeezy', 'scarpe', 'sneakers', 'jordan 5', 'jordan 11', 'jordan 12', 'jordan 13']
    brand_sportivi = ['nike', 'jordan', 'adidas']
    
    if any(b in brand or b in titolo or b in parola_chiave.lower() for b in brand_sportivi) or any(m in titolo or m in descrizione for m in modelli_scarpe):
        if any(m in titolo or m in descrizione for m in modelli_scarpe):
            return prezzo <= 65.0  
        elif any(m in titolo or m in descrizione for m in ['t-shirt', 'maglietta', 'tee']):
            return prezzo <= 15.0
        else:
            return prezzo <= 35.0

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
    except Exception as e:
        print(f"Errore connessione iniziale: {e}")
        return

    url_base_sicuro = "https://www.vinted.it"
    percorso_api = "/api/v2/catalog/items"
    id_annunci_visti = set()
    
    parole_bannate_reali = ["rotto", "rotta", "rovinato", "rovinata", "bucato", "bucata", "usurato"]

    # --- FASE 1: PRIMO GIRO DI PRE-CARICAMENTO ---
    print("📥 Fase di riscaldamento: memorizzo gli annunci attuali per evitare duplicati...")
    for ricerca in lista_ricerche:
        parametri = {
            'search_text': ricerca["nome"],
            'order': 'newest_first',
            'per_page': 30,
            'catalog_ids[]': [5, 123],
            'size_ids[]': [207, 208, 209, 778, 779, 363, 364, 366]
        }
        try:
            risposta = session.get(url_base_sicuro + percorso_api, params=parametri, timeout=7)
            if risposta.status_code == 200:
                for item in risposta.json().get('items', []):
                    id_annunci_visti.add(item.get('id'))
        except Exception:
            pass
        time.sleep(1.0)
    
    print(f"✅ Riscaldamento completato. Memorizzati {len(id_annunci_visti)} articoli già online.")
    invia_notifica_telegram("🛡️ BOT BLINDATO IN MODALITÀ COESIONE! Attive solo taglie M/L/XL, Pantaloni 33/34/36, Scarpe 42.5/43. Caccia aperta.")
    print("="*60)

    # --- FASE 2: MONITORAGGIO REALE IN DIRETTA ---
    while True:
        random.shuffle(lista_ricerche)
        
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_massimo = ricerca["prezzo_max"]

            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 10,
                'status_ids[]': [1, 2, 3, 6],
                'catalog_ids[]': [5, 123],
                'size_ids[]': [207, 208, 209, 778, 779, 363, 364, 366]
            }
            
            try:
                risposta = session.get(url_base_sicuro + percorso_api, params=parametri, timeout=7)
                
                if risposta.status_code == 200:
                    articoli = risposta.json().get('items', [])
                    
                    for item in articoli:
                        item_id = item.get('id')
                        
                        if item_id in id_annunci_visti:
                            continue
                            
                        titolo = item.get('title', 'Nessun titolo')
                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').lower().strip()

                        if not check_articolo_valido(item, parola_chiave, prezzo_massimo):
                            id_annunci_visti.add(item_id)
                            continue

                        if any(parola in titolo.lower() for parola in parole_bannate_reali):
                            id_annunci_visti.add(item_id)
                            continue

                        # === INVIO NOTIFICA IPER-FILTRATA ===
                        testo_notifica = (
                            f"⚡ RECENTISSIMO ABBIGLIAMENTO UOMO!\n"
                            f"🔥 Brand: {parola_chiave.upper()}\n"
                            f"👕 Articolo: {titolo}\n"
                            f"📏 Taglia: {taglia_vinted.upper()}\n"
                            f"💰 Prezzo: {prezzo} €\n\n"
                            f"🔗 LINK DIRETTO:\n{link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        
                        id_annunci_visti.add(item_id)
                        
                elif risposta.status_code == 429:
                    time.sleep(60)
                    
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass
            
        time.sleep(secondi_attesa_giro)

# LISTA COMPLETA
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

monitora_vinted_istantaneo(MIE_RICERCHE, secondi_attesa_giro=10)
