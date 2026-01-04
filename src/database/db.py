"""
Funções de inicialização e operações do banco de dados
"""
import sqlite3
from pathlib import Path
from src.config.settings import DB_NAME


def get_connection():
    """Retorna uma conexão com o banco de dados"""
    # Garantir que o diretório existe
    DB_NAME.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_NAME))


def init_flights_db():
    """Inicializa a tabela de voos"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT, destino TEXT, data_ida TEXT, data_volta TEXT,
            companhia TEXT, preco_bruto TEXT, preco_numerico REAL,
            ida_saida TEXT, ida_chegada TEXT, ida_duracao TEXT, ida_escalas TEXT,
            volta_saida TEXT, volta_chegada TEXT, volta_duracao TEXT, volta_escalas TEXT,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def init_cars_db():
    """Inicializa a tabela de aluguel de carros"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aluguel_carros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_retirada TEXT, local_entrega TEXT,
            data_inicio TEXT, data_fim TEXT,
            categoria TEXT, locadora TEXT, capacidade TEXT,
            preco_total TEXT, preco_numerico REAL,
            valor_diaria REAL,
            dias_viagem INTEGER,
            tempo_viagem_horas TEXT,
            distancia_km INTEGER,
            mesmo_local INTEGER,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def init_hotels_db():
    """Inicializa a tabela de hospedagens"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hospedagem (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cidade TEXT,
            quartos INTEGER,
            adultos INTEGER,
            criancas INTEGER,
            data_checkin TEXT,
            data_checkout TEXT,
            nome_hotel TEXT,
            tipo_acomodacao TEXT,
            avaliacao TEXT,
            num_avaliacoes TEXT,
            preco_total TEXT,
            preco_numerico REAL,
            amenidades TEXT,
            coletado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def init_all_databases():
    """Inicializa todas as tabelas do banco de dados"""
    init_flights_db()
    init_cars_db()
    init_hotels_db()

