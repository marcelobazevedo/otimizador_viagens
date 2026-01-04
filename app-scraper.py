import streamlit as st
import pandas as pd
import os
import sqlite3
import math
from datetime import date, datetime, timedelta

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

st.title("🌍 Otimizador de Viagens")
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
    if st.button("➕ Adicionar Pesquisa", use_container_width=True):
        adicionar_pesquisa()
        st.rerun()

# --- BOTÃO PARA INICIAR TODAS AS PESQUISAS ---
st.markdown("---")
st.header("🚀 Executar Pesquisas")

if st.button("🔍 Iniciar Todas as Pesquisas", type="primary", use_container_width=True):
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
                print(f"\n[DEBUG app.py] alugueis_unicos: {alugueis_unicos}")
                print(f"[DEBUG app.py] Total de aluguéis: {len(alugueis_unicos)}")
                
                if alugueis_unicos:
                    st.info(f"📊 Identificados {len(alugueis_unicos)} deslocamento(s) interno(s) para comparar")
                    
                    for aluguel in alugueis_unicos:
                        print(f"\n[DEBUG app.py] Processando aluguel: {aluguel}")
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
                            print(f"\n[DEBUG app.py] Chamando buscar_carros com:")
                            print(f"  - local_retirada: {aluguel['retirada']}")
                            print(f"  - local_entrega: {aluguel['entrega']}")
                            print(f"  - data_inicio: {aluguel['data_inicio']}")
                            print(f"  - data_fim: {aluguel['data_fim']}")
                            
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
                                print(f"[DEBUG app.py] buscar_carros executado com sucesso")
                            except Exception as e:
                                print(f"[ERRO app.py] Erro ao chamar buscar_carros: {e}")
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

# --- SIDEBAR: INFORMAÇÕES E OPÇÕES ---
st.sidebar.header("ℹ️ Informações")
st.sidebar.markdown(f"""
**Pesquisas configuradas:** {len(pesquisas_validas)}

**Como usar:**
1. Configure uma ou mais pesquisas
2. Clique em "Adicionar Pesquisa" para mais rotas
3. Clique em "Iniciar Todas as Pesquisas"
4. Aguarde a coleta dos dados
""")

if pesquisas_validas:
    st.sidebar.markdown("### 📋 Resumo das Pesquisas")
    for idx, p in enumerate(pesquisas_validas, 1):
        st.sidebar.markdown(f"**{idx}.** {p['origem']} → {p['destino']}")
        if p['data_volta']:
            st.sidebar.caption(f"{p['data_ida']} a {p['data_volta']}")
        else:
            st.sidebar.caption(f"{p['data_ida']} (só ida)")

# --- SEÇÃO: VISUALIZAR RESULTADOS ---
st.markdown("---")
st.header("📊 Resultados das Pesquisas")

# Filtros de pesquisa
col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    filtro_origem = st.text_input("🔍 Filtrar por Origem (IATA)", placeholder="Ex: BSB, GYN")
with col_filtro2:
    filtro_destino = st.text_input("🔍 Filtrar por Destino (IATA)", placeholder="Ex: ATL, MCO")

if st.button("🔄 Atualizar Resultados", type="secondary", use_container_width=True):
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