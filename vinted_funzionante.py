import time
import random
import requests
import threading
import sys
import re
import os
from flask import Flask

# ================= CONFIGURAZIONE TELEGRAM =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"  # Il tuo token BotFather
ID_CHAT_TELEGRAM = "387028237"    # Il tuo ID numerico
# ===========================================================

# Set globali persistenti per evitare QUALSIASI doppione
id_visti_assoluti = set()
lock_id = threading.Lock()

# --- MAPPA RESTRITTIVA DELLE CATEGORIE UFFICIALI UOMO VINTED ---
# Solo ed esclusivamente le categorie richieste. Canotte, intimo e accessori non sono inclusi.
CATEGORIE_UOMO_AMMESSE = {
    5,    # Uomo / Scarpe
    79,   # Uomo / Scarpe / Sneakers
    80,   # Uomo / Scarpe / Stivali
    81,   # Uomo / Scarpe / Stringate & Mocassini
    2050, # Uomo / Scarpe / Altre scarpe
    2054, # Uomo / Abbigliamento / Top e t-shirt (T-shirt, Magliette, Polo)
    2056, # Uomo / Abbigliamento / Maglioni e felpe (Felpe con cappuccio, Girocollo, Maglioni)
    2058, # Uomo / Abbigliamento / Cappotti e giacche (Giacche, Cappotti, Piumini)
    2060, # Uomo / Abbigliamento / Pantaloni (Chino, Cargo, Tuta)
    2062, # Uomo / Abbigliamento / Jeans
    2064, # Uomo / Abbigliamento / Pantaloncini e shorts
}

# Inizializzazione Flask per tenere in vita il processo su Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Vinted Online & Active", 200

def avvia_server_web():
    porta = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=porta)

def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": ID_CHAT_TELEGRAM, "text": messaggio, "disable_web_page_preview": False}
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 429:
            retry_after = res.json().get('parameters', {}).get('retry_after', 2)
            time.sleep(retry_after)
            requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRORE TELEGRAM] {e}")

def check_articolo_valido(item, brand_cercato, prezzo_massimo_default, prezzo_minimo_custom=0.0, stats=None):
    if stats is None:
        stats = {"brand": 0, "categoria": 0, "taglia": 0, "prezzo": 0}

    if item.get('is_closed') or item.get('is_sold') or item.get('is_reserved') or item.get('is_hidden'):
        return False

    titolo = item.get('title', '').lower().strip()
    descrizione = item.get('description', '').lower().strip()
    brand_reale = item.get('brand_title', '').lower().strip()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    taglia = item.get('size_title', '').lower().strip()
    catalog_id = item.get('catalog_id')

    # --- 1. FILTRO BRAND ---
    brand_cercato_clean = brand_cercato.lower().strip()
    if brand_cercato_clean == "erd":
        brand_cercato_clean = "enfants riches"

    if brand_reale:
        if brand_cercato_clean not in brand_reale:
            if brand_cercato_clean == "enfants riches" and "erd" in brand_reale:
                pass
            else:
                stats["brand"] += 1
                return False
    else:
        if brand_cercato_clean not in titolo and brand_cercato_clean not in descrizione:
            stats["brand"] += 1
            return False

    # --- 2. FILTRO REPLICA / FAKE ---
    parole_replica = [
        'inspired', 'inspired by', 'replica', 'replica 1:1', 'aaa', 'ua', 
        'fake', 'style', 'tipo', 'stile', 'simile', 'look', 'lookalike', 'inspired style'
    ]
    if any(p in titolo or p in descrizione for p in parole_replica):
        if not any(p in brand_cercato_clean for p in parole_replica):
            stats["brand"] += 1
            return False

    # --- 3. FILTRO CATEGORIE E SESSO (Rigido su catalog_id) ---
    # Blocco immediato canotte e canottiere testuali se sfuggono al catalogo principale
    parole_bannate_categoria = ['canotta', 'canottiera', 'singlet', 'tank top', 'vest']
    if any(p in titolo for p in parole_bannate_categoria):
        stats["categoria"] += 1
        return False

    if catalog_id is not None:
        if catalog_id not in CATEGORIE_UOMO_AMMESSE:
            stats["categoria"] += 1
            return False
    else:
        # Fallback totale sesso e bambini se manca catalog_id
        parole_bannate_sesso = ['woman', 'women', 'female', 'femme', 'donna', 'ladies', 'damen', 'kid', 'kids', 'baby', 'bambin', 'years', 'ans', 'anni']
        if any(p in titolo or p in descrizione for p in parole_bannate_sesso):
            stats["categoria"] += 1
            return False

    # --- 4. FILTRO TAGLIE STRIGENTISSIMO (No taglie enormi/fuori range) ---
    vestiti_ok = {'m', 'l', 'xl'}
    pantaloni_ok = {'33', '34', '36', 'w33', 'w34', 'w36'}
    scarpe_ok = {'42.5', '42 1/2', '42½', '43', '43 1/3', '43⅓'}
    
    token_taglia = set(re.split(r'[\s/(),.-]+', taglia))
    
    # Se contiene taglie giganti non richieste, scarta subito
    if 'xxl' in token_taglia or '3xl' in token_taglia or '4xl' in token_taglia or 'xs' in token_taglia or 's' in token_taglia:
        stats["taglia"] += 1
        return False

    passa_taglia = False
    if any(s in taglia for s in scarpe_ok):
        passa_taglia = True
    elif any(p in token_taglia for p in pantaloni_ok):
        passa_taglia = True
    elif token_taglia.intersection(vestiti_ok):
        passa_taglia = True

    if not passa_taglia:
        stats["taglia"] += 1
        return False

    # --- 5. FILTRO PREZZO ---
    if not (prezzo_minimo_custom <= prezzo <= prezzo_massimo_default):
        stats["prezzo"] += 1
        return False

    return True

