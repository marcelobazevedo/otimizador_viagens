"""
Utilitários para cálculos de distância
"""
import math
import pandas as pd
from src.utils.airports import load_airport_data


def calculate_distance(iata1: str, iata2: str, df_airports: pd.DataFrame = None) -> int:
    """
    Calcula distância aproximada em linha reta entre dois aeroportos (em km)
    Multiplica por 1.3 para aproximar distância rodoviária
    
    Args:
        iata1: Código IATA do primeiro aeroporto
        iata2: Código IATA do segundo aeroporto
        df_airports: DataFrame de aeroportos (opcional, carrega se não fornecido)
    
    Returns:
        Distância rodoviária aproximada em km, ou None se aeroportos não encontrados
    """
    if df_airports is None:
        df_airports = load_airport_data()
    
    coords1 = df_airports[df_airports['iata_code'] == iata1][['latitude_deg', 'longitude_deg']]
    coords2 = df_airports[df_airports['iata_code'] == iata2][['latitude_deg', 'longitude_deg']]
    
    if coords1.empty or coords2.empty:
        return None
    
    lat1, lon1 = coords1.iloc[0]['latitude_deg'], coords1.iloc[0]['longitude_deg']
    lat2, lon2 = coords2.iloc[0]['latitude_deg'], coords2.iloc[0]['longitude_deg']
    
    # Fórmula de Haversine para distância em linha reta
    R = 6371  # Raio da Terra em km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distancia_linha_reta = R * c
    
    # Multiplicar por 1.3 para aproximar distância rodoviária
    distancia_rodoviaria = distancia_linha_reta * 1.3
    return round(distancia_rodoviaria)


def calculate_travel_time(distance_km: int, avg_speed: int = 80) -> tuple:
    """
    Calcula tempo de viagem baseado na distância
    
    Args:
        distance_km: Distância em km
        avg_speed: Velocidade média em km/h (padrão: 80)
    
    Returns:
        Tupla (horas, minutos, string_formatada)
    """
    tempo_total_horas = distance_km / avg_speed
    horas = int(tempo_total_horas)
    minutos = int((tempo_total_horas - horas) * 60)
    tempo_formatado = f"{horas:02d}:{minutos:02d}"
    return horas, minutos, tempo_formatado


def calculate_travel_days(distance_km: int, km_per_day: int = 800) -> int:
    """
    Calcula dias necessários para viagem baseado na distância
    
    Args:
        distance_km: Distância em km
        km_per_day: Quilômetros por dia (padrão: 800)
    
    Returns:
        Número de dias necessários (arredondado para cima)
    """
    return math.ceil(distance_km / km_per_day)

