import sqlite3

DB_NAME = "voos_kayak_detalhado.db"

def relatorio_completo_viagem():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    print(f"\n{'='*100}")
    print(f"{'RESUMO CONSOLIDADO DE VIAGEM (MELHORES PREÇOS POR TRECHO)':^100}")
    print(f"{'='*100}\n")

    # 1. Melhores Voos
    print("--- VOOS MAIS BARATOS ---")
    cursor.execute("SELECT origem, destino, data_ida, preco_bruto FROM voos ORDER BY preco_numerico ASC LIMIT 5")
    for v in cursor.fetchall():
        print(f"Voo: {v[0]} -> {v[1]} | Data: {v[2]} | Preço: {v[3]}")

    # 2. Melhores Aluguéis
    print("\n--- ALUGUÉIS DE CARROS MAIS BARATOS ---")
    try:
        cursor.execute("SELECT local_retirada, local_entrega, categoria, locadora, preco_total FROM aluguel_carros ORDER BY preco_numerico ASC LIMIT 5")
        for c in cursor.fetchall():
            print(f"Carro: {c[0]} -> {c[1]} | {c[2]} ({c[3]}) | Total: {c[4]}")
    except:
        print("[!] Tabela de carros ainda vazia ou não criada.")

    conn.close()
    print(f"\n{'='*100}\n")

if __name__ == "__main__":
    relatorio_completo_viagem()