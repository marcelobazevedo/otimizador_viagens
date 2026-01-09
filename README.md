# Otimizador de Viagens

Sistema inteligente de otimização multimodal de rotas de viagem que utiliza **algoritmos genéticos (NSGA-II)** para encontrar as melhores combinações de voos e aluguel de carros. O sistema coleta dados através de web scraping (Google Flights e Kayak) e oferece uma interface Streamlit interativa com visualização em mapas para planejamento completo de viagens.

## 🎯 Principais Funcionalidades

- **Otimização Multiobjetivo**: Balanceamento entre custo e tempo usando NSGA-II
- **Web Scraping Inteligente**: Coleta automática de preços de voos e carros
- **Visualização Interativa**: Mapas com rotas e conexões
- **Planejamento Multimodal**: Combina voos e aluguel de carros
- **Configuração Flexível**: Ajuste de orçamento e preferências (custo vs tempo)

## Estrutura do Projeto

``` text
otimizador_viagens/
├── docs/                        # Documentações
│   └── diagrama-sequencia.png  # Diagrama de sequência do sistema
├── backend/                     # Motor de otimização
│   ├── engine.py               # Algoritmo NSGA-II e solver
│   └── plot_graph.py           # Visualização de grafos
├── utils/                       # Utilitários
│   └── br-us-airports.csv      # Base de dados de aeroportos BR/US
├── data/                        # Dados (Docker)
│   └── voos_local.db           # Banco SQLite (gerado automaticamente)
├── app.py                       # Interface Streamlit principal
├── app-itinerario.py           # App focado em otimização
├── scraper_local.py            # Scraper Google Flights (voos)
├── scraper_aluguel_carros.py   # Scraper Kayak (carros)
├── requirements.txt            # Dependências Python
├── Dockerfile.streamlit        # Dockerfile para Streamlit
├── docker-compose.yml          # Configuração Docker Compose
└── .dockerignore               # Arquivos ignorados no build
```

## Funcionalidades Detalhadas

### 🔍 Coleta de Dados (Web Scraping)
- **Scraping de Voos**: Google Flights com delays aleatórios e simulação de comportamento humano
- **Scraping de Carros**: Kayak com suporte a retirada/devolução em locais diferentes
- **Base de Aeroportos**: +200 aeroportos Brasil/Estados Unidos com coordenadas GPS
- **Banco de Dados SQLite**: Armazenamento persistente com histórico de preços

### 🧠 Otimização de Itinerários
- **Algoritmo NSGA-II**: Otimização multiobjetivo (custo × tempo)
- **Configuração de Alpha (α)**: Peso entre custo (α=1.0) e tempo (α=0.0)
- **Restrições Inteligentes**: Orçamento, continuidade de rota, viabilidade temporal
- **Frente de Pareto**: Múltiplas soluções ótimas para escolha do usuário

### 🗺️ Visualização e Interface
- **Mapas Interativos**: Folium com rotas de voos e carros
- **Gráfico de Conexões**: Todas as rotas disponíveis no banco
- **Análise de Preços**: Tabelas detalhadas com métricas de voos e carros
- **Interface Intuitiva**: Streamlit com abas para scraping e otimização

## Pré-requisitos

- Docker e Docker Compose instalados
- Python 3.12+ (para execução local do scraper)
- Playwright (para o scraper)

## Diagrama de Sequência
![Diagrama de Sequência do Sistema](docs/images/diagrama-sequencia.png)

O diagrama mostra o fluxo completo:
1. Usuário configura parâmetros (origem, destinos, datas, orçamento)
2. Sistema executa scrapers (voos e carros) usando Playwright
3. Dados são salvos no banco SQLite
4. Engine NSGA-II processa otimização multiobjetivo
5. Resultados são exibidos em mapas e tabelas interativas

## Instalação e Configuração

### 1. Clone o repositório
```sh
git clone git@github.com:marcelobazevedo/otimizador_viagens.git

cd otimizador_viagens
```

### 2. Configurar variáveis de ambiente


Crie um arquivo `.env` na raiz do projeto (opcional, apenas se usar API Amadeus):

``` bash
AMADEUS_TOKEN=seu_token_aqui
```

### 3. Executar aplicação Streamlit com Docker

#### Construir e iniciar o container:

``` bash
docker-compose up -d streamlit-app
```

#### Ver logs:

``` bash
docker-compose logs -f streamlit-app
```

#### Parar o serviço:

``` bash
docker-compose down
```

#### Reconstruir após mudanças:

``` bash
docker-compose build streamlit-app
docker-compose up -d streamlit-app
```

A aplicação estará disponível em: `http://localhost:8501`


### 4. Configurar o Scraper

Execução manual do scraper.

#### Instalar dependências do scraper:

