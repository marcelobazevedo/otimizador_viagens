"""
Modelos de dados (schemas) para o banco de dados
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Flight:
    """Modelo de dados para voos"""
    origem: str
    destino: str
    data_ida: str
    data_volta: Optional[str]
    companhia: str
    preco_bruto: str
    preco_numerico: float
    ida_saida: Optional[str] = None
    ida_chegada: Optional[str] = None
    ida_duracao: Optional[str] = None
    ida_escalas: Optional[str] = None
    volta_saida: Optional[str] = None
    volta_chegada: Optional[str] = None
    volta_duracao: Optional[str] = None
    volta_escalas: Optional[str] = None
    coletado_em: Optional[datetime] = None


@dataclass
class CarRental:
    """Modelo de dados para aluguel de carros"""
    local_retirada: str
    local_entrega: str
    data_inicio: str
    data_fim: str
    categoria: str
    locadora: str
    capacidade: str
    preco_total: str
    preco_numerico: float
    valor_diaria: float
    dias_viagem: Optional[int] = None
    tempo_viagem_horas: Optional[str] = None
    distancia_km: Optional[int] = None
    mesmo_local: bool = False
    coletado_em: Optional[datetime] = None


@dataclass
class Hotel:
    """Modelo de dados para hospedagens"""
    cidade: str
    quartos: int
    adultos: int
    criancas: int
    data_checkin: str
    data_checkout: str
    nome_hotel: str
    tipo_acomodacao: str
    avaliacao: str
    num_avaliacoes: str
    preco_total: str
    preco_numerico: float
    amenidades: str
    coletado_em: Optional[datetime] = None