def esegui_ricerca_manuale(session, brand_cercato, p_min, p_max):
    url_base = "https://www.vinted.it/api/v2/catalog/items"
    invia_notifica_telegram(f"🔍 [RICERCA] Avvio ricerca per: {brand_cercato.upper()} ({p_min}€ - {p_max}€)...")
    
    debug_stats = {"ricevuti": 0, "brand": 0, "categoria": 0, "taglia": 0, "prezzo": 0, "inviati": 0}
    articoli_validi_trovati = []
    page = 1
    max_pagine_tentativi = 4
    
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
                time.sleep(10)
                continue
                
            if risposta.status_code != 200:
                break
                
            articoli = risposta.json().get('items', [])
            if not articoli:
                break
                
            debug_stats["ricevuti"] += len(articoli)
                
            for item in articoli:
                item_id = item.get('id')
                
                with lock_id:
                    if item_id in id_visti_assoluti:
                        continue
                
                if check_articolo_valido(item, brand_cercato, p_max, p_min, stats=debug_stats):
                    articoli_validi_trovati.append(item)
                    if len(articoli_validi_trovati) == 10:
                        break
                        
            page += 1
            time.sleep(0.5)
            
        except Exception as e:
            break

    debug_stats["inviati"] = len(articoli_validi_trovati)
    report_testo = (
        f"📊 DIAGNOSTICA LIVE ({brand_cercato.upper()}):\n"
        f"• Scaricati totali: {debug_stats['ricevuti']}\n"
        f"• Scartati Brand/Replica: {debug_stats['brand']}\n"
        f"• Scartati Categoria/Filtro Canotte: {debug_stats['categoria']}\n"
        f"• Scartati Taglia (Escluse XS/S/XXL+): {debug_stats['taglia']}\n"
        f"• Scartati Prezzo: {debug_stats['prezzo']}\n"
        f"• Idonei inviati: {debug_stats['inviati']}"
    )
    print(report_testo)

    if not articoli_validi_trovati:
        invia_notifica_telegram(f"❌ Nessun pezzo idoneo trovato.\n\n{report_testo}")
        return

    # Ordinamento finale per prezzo crescente
    articoli_validi_trovati.sort(key=lambda x: float(x.get('price', {}).get('amount', '0')))

    for item in articoli_validi_trovati:
        item_id = item.get('id')
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
        time.sleep(0.3)

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
                            threading.Thread(
                                target=esegui_ricerca_manuale, 
                                args=(session, brand_cercato, prezzo_min, prezzo_max),
                                name=f"ManualSearch-{random.randint(100,999)}"
                            ).start()
                        except ValueError:
                            invia_notifica_telegram("⚠️ Cifre prezzo non valide. Struttura: cerca Stussy, 10, 40")
                    else:
                        invia_notifica_telegram("⚠️ Formato errato. Esempio: cerca Brand, Min, Max")
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
                            if item_id in id_visti_assoluti:
                                continue
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
                        
                time.sleep(random.uniform(2.5, 4.0))
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
        res = session.get("https://www.vinted.it/catalog", timeout=10)
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

    invia_notifica_telegram("🛡️ CENTRALINA STRUTTURATA IMMORTALE ATTIVA!\n• Web Server integrato porta 10000 per Render.\n• Filtro restrittivo anti-canotte abilitato.")

    # Avvio del Web Server in un thread separato per soddisfare Render
    threading.Thread(target=avvia_server_web, daemon=True, name="WebServerThread").start()
    
    # Avvio dei moduli core del Bot
    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE), daemon=True).start()
    gestisci_comandi_telegram(session)
