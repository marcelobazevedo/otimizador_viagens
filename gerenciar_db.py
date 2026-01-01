"""
Script para gerenciar o banco de dados voos_local.db

Permite visualizar, editar e limpar dados do banco de forma fácil.
"""

import sqlite3
import os
from datetime import datetime

# Detectar caminho do banco
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "data" if os.path.exists("data") else "."
DB_NAME = os.path.join(DATA_DIR, "voos_local.db")

def conectar():
    """Conecta ao banco de dados"""
    return sqlite3.connect(DB_NAME)

def listar_voos(limite=10):
    """Lista os voos mais baratos"""
    conn = conectar()
    cursor = conn.cursor()
    
    print(f"\n{'='*100}")
    print(f"{'VOOS MAIS BARATOS':^100}")
    print(f"{'='*100}\n")
    
    query = """
        SELECT origem, destino, data_ida, companhia, preco_bruto, hora_saida, duracao, escalas
        FROM voos
        ORDER BY preco_numerico ASC
        LIMIT ?
    """
    
    cursor.execute(query, (limite,))
    voos = cursor.fetchall()
    
    if not voos:
        print("Nenhum voo encontrado no banco de dados.")
    else:
        for i, voo in enumerate(voos, 1):
            print(f"{i}. {voo[0]} → {voo[1]}")
            print(f"   Data: {voo[2]} | Companhia: {voo[3]}")
            print(f"   Preço: {voo[4]} | Saída: {voo[5]} | Duração: {voo[6]}")
            print(f"   Escalas: {voo[7]}")
            print()
    
    conn.close()
    return len(voos)

def listar_carros(limite=10):
    """Lista os carros mais baratos"""
    conn = conectar()
    cursor = conn.cursor()
    
    print(f"\n{'='*100}")
    print(f"{'ALUGUEL DE CARROS MAIS BARATOS':^100}")
    print(f"{'='*100}\n")
    
    query = """
        SELECT local_retirada, local_entrega, data_inicio, data_fim, 
               categoria, locadora, preco_total
        FROM aluguel_carros
        ORDER BY preco_numerico ASC
        LIMIT ?
    """
    
    cursor.execute(query, (limite,))
    carros = cursor.fetchall()
    
    if not carros:
        print("Nenhum aluguel de carro encontrado no banco de dados.")
    else:
        for i, carro in enumerate(carros, 1):
            print(f"{i}. {carro[0]} → {carro[1]}")
            print(f"   Período: {carro[2]} até {carro[3]}")
            print(f"   Veículo: {carro[4]} ({carro[5]})")
            print(f"   Preço Total: {carro[6]}")
            print()
    
    conn.close()
    return len(carros)

def estatisticas():
    """Mostra estatísticas do banco de dados"""
    conn = conectar()
    cursor = conn.cursor()
    
    print(f"\n{'='*100}")
    print(f"{'ESTATÍSTICAS DO BANCO DE DADOS':^100}")
    print(f"{'='*100}\n")
    
    # Total de voos
    cursor.execute("SELECT COUNT(*) FROM voos")
    total_voos = cursor.fetchone()[0]
    print(f"📊 Total de voos: {total_voos}")
    
    # Total de carros
    cursor.execute("SELECT COUNT(*) FROM aluguel_carros")
    total_carros = cursor.fetchone()[0]
    print(f"🚗 Total de aluguéis de carros: {total_carros}")
    
    # Voo mais barato
    if total_voos > 0:
        cursor.execute("SELECT origem, destino, preco_bruto FROM voos ORDER BY preco_numerico ASC LIMIT 1")
        voo_barato = cursor.fetchone()
        print(f"\n✈️  Voo mais barato: {voo_barato[0]} → {voo_barato[1]} por {voo_barato[2]}")
    
    # Carro mais barato
    if total_carros > 0:
        cursor.execute("SELECT local_retirada, categoria, preco_total FROM aluguel_carros ORDER BY preco_numerico ASC LIMIT 1")
        carro_barato = cursor.fetchone()
        print(f"🚗 Carro mais barato: {carro_barato[1]} em {carro_barato[0]} por {carro_barato[2]}")
    
    # Rotas mais pesquisadas
    if total_voos > 0:
        print(f"\n📍 Rotas mais pesquisadas:")
        cursor.execute("""
            SELECT origem, destino, COUNT(*) as total 
            FROM voos 
            GROUP BY origem, destino 
            ORDER BY total DESC 
            LIMIT 5
        """)
        for rota in cursor.fetchall():
            print(f"   • {rota[0]} → {rota[1]}: {rota[2]} opções")
    
    conn.close()

def limpar_dados_antigos(dias=7):
    """Remove dados mais antigos que X dias"""
    conn = conectar()
    cursor = conn.cursor()
    
    # Limpar voos
    cursor.execute(f"""
        DELETE FROM voos 
        WHERE coletado_em < datetime('now', '-{dias} days')
    """)
    voos_removidos = cursor.rowcount
    
    # Limpar carros
    cursor.execute(f"""
        DELETE FROM aluguel_carros 
        WHERE coletado_em < datetime('now', '-{dias} days')
    """)
    carros_removidos = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"\n🗑️  Removidos {voos_removidos} voos e {carros_removidos} carros com mais de {dias} dias.")

def limpar_tudo():
    """Remove todos os dados do banco"""
    resposta = input("\n⚠️  Tem certeza que deseja limpar TODOS os dados? (sim/não): ")
    if resposta.lower() == 'sim':
        conn = conectar()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM voos")
        voos_removidos = cursor.rowcount
        
        cursor.execute("DELETE FROM aluguel_carros")
        carros_removidos = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"\n🗑️  Banco limpo! Removidos {voos_removidos} voos e {carros_removidos} carros.")
    else:
        print("\n❌ Operação cancelada.")

def menu():
    """Menu interativo"""
    while True:
        print(f"\n{'='*100}")
        print(f"{'GERENCIADOR DO BANCO DE DADOS - voos_local.db':^100}")
        print(f"{'='*100}\n")
        print(f"Banco: {DB_NAME}\n")
        print("1. 📊 Ver estatísticas")
        print("2. ✈️  Listar voos mais baratos")
        print("3. 🚗 Listar carros mais baratos")
        print("4. 🗑️  Limpar dados antigos (7 dias)")
        print("5. ⚠️  Limpar TODOS os dados")
        print("0. 🚪 Sair")
        
        opcao = input("\nEscolha uma opção: ")
        
        if opcao == "1":
            estatisticas()
        elif opcao == "2":
            limite = input("Quantos voos mostrar? (padrão: 10): ")
            limite = int(limite) if limite.isdigit() else 10
            listar_voos(limite)
        elif opcao == "3":
            limite = input("Quantos carros mostrar? (padrão: 10): ")
            limite = int(limite) if limite.isdigit() else 10
            listar_carros(limite)
        elif opcao == "4":
            limpar_dados_antigos()
        elif opcao == "5":
            limpar_tudo()
        elif opcao == "0":
            print("\n👋 Até logo!")
            break
        else:
            print("\n❌ Opção inválida!")
        
        input("\nPressione ENTER para continuar...")

if __name__ == "__main__":
    # Verificar se banco existe
    if not os.path.exists(DB_NAME):
        print(f"⚠️  Banco de dados não encontrado em: {DB_NAME}")
        print("Execute os scrapers primeiro para criar o banco.")
    else:
        menu()
