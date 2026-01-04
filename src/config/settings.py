"""
Configurações centralizadas do projeto
"""
import os
from pathlib import Path

# Diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Configuração de diretório de dados
# Prioridade: /app/data (Docker) > data/ (local) > . (raiz)
if os.path.exists("/app/data"):
    DATA_DIR = Path("/app/data")
elif os.path.exists("data"):
    DATA_DIR = Path("data")
else:
    DATA_DIR = BASE_DIR

# Nome do banco de dados
DB_NAME = DATA_DIR / "voos_local.db"

# Diretório de utilitários
UTILS_DIR = BASE_DIR / "utils"

# Arquivo CSV de aeroportos
AIRPORTS_CSV = UTILS_DIR / "br-us-airports.csv"

# Configurações de scraping
SCRAPING_DELAY_MIN = 10
SCRAPING_DELAY_MAX = 15
SCRAPING_WAIT_TIME = 20  # Tempo de espera para bypass de segurança

# Configurações de viagem
DEFAULT_KM_PER_DAY = 800  # km por dia de viagem
DEFAULT_AVG_SPEED = 80  # km/h velocidade média

