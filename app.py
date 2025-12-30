import streamlit as st
import pandas as pd
import os

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

# --- EXECUÇÃO ---
if st.button("Calcular Melhor Itinerário", type="primary"):
    if not origem_iata or not destinos_iata:
        st.warning("Por favor, selecione a origem e ao menos um destino.")
    else:
        with st.spinner('Executando modelo de otimização...'):
            # Aqui entrará sua Engine de Otimização
            st.info(f"Otimizando de {origem_iata} para {destinos_iata}")
            # simulando resultado
            st.success("Itinerário gerado com sucesso!")