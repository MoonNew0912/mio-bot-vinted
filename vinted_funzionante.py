import time
import random
import requests
import threading
import sys
import re
import os
from flask import Flask

# ================= CONFIGURAZIONE TELEGRAM =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"
ID_CHAT_TELEGRAM = "387028237"
# ===========================================================

id_visti_assoluti = set()
lock_id = threading.Lock()

# Categorie Vinted Uomo ammesse
CATEGORIE_UOMO_AMMESSE = {5, 79, 80, 81, 2050, 2054, 2056, 2058, 2060, 2062, 2064}

# ID Categorie specifiche per differenziare i prezzi massimi
CAT_PANTALONI = {80, 81, 2058, 2060}  # Jeans, pantaloni, shorts, ecc.
CAT_SCARPE = {5}                     # Scarpe uomo
# Le altre (felpe, t-shirt, giacche) verranno considerate "parte superiore" o gestite di conseguenza

app = Flask(__name__)

@app.route('/')
@app.route('/healthz')
def home():
    return "Bot Vinted Online & Active", 200

def avvia_server_web():
    porta = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=porta, debug=False, use_reloader=False)

def invia_notifica_telegram(messaggio):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": ID_CHAT_TELEGRAM, "text": messaggio, "disable_web_page_preview": False}
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code == 429:
            retry_after = res.json().get('parameters', {}).get('retry_after', 2)
            time.sleep(retry_after)
            requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

def check_articolo_valido(item, brand_cercato, prezzo_minimo_custom=0.0, stats=None):
    if stats is None:
        stats = {"brand": 0, "categoria": 0, "taglia": 0, "prezzo": 0, "vecchio": 0}

    if item.get('is_closed') or item.get('is_sold') or item.get('is_reserved') or item.get('is_hidden'):
        return False

    # --- FILTRO ANTICHITÀ (Solo roba fresca di minuti) ---
    orario_upload = item.get('photo', {}).get('high_resolution', {}).get('timestamp')
    if orario_upload:
        tempo_corrente = int(time.time())
        if (tempo_corrente - orario_upload) > 1200: # 20 minuti
            stats["vecchio"] = stats.get("vecchio", 0) + 1
            return False

    titolo = item.get('title', '').lower().strip()
    descrizione = item.get('description', '').lower().strip()
    brand_reale = item.get('brand_title', '').lower().strip()
    prezzo = float(item.get('price', {}).get('amount', '0'))
    taglia = item.get('size_title', '').lower().strip()
    catalog_id = item.get('catalog_id')

    # --- FILTRO BRAND ---
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

    # --- FILTRO CANOTTE / FEMMINILE ---
    parole_bannate_categoria = ['canotta', 'canottiera', 'singlet', 'tank top', 'vest']
    if any(p in titolo for p in parole_bannate_categoria):
        stats["categoria"] += 1
        return False

    if catalog_id is not None:
        if catalog_id not in CATEGORIE_UOMO_AMMESSE:
            stats["categoria"] += 1
            return False
    else:
        parole_bannate_sesso = ['woman', 'women', 'female', 'femme', 'donna', 'ladies', 'damen', 'kid', 'kids', 'baby', 'bambin', 'years', 'ans', 'anni']
        if any(p in titolo or p in descrizione for p in parole_bannate_sesso):
            stats["categoria"] += 1
            return False

    # --- FILTRO TAGLIE STRINGENTISSIMO ---
    vestiti_ok = {'m', 'l', 'xl'}
    pantaloni_ok = {'33', '34', '36', 'w33', 'w34', 'w36'}
    scarpe_ok = {'42.5', '42 1/2', '42½', '43', '43 1/3', '43⅓'}
    
    token_taglia = set(re.split(r'[\s/(),.-]+', taglia))
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

    # --- DINAMICA DI FILTRO PREZZI INTELLIGENTE ---
    prezzo_max_calcolato = 50.0  # Default di sicurezza per brand commerciali generali
    
    brand_archivio_lusso = ["rick owens", "enfants riches", "erd", "prada", "raf simons", "margiela", "chrome hearts"]
    brand_commerciali = ["nike", "jordan", "adidas", "carhartt"]

    # 1. Se è un brand d'archivio/nicchia alto, estendiamo la tolleranza fino a 80€
    if any(bl in brand_reale or bl in brand_cercato_clean for bl in brand_archivio_lusso):
        prezzo_max_calcolato = 80.0
    # 2. Se fa parte dei brand commerciali espliciti indicati, il tetto è 50€
    elif any(bc in brand_reale or bc in brand_cercato_clean for bc in brand_commerciali):
        prezzo_max_calcolato = 50.0
    # 3. Altrimenti, applichiamo il filtro rigido per categoria merceologica richiesto
    else:
        if catalog_id in CAT_SCARPE:
            prezzo_max_calcolato = 80.0
        elif catalog_id in CAT_PANTALONI:
            prezzo_max_calcolato = 40.0
        else:
            # T-shirt, felpe, knitwear, e tutta la parte superiore
            prezzo_max_calcolato = 20.0

    if not (prezzo_minimo_custom <= prezzo <= prezzo_max_calcolato):
        stats["prezzo"] += 1
        return False

    return True

