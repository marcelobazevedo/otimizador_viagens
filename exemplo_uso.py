"""
Exemplo de uso dos scrapers integrados

Este arquivo demonstra como usar os scrapers de forma independente
se você preferir não usar a interface Streamlit.
"""

from scraper_local import rodar_crawler as buscar_passagens, init_db as init_db_voos
from scraper_aluguel_carros import rodar_crawler as buscar_carros, init_db as init_db_carros

def exemplo_completo():
    """
    Exemplo completo de busca de passagens e carros
    """
    # Configurações da viagem
    origem = 'GYN'
    destinos = ['ATL', 'MSY', 'CHC']
    data_ida = '2026-06-15'
    data_volta = '2026-06-22'
    
    print("="*80)
    print("INICIANDO BUSCA COMPLETA DE PASSAGENS E CARROS")
    print("="*80)
    print(f"\nOrigem: {origem}")
    print(f"Destinos: {', '.join(destinos)}")
    print(f"Período: {data_ida} até {data_volta}\n")
    
    # Inicializar bancos de dados
    print("Inicializando bancos de dados...")
    init_db_voos()
    init_db_carros()
    
    # 1. Buscar passagens
    print("\n" + "="*80)
    print("ETAPA 1: BUSCANDO PASSAGENS")
    print("="*80)
    print("\nO scraper irá buscar:")
    print(f"  - Passagens de {origem} para cada destino: {', '.join(destinos)}")
    if len(destinos) > 1:
        print(f"  - Passagens entre os destinos (todas as combinações)")
    print("\nEssa busca pode levar vários minutos...\n")
    
    buscar_passagens(
        origem=origem,
        destinos=destinos,
        data_ida=data_ida,
        data_volta=data_volta
    )
    
    # 2. Buscar aluguel de carros
    print("\n" + "="*80)
    print("ETAPA 2: BUSCANDO ALUGUEL DE CARROS")
    print("="*80)
    print("\nO scraper irá buscar:")
    print(f"  - Aluguel de carros em cada destino: {', '.join(destinos)}")
    if len(destinos) > 1:
        print(f"  - Opções de aluguel entre cidades diferentes")
    print("\nEssa busca pode levar vários minutos...\n")
    
    buscar_carros(
        destinos=destinos,
        data_inicio=data_ida,
        data_fim=data_volta
    )
    
    print("\n" + "="*80)
    print("BUSCA CONCLUÍDA!")
    print("="*80)
    print("\nOs dados foram salvos no banco de dados 'voos_local.db'")
    print("Use o script 'visualizar_precos.py' para visualizar os resultados")

def exemplo_apenas_passagens():
    """
    Exemplo buscando apenas passagens
    """
    init_db_voos()
    
    buscar_passagens(
        origem='GYN',
        destinos=['ATL'],
        data_ida='2026-06-15',
        data_volta='2026-06-22'
    )

def exemplo_apenas_carros():
    """
    Exemplo buscando apenas carros
    """
    init_db_carros()
    
    buscar_carros(
        destinos=['ATL', 'MSY'],
        data_inicio='2026-06-15',
        data_fim='2026-06-22'
    )

if __name__ == "__main__":
    # Descomente a função que deseja executar:
    
    # exemplo_completo()  # Busca completa de passagens e carros
    # exemplo_apenas_passagens()  # Apenas passagens
    # exemplo_apenas_carros()  # Apenas carros
    
    print("\nDESCOMENTE UMA DAS FUNÇÕES ACIMA PARA EXECUTAR!")
