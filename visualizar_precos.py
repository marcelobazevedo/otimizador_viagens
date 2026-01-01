import sqlite3
import os

# Usar diretório de dados se existir (Docker), senão usar diretório atual
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "data" if os.path.exists("data") else "."
DB_NAME = os.path.join(DATA_DIR, "voos_local.db")

def consultar_voos_completos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = '''
        SELECT origem, destino, data_ida, data_volta, companhia, 
               hora_saida, hora_chegada, duracao, escalas, preco_bruto 
        FROM voos 
        ORDER BY preco_numerico ASC
    '''
    
    try:
        cursor.execute(query)
        resultados = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"\n[!] Erro de banco de dados: {e}")
        return
    finally:
        conn.close()

    if not resultados:
        print("\n[!] Nenhum dado encontrado no banco.")
        return

    # Definição das larguras das colunas para manter o alinhamento
    # Aumentamos o cabeçalho para incluir a coluna VOLTA
    header = (f"{'ORIG':<5} | {'DEST':<5} | {'IDA':<10} | {'VOLTA':<10} | "
              f"{'CIA':<12} | {'SAÍDA':<6} | {'CHEG':<6} | {'DURAC':<7} | {'ESC':<9} | {'PREÇO'}")
    
    print("\n" + "="*len(header))
    print(header)
    print("-" * len(header))

    for r in resultados:
        origem, destino, ida, volta, cia, saida, chegada, duracao, escalas, preco = r
        
        # Limita o nome da companhia para não quebrar a tabela
        cia_formatada = cia[:12]
        
        print(f"{origem:<5} | {destino:<5} | {ida:<10} | {volta:<10} | "
              f"{cia_formatada:<12} | {saida:<6} | {chegada:<6} | {duracao:<7} | {escalas:<9} | {preco}")
    
    print("=" * len(header) + "\n")

if __name__ == "__main__":
    consultar_voos_completos()