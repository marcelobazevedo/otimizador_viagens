"""
Módulo de banco de dados
"""

from .db import init_flights_db, init_cars_db, init_hotels_db
from .models import Flight, CarRental, Hotel

__all__ = [
    'init_flights_db',
    'init_cars_db', 
    'init_hotels_db',
    'Flight',
    'CarRental',
    'Hotel'
]

