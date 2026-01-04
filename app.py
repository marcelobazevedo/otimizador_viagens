import streamlit as st
import pandas as pd
import os
import sqlite3
import math
import networkx as nx
import matplotlib.pyplot as plt
from datetime import date, datetime, timedelta
import folium
from streamlit_folium import st_folium

# Importar os scrapers
from scraper_local import rodar_crawler as buscar_passagens, init_db as init_db_voos
from scraper_aluguel_carros import rodar_crawler as buscar_carros, init_db as init_db_carros

# --- CONFIGURAÇÃO DE BANCO DE DADOS ---
DATA_DIR = "/app/data" if os.path.exists("/app/data") else "data" if os.path.exists("data") else "."
DB_NAME = os.path.join(DATA_DIR, "voos_local.db")

# --- CONFIGURAÇÃO E CARREGAMENTO DE DADOS ---
@st.cache_data
def load_airport_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'utils', 'br-us-airports.csv')
    
    if not os.path.exists(csv_path):
        st.error(f"Arquivo não encontrado: {csv_path}")
        return pd.DataFrame()

    df = pd.read_csv(csv_path, sep=';')
    
    # Criar label de exibição: "IATA - Nome do Aeroporto"
    df['display_label'] = (
        df['iata_code'] + " - " + 
        df['name']
    )
    return df

# --- FUNÇÕES DE MAPA ---
def plot_connection_graph_map(db_path, df_airports):
    """Gera um mapa com todas as conexões encontradas no banco de dados."""
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    df_voos = pd.read_sql_query("SELECT origem, destino FROM voos", conn)
    df_carros = pd.read_sql_query("SELECT local_retirada as origem, local_entrega as destino FROM aluguel_carros", conn)
    conn.close()
    
    df_total = pd.concat([df_voos, df_carros]).drop_duplicates()
    
    if df_total.empty:
        return None
    
    # Obter coordenadas de todos os aeroportos únicos
    aeroportos_unicos = set(df_total['origem'].tolist() + df_total['destino'].tolist())
    coords_dict = {}
    
    for iata in aeroportos_unicos:
        airport_info = df_airports[df_airports['iata_code'] == iata]
        if not airport_info.empty:
            coords_dict[iata] = {
                'lat': airport_info.iloc[0]['latitude_deg'],
                'lon': airport_info.iloc[0]['longitude_deg'],
                'name': airport_info.iloc[0]['name']
            }
    
    if not coords_dict:
        return None
    
    # Calcular centro do mapa
    avg_lat = sum(c['lat'] for c in coords_dict.values()) / len(coords_dict)
    avg_lon = sum(c['lon'] for c in coords_dict.values()) / len(coords_dict)
    
    # Criar mapa
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=3)
    
    # Adicionar marcadores para cada aeroporto
    for iata, info in coords_dict.items():
        folium.Marker(
            location=[info['lat'], info['lon']],
            popup=f"{iata} - {info['name']}",
            tooltip=iata,
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)
    
    # Adicionar linhas para cada conexão
    for _, row in df_total.iterrows():
        orig = row['origem']
        dest = row['destino']
        
        if orig in coords_dict and dest in coords_dict:
            folium.PolyLine(
                locations=[
                    [coords_dict[orig]['lat'], coords_dict[orig]['lon']],
                    [coords_dict[dest]['lat'], coords_dict[dest]['lon']]
                ],
                color='gray',
                weight=2,
                opacity=0.6,
                popup=f"{orig} → {dest}"
            ).add_to(m)
    
    return m

