import sqlite3
import time
import random
import re
from playwright.sync_api import sync_playwright

# --- CONFIGURAÇÕES DE BUSCA ---
# Defina suas rotas e datas aqui
ROTAS = [
    {'origem': 'GYN', 'destino': 'ATL', 'data': '2025-05-15'},
    {'origem': 'ATL', 'destino': 'BSB', 'data': '2025-05-20'},
    # Adicione quantas quiser
]

DB_NAME = "voos_local.db"

# --- 1. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT,
            destino TEXT,
            data_voo TEXT,
            companhia TEXT,
            preco_bruto TEXT,
            preco_numerico REAL,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def salvar_voo(dados):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Limpeza básica do preço para salvar numérico também (para ordenar depois)
    try:
        # Remove "R$", pontos e espaços, troca vírgula por ponto
        limpo = re.sub(r'[^\d,]', '', dados['preco'])
        preco_num = float(limpo.replace(',', '.'))
    except:
        preco_num = 0.0

    cursor.execute('''
        INSERT INTO voos (origem, destino, data_voo, companhia, preco_bruto, preco_numerico)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (dados['origem'], dados['destino'], dados['data'], dados['companhia'], dados['preco'], preco_num))
    
    conn.commit()
    conn.close()
    print(f"   [SALVO] {dados['companhia']} | {dados['preco']}")

# --- 2. MOTOR DE SCRAPING ---
def extrair_dados_da_pagina(page, origem, destino, data):
    print("   -> Analisando resultados...")
    
    # Google Flights carrega dinamicamente. Vamos garantir que a lista carregou.
    # O seletor 'body' sempre existe, mas queremos esperar pelos resultados.
    # Estratégia: Esperar aparecer algum texto de preço "R$"
    try:
        page.wait_for_selector('div[role="listitem"]', timeout=15000)
    except:
        print("   [!] Timeout: A lista de voos não carregou ou não há voos.")
        return

    # Pega todos os itens da lista principal
    # role="listitem" é um padrão de acessibilidade que o Google mantém, 
    # é mais seguro que classes CSS aleatórias como '.JMc5Xc'
    voos_elementos = page.locator('div[role="listitem"]').all()
    
    if not voos_elementos:
        print("   [!] Nenhum elemento de lista encontrado.")
        return

    count = 0
    for voo in voos_elementos:
        try:
            # Pega todo o texto do cartão do voo e divide em linhas
            texto_completo = voo.inner_text()
            linhas = texto_completo.split('\n')
            
            # --- LÓGICA HEURÍSTICA ---
            # O Google Flights geralmente tem essa estrutura visual:
            # Hora | Cia Aérea | Duração | Escalas | Preço
            
            # 1. Achar o preço: busca a linha que tem "R$"
            preco = next((linha for linha in linhas if "R$" in linha), None)
            
            # 2. Achar a companhia: Geralmente é uma das primeiras linhas que NÃO é hora.
            # Vamos assumir que a Cia Aérea não contém números (simplificação)
            # ou usar uma lista de conhecidas se necessário.
            companhia = "N/A"
            for linha in linhas:
                # Ignora linhas de horário (ex: 10:00) ou duração (ex: 12 h 30 min)
                if not re.search(r'\d', linha) and len(linha) > 2: 
                    companhia = linha
                    break
            
            if preco and "R$" in preco:
                salvar_voo({
                    'origem': origem,
                    'destino': destino,
                    'data': data,
                    'companhia': companhia,
                    'preco': preco
                })
                count += 1
                
        except Exception as e:
            # Erros em itens individuais não devem parar o script
            continue
            
    print(f"   -> {count} voos processados nesta página.")

def rodar_crawler():
    with sync_playwright() as p:
        # headless=False: Abre o navegador visualmente.
        # Isso é CRUCIAL para o Google não te bloquear imediatamente.
        # Se colocar True, o Google detecta mais fácil que é um robô.
        browser = p.chromium.launch(headless=False, args=["--lang=pt-BR"])
        
        # Cria um contexto com User Agent comum para parecer um PC normal
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()

        for item in ROTAS:
            origem = item['origem']
            destino = item['destino']
            data = item['data']

            # URL construída manualmente para o Google Flights
            url = f"https://www.google.com/travel/flights?q=Flights%20to%20{destino}%20from%20{origem}%20on%20{data}&curr=BRL"
            
            print(f"\n--- Iniciando busca: {origem} -> {destino} ({data}) ---")
            
            try:
                page.goto(url)
                
                # Tenta fechar popups de Cookies se aparecerem (comum na Europa/BR)
                try:
                    botao_cookie = page.get_by_text("Aceitar", exact=True)
                    if botao_cookie.is_visible():
                        botao_cookie.click()
                        time.sleep(2)
                except:
                    pass

                # Pausa humana aleatória (essencial para evitar bloqueio)
                time.sleep(random.uniform(4, 8))
                
                extrair_dados_da_pagina(page, origem, destino, data)

            except Exception as e:
                print(f"   [ERRO CRÍTICO] Falha ao acessar {url}: {e}")

            # Pausa longa entre rotas diferentes
            espera = random.randint(10, 20)
            print(f"   (Dormindo {espera}s para não irritar o Google...)")
            time.sleep(espera)

        browser.close()

if __name__ == "__main__":
    init_db()
    print("Iniciando Crawler Local (Sem API)...")
    rodar_crawler()
    print("\nProcesso finalizado. Verifique o arquivo 'voos_local.db'.")