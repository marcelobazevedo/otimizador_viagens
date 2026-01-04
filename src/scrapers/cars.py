"""
Scraper de aluguel de carros do Kayak
"""
import sqlite3
import time
import random
import re
import os
from typing import List, Optional, Dict
from playwright.sync_api import sync_playwright, Page

from src.config.settings import DB_NAME, SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX
from src.database.db import init_cars_db, get_connection


class CarsScraper:
    """Scraper para coletar dados de aluguel de carros do Kayak"""
    
    def __init__(self):
        self.is_docker = os.path.exists('/.dockerenv') or os.path.exists('/app/data')
        self.headless_mode = self.is_docker
        init_cars_db()
    
    def _save_car(self, dados: Dict):
        """Salva um aluguel de carro no banco de dados"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            limpo = re.sub(r'[^\d]', '', dados['preco'])
            preco_num = float(limpo) / 100 if len(limpo) > 2 else float(limpo)
        except:
            preco_num = 0.0
        
        # Calcular valor da diária
        dias_viagem = dados.get('dias_viagem', 1)
        valor_diaria = preco_num / dias_viagem if dias_viagem > 0 else 0.0
        
        # Verificar se é mesmo local
        mesmo_local = 1 if dados['retirada'] == dados['entrega'] else 0
        
        cursor.execute('''
            INSERT INTO aluguel_carros (local_retirada, local_entrega, data_inicio, data_fim, 
                                       categoria, locadora, capacidade, preco_total, preco_numerico,
                                       valor_diaria, dias_viagem, tempo_viagem_horas, distancia_km, mesmo_local)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (dados['retirada'], dados['entrega'], dados['data_ini'], dados['data_fim'], 
              dados['categoria'], dados['locadora'], dados['capacidade'], dados['preco'], preco_num,
              valor_diaria, dados.get('dias_viagem'), dados.get('tempo_viagem_horas'), 
              dados.get('distancia_km'), mesmo_local))
        conn.commit()
        conn.close()
    
    def _extract_car_data(self, page: Page, info: Dict):
        """Extrai dados de aluguel de carros da página do Kayak"""
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
        
        precos_elementos = page.get_by_text(re.compile(r"R\$\s?[\d\.]+")).all()
        print(f"   [DEBUG] Encontrados {len(precos_elementos)} elementos com preços")
        
        count_salvos = 0
        vistos = set()
        
        for el in precos_elementos:
            try:
                # Sobe na hierarquia para pegar o bloco do card
                card = el.locator("..").locator("..").locator("..").locator("..")
                texto = card.inner_text()
                
                if "R$" not in texto or len(texto) < 50:
                    continue
                
                preco_match = re.search(r'R\$\s?([\d\.]+)', texto)
                if not preco_match:
                    continue
                preco_str = preco_match.group(0)
                
                # Evita duplicatas
                if preco_str + texto[:30] in vistos:
                    continue
                vistos.add(preco_str + texto[:30])
                
                linhas = [l.strip() for l in texto.split('\n') if len(l.strip()) > 2]
                categoria = linhas[0] if linhas else "Veículo"
                
                locadoras_comuns = ['Hertz', 'Localiza', 'Movida', 'Unidas', 'Sixt', 'Alamo', 'Avis', 'Budget', 'Enterprise']
                locadora = "Locadora"
                for l in locadoras_comuns:
                    if l.lower() in texto.lower():
                        locadora = l
                        break
                
                self._save_car({
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
    
    def scrape(self, local_retirada: str, local_entrega: str, data_inicio: str, data_fim: str,
               dias_viagem: Optional[int] = None, tempo_viagem_horas: Optional[str] = None,
               distancia_km: Optional[int] = None):
        """
        Executa o crawler de aluguel de carros.
        
        Args:
            local_retirada: Código IATA do local de retirada do carro
            local_entrega: Código IATA do local de entrega/devolução do carro
            data_inicio: Data de início do aluguel (formato 'YYYY-MM-DD')
            data_fim: Data de fim do aluguel (formato 'YYYY-MM-DD')
            dias_viagem: Número de dias necessários para a viagem de carro
            tempo_viagem_horas: Tempo de viagem em formato HH:MM
            distancia_km: Distância em km entre origem e destino
        """
        print(f"\n[DEBUG rodar_crawler] Chamado com:")
        print(f"  - local_retirada: {local_retirada}")
        print(f"  - local_entrega: {local_entrega}")
        print(f"  - data_inicio: {data_inicio}")
        print(f"  - data_fim: {data_fim}")
        print(f"  - dias_viagem: {dias_viagem}")
        print(f"  - tempo_viagem_horas: {tempo_viagem_horas}")
        print(f"  - distancia_km: {distancia_km}")
        print(f"  - DB_NAME: {DB_NAME}")
        
        alugueis = [{
            'retirada': local_retirada,
            'entrega': local_entrega,
            'data_ini': data_inicio,
            'data_fim': data_fim,
            'dias_viagem': dias_viagem,
            'tempo_viagem_horas': tempo_viagem_horas,
            'distancia_km': distancia_km
        }]
        print(f"[INFO] Pesquisando aluguel: {local_retirada} → {local_entrega}")
        
        launch_args = [
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
            "--ignore-ssl-errors"
        ]
        
        with sync_playwright() as p:
            print("\n=== INICIANDO SCRAPER DE CARROS (SIGLAS IATA) ===")
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
                    tempo_espera = 60 if self.headless_mode else 45
                    print(f"    Aguardando renderização ({tempo_espera}s)...")
                    time.sleep(tempo_espera)
                    
                    self._extract_car_data(page, info)
                except Exception as e:
                    print(f"   [ERRO] {e}")
            
            browser.close()
            print("\n=== PROCESSO FINALIZADO ===")


# Funções de compatibilidade para manter API antiga
def rodar_crawler(local_retirada=None, local_entrega=None, data_inicio=None, data_fim=None,
                  destinos=None, dias_viagem=None, tempo_viagem_horas=None, distancia_km=None):
    """Função de compatibilidade - mantém API antiga"""
    scraper = CarsScraper()
    if local_retirada and data_inicio and data_fim:
        scraper.scrape(
            local_retirada=local_retirada,
            local_entrega=local_entrega or local_retirada,
            data_inicio=data_inicio,
            data_fim=data_fim,
            dias_viagem=dias_viagem,
            tempo_viagem_horas=tempo_viagem_horas,
            distancia_km=distancia_km
        )


def init_db():
    """Função de compatibilidade - mantém API antiga"""
    init_cars_db()


if __name__ == "__main__":
    # Exemplo de uso standalone
    scraper = CarsScraper()
    scraper.scrape(
        local_retirada='ATL',
        local_entrega='MSY',
        data_inicio='2026-06-10',
        data_fim='2026-06-20'
    )

