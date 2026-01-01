import sqlite3
import time
import random
import re
from playwright.sync_api import sync_playwright

# --- CONFIGURAÇÕES ---
ROTAS = [
    {'origem': 'GYN', 'destino': 'ATL', 'ida': '2026-06-15', 'volta': '2026-06-22'},
    {'origem': 'BSB', 'destino': 'ATL', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'GYN', 'destino': 'CHC', 'ida': '2026-06-15', 'volta': '2026-06-22'},
    {'origem': 'BSB', 'destino': 'CHC', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'GYN', 'destino': 'MSY', 'ida': '2026-06-15', 'volta': '2026-06-22'},
    {'origem': 'BSB', 'destino': 'MSY', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'CHA', 'destino': 'ATL', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'CHC', 'destino': 'MSY', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'ATL', 'destino': 'CHC', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'ATL', 'destino': 'MSY', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'MSY', 'destino': 'CHC', 'ida': '2026-06-10', 'volta': '2026-06-20'},
    {'origem': 'MSY', 'destino': 'ATL', 'ida': '2026-06-10', 'volta': '2026-06-20'},
]
DB_NAME = "voos_local.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT, destino TEXT, data_ida TEXT, data_volta TEXT,
            companhia TEXT, preco_bruto TEXT, preco_numerico REAL,
            hora_saida TEXT, hora_chegada TEXT, duracao TEXT, escalas TEXT,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def salvar_voo(dados):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        limpo = re.sub(r'[^\d]', '', dados['preco'])
        preco_num = float(limpo)
    except: preco_num = 0.0
    
    cursor.execute('''
        INSERT INTO voos (origem, destino, data_ida, data_volta, companhia, preco_bruto, preco_numerico, 
                          hora_saida, hora_chegada, duracao, escalas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dados['origem'], dados['destino'], dados['ida'], dados['volta'], 
          dados['companhia'], dados['preco'], preco_num, 
          dados['saida'], dados['chegada'], dados['duracao'], dados['escalas']))
    conn.commit()
    conn.close()

def extrair_dados_kayak(page, rota):
    print(f"   -> Extraindo detalhes para {rota['origem']}...")
    
    try:
        page.wait_for_selector('.nrc6', timeout=30000)
    except:
        print("   [!] Erro: Cards de voo não carregaram.")
        return

    # Scroll para garantir renderização
    page.mouse.wheel(0, 1000)
    time.sleep(2)

    cards = page.query_selector_all('.nrc6')
    
    count = 0
    for card in cards:
        try:
            texto = card.inner_text()
            if "R$" not in texto: continue

            # 1. Preço
            preco_match = re.search(r'R\$\s?([\d\.]+)', texto)
            preco_final = preco_match.group(0) if preco_match else "N/A"

            # 2. Horários (Saída e Chegada) - Geralmente formato 00:00 – 00:00
            horarios = re.findall(r'(\d{1,2}:\d{2})', texto)
            saida = horarios[0] if len(horarios) >= 1 else "N/A"
            chegada = horarios[1] if len(horarios) >= 2 else "N/A"

            # 3. Duração (Ex: 10h 15m)
            duracao_match = re.search(r'(\d{1,2}h\s\d{1,2}m)', texto)
            duracao = duracao_match.group(1) if duracao_match else "N/A"

            # 4. Escalas (Ex: direto, 1 escala, 2 escalas)
            escalas = "direto"
            if "direto" not in texto.lower():
                escala_match = re.search(r'(\d\sescala[s]?)', texto.lower())
                escalas = escala_match.group(1) if escala_match else "Com escalas"

            # 5. Companhia (Busca por elementos de imagem/texto específicos)
            cia_element = card.query_selector('.J0g6-operator-text')
            companhia = cia_element.inner_text() if cia_element else "Múltiplas"

            salvar_voo({
                **rota, 
                'companhia': companhia, 
                'preco': preco_final,
                'saida': saida,
                'chegada': chegada,
                'duracao': duracao,
                'escalas': escalas
            })
            count += 1
            if count >= 8: break 
        except Exception as e:
            continue
            
    print(f"   [SUCESSO] {count} voos detalhados salvos.")

def rodar_crawler():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Mantenha False para ver o processo
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for rota in ROTAS:
            url = f"https://www.kayak.com.br/flights/{rota['origem']}-{rota['destino']}/{rota['ida']}/{rota['volta']}?sort=price_a"
            print(f"\n--- Rota: {rota['origem']} -> {rota['destino']} ---")
            try:
                page.goto(url, wait_until="domcontentloaded")
                time.sleep(20) # Tempo para bypass de segurança
                extrair_dados_kayak(page, rota)
            except Exception as e:
                print(f"   [ERRO] {e}")
            
            time.sleep(random.randint(10, 15))

        browser.close()

if __name__ == "__main__":
    init_db()
    rodar_crawler()