def esegui_ricerca_manuale(session, brand_cercato, p_min, p_max):
    url_base = "https://www.vinted.it/api/v2/catalog/items"
    invia_notifica_telegram(f"🔍 [RICERCA] Estrazione articoli REAL-TIME per: {brand_cercato.upper()}...")
    
    debug_stats = {"ricevuti": 0, "brand": 0, "categoria": 0, "taglia": 0, "prezzo": 0, "vecchio": 0, "inviati": 0}
    articoli_validi_trovati = []
    
    parametri = {
        'search_text': brand_cercato,
        'order': 'newest_first',
        'per_page': 30,
        'page': 1
    }
    
    try:
        risposta = session.get(url_base, params=parametri, timeout=10)
        if risposta.status_code == 200:
            articoli = risposta.json().get('items', [])
            debug_stats["ricevuti"] = len(articoli)
            
            for item in articoli:
                item_id = item.get('id')
                with lock_id:
                    if item_id in id_visti_assoluti:
                        continue
                
                # Nella ricerca manuale forzata manteniamo flessibilità
                if check_articolo_valido(item, brand_cercato, p_min, stats=debug_stats):
                    # Sovrascriviamo il limite calcolato solo se l'utente ha inserito un p_max custom da tastiera
                    prezzo = float(item.get('price', {}).get('amount', '0'))
                    if prezzo <= p_max:
                        articoli_validi_trovati.append(item)
                        if len(articoli_validi_trovati) == 5:
                            break
    except Exception:
        pass

    debug_stats["inviati"] = len(articoli_validi_trovati)
    report_testo = (
        f"📊 REPORT RAPIDO ({brand_cercato.upper()}):\n"
        f"• Esaminati nel feed: {debug_stats['ricevuti']}\n"
        f"• Idonei Novità Inviati: {debug_stats['inviati']}"
    )

    if not articoli_validi_trovati:
        invia_notifica_telegram(f"❌ Nessun articolo recente idoneo trovato nei parametri di budget inseriti.\n\n{report_testo}")
        return

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
            f"✨ NUOVO INSERIMENTO FILTRATO ✨\n"
            f"🔥 Brand: {brand_effettivo}\n"
            f"👕 Articolo: {titolo}\n"
            f"📏 Taglia: {taglia_vinted}\n"
            f"💰 Prezzo: {prezzo} €\n"
            f"🔗 Link: {link}"
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
            r = requests.get(url_updates, params={'offset': last_update_id, 'timeout': 10}, timeout=15).json()
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
                                daemon=True
                            ).start()
                        except ValueError:
                            invia_notifica_telegram("⚠️ Prezzi non validi.")
                    else:
                        invia_notifica_telegram("⚠️ Usa: cerca Brand, Min, Max")
        except Exception:
            time.sleep(3)

def monitora_vinted_background(session, lista_ricerche):
    while True:
        random.shuffle(lista_ricerche)
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]

            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 20
            }
            
            try:
                risposta = session.get("https://www.vinted.it/api/v2/catalog/items", params=parametri, timeout=7)
                if risposta.status_code == 200:
                    articoli = risposta.json().get('items', [])
                    for item in articoli:
                        item_id = item.get('id')
                        
                        with lock_id:
                            if item_id in id_visti_assoluti:
                                continue
                            if not check_articolo_valido(item, parola_chiave):
                                continue
                            id_visti_assoluti.add(item_id)

                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').upper().strip()
                        brand_rilevato = item.get('brand_title', 'Generico').upper()
                        titolo = item.get('title', 'Nessun titolo')

                        testo_notifica = (
                            f"⚡️ ULTIMISSIMO ARRIVO VARIABILE ⚡️\n"
                            f"🔥 Brand: {brand_rilevato}\n"
                            f"👕 Articolo: {titolo}\n"
                            f"📏 Taglia: {taglia_vinted}\n"
                            f"💰 Prezzo: {prezzo} €\n"
                            f"🔗 Link: {link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        time.sleep(0.5)
                time.sleep(random.uniform(3.0, 5.0))
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
        pass

    # Lista delle ricerche attive con budget intelligenti integrati direttamente nel filtro
    MIE_RICERCHE = [
        {"nome": "Stussy"}, {"nome": "Supreme"}, {"nome": "Palace"}, {"nome": "Burberry"},
        {"nome": "Prada"}, {"nome": "Corteiz"}, {"nome": "Fear of God Essentials"}, 
        {"nome": "Denim Tears"}, {"nome": "Cactus Plant"}, {"nome": "Off-White"},
        {"nome": "Raf Simons"}, {"nome": "Rick Owens"}, {"nome": "Enfants Riches Déprimés"}, 
        {"nome": "ERD"}, {"nome": "Helmut Lang"}, {"nome": "Margiela"}, {"nome": "Yohji Yamamoto"}, 
        {"nome": "Comme des Garçons"}, {"nome": "Undercover"}, {"nome": "CP Company"},
        {"nome": "Stone Island"}, {"nome": "Carhartt"}, {"nome": "Nike"}, {"nome": "Jordan"},
        {"nome": "Adidas"}, {"nome": "Chrome Hearts"}
    ]

    threading.Thread(target=avvia_server_web, name="RenderFlaskServer", daemon=True).start()
    threading.Thread(target=monitora_vinted_background, args=(session, MIE_RICERCHE), name="MonitorVintedBackground", daemon=True).start()
    
    invia_notifica_telegram("🛡️ CENTRALINA INTELLIGENTE ATTIVA!\n• Filtro Categoria Abbigliamento Attivo (Sup: 20€ / Pant: 40€ / Scarpe: 80€).\n• Eccezione Brand di Lusso/Nicchia fino a 80€.\n• Brand commerciali limitati a 50€.")

    gestisci_comandi_telegram(session)