def plot_itinerary_graph_map(itinerario, df_airports):
    """Gera o mapa do itinerário sequencial da solução encontrada pelo solver."""
    if itinerario is None or itinerario.empty:
        return None
    
    # Garantir que o index está resetado
    itinerario = itinerario.reset_index(drop=True)
    
    # Obter coordenadas de todos os aeroportos do itinerário
    aeroportos_unicos = set(itinerario['origem'].tolist() + itinerario['destino'].tolist())
    coords_dict = {}
    
    for iata in aeroportos_unicos:
        if pd.isna(iata) or not iata:
            continue
        airport_info = df_airports[df_airports['iata_code'] == iata]
        if not airport_info.empty:
            lat = airport_info.iloc[0]['latitude_deg']
            lon = airport_info.iloc[0]['longitude_deg']
            # Verificar se as coordenadas são válidas
            if pd.notna(lat) and pd.notna(lon) and isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                coords_dict[iata] = {
                    'lat': float(lat),
                    'lon': float(lon),
                    'name': airport_info.iloc[0]['name']
                }
    
    if not coords_dict:
        return None
    
    # Calcular centro do mapa
    avg_lat = sum(c['lat'] for c in coords_dict.values()) / len(coords_dict)
    avg_lon = sum(c['lon'] for c in coords_dict.values()) / len(coords_dict)
    
    # Criar mapa
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=4, tiles='OpenStreetMap')
    
    # Cores para diferentes tipos de transporte
    cores = {
        'Voo': 'blue',
        'Carro': 'green'
    }
    
    # Adicionar marcadores e linhas sequenciais
    aeroportos_adicionados = set()
    
    for i, row in itinerario.iterrows():
        orig = row['origem']
        dest = row['destino']
        seq = i + 1
        modo = row['tipo']
        custo = row['preco_numerico']
        tempo = row.get('duracao', 'N/A')
        
        if orig in coords_dict and dest in coords_dict:
            cor = cores.get(modo, 'gray')
            
            # Adicionar marcador de origem (se ainda não foi adicionado)
            if orig not in aeroportos_adicionados:
                cor_icone = 'red' if i == 0 else 'blue'
                folium.Marker(
                    location=[coords_dict[orig]['lat'], coords_dict[orig]['lon']],
                    popup=folium.Popup(f"<b>{orig}</b><br>{coords_dict[orig]['name']}", max_width=200),
                    tooltip=f"{orig}",
                    icon=folium.Icon(color=cor_icone, icon='info-sign')
                ).add_to(m)
                aeroportos_adicionados.add(orig)
            
            # Adicionar marcador de destino
            if dest not in aeroportos_adicionados:
                cor_icone = 'green' if i == len(itinerario) - 1 else 'blue'
                folium.Marker(
                    location=[coords_dict[dest]['lat'], coords_dict[dest]['lon']],
                    popup=folium.Popup(f"<b>{dest}</b><br>{coords_dict[dest]['name']}<br>Passo #{seq}", max_width=200),
                    tooltip=f"{dest}",
                    icon=folium.Icon(color=cor_icone, icon='info-sign')
                ).add_to(m)
                aeroportos_adicionados.add(dest)
            
            # Adicionar linha com informações
            popup_text = f"""
            <b>Passo {seq}: {orig} → {dest}</b><br>
            <b>Tipo:</b> {modo}<br>
            <b>Custo:</b> R$ {custo:,.2f}<br>
            <b>Duração:</b> {tempo}
            """
            
            folium.PolyLine(
                locations=[
                    [coords_dict[orig]['lat'], coords_dict[orig]['lon']],
                    [coords_dict[dest]['lat'], coords_dict[dest]['lon']]
                ],
                color=cor,
                weight=4 if modo == 'Voo' else 3,
                opacity=0.8,
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"#{seq} {modo}: {orig} → {dest}"
            ).add_to(m)
    
    # Adicionar legenda
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: 90px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Legenda:</b></p>
    <p><span style="color:blue">━━━</span> Voo</p>
    <p><span style="color:green">━━━</span> Carro</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def plot_connection_graph(db_path, df_airports):
    """Gera um mapa com todas as conexões encontradas no banco de dados."""
    m = plot_connection_graph_map(db_path, df_airports)
    if m:
        st_folium(m, width=700, height=500)
    else:
        st.warning("Nenhum dado encontrado no banco para gerar o mapa.")

