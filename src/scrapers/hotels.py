"""
Scraper de hospedagens do Kayak
"""
import sqlite3
import time
import random
import re
import os
from typing import List, Optional, Dict
from playwright.sync_api import sync_playwright, Page

from src.config.settings import DB_NAME, SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX
from src.database.db import init_hotels_db, get_connection


class HotelsScraper:
    """Scraper para coletar dados de hospedagens do Kayak"""
    
    QUARTOS = 1  # Sempre 1 quarto
    
    def __init__(self):
        self.is_docker = os.path.exists('/.dockerenv') or os.path.exists('/app/data')
        self.headless_mode = self.is_docker
        init_hotels_db()
    
    def _save_hotel(self, dados: Dict):
        """Salva uma hospedagem no banco de dados"""
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            limpo = re.sub(r'[^\d]', '', dados['preco'])
            preco_num = float(limpo) if limpo else 0.0
        except:
            preco_num = 0.0
        
        cursor.execute('''
            INSERT INTO hospedagem (cidade, quartos, adultos, criancas, data_checkin, data_checkout,
                                   nome_hotel, tipo_acomodacao, avaliacao, num_avaliacoes,
                                   preco_total, preco_numerico, amenidades)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dados['cidade'], dados['quartos'], dados['adultos'], dados['criancas'],
            dados['data_checkin'], dados['data_checkout'], dados['nome_hotel'],
            dados['tipo_acomodacao'], dados['avaliacao'], dados['num_avaliacoes'],
            dados['preco'], preco_num, dados['amenidades']
        ))
        conn.commit()
        conn.close()
    
    def _extract_hotel_data(self, page: Page, info: Dict):
        """Extrai dados de hospedagens da página do Kayak"""
        print(f"   -> Iniciando varredura por hotéis...")
        
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
        
        # Buscar elementos com preços
        precos_elementos = page.get_by_text(re.compile(r"R\$\s?[\d\.]+")).all()
        print(f"   [DEBUG] Encontrados {len(precos_elementos)} elementos com preços")
        
        count_salvos = 0
        vistos = set()
        
        for el in precos_elementos:
            try:
                # Sobe na hierarquia para pegar o bloco do card do hotel
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
                nome_hotel = linhas[0] if linhas else "Hotel"
                
                # Tentar extrair tipo de acomodação
                tipo_acomodacao = "Hotel"
                if "apart" in texto.lower():
                    tipo_acomodacao = "Apart Hotel"
                elif "pousada" in texto.lower():
                    tipo_acomodacao = "Pousada"
                elif "resort" in texto.lower():
                    tipo_acomodacao = "Resort"
                
                # Tentar extrair avaliação
                avaliacao_match = re.search(r'(\d+[,\.]?\d*)/10', texto)
                avaliacao = avaliacao_match.group(1) if avaliacao_match else "N/A"
                
                # Tentar extrair número de avaliações
                num_avaliacoes_match = re.search(r'\((\d+[\.\d]*)\s*avalia', texto.lower())
                num_avaliacoes = num_avaliacoes_match.group(1) if num_avaliacoes_match else "N/A"
                
                # Amenidades comuns
                amenidades_lista = []
                amenidades_comuns = ['Wi-Fi', 'Piscina', 'Estacionamento', 'Café da manhã', 'Academia', 'Ar-condicionado']
                for amenidade in amenidades_comuns:
                    if amenidade.lower() in texto.lower():
                        amenidades_lista.append(amenidade)
                amenidades = ", ".join(amenidades_lista) if amenidades_lista else "N/A"
                
                self._save_hotel({
                    **info,
                    'quartos': self.QUARTOS,
                    'nome_hotel': nome_hotel,
                    'tipo_acomodacao': tipo_acomodacao,
                    'avaliacao': avaliacao,
                    'num_avaliacoes': num_avaliacoes,
                    'preco': preco_str,
                    'amenidades': amenidades
                })
                count_salvos += 1
                
                # Limitar quantidade para não demorar muito
                if count_salvos >= 15:
                    break
            except Exception as e:
                continue
        
        print(f"   [SUCESSO] {count_salvos} hospedagens salvas.")
    
    def scrape(self, hospedagens: List[Dict]):
        """
        Executa o crawler de hospedagens.
        
        Args:
            hospedagens: Lista de dicionários com os dados das hospedagens a pesquisar
                Cada dicionário deve conter: cidade, adultos, criancas, data_checkin, data_checkout
        """
        if not hospedagens:
            print("[INFO] Nenhuma hospedagem fornecida.")
            return
        
        print(f"[INFO] Pesquisando {len(hospedagens)} hospedagens...")
        
        launch_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled"
        ]
        
        with sync_playwright() as p:
            print("\n=== INICIANDO SCRAPER DE HOSPEDAGENS ===")
            print(f"[INFO] Modo headless: {self.headless_mode}")
            browser = p.chromium.launch(
                headless=self.headless_mode,
                args=launch_args
            )
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            for info in hospedagens:
                # Formato da URL do Kayak para hotéis:
                # https://www.kayak.com.br/hotels/Atlanta,GA/2026-06-10/2026-06-15/2adults
                cidade_formatada = info['cidade'].replace(' ', '-').replace(',', '%2C')
                guests = f"{info['adultos']}adults"
                if info['criancas'] > 0:
                    guests += f"-{info['criancas']}children"
                
                url = f"https://www.kayak.com.br/hotels/{cidade_formatada}/{info['data_checkin']}/{info['data_checkout']}/{guests}?sort=rank_a"
                
                print(f"\n--- Cidade: {info['cidade']} | {info['adultos']} adultos, {info['criancas']} crianças ---")
                print(f"    Check-in: {info['data_checkin']} | Check-out: {info['data_checkout']}")
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    
                    # Aumentar tempo de espera em headless
                    tempo_espera = 60 if self.headless_mode else 45
                    print(f"    Aguardando renderização ({tempo_espera}s)...")
                    time.sleep(tempo_espera)
                    
                    self._extract_hotel_data(page, info)
                except Exception as e:
                    print(f"   [ERRO] {e}")
                
                # Delay entre requisições
                time.sleep(random.randint(SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX))
            
            browser.close()
            print("\n=== PROCESSO FINALIZADO ===")


# Funções de compatibilidade para manter API antiga
def rodar_crawler(hospedagens=None):
    """Função de compatibilidade - mantém API antiga"""
    scraper = HotelsScraper()
    scraper.scrape(hospedagens or [])


def init_db():
    """Função de compatibilidade - mantém API antiga"""
    init_hotels_db()


if __name__ == "__main__":
    # Exemplo de uso standalone
    scraper = HotelsScraper()
    scraper.scrape([
        {
            'cidade': 'Atlanta, GA',
            'adultos': 2,
            'criancas': 0,
            'data_checkin': '2026-06-10',
            'data_checkout': '2026-06-15'
        }
    ])

