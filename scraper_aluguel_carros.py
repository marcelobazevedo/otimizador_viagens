import sqlite3
import time
import random
import re
import os
from playwright.sync_api import sync_playwright

# --- CONFIGURAÇÕES ---
# Usar diretório de dados se existir (Docker ou local), senão usar diretório atual
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "data" if os.path.exists("data") else "."
DB_NAME = os.path.join(DATA_DIR, "voos_local.db")

# Lista padrão para execução standalone
ALUGUEIS_CARRO = [
    {'retirada': 'ATL', 'entrega': 'MSY', 'data_ini': '2026-06-10', 'data_fim': '2026-06-20'},
    {'retirada': 'MSY', 'entrega': 'CHC', 'data_ini': '2026-06-12', 'data_fim': '2026-06-18'},
]

def gerar_alugueis(destinos, data_inicio, data_fim):
    """
    Gera lista de aluguéis de carro com base nos destinos fornecidos.
    
    Args:
        destinos: Lista de códigos IATA dos aeroportos/cidades de destino
        data_inicio: Data de início do aluguel (formato 'YYYY-MM-DD')
        data_fim: Data de fim do aluguel (formato 'YYYY-MM-DD')
    
    Returns:
        Lista de dicionários com os aluguéis a serem pesquisados
    """
    alugueis = []
    
    # Para cada destino, adicionar pesquisa de aluguel no mesmo local
    for destino in destinos:
        alugueis.append({
            'retirada': destino,
            'entrega': destino,  # Mesmo local de retirada e entrega
            'data_ini': data_inicio,
            'data_fim': data_fim
        })
    
    # Se houver múltiplos destinos, adicionar opções de aluguel entre cidades
    if len(destinos) > 1:
        for i, dest1 in enumerate(destinos):
            for dest2 in destinos[i+1:]:
                # Aluguel com retirada em uma cidade e devolução em outra
                alugueis.append({
                    'retirada': dest1,
                    'entrega': dest2,
                    'data_ini': data_inicio,
                    'data_fim': data_fim
                })
    
    return alugueis

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
    for i in range(5):
        page.mouse.wheel(0, 800)
        time.sleep(2)
    
    # Aguardar um pouco mais para garantir que a página carregou
    time.sleep(5)
    
    # Debug: verificar se a página tem conteúdo
    page_content = page.content()
    if "R$" in page_content:
        print(f"   [DEBUG] Página contém preços em R$")
    else:
        print(f"   [AVISO] Página não contém preços em R$ - pode estar bloqueada")
        return

    # CORREÇÃO: Nome da variável definido e usado corretamente
    precos_elementos = page.get_by_text(re.compile(r"R\$\s?[\d\.]+")).all()
    print(f"   [DEBUG] Encontrados {len(precos_elementos)} elementos com preços")
    
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

def rodar_crawler(destinos=None, data_inicio=None, data_fim=None):
    """
    Executa o crawler de aluguel de carros.
    
    Args:
        destinos: Lista de códigos IATA dos aeroportos/cidades de destino
        data_inicio: Data de início do aluguel (formato 'YYYY-MM-DD')
        data_fim: Data de fim do aluguel (formato 'YYYY-MM-DD')
    """
    # Se não forem fornecidos parâmetros, usar valores padrão
    if not destinos or not data_inicio or not data_fim:
        print("[INFO] Usando aluguéis padrão da lista ALUGUEIS_CARRO...")
        alugueis = ALUGUEIS_CARRO
    else:
        alugueis = gerar_alugueis(destinos, data_inicio, data_fim)
        print(f"[INFO] Gerando {len(alugueis)} opções de aluguel para pesquisa...")
    
    # Detectar se está rodando em Docker (sem display gráfico)
    is_docker = os.path.exists('/.dockerenv') or os.path.exists('/app/data')
    headless_mode = is_docker  # True no Docker, False localmente
    
    with sync_playwright() as p:
        print("\n=== INICIANDO SCRAPER DE CARROS (SIGLAS IATA) ===")
        print(f"[INFO] Modo headless: {headless_mode}")
        browser = p.chromium.launch(
            headless=headless_mode,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for info in alugueis:
            url = f"https://www.kayak.com.br/cars/{info['retirada']}/{info['entrega']}/{info['data_ini']}/{info['data_fim']}?sort=price_a"
            
            print(f"\n--- Rota: {info['retirada']} -> {info['entrega']} ---")
            try:
                page.goto(url, wait_until="domcontentloaded")
                
                # Tenta lidar com pop-up de seleção de local, se aparecer
                try:
                    page.wait_for_selector('.JyN7-item', timeout=5000)
                    print("    [!] Seleção detectada. Escolhendo primeira opção...")
                    page.click('.JyN7-item >> nth=0')
                    time.sleep(3)
                except:
                    pass

                # Aumentar tempo de espera em headless
                tempo_espera = 60 if headless_mode else 45
                print(f"    Aguardando renderização ({tempo_espera}s)...")
                time.sleep(tempo_espera)
                
                extrair_dados_final(page, info)
            except Exception as e:
                print(f"   [ERRO] {e}")

        browser.close()
        print("\n=== PROCESSO FINALIZADO ===")

if __name__ == "__main__":
    init_db()
    rodar_crawler()
