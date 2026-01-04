"""
Utilitários para trabalhar com dados de aeroportos
"""
import pandas as pd
from pathlib import Path
from src.config.settings import AIRPORTS_CSV


def load_airport_data():
    """
    Carrega os dados de aeroportos do arquivo CSV
    
    Returns:
        DataFrame com dados de aeroportos, incluindo coluna 'display_label'
    """
    if not AIRPORTS_CSV.exists():
        raise FileNotFoundError(f"Arquivo de aeroportos não encontrado: {AIRPORTS_CSV}")
    
    df = pd.read_csv(AIRPORTS_CSV, sep=';')
    
    # Criar label de exibição: "IATA - Nome do Aeroporto"
    df['display_label'] = (
        df['iata_code'] + " - " + 
        df['name']
    )
    return df


def get_airport_info(iata_code: str, df_airports: pd.DataFrame = None):
    """
    Obtém informações de um aeroporto pelo código IATA
    
    Args:
        iata_code: Código IATA do aeroporto
        df_airports: DataFrame de aeroportos (opcional, carrega se não fornecido)
    
    Returns:
        Series com informações do aeroporto ou None se não encontrado
    """
    if df_airports is None:
        df_airports = load_airport_data()
    
    result = df_airports[df_airports['iata_code'] == iata_code.upper()]
    return result.iloc[0] if not result.empty else None

