import time
import random
import requests
import sys

# ================= CONFIGURAZIONE TELEGRAM =================
TOKEN_TELEGRAM = "8948272794:AAGGc6pEGnl23ovQK7Ct_GpeYC_Tm0QPL2w"  # Incolla qui il token preso da BotFather
ID_CHAT_TELEGRAM = "387028237"    # Incolla qui il tuo ID numerico preso da userinfobot
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
        invia_notifica_telegram("🚀 Bot Vinted avviato! I link funzionano anche sul PC.")
    except Exception as e:
        print(f"Errore connessione iniziale: {e}")
        return

    url_base_sicuro = "https://www.vinted.it"
    percorso_api = "/api/v2/catalog/items"
    id_annunci_visti = set()
    
    parole_bannate_reali = ["rotto", "rotta", "rovinato", "rovinata", "bucato", "bucata", "usurato"]

    print(f"⚡ BOT AVVIATO SU {len(lista_ricerche)} RICERCHE.")
    print("="*60)

    while True:
        random.shuffle(lista_ricerche)
        
        for ricerca in lista_ricerche:
            parola_chiave = ricerca["nome"]
            prezzo_massimo = ricerca["prezzo_max"]
            taglie_accettate = ricerca["taglie"]

            parametri = {
                'search_text': parola_chiave,
                'order': 'newest_first',
                'per_page': 20,
                'status_ids[]': [1, 2, 3, 6]
            }
            
            try:
                risposta = session.get(url_base_sicuro + percorso_api, params=parametri, timeout=7)
                
                if risposta.status_code == 200:
                    articoli = risposta.json().get('items', [])
                    print(f"[DEBUG] '{parola_chiave}' -> Trovati {len(articoli)} articoli recenti.")
                    
                    for item in articoli:
                        item_id = item.get('id')
                        if item_id in id_annunci_visti:
                            continue
                            
                        titolo = item.get('title', 'Nessun titolo')
                        prezzo = float(item.get('price', {}).get('amount', '0'))
                        link = item.get('url', '')
                        taglia_vinted = item.get('size_title', '').lower().strip()

                        # 1. Controllo Prezzo Max
                        if prezzo > prezzo_massimo:
                            continue
                            
                        # 2. Controllo Taglie
                        taglia_valida = False
                        for t in taglie_accettate:
                            t_clean = str(t).lower().strip()
                            if t_clean in taglia_vinted or t_clean in titolo.lower():
                                if t_clean in ["m", "l"] and ("xl" in taglia_vinted or "xxl" in taglia_vinted):
                                    continue
                                taglia_valida = True
                                break
                        if not taglia_valida:
                            continue

                        # 3. Controllo Parole Bandite
                        if any(parola in titolo.lower() for parola in parole_bannate_reali):
                            continue

                        # === COSTRUZIONE NOTIFICA TELEGRAM ===
                        testo_notifica = (
                            f"🎯 AFFARE TROVATO!\n"
                            f"🔥 Brand: {parola_chiave.upper()}\n"
                            f"👕 Articolo: {titolo}\n"
                            f"📏 Taglia: {taglia_vinted.upper()}\n"
                            f"💰 Prezzo: {prezzo} €\n\n"
                            f"🔗 LINK:\n{link}"
                        )
                        invia_notifica_telegram(testo_notifica)
                        
                        # === STAMPA SUL COMPUTER (PROMPT) ===
                        # Stampiamo il link pulito isolato in modo che Windows lo riconosca come cliccabile
                        print("\n" + "="*50)
                        print(f"🌟 TROVATO: {parola_chiave.upper()} - {titolo}")
                        print(f"💰 Prezzo: {prezzo}€ | Taglia: {taglia_vinted.upper()}")
                        print(f"🔗 LINK PER COMPUTER:")
                        print(f"{link}")  # Riga singola senza fronzoli, ottimale per il click sul terminale
                        print("="*50 + "\n")
                        
                        id_annunci_visti.add(item_id)
                        break
                        
                elif risposta.status_code == 429:
                    print("\n[!] Rate limit (429)! Attesa 60 secondi...")
                    time.sleep(60)
                    
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass
            
        print(f"--- Giro completato. Pausa... ---")
        time.sleep(secondi_attesa_giro)

# LISTA COMPLETA DEI TUOI BRAND
MIE_RICERCHE = [
    {"nome": "Stussy", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Stussy", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Supreme", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Supreme", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Palace", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Palace", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Burberry", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Burberry", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Prada", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Prada", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Corteiz", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Corteiz", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Essentials", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Essentials", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Denim Tears", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Denim Tears", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Cactus Plant", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Cactus Plant", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Off-White", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Off-White", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Raf Simons", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Raf Simons", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Rick Owens", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Rick Owens", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Helmut Lang", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Helmut Lang", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Margiela", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Margiela", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Yohji Yamamoto", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Yohji Yamamoto", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Comme des Garçons", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Comme des Garçons", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Undercover", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Undercover", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "CP Company", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "CP Company", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Stone Island", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Stone Island", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Carhartt", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Carhartt", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Nike Vintage", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Nike Vintage", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Adidas Originals", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Adidas Originals", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Chrome Hearts", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Chrome Hearts", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Hellstar", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Hellstar", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Sp5der", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Sp5der", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Syna World", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Syna World", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Trapstar", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Trapstar", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Sicko Born", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Sicko Born", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Gallery Dept", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Gallery Dept", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "RRR123", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "RRR123", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Balenciaga", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Balenciaga", "prezzo_max": 40.0, "taglie": ["43"]},
    {"nome": "Vetements", "prezzo_max": 20.0, "taglie": ["M", "L"]},
    {"nome": "Vetements", "prezzo_max": 40.0, "taglie": ["43"]}
]

monitora_vinted_istantaneo(MIE_RICERCHE, secondi_attesa_giro=10)