import sqlite3
import time
import random
import re
from playwright.sync_api import sync_playwright

# --- CONFIGURAÇÕES ---
DB_NAME = "voos_local.db"

# Lista simplificada usando apenas códigos IATA
ALUGUEIS_CARRO = [
    {'retirada': 'ATL', 'entrega': 'MSY', 'data_ini': '2026-06-10', 'data_fim': '2026-06-20'},
    {'retirada': 'MSY', 'entrega': 'CHC', 'data_ini': '2026-06-12', 'data_fim': '2026-06-18'},
]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aluguel_carros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_retirada TEXT, local_entrega TEXT,
            data_inicio TEXT, data_fim TEXT,
            categoria TEXT, locadora TEXT, capacidade TEXT,
            preco_total TEXT, preco_numerico REAL,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def salvar_carro(dados):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        limpo = re.sub(r'[^\d]', '', dados['preco'])
        preco_num = float(limpo) / 100 if len(limpo) > 2 else float(limpo)
    except: preco_num = 0.0
    
    cursor.execute('''
        INSERT INTO aluguel_carros (local_retirada, local_entrega, data_inicio, data_fim, 
                                   categoria, locadora, capacidade, preco_total, preco_numerico)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dados['retirada'], dados['entrega'], dados['data_ini'], dados['data_fim'], 
          dados['categoria'], dados['locadora'], dados['capacidade'], dados['preco'], preco_num))
    conn.commit()
    conn.close()

def extrair_dados_final(page, info):
    print(f"   -> Iniciando varredura por texto de preço...")
    
    # Scroll para garantir renderização
    for _ in range(5):
        page.mouse.wheel(0, 800)
        time.sleep(1)

    # CORREÇÃO: Nome da variável definido e usado corretamente
    precos_elementos = page.get_by_text(re.compile(r"R\$\s?[\d\.]+")).all()
    
    count_salvos = 0
    vistos = set()

    for el in precos_elementos:
        try:
            # Sobe na hierarquia para pegar o bloco do card
            card = el.locator("..").locator("..").locator("..").locator("..")
            texto = card.inner_text()
            
            if "R$" not in texto or len(texto) < 50: continue

            preco_match = re.search(r'R\$\s?([\d\.]+)', texto)
            if not preco_match: continue
            preco_str = preco_match.group(0)

            # Evita duplicatas
            if preco_str + texto[:30] in vistos: continue
            vistos.add(preco_str + texto[:30])

            linhas = [l.strip() for l in texto.split('\n') if len(l.strip()) > 2]
            categoria = linhas[0] if linhas else "Veículo"
            
            locadoras_comuns = ['Hertz', 'Localiza', 'Movida', 'Unidas', 'Sixt', 'Alamo', 'Avis', 'Budget', 'Enterprise']
            locadora = "Locadora"
            for l in locadoras_comuns:
                if l.lower() in texto.lower():
                    locadora = l
                    break

            salvar_carro({
                **info,
                'categoria': categoria,
                'locadora': locadora,
                'capacidade': "5 passageiros",
                'preco': preco_str
            })
            count_salvos += 1
        except:
            continue
            
    print(f"   [SUCESSO] {count_salvos} opções salvas.")

def rodar_crawler():
    with sync_playwright() as p:
        print("\n=== INICIANDO SCRAPER DE CARROS (SIGLAS IATA) ===")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        for info in ALUGUEIS_CARRO:
            url = f"https://www.kayak.com.br/cars/{info['retirada']}/{info['entrega']}/{info['data_ini']}/{info['data_fim']}?sort=price_a"
            
            print(f"\n--- Rota: {info['retirada']} -> {info['entrega']} ---")
            try:
                page.goto(url, wait_until="domcontentloaded")
                
                # Tenta lidar com pop-up de seleção de local, se aparecer
                try:
                    page.wait_for_selector('.JyN7-item', timeout=5000)
                    print("    [!] Seleção detectada. Escolhendo primeira opção...")
                    page.click('.JyN7-item >> nth=0')
                except:
                    pass

                print("    Aguardando renderização (45s)...")
                time.sleep(45)
                
                extrair_dados_final(page, info)
            except Exception as e:
                print(f"   [ERRO] {e}")

        browser.close()
        print("\n=== PROCESSO FINALIZADO ===")

if __name__ == "__main__":
    init_db()
    rodar_crawler()
