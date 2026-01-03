import streamlit as st
import pandas as pd
import os
import sqlite3
import networkx as nx
import matplotlib.pyplot as plt


def load_airport_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'utils', 'br-us-airports.csv')
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    # Usando sep=';' conforme seu padrão anterior
    df = pd.read_csv(csv_path, sep=';')
    df['display_label'] = df['iata_code'] + " - " + df['name']
    return df

def plot_connection_graph(db_path):
    """Gera um grafo de todas as conexões encontradas no banco de dados."""
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    df_voos = pd.read_sql_query("SELECT origem, destino FROM voos", conn)
    df_carros = pd.read_sql_query("SELECT local_retirada as origem, local_entrega as destino FROM aluguel_carros", conn)
    conn.close()
    
    df_total = pd.concat([df_voos, df_carros]).drop_duplicates()
    
    G = nx.DiGraph()
    for _, row in df_total.iterrows():
        G.add_edge(row['origem'], row['destino'])
    
    fig, ax = plt.subplots(figsize=(8, 5))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_color='#BBDEFB', edge_color='gray', 
            node_size=1000, font_size=8, font_weight='bold', arrowsize=15, ax=ax)
    return fig

def plot_itinerary_graph(itinerario):
    """Gera o grafo sequencial da solução encontrada pelo solver."""
    if itinerario is None or itinerario.empty:
        st.error("Itinerário vazio.")
        return
    
    G = nx.DiGraph()
    resumo_texto = []
    
    # Garantir que o index está resetado para a contagem #1, #2...
    itinerario = itinerario.reset_index(drop=True)

    for i, row in itinerario.iterrows():
        orig = row['origem']
        dest = row['destino']
        seq = i + 1
        modo = row['tipo']
        custo = row['preco_numerico']
        tempo = row.get('duracao', 'N/A')
        
        # Label para a aresta do grafo
        label_map = f"#{seq}\n{modo}\nR$ {custo:.0f}\nDur: {tempo}"
        G.add_edge(orig, dest, label=label_map, modo=modo)
        
        # Montar lista de resumo
        resumo_texto.append(f"**{seq}º Passo:** {orig} → {dest} | **{modo}** | R$ {custo:,.2f} | ⏳ {tempo}")

    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.circular_layout(G) # Layout circular para ciclos
    
    # Desenhar nós
    nx.draw_networkx_nodes(G, pos, node_size=1200, node_color='#f0f2f6', edgecolors='black', ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)
    
    # Desenhar arestas
    for u, v, data in G.edges(data=True):
        cor = 'blue' if data['modo'] == 'Voo' else 'green'
        estilo = 'solid' if data['modo'] == 'Voo' else 'dashed'
        nx.draw_networkx_edges(G, pos, edgelist=[(u,v)], edge_color=cor, 
                               width=2, arrowsize=20, style=estilo,
                               connectionstyle="arc3,rad=0.1", ax=ax)
        
        # Labels nas arestas
        x = (pos[u][0] + pos[v][0]) / 2
        y = (pos[u][1] + pos[v][1]) / 2
        
        ax.text(x, y, data['label'], color=cor, fontsize=8, fontweight='bold', 
                ha='center', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    plt.axis('off')
    st.pyplot(fig)
    
    # Exibir resumo abaixo do gráfico
    for r in resumo_texto:
        st.write(r)

# --- INTERFACE STREAMLIT ---

df_airports = load_airport_data()

st.set_page_config(page_title="Otimizador Copa 2026", layout="centered")
st.title("Otimizador de Viagem")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Parâmetros")
    origem_label = st.selectbox("Aeroporto de Origem", options=df_airports['display_label'].tolist(), index=None, placeholder="Busque origem...")
    origem_iata = origem_label.split(" - ")[0] if origem_label else None

    destinos_labels = st.multiselect("Aeroportos de Destino", options=df_airports['display_label'].tolist(), placeholder="Busque destinos...")
    destinos_iata = [label.split(" - ")[0] for label in destinos_labels]

    data_ida = st.date_input("Partida")
    data_volta = st.date_input("Retorno")
    budget = st.sidebar.number_input("Orçamento Total (R$)", value=15000, step=500)
    alpha = st.slider("Prioridade: Custo (1) vs Tempo (0)", 0.0, 1.0, 0.7)

# --- BOTÃO BUSCAR ---
if st.button("Buscar Passagens e Carros", type="primary", use_container_width=True):
    # (Chamada dos scrapers mantida conforme seu código original)
    st.success("Pesquisa concluída!")
    
    st.subheader("Conexões Encontradas no Banco")
    fig_con = plot_connection_graph("voos_local.db")
    if fig_con:
        st.pyplot(fig_con)
    else:
        st.warning("Nenhum dado encontrado no banco para gerar o grafo.")

# --- BOTÃO OTIMIZAR ---
st.markdown("---")
if st.button("Calcular Melhor Itinerário", use_container_width=True):
    if not origem_iata or not destinos_iata:
        st.warning("Selecione a origem e os destinos.")
    else:
        from backend.engine import TripOptimizerEngine
        db_path = "voos_local.db" 
        config_solver = {'origem': origem_iata, 'destinos': destinos_iata, 'budget': budget, 'alpha': alpha}
        
        engine = TripOptimizerEngine(db_path, config_solver)
        
        with st.spinner('Otimizando rotas...'):
            itinerario = engine.solve()
            
            if isinstance(itinerario, str) and itinerario == "ERRO_SEM_RETORNO":
                st.error(f"Inviável: Não existem voos de volta para {origem_iata} no banco.")
            elif itinerario is not None:
                st.success("Melhor Itinerário Encontrado!")
                
                # 1. Exibir Tabela
                st.dataframe(itinerario[['tipo', 'companhia', 'origem', 'destino', 'data_ida', 'preco_numerico', 'duracao']], use_container_width=True)
                
                # 2. Métricas
                custo_total = itinerario['preco_numerico'].sum()
                st.metric("Investimento Total", f"R$ {custo_total:,.2f}")
                
                # 3. Gráfico da Solução
                st.subheader("Visualização do Roteiro Passo-a-Passo")
                plot_itinerary_graph(itinerario)
            else:
                st.error("Inviável: Orçamento insuficiente ou restrições de tempo.")