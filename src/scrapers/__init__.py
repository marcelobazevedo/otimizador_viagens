"""
Módulo de scrapers para coleta de dados de viagens
"""

from .flights import FlightsScraper
from .cars import CarsScraper
from .hotels import HotelsScraper

__all__ = ['FlightsScraper', 'CarsScraper', 'HotelsScraper']