def plot_itinerary_graph(itinerario, df_airports):
    """Gera o mapa do itinerário sequencial da solução encontrada pelo solver."""
    if itinerario is None or itinerario.empty:
        st.error("Itinerário vazio.")
        return
    
    resumo_texto = []
    itinerario = itinerario.reset_index(drop=True)

    for i, row in itinerario.iterrows():
        orig = row['origem']
        dest = row['destino']
        seq = i + 1
        modo = row['tipo']
        custo = row['preco_numerico']
        tempo = row.get('duracao', 'N/A')
        
        resumo_texto.append(f"**{seq}º Passo:** {orig} → {dest} | **{modo}** | R$ {custo:,.2f} | ⏳ {tempo}")

    # Plotar mapa
    try:
        m = plot_itinerary_graph_map(itinerario, df_airports)
        if m is not None:
            # Usar st_folium com parâmetros explícitos
            st_folium(m, width=700, height=500, returned_objects=[])
        else:
            st.error("Não foi possível gerar o mapa do itinerário. Verifique se os aeroportos têm coordenadas válidas.")
            st.info(f"Aeroportos no itinerário: {set(itinerario['origem'].tolist() + itinerario['destino'].tolist())}")
    except Exception as e:
        st.error(f"Erro ao gerar o mapa: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    
    # Exibir resumo abaixo do mapa
    st.markdown("### 📋 Resumo do Itinerário")
    for r in resumo_texto:
        st.markdown(r)

# Inicializar session_state para gerenciar pesquisas
if 'pesquisas' not in st.session_state:
    st.session_state.pesquisas = [{'id': 0}]
if 'contador_pesquisas' not in st.session_state:
    st.session_state.contador_pesquisas = 1

def adicionar_pesquisa():
    st.session_state.pesquisas.append({'id': st.session_state.contador_pesquisas})
    st.session_state.contador_pesquisas += 1

def remover_pesquisa(pesquisa_id):
    st.session_state.pesquisas = [p for p in st.session_state.pesquisas if p['id'] != pesquisa_id]

df_airports = load_airport_data()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Otimizador de Viagens", layout="wide")
st.title("🌍 Otimizador de Viagens")

# --- ABAS PRINCIPAIS ---
tab1, tab2 = st.tabs(["🔍 Scraper de Passagens", "📊 Otimizador de Itinerário"])

# ==========================================
# ABA 1: SCRAPER DE PASSAGENS
# ==========================================
with tab1:
    st.markdown("Configure suas pesquisas de voos e execute todas de uma vez")
    
    # --- ÁREA PRINCIPAL: FORMULÁRIOS DE PESQUISA ---
    st.markdown("---")
    st.header("📋 Pesquisas de Voos")
    
    pesquisas_validas = []
    
    for idx, pesquisa in enumerate(st.session_state.pesquisas):
        with st.container(border=True):
            # Cabeçalho com botão de remover
            col_header1, col_header2 = st.columns([5, 1])
            with col_header1:
                st.markdown(f"### 📍 Pesquisa {idx + 1}")
            with col_header2:
                if len(st.session_state.pesquisas) > 1:
                    if st.button("🗑️", key=f"remover_{pesquisa['id']}", help="Remover esta pesquisa"):
                        remover_pesquisa(pesquisa['id'])
                        st.rerun()
            
            # Campos de origem e destino
            col1, col2 = st.columns(2)
            
            with col1:
                origem_label = st.selectbox(
                    "✈️ Aeroporto de Origem",
                    options=df_airports['display_label'].tolist(),
                    index=None,
                    placeholder="Selecione o aeroporto de origem",
                    key=f"origem_{pesquisa['id']}"
                )
            
            with col2:
                destino_label = st.selectbox(
                    "🎯 Aeroporto de Destino",
                    options=df_airports['display_label'].tolist(),
                    index=None,
                    placeholder="Selecione o aeroporto de destino",
                    key=f"destino_{pesquisa['id']}"
                )
            
            # Campos de data
            col_data1, col_data2 = st.columns(2)
            
            with col_data1:
                data_ida = st.date_input(
                    "📅 Data de Partida",
                    value=None,
                    key=f"data_ida_{pesquisa['id']}"
                )
            
            with col_data2:
                data_volta = st.date_input(
                    "📅 Data de Retorno (Opcional)",
                    value=None,
                    key=f"data_volta_{pesquisa['id']}",
                    help="Deixe em branco para voos só de ida"
                )
            
            # Validar e armazenar dados da pesquisa
            if origem_label and destino_label and data_ida:
                origem_iata = df_airports[df_airports['display_label'] == origem_label].iloc[0]['iata_code']
                destino_iata = df_airports[df_airports['display_label'] == destino_label].iloc[0]['iata_code']
                
                pesquisa_data = {
                    'origem': origem_iata,
                    'destino': destino_iata,
                    'data_ida': data_ida.strftime('%Y-%m-%d'),
                    'data_volta': data_volta.strftime('%Y-%m-%d') if data_volta else None,
                    'origem_label': origem_label,
                    'destino_label': destino_label
                }
                
                pesquisas_validas.append(pesquisa_data)
                
                # Mostrar resumo da pesquisa
                if data_volta:
                    st.info(f"🔍 {origem_iata} → {destino_iata} | {data_ida.strftime('%d/%m/%Y')} até {data_volta.strftime('%d/%m/%Y')}")
                else:
                    st.info(f"🔍 {origem_iata} → {destino_iata} | {data_ida.strftime('%d/%m/%Y')} (só ida)")
    
    # Botão para adicionar nova pesquisa
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("➕ Adicionar Pesquisa", use_container_width=True, key="add_pesquisa_tab1"):
            adicionar_pesquisa()
            st.rerun()
    
    # --- BOTÃO PARA INICIAR TODAS AS PESQUISAS ---
    st.markdown("---")
    st.header("🚀 Executar Pesquisas")
    
    if st.button("🔍 Iniciar Todas as Pesquisas", type="primary", use_container_width=True, key="exec_pesquisas"):
        if not pesquisas_validas:
            st.warning("⚠️ Por favor, configure ao menos uma pesquisa completa (origem e destino).")
        else:
            st.info(f"📊 Iniciando {len(pesquisas_validas)} pesquisa(s)...")
            
            with st.spinner('Executando pesquisas...'):
                try:
                    # Inicializar bancos de dados
                    init_db_voos()
                    init_db_carros()
                    
                    # ANÁLISE DO ITINERÁRIO PARA IDENTIFICAR DESLOCAMENTOS INTERNOS
                    alugueis_carros = []
                    
                    # Função para calcular distância aproximada entre dois aeroportos (em km)
                    def calcular_distancia(iata1, iata2):
                        """Calcula distância aproximada em linha reta entre dois aeroportos"""
                        import math
                        
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
                    
                    # Para cada pesquisa de voo, verificar se é deslocamento interno
                    for idx, pesquisa in enumerate(pesquisas_validas):
                        origem_iata = pesquisa['origem']
                        destino_iata = pesquisa['destino']
                        
                        # Obter países
                        origem_pais = df_airports[df_airports['iata_code'] == origem_iata]['country_name'].iloc[0] if len(df_airports[df_airports['iata_code'] == origem_iata]) > 0 else None
                        destino_pais = df_airports[df_airports['iata_code'] == destino_iata]['country_name'].iloc[0] if len(df_airports[df_airports['iata_code'] == destino_iata]) > 0 else None
                        
                        # Se origem e destino no MESMO PAÍS, é um deslocamento interno - cotar aluguel
                        if origem_pais and destino_pais and origem_pais == destino_pais:
                            # Calcular distância rodoviária
                            distancia_km = calcular_distancia(origem_iata, destino_iata)
                            
                            if distancia_km:
                                # Calcular dias de viagem de carro (800 km/dia)
                                dias_viagem = math.ceil(distancia_km / 800)
                                
                                # Calcular tempo de viagem em horas (velocidade média 80 km/h)
                                tempo_total_horas = distancia_km / 80
                                horas = int(tempo_total_horas)
                                minutos = int((tempo_total_horas - horas) * 60)
                                tempo_viagem_horas = f"{horas:02d}:{minutos:02d}"
                                
                                # Data de retirada: data de chegada nesta cidade
                                data_retirada = pesquisa['data_ida']
                                
                                # Data de devolução: data do próximo voo (ou 1 dia após se for o último)
                                if idx + 1 < len(pesquisas_validas):
                                    proxima_pesquisa = pesquisas_validas[idx + 1]
                                    data_devolucao = proxima_pesquisa['data_ida']
                                else:
                                    from datetime import datetime, timedelta
                                    data_ida_dt = datetime.strptime(pesquisa['data_ida'], '%Y-%m-%d')
                                    data_devolucao = (data_ida_dt + timedelta(days=dias_viagem)).strftime('%Y-%m-%d')
                                
                                # Calcular total de dias de aluguel
                                from datetime import datetime
                                data_ret_dt = datetime.strptime(data_retirada, '%Y-%m-%d')
                                data_dev_dt = datetime.strptime(data_devolucao, '%Y-%m-%d')
                                dias_aluguel = (data_dev_dt - data_ret_dt).days
                                
                                alugueis_carros.append({
                                    'retirada': origem_iata,
                                    'entrega': destino_iata,
                                    'data_inicio': data_retirada,
                                    'data_fim': data_devolucao,
                                    'pais': origem_pais,
                                    'trecho': f"{origem_iata} → {destino_iata}",
                                    'distancia_km': distancia_km,
                                    'dias_viagem': dias_viagem,
                                    'dias_aluguel': dias_aluguel,
                                    'tempo_viagem_horas': tempo_viagem_horas
                                })
                    
                    # Remover duplicatas de aluguel
                    alugueis_unicos = []
                    for aluguel in alugueis_carros:
                        if not any(a['retirada'] == aluguel['retirada'] and 
                                 a['entrega'] == aluguel['entrega'] and 
                                 a['data_inicio'] == aluguel['data_inicio'] and 
                                 a['data_fim'] == aluguel['data_fim'] 
                                 for a in alugueis_unicos):
                            alugueis_unicos.append(aluguel)
                    
                    # Processar cada pesquisa de passagem
                    for idx, pesquisa in enumerate(pesquisas_validas, 1):
                        st.markdown(f"### 🔍 Pesquisa {idx}/{len(pesquisas_validas)}")
                        st.write(f"**Rota:** {pesquisa['origem']} ({pesquisa['origem_label']}) → {pesquisa['destino']} ({pesquisa['destino_label']})")
                        
                        periodo_texto = f"{pesquisa['data_ida']}"
                        if pesquisa['data_volta']:
                            periodo_texto += f" a {pesquisa['data_volta']}"
                        else:
                            periodo_texto += " (só ida)"
                        st.write(f"**Período:** {periodo_texto}")
                        
                        # Buscar passagens
                        with st.status(f"Pesquisando passagens para {pesquisa['origem']} → {pesquisa['destino']}...", expanded=True) as status:
                            st.write("Iniciando scraper de passagens...")
                            buscar_passagens(
                                origem=pesquisa['origem'],
                                destinos=[pesquisa['destino']],
                                data_ida=pesquisa['data_ida'],
                                data_volta=pesquisa['data_volta']
                            )
                            status.update(label=f"✅ Passagens coletadas para {pesquisa['origem']} → {pesquisa['destino']}", state="complete")
                        
                        st.markdown("---")
                    
                    # Processar aluguéis de carros identificados
                    st.markdown("### 🚗 Aluguel de Carros - Comparação Avião vs Carro")
                    
                    if alugueis_unicos:
                        st.info(f"📊 Identificados {len(alugueis_unicos)} deslocamento(s) interno(s) para comparar")
                        
                        for aluguel in alugueis_unicos:
                            mesmo_local = aluguel['retirada'] == aluguel['entrega']
                            
                            st.markdown(f"#### {aluguel['trecho']} ({aluguel['pais']})")
                            
                            # Exibir informações de viagem
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("🛣️ Distância Rodoviária", f"{aluguel['distancia_km']} km")
                            with col2:
                                st.metric("⏱️ Tempo de Viagem", aluguel['tempo_viagem_horas'])
                            with col3:
                                st.metric("🗓️ Dias de Viagem", f"{aluguel['dias_viagem']} dia(s)")
                            with col4:
                                st.metric("📅 Dias de Aluguel", f"{aluguel['dias_aluguel']} dia(s)")
                            
                            if mesmo_local:
                                st.write(f"🚗 Retirada e devolução em **{aluguel['retirada']}** (mesmo local)")
                                taxa_info = "Preços sem taxa de devolução"
                            else:
                                st.write(f"🚗 Retirada em **{aluguel['retirada']}**, Devolução em **{aluguel['entrega']}** (locais diferentes)")
                                taxa_info = "⚠️ Preços incluem taxa de devolução em local diferente (one-way fee)"
                            
                            st.write(f"📅 Período do aluguel: {aluguel['data_inicio']} a {aluguel['data_fim']}")
                            st.caption(f"💡 A {aluguel['tempo_viagem_horas']} de viagem (considerando velocidade média de 80 km/h)")
                            
                            with st.status(f"Pesquisando carros: {aluguel['retirada']} → {aluguel['entrega']}...", expanded=True) as status:
                                st.write(taxa_info)
                                st.write(f"Pesquisando aluguel para {aluguel['dias_aluguel']} dias...")
                                
                                try:
                                    buscar_carros(
                                        local_retirada=aluguel['retirada'],
                                        local_entrega=aluguel['entrega'],
                                        data_inicio=aluguel['data_inicio'],
                                        data_fim=aluguel['data_fim'],
                                        dias_viagem=aluguel['dias_viagem'],
                                        tempo_viagem_horas=aluguel['tempo_viagem_horas'],
                                        distancia_km=aluguel['distancia_km']
                                    )
                                except Exception as e:
                                    st.error(f"Erro ao buscar carros: {e}")
                                    import traceback
                                    traceback.print_exc()
                                
                                status.update(label=f"✅ Carros coletados: {aluguel['retirada']} → {aluguel['entrega']}", state="complete")
                            
                            st.markdown("---")
                    else:
                        st.info("⏭️ Nenhum deslocamento interno identificado (sem viagens entre cidades do mesmo país)")
                    
                    st.success("✅ Todas as pesquisas foram concluídas! Dados salvos no banco de dados.")
                    st.info("💡 Use o botão 'Atualizar Resultados' abaixo para visualizar as passagens coletadas")
                    
                except Exception as e:
                    st.error(f"❌ Erro durante a execução: {str(e)}")
                    st.exception(e)
    
    # --- SEÇÃO: VISUALIZAR RESULTADOS ---
    st.markdown("---")
    st.header("📊 Resultados das Pesquisas")
    
    # Filtros de pesquisa
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        filtro_origem = st.text_input("🔍 Filtrar por Origem (IATA)", placeholder="Ex: BSB, GYN", key="filtro_origem_tab1")
    with col_filtro2:
        filtro_destino = st.text_input("🔍 Filtrar por Destino (IATA)", placeholder="Ex: ATL, MCO", key="filtro_destino_tab1")
    
    if st.button("🔄 Atualizar Resultados", type="secondary", use_container_width=True, key="atualizar_tab1"):
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Construir query com filtros
            query = '''
                SELECT origem, destino, data_ida, data_volta, companhia, 
                       ida_saida, ida_chegada, ida_duracao, ida_escalas,
                       volta_saida, volta_chegada, volta_duracao, volta_escalas,
                       preco_bruto, preco_numerico
                FROM voos 
                WHERE 1=1
            '''
            params = []
            
            if filtro_origem:
                query += " AND origem = ?"
                params.append(filtro_origem.upper())
            
            if filtro_destino:
                query += " AND destino = ?"
                params.append(filtro_destino.upper())
            
            query += " ORDER BY preco_numerico ASC"
            
            cursor.execute(query, params)
            resultados = cursor.fetchall()
            conn.close()
            
            if resultados:
                st.success(f"✅ {len(resultados)} voo(s) encontrado(s)")
                
                # Criar DataFrame para melhor visualização
                df_voos = pd.DataFrame(resultados, columns=[
                    'Origem', 'Destino', 'Data Ida', 'Data Volta', 'Companhia',
                    'Ida Saída', 'Ida Chegada', 'Ida Duração', 'Ida Escalas',
                    'Volta Saída', 'Volta Chegada', 'Volta Duração', 'Volta Escalas',
                    'Preço', 'Preço Num'
                ])
                
                # Criar colunas formatadas para exibição
                df_voos_display = df_voos.copy()
                
                # Formatar coluna de IDA
                df_voos_display['✈️ IDA'] = df_voos_display.apply(
                    lambda row: f"{row['Ida Saída']} → {row['Ida Chegada']} ({row['Ida Duração']}, {row['Ida Escalas']})", 
                    axis=1
                )
                
                # Formatar coluna de VOLTA (se houver)
                df_voos_display['🔄 VOLTA'] = df_voos_display.apply(
                    lambda row: f"{row['Volta Saída']} → {row['Volta Chegada']} ({row['Volta Duração']}, {row['Volta Escalas']})" 
                                if pd.notna(row['Volta Saída']) else '-', 
                    axis=1
                )
                
                # Selecionar apenas colunas relevantes para exibição
                df_display_final = df_voos_display[['Origem', 'Destino', 'Data Ida', 'Data Volta', 'Companhia', '✈️ IDA', '🔄 VOLTA', 'Preço']]
                
                # Exibir tabela
                st.dataframe(
                    df_display_final,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Preço": st.column_config.TextColumn("💰 Preço"),
                        "Origem": st.column_config.TextColumn("✈️ Origem", width="small"),
                        "Destino": st.column_config.TextColumn("🎯 Destino", width="small"),
                        "✈️ IDA": st.column_config.TextColumn("✈️ IDA", width="large"),
                        "🔄 VOLTA": st.column_config.TextColumn("🔄 VOLTA", width="large"),
                    }
                )
                
                # Estatísticas
                st.markdown("### 📈 Estatísticas")
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("Total de Voos", len(resultados))
                with col_stat2:
                    diretos_ida = len(df_voos[df_voos['Ida Escalas'] == 'direto'])
                    st.metric("Voos Diretos (Ida)", diretos_ida)
                with col_stat3:
                    min_preco = df_voos['Preço Num'].min()
                    st.metric("Menor Preço", f"R$ {min_preco:,.2f}")
                with col_stat4:
                    media_preco = df_voos['Preço Num'].mean()
                    st.metric("Preço Médio", f"R$ {media_preco:,.2f}")
            else:
                st.warning("⚠️ Nenhum voo encontrado com os filtros aplicados. Execute uma pesquisa primeiro!")
        
        except Exception as e:
            st.error(f"❌ Erro ao buscar resultados: {str(e)}")

