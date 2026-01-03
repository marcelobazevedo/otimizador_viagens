import sqlite3
import os

# Usar diretório de dados se existir (Docker), senão usar diretório atual
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "data" if os.path.exists("data") else "."
DB_NAME = os.path.join(DATA_DIR, "voos_local.db")

def limpar_duplicatas():
    """Remove registros duplicados mantendo apenas o mais recente de cada grupo"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    print("=== LIMPANDO DUPLICATAS ===")
    
    # Contar total antes
    cursor.execute("SELECT COUNT(*) FROM voos")
    total_antes = cursor.fetchone()[0]
    print(f"Total de voos antes: {total_antes}")
    
    # Remover duplicatas mantendo apenas o registro com ID mais recente
    cursor.execute('''
        DELETE FROM voos
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM voos
            GROUP BY origem, destino, data_ida, data_volta, companhia, hora_saida, hora_chegada
        )
    ''')
    
    removidos = cursor.rowcount
    conn.commit()
    
    # Contar total depois
    cursor.execute("SELECT COUNT(*) FROM voos")
    total_depois = cursor.fetchone()[0]
    
    print(f"Total de voos depois: {total_depois}")
    print(f"Registros duplicados removidos: {removidos}")
    
    # Otimizar o banco de dados
    cursor.execute("VACUUM")
    conn.commit()
    conn.close()
    
    print("\n✅ Limpeza concluída!")

if __name__ == "__main__":
    limpar_duplicatas()
