import streamlit as st
import pandas as pd
import os
import subprocess
import sys

# Importar os scrapers
from scraper_local import rodar_crawler as buscar_passagens, init_db as init_db_voos
from scraper_aluguel_carros import rodar_crawler as buscar_carros, init_db as init_db_carros

# --- CONFIGURAÇÃO E CARREGAMENTO DE DADOS ---
@st.cache_data
def load_airport_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Ajuste o nome do arquivo para o consolidado que geramos
    csv_path = os.path.join(script_dir, 'utils', 'br-us-airports.csv')
    
    if not os.path.exists(csv_path):
        st.error(f"Arquivo não encontrado: {csv_path}")
        return pd.DataFrame()

    # Como você usou ';' no seu exemplo, mantive o separador
    df = pd.read_csv(csv_path, sep=';')
    
    # Criar label de exibição: "Cidade - Nome do Aeroporto (IATA)"
    df['display_label'] = (
        df['iata_code'] + " - " + 
        df['name']
    )
    return df

df_airports = load_airport_data()

st.title("Otimizador de Viagem")

st.sidebar.header("Parâmetros da Viagem")


#origem_label deve ser selectbox e guardar o dataframe selecionado  
origem_label = st.sidebar.selectbox(
    "Aeroporto de Origem",
    options=df_airports['display_label'].tolist(),
    index=None,
    placeholder="Digite para buscar...",
    key="origem_select"
)

# Guardar o dataframe da linha selecionada
origem_df = None
origem_iata = None
if origem_label:
    # Encontrar a linha correspondente no dataframe
    origem_df = df_airports[df_airports['display_label'] == origem_label].iloc[0]
    # Extrair o código IATA (primeira parte antes do " - ")
    origem_iata = origem_df['iata_code']
    print(f"Origem selecionada: {origem_iata}")

destinos_labels = st.sidebar.multiselect(
    "Aeroporto de Destinos",
    options=df_airports['display_label'].tolist(),
    placeholder="Busque um ou mais aeroportos...",
    key="destino_select"
)

# Guardar os dataframes dos destinos selecionados
destinos_df = []
destinos_iata = []
if destinos_labels:
    for destino_label in destinos_labels:        
        destino_row = df_airports[df_airports['display_label'] == destino_label].iloc[0]
        destinos_df.append(destino_row)
        destinos_iata.append(destino_row['iata_code'])
    print(f"Destinos selecionados: {destinos_iata}") 


col1, col2 = st.sidebar.columns(2)
with col1:
    data_ida = st.date_input("Partida")
with col2:
    data_volta = st.date_input("Retorno")

budget = st.sidebar.number_input("Orçamento Total (R$)", value=15000, step=500)
# alpha = st.sidebar.slider("Prioridade Custo vs Tempo", 0.0, 1.0, 0.7, 
#                           help="0 = Prioriza Tempo, 1 = Prioriza Custo")

# --- BOTÕES DE AÇÃO ---
st.markdown("---")

# Botão para executar o scraping
if st.button("🔍 Buscar Passagens e Carros", type="primary", use_container_width=True):
    if not origem_iata or not destinos_iata:
        st.warning("Por favor, selecione a origem e ao menos um destino.")
    else:
        # Converter datas para formato string YYYY-MM-DD
        data_ida_str = data_ida.strftime('%Y-%m-%d')
        data_volta_str = data_volta.strftime('%Y-%m-%d')
        
        with st.spinner('Executando pesquisa de passagens e carros...'):
            try:
                # Inicializar bancos de dados
                init_db_voos()
                init_db_carros()
                
                st.info(f"🔍 Buscando passagens de {origem_iata} para {', '.join(destinos_iata)}")
                
                # 1. Buscar passagens
                st.write("### Etapa 1: Buscando passagens aéreas")
                st.write(f"- Origem: {origem_iata}")
                st.write(f"- Destinos: {', '.join(destinos_iata)}")
                st.write(f"- Período: {data_ida_str} a {data_volta_str}")
                
                # Executar busca de passagens em processo separado para evitar problemas
                with st.status("Pesquisando passagens...", expanded=True) as status:
                    st.write("Iniciando scraper de passagens...")
                    buscar_passagens(
                        origem=origem_iata,
                        destinos=destinos_iata,
                        data_ida=data_ida_str,
                        data_volta=data_volta_str
                    )
                    status.update(label="Passagens coletadas!", state="complete")
                
                # 2. Buscar aluguel de carros
                st.write("### Etapa 2: Buscando aluguel de carros")
                st.write(f"- Locais: {', '.join(destinos_iata)}")
                st.write(f"- Período: {data_ida_str} a {data_volta_str}")
                
                with st.status("Pesquisando aluguel de carros...", expanded=True) as status:
                    st.write("Iniciando scraper de carros...")
                    buscar_carros(
                        destinos=destinos_iata,
                        data_inicio=data_ida_str,
                        data_fim=data_volta_str
                    )
                    status.update(label="Carros coletados!", state="complete")
                
                st.success("✅ Pesquisa concluída! Dados salvos no banco de dados.")
                st.info("💡 Use o arquivo visualizar_precos.py para ver os resultados ou acesse o banco voos_local.db")
                
            except Exception as e:
                st.error(f"Erro durante a execução: {str(e)}")
                st.exception(e)

# Botão para calcular melhor itinerário (será implementado futuramente)
st.markdown("---")
if st.button("📊 Calcular Melhor Itinerário", use_container_width=True):
    if not origem_iata or not destinos_iata:
        st.warning("Por favor, selecione a origem e ao menos um destino.")
    else:
        st.info("🚧 Funcionalidade em desenvolvimento. Esta função irá otimizar o itinerário com base nos dados coletados.")
        st.write(f"Origem: {origem_iata}")
        st.write(f"Destinos: {', '.join(destinos_iata)}")
        st.write(f"Orçamento: R$ {budget:,.2f}")