# ==========================================
# ABA 2: OTIMIZADOR DE ITINERÁRIO
# ==========================================
with tab2:
    st.markdown("Otimize seu itinerário completo usando os dados coletados")
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Parâmetros")
        origem_label = st.selectbox("Aeroporto de Origem", options=df_airports['display_label'].tolist(), index=None, placeholder="Busque origem...", key="origem_otimizador")
        origem_iata = origem_label.split(" - ")[0] if origem_label else None

        destinos_labels = st.multiselect("Aeroportos de Destino", options=df_airports['display_label'].tolist(), placeholder="Busque destinos...", key="destinos_otimizador")
        destinos_iata = [label.split(" - ")[0] for label in destinos_labels]

        data_ida = st.date_input("Partida", key="data_ida_otimizador")
        data_volta = st.date_input("Retorno", key="data_volta_otimizador")
        budget = st.number_input("Orçamento Total (R$)", value=15000, step=500, key="budget_otimizador")
        alpha = st.slider("Prioridade: Custo (1) vs Tempo (0)", 0.0, 1.0, 0.7, key="alpha_otimizador")
    
    # --- BOTÃO OTIMIZAR ---
    st.markdown("---")
    if st.button("Calcular Melhor Itinerário", use_container_width=True, key="calcular_itinerario"):
        if not origem_iata or not destinos_iata:
            st.warning("Selecione a origem e os destinos.")
        else:
            from backend.engine import TripOptimizerEngine
            
            config_solver = {'origem': origem_iata, 'destinos': destinos_iata, 'budget': budget, 'alpha': alpha}
            
            engine = TripOptimizerEngine(DB_NAME, config_solver)
            
            with st.spinner('Otimizando rotas...'):
                itinerario = engine.solve()
                
                if isinstance(itinerario, str):
                    if itinerario == "ERRO_SEM_RETORNO":
                        st.error(f"Inviável: Não existem voos de volta para {origem_iata} no banco.")
                    elif itinerario == "ERRO_SEM_DADOS":
                        st.error("Inviável: Não há dados suficientes no banco para otimizar.")
                    else:
                        st.error(f"Erro: {itinerario}")
                elif itinerario is not None:
                    st.success("Melhor Itinerário Encontrado!")
                    
                    # 1. Exibir Tabela
                    st.dataframe(itinerario[['tipo', 'companhia', 'origem', 'destino', 'data_ida', 'preco_numerico', 'duracao']], use_container_width=True)
                    
                    # 2. Métricas
                    custo_total = itinerario['preco_numerico'].sum()
                    st.metric("Investimento Total", f"R$ {custo_total:,.2f}")
                    
                    # 3. Mapa da Solução (plotado automaticamente após otimização)
                    st.subheader("🗺️ Visualização do Roteiro no Mapa")
                    plot_itinerary_graph(itinerario, df_airports)
                else:
                    st.error("Inviável: Orçamento insuficiente ou restrições de tempo.")

# --- SIDEBAR GLOBAL: INFORMAÇÕES E OPÇÕES ---
st.sidebar.markdown("---")
st.sidebar.header("ℹ️ Informações")
st.sidebar.markdown(f"""
**Pesquisas configuradas:** {len(pesquisas_validas) if 'pesquisas_validas' in locals() else 0}

**Como usar:**
1. Use a aba "Scraper" para coletar dados de voos e carros
2. Use a aba "Otimizador" para encontrar o melhor itinerário
3. Configure parâmetros e execute as pesquisas
4. Visualize os resultados em mapas interativos
""")