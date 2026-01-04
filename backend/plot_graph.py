import networkx as nx
import matplotlib.pyplot as plt

def plot_graph(df_voos, df_carros):
    G = nx.DiGraph()
    
    # Adiciona voos
    for _, row in df_voos.iterrows():
        G.add_edge(row['origem'], row['destino'], weight=row['preco_numerico'], type='Voo')
    
    # Adiciona carros (apenas entre cidades diferentes)
    inter_city = df_carros[df_carros['local_retirada'] != df_carros['local_entrega']]
    for _, row in inter_city.iterrows():
        G.add_edge(row['local_retirada'], row['local_entrega'], weight=row['preco_numerico'], type='Carro')
    
    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color='lightblue', edge_color='gray', node_size=800, ax=ax)
    return fig

# No Streamlit:
# st.pyplot(plot_graph(df_voos, df_carros))