# Criar ambiente virtual (recomendado)
``` bash
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

# Instalar dependências

``` bash
pip install -r requirements.txt
pip install playwright pandas python-dotenv
```


# Instalar navegador Chromium do Playwright
``` bash
playwright install chromium
``` 

#### Configurar rotas no scraper:

Edite o arquivo `scraper_local.py` e configure as rotas na variável `ROTAS`:

``` json
ROTAS = [
    {'origem': 'GYN', 'destino': 'ATL', 'data': '2025-05-15'},
    {'origem': 'ATL', 'destino': 'BSB', 'data': '2025-05-20'},
    # Adicione quantas rotas quiser
]
```

#### Executar o scraper:

``` bash
python scraper_local.py
```

O scraper irá:
- Abrir o navegador (headless=False para evitar detecção)
- Navegar pelo Google Flights
- Coletar dados de voos
- Salvar no banco `voos_local.db`

**⚠️ Importante**: O scraper usa `headless=False` para evitar detecção pelo Google. Certifique-se de ter um display disponível na VPS ou configure X11 forwarding.

## Agendamento do Scraper na VPS

Para executar o scraper periodicamente, configure um cron job:

### 1. Editar crontab:

crontab -e
### 2. Adicionar linha para executar diariamente às 2h da manhã:

``` bash
0 2 * * *
cd /caminho/para/otimizador_viagens && /usr/bin/python3 scraper_local.py >> /var/log/scraper.log 2>&1
```

Ou executar a cada 6 horas:

``` bash
0 */6 * * *
cd /caminho/para/otimizador_viagens && /usr/bin/python3 scraper_local.py >> /var/log/scraper.log 2>&1
```

### Estrutura das Tabelas do Banco de Dados

#### Tabela `voos`:
- `id`: ID único do registro
- `origem`: Código IATA do aeroporto de origem
- `destino`: Código IATA do aeroporto de destino
- `data_voo`: Data do voo (formato: YYYY-MM-DD)
- `companhia`: Nome da companhia aérea
- `duracao`: Duração do voo (ex: "5h 30m")
- `duracao_min`: Duração em minutos (para otimização)
- `preco_bruto`: Preço em formato texto (ex: "R$ 1.500,00")
- `preco_numerico`: Preço em formato numérico (para ordenação)
- `coletado_em`: Timestamp de quando o dado foi coletado

#### Tabela `aluguel_carros`:
- `id`: ID único do registro
- `local_retirada`: Código IATA do local de retirada
- `local_entrega`: Código IATA do local de devolução
- `data_inicio`: Data de retirada (YYYY-MM-DD)
- `data_fim`: Data de devolução (YYYY-MM-DD)
- `categoria`: Categoria do veículo (Compact, SUV, etc.)
- `locadora`: Nome da locadora
- `capacidade`: Capacidade de passageiros/bagagens
- `preco_total`: Preço total do aluguel
- `preco_numerico`: Preço numérico (para ordenação)
- `valor_diaria`: Valor da diária calculado
- `dias_viagem`: Número de dias do aluguel
- `tempo_viagem_horas`: Tempo estimado de viagem
- `distancia_km`: Distância entre cidades
- `mesmo_local`: Flag indicando se retirada = devolução
- `coletado_em`: Timestamp da coleta

### Consultar dados:

``` bash
sqlite3 voos_local.db
-- Ver todos os voos
SELECT * FROM voos;
``` 

``` bash
-- Ver voos de uma rota específica
SELECT * FROM voos WHERE origem='GYN' AND destino='ATL';
``` 

``` bash
-- Ver voos mais baratos
SELECT * FROM voos ORDER BY preco_numerico ASC LIMIT 10;
``` 

``` bash
-- Ver carros disponíveis para um destino
SELECT * FROM aluguel_carros WHERE local_retirada='ATL';
``` 

## 🧪 Como Usar o Otimizador

### Interface Streamlit

1. **Aba "Scraper de Passagens"**:
   - Configure origem, destinos e datas
   - Execute os scrapers para coletar dados
   - Visualize preços de voos e carros

2. **Aba "Otimizador de Itinerário"**:
   - Configure orçamento máximo
   - Ajuste o Alpha (α):
     - α = 1.0: Prioriza menor custo
     - α = 0.5: Balanceado
     - α = 0.0: Prioriza menor tempo
   - Execute a otimização (NSGA-II)
   - Visualize:
     - Mapa interativo com rotas
     - Frente de Pareto com soluções
     - Tabela detalhada do itinerário

### Parâmetros do Algoritmo NSGA-II

- **População**: 100 indivíduos
- **Gerações**: 50 iterações
- **Operadores**:
  - Crossover: Two-Point (prob=0.9)
  - Mutação: Bit-flip (prob=0.1)
- **Objetivos**: Minimizar custo e tempo
- **Restrições**: Orçamento, continuidade de rota

## Configuração Avançada

### Alterar porta do Streamlit

Edite `docker-compose.yml`:

``` yml
ports:
  - "8080:8501"  # Mude 8080 para a porta desejada
```

### Volumes Docker

O docker-compose monta os seguintes volumes:
- `./utils`: Base de dados de aeroportos (somente leitura)
- `./voos_local.db`: Banco de dados SQLite (leitura/escrita)

## Notas Importantes

- O scraper usa delays aleatórios para simular comportamento humano
- O Google pode detectar e bloquear scraping excessivo
- Recomenda-se executar o scraper com moderação (1-2 vezes por dia)
- O banco de dados é compartilhado entre o scraper e a aplicação Streamlit
>>>>>>> origin/cria-interface-web
