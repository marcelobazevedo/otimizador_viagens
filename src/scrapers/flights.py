"""
Scraper de voos do Kayak
"""
import sqlite3
import time
import random
import re
import os
from typing import List, Optional, Dict
from playwright.sync_api import sync_playwright, Page

from src.config.settings import DB_NAME, SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX, SCRAPING_WAIT_TIME
from src.database.db import init_flights_db, get_connection


class FlightsScraper:
    """Scraper para coletar dados de voos do Kayak"""
    
    def __init__(self):
        self.is_docker = os.path.exists('/.dockerenv') or os.path.exists('/app/data')
        self.headless_mode = self.is_docker
        init_flights_db()
    
    def _generate_routes(self, origem: str, destinos: List[str], data_ida: str, data_volta: Optional[str] = None) -> List[Dict]:
        """
        Gera lista de rotas com base nos parâmetros fornecidos.
        
        Args:
            origem: Código IATA do aeroporto de origem
            destinos: Lista de códigos IATA dos aeroportos de destino
            data_ida: Data de partida (formato 'YYYY-MM-DD')
            data_volta: Data de retorno (formato 'YYYY-MM-DD' ou None)
        
        Returns:
            Lista de dicionários com as rotas a serem pesquisadas
        """
        rotas = []
        
        # Apenas origem -> cada destino (sem combinações entre destinos)
        for destino in destinos:
            rotas.append({
                'origem': origem,
                'destino': destino,
                'ida': data_ida,
                'volta': data_volta
            })
        
        return rotas
    
    def _save_flight(self, dados: Dict) -> bool:
        """Salva um voo no banco de dados, evitando duplicatas"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            limpo = re.sub(r'[^\d]', '', dados['preco'])
            preco_num = float(limpo)
        except:
            preco_num = 0.0
        
        # Normalizar data_volta para None se for string vazia ou 'None'
        data_volta = dados.get('volta')
        if data_volta in ['', 'None', 'null']:
            data_volta = None
        
        # Verificar se já existe um voo EXATAMENTE igual
        if data_volta:
            cursor.execute('''
                SELECT COUNT(*) FROM voos 
                WHERE origem=? AND destino=? AND data_ida=? AND data_volta=? 
                AND companhia=? AND ida_saida=? AND ida_chegada=? AND ida_duracao=? AND ida_escalas=?
                AND volta_saida=? AND volta_chegada=? AND volta_duracao=? AND volta_escalas=?
            ''', (dados['origem'], dados['destino'], dados['ida'], data_volta,
                  dados['companhia'], 
                  dados.get('ida_saida'), dados.get('ida_chegada'), dados.get('ida_duracao'), dados.get('ida_escalas'),
                  dados.get('volta_saida'), dados.get('volta_chegada'), dados.get('volta_duracao'), dados.get('volta_escalas')))
        else:
            cursor.execute('''
                SELECT COUNT(*) FROM voos 
                WHERE origem=? AND destino=? AND data_ida=? AND data_volta IS NULL 
                AND companhia=? AND ida_saida=? AND ida_chegada=? AND ida_duracao=? AND ida_escalas=?
            ''', (dados['origem'], dados['destino'], dados['ida'],
                  dados['companhia'], 
                  dados.get('ida_saida'), dados.get('ida_chegada'), dados.get('ida_duracao'), dados.get('ida_escalas')))
        
        if cursor.fetchone()[0] > 0:
            print(f"   [SKIP] Voo duplicado ignorado: {dados['companhia']}")
            conn.close()
            return False
        
        cursor.execute('''
            INSERT INTO voos (origem, destino, data_ida, data_volta, companhia, preco_bruto, preco_numerico, 
                              ida_saida, ida_chegada, ida_duracao, ida_escalas,
                              volta_saida, volta_chegada, volta_duracao, volta_escalas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (dados['origem'], dados['destino'], dados['ida'], data_volta, 
              dados['companhia'], dados['preco'], preco_num,
              dados.get('ida_saida'), dados.get('ida_chegada'), dados.get('ida_duracao'), dados.get('ida_escalas'),
              dados.get('volta_saida'), dados.get('volta_chegada'), dados.get('volta_duracao'), dados.get('volta_escalas')))
        conn.commit()
        conn.close()
        return True
    
    def _extract_flight_data(self, page: Page, rota: Dict):
        """Extrai dados de voos da página do Kayak"""
        print(f"   -> Extraindo detalhes para {rota['origem']} -> {rota['destino']}...")
        
        try:
            print(f"   -> Aguardando carregamento dos cards de voo...")
            page.wait_for_selector('.nrc6', timeout=30000)
            print(f"   -> Cards carregados!")
        except Exception as e:
            print(f"   [!] Erro: Cards de voo não carregaram. Detalhes: {e}")
            print(f"   [!] URL atual: {page.url}")
            return
        
        # Scroll para garantir renderização
        page.mouse.wheel(0, 1000)
        time.sleep(2)
        
        cards = page.query_selector_all('.nrc6')
        print(f"   -> Encontrados {len(cards)} cards de voo")
        
        count = 0
        for card in cards:
            try:
                texto = card.inner_text()
                if "R$" not in texto:
                    continue
                
                # 1. Preço
                preco_match = re.search(r'R\$\s?([\d\.]+)', texto)
                preco_final = preco_match.group(0) if preco_match else "N/A"
                
                # 2. Extrair horários e durações separados para IDA e VOLTA
                horarios = re.findall(r'(\d{1,2}:\d{2})', texto)
                duracoes = re.findall(r'(\d{1,2}h\s\d{1,2}m)', texto)
                
                # Função auxiliar para extrair escalas
                def extrair_escalas(texto_parte):
                    if "direto" in texto_parte.lower():
                        return "direto"
                    escala_match = re.search(r'(\d+)\s*escala[s]?', texto_parte.lower())
                    if escala_match:
                        num_escalas = int(escala_match.group(1))
                        return f"{num_escalas} escala" if num_escalas == 1 else f"{num_escalas} escalas"
                    if "parada" in texto_parte.lower() or "conexão" in texto_parte.lower():
                        return "1 escala"
                    return "N/A"
                
                # Para voos ida e volta: geralmente 4 horários
                # Para voos só ida: 2 horários
                tem_volta = rota.get('volta') is not None
                
                if tem_volta and len(horarios) >= 4:
                    # Ida e volta
                    ida_saida = horarios[0]
                    ida_chegada = horarios[1]
                    volta_saida = horarios[2]
                    volta_chegada = horarios[3]
                    ida_duracao = duracoes[0] if len(duracoes) >= 1 else "N/A"
                    volta_duracao = duracoes[1] if len(duracoes) >= 2 else "N/A"
                    
                    # Tentar extrair escalas separadas
                    linhas = texto.split('\n')
                    ida_escalas = extrair_escalas(' '.join(linhas[:len(linhas)//2]))
                    volta_escalas = extrair_escalas(' '.join(linhas[len(linhas)//2:]))
                else:
                    # Só ida
                    ida_saida = horarios[0] if len(horarios) >= 1 else "N/A"
                    ida_chegada = horarios[1] if len(horarios) >= 2 else "N/A"
                    volta_saida = None
                    volta_chegada = None
                    ida_duracao = duracoes[0] if len(duracoes) >= 1 else "N/A"
                    volta_duracao = None
                    ida_escalas = extrair_escalas(texto)
                    volta_escalas = None
                
                # 5. Companhia
                cia_element = card.query_selector('.J0g6-operator-text')
                companhia = cia_element.inner_text() if cia_element else "Múltiplas"
                
                voo_data = {
                    **rota,
                    'companhia': companhia,
                    'preco': preco_final,
                    'ida_saida': ida_saida,
                    'ida_chegada': ida_chegada,
                    'ida_duracao': ida_duracao,
                    'ida_escalas': ida_escalas,
                    'volta_saida': volta_saida,
                    'volta_chegada': volta_chegada,
                    'volta_duracao': volta_duracao,
                    'volta_escalas': volta_escalas
                }
                print(f"   -> Salvando voo: {companhia} - {preco_final}")
                if tem_volta:
                    print(f"      IDA: {ida_saida}-{ida_chegada} ({ida_duracao}, {ida_escalas})")
                    print(f"      VOLTA: {volta_saida}-{volta_chegada} ({volta_duracao}, {volta_escalas})")
                else:
                    print(f"      IDA: {ida_saida}-{ida_chegada} ({ida_duracao}, {ida_escalas})")
                self._save_flight(voo_data)
                count += 1
                if count >= 8:
                    break
            except Exception as e:
                print(f"   [!] Erro ao processar card: {e}")
                continue
        
        print(f"   [SUCESSO] {count} voos detalhados salvos.")
        if count == 0:
            print(f"   [AVISO] Nenhum voo foi salvo! Verifique se a página carregou corretamente.")
    
    def scrape(self, origem: str, destinos: List[str], data_ida: str, data_volta: Optional[str] = None):
        """
        Executa o crawler de passagens aéreas.
        
        Args:
            origem: Código IATA do aeroporto de origem
            destinos: Lista de códigos IATA dos aeroportos de destino
            data_ida: Data de partida (formato 'YYYY-MM-DD')
            data_volta: Data de retorno (formato 'YYYY-MM-DD' ou None para só ida)
        """
        rotas = self._generate_routes(origem, destinos, data_ida, data_volta)
        print(f"[INFO] Gerando {len(rotas)} rotas para pesquisa...")
        for r in rotas:
            print(f"[INFO]   - {r['origem']} -> {r['destino']} | Ida: {r['ida']} | Volta: {r.get('volta', 'N/A')}")
        
        launch_args = [
            "--lang=pt-BR",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--mute-audio",
            "--no-first-run",
            "--safebrowsing-disable-auto-update",
            "--ignore-certificate-errors",
            "--ignore-ssl-errors",
            "--ignore-certificate-errors-spki-list"
        ]
        
        with sync_playwright() as p:
            print(f"[INFO] Modo headless: {self.headless_mode}")
            
            try:
                browser = p.chromium.launch(
                    headless=self.headless_mode,
                    args=launch_args,
                    chromium_sandbox=False
                )
            except Exception as e:
                print(f"[ERRO] Falha ao iniciar browser: {e}")
                print("[INFO] Tentando com configurações alternativas...")
                browser = p.chromium.launch(
                    headless=True,
                    args=launch_args + ["--single-process"]
                )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            for rota in rotas:
                # Construir URL baseado se tem data de volta ou não
                if rota.get('volta'):
                    url = f"https://www.kayak.com.br/flights/{rota['origem']}-{rota['destino']}/{rota['ida']}/{rota['volta']}?sort=price_a"
                else:
                    url = f"https://www.kayak.com.br/flights/{rota['origem']}-{rota['destino']}/{rota['ida']}?sort=price_a"
                
                print(f"\n--- Rota: {rota['origem']} -> {rota['destino']} ---")
                print(f"    Tipo: {'Ida e volta' if rota.get('volta') else 'Só ida'}")
                print(f"    URL: {url}")
                try:
                    print(f"    Acessando página...")
                    page.goto(url, wait_until="domcontentloaded")
                    print(f"    Aguardando {SCRAPING_WAIT_TIME} segundos para bypass de segurança...")
                    time.sleep(SCRAPING_WAIT_TIME)
                    print(f"    Iniciando extração de dados...")
                    self._extract_flight_data(page, rota)
                except Exception as e:
                    print(f"   [ERRO] {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
                
                time.sleep(random.randint(SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX))
            
            browser.close()


# Funções de compatibilidade para manter API antiga
def rodar_crawler(origem=None, destinos=None, data_ida=None, data_volta=None):
    """Função de compatibilidade - mantém API antiga"""
    scraper = FlightsScraper()
    scraper.scrape(origem, destinos, data_ida, data_volta)


def init_db():
    """Função de compatibilidade - mantém API antiga"""
    init_flights_db()


if __name__ == "__main__":
    # Exemplo de uso standalone
    scraper = FlightsScraper()
    scraper.scrape(
        origem='GYN',
        destinos=['ATL'],
        data_ida='2026-06-15',
        data_volta='2026-06-22'
    )

