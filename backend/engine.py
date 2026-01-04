import pandas as pd
import sqlite3
import pulp
import re
from math import radians, cos, sin, asin, sqrt

class TripOptimizerEngine:
    def __init__(self, db_path, config):
        self.db_path = db_path
        self.config = config # {origem: 'BSB', destinos: ['ATL'], budget: 15000, alpha: 0.7}
        self.prob = pulp.LpProblem("World_Cup_Optimization", pulp.LpMinimize)
        # Carregar coordenadas para estimativa de carros
        try:
            self.df_airports = pd.read_csv('utils/br-us-airports.csv', sep=';')
        except:
            self.df_airports = pd.DataFrame()

    def _get_minutes(self, duration_str):
        """Converte '6h 20m' para minutos inteiros."""
        if not isinstance(duration_str, str) or pd.isna(duration_str):
            return 0
        try:
            hours = re.search(r'(\d+)h', str(duration_str))
            minutes = re.search(r'(\d+)m', str(duration_str))
            h = int(hours.group(1)) if hours else 0
            m = int(minutes.group(1)) if minutes else 0
            return h * 60 + m
        except:
            return 0

    def _estimate_car_duration(self, orig, dest):
        """Estima tempo de carro baseado na distância entre aeroportos."""
        try:
            coords = self.df_airports.set_index('iata_code')
            lat1, lon1 = coords.loc[orig, ['latitude_deg', 'longitude_deg']]
            lat2, lon2 = coords.loc[dest, ['latitude_deg', 'longitude_deg']]
            
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1 
            dlat = lat2 - lat1 
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a)) 
            km = 6371 * c
            
            # Velocidade média: 85 km/h
            total_min = int((km / 85) * 60)
            return f"{total_min // 60}h {total_min % 60}m", total_min
        except:
            return "4h 00m", 240 # Default de segurança

    def load_and_filter_data(self):
        conn = sqlite3.connect(self.db_path)
        permitidas = [self.config['origem']] + self.config['destinos']
        
        # Filtro estrito para evitar cidades não selecionadas
        self.df_voos = pd.read_sql_query(
            f"SELECT * FROM voos WHERE origem IN {tuple(permitidas)} AND destino IN {tuple(permitidas)}", conn)
        self.df_carros = pd.read_sql_query(
            f"SELECT * FROM aluguel_carros WHERE local_retirada IN {tuple(permitidas)} AND local_entrega IN {tuple(permitidas)}", conn)
        conn.close()

        # Processar durações dos voos
        # A tabela tem ida_duracao e volta_duracao, precisamos combinar
        def calcular_duracao_total(row):
            """Calcula duração total combinando ida e volta se existir"""
            ida_min = self._get_minutes(row.get('ida_duracao', ''))
            volta_min = self._get_minutes(row.get('volta_duracao', '')) if pd.notna(row.get('volta_duracao')) else 0
            return ida_min + volta_min
        
        # Criar coluna duracao_min com a soma de ida e volta
        self.df_voos['duracao_min'] = self.df_voos.apply(calcular_duracao_total, axis=1)
        
        # Criar coluna duracao formatada para exibição
        def formatar_duracao(row):
            """Formata duração para exibição"""
            ida = row.get('ida_duracao', 'N/A')
            volta = row.get('volta_duracao', None)
            if pd.notna(volta) and volta:
                return f"{ida} + {volta}"
            return str(ida)
        
        self.df_voos['duracao'] = self.df_voos.apply(formatar_duracao, axis=1)
        
        # Processar durações dos carros
        for idx, row in self.df_carros.iterrows():
            d_str, d_min = self._estimate_car_duration(row['local_retirada'], row['local_entrega'])
            self.df_carros.at[idx, 'duracao'] = d_str
            self.df_carros.at[idx, 'duracao_min'] = d_min

    def build_model(self):
        v_idx, c_idx = self.df_voos.index, self.df_carros.index
        self.x_v = pulp.LpVariable.dicts("v", v_idx, cat=pulp.LpBinary)
        self.x_c = pulp.LpVariable.dicts("c", c_idx, cat=pulp.LpBinary)

        # Função Objetivo: Alpha * Custo + (1-Alpha) * Tempo
        custo = pulp.lpSum([self.x_v[i]*self.df_voos.loc[i, 'preco_numerico'] for i in v_idx]) + \
                pulp.lpSum([self.x_c[j]*self.df_carros.loc[j, 'preco_numerico'] for j in c_idx])
        tempo = pulp.lpSum([self.x_v[i]*self.df_voos.loc[i, 'duracao_min'] for i in v_idx]) + \
                pulp.lpSum([self.x_c[j]*self.df_carros.loc[j, 'duracao_min'] for j in c_idx])
        
        self.prob += self.config['alpha'] * custo + (1 - self.config['alpha']) * tempo

        # Restrições de Fluxo (Ciclo Hamiltoniano)
        origem = self.config['origem']
        destinos = self.config['destinos']

        self.prob += pulp.lpSum([self.x_v[i] for i in v_idx if self.df_voos.loc[i, 'origem'] == origem]) + \
                     pulp.lpSum([self.x_c[j] for j in c_idx if self.df_carros.loc[j, 'local_retirada'] == origem]) == 1
        
        self.prob += pulp.lpSum([self.x_v[i] for i in v_idx if self.df_voos.loc[i, 'destino'] == origem]) + \
                     pulp.lpSum([self.x_c[j] for j in c_idx if self.df_carros.loc[j, 'local_entrega'] == origem]) == 1

        for cidade in destinos:
            entrada = pulp.lpSum([self.x_v[i] for i in v_idx if self.df_voos.loc[i, 'destino'] == cidade]) + \
                      pulp.lpSum([self.x_c[j] for j in c_idx if self.df_carros.loc[j, 'local_entrega'] == cidade])
            saida = pulp.lpSum([self.x_v[i] for i in v_idx if self.df_voos.loc[i, 'origem'] == cidade]) + \
                    pulp.lpSum([self.x_c[j] for j in c_idx if self.df_carros.loc[j, 'local_retirada'] == cidade])
            self.prob += entrada == 1
            self.prob += saida == 1

        self.prob += custo <= self.config['budget']

    def solve(self):
        self.load_and_filter_data()
        
        # Verificar se há dados
        if self.df_voos.empty:
            return "ERRO_SEM_DADOS"
        
        if self.df_voos[self.df_voos['destino'] == self.config['origem']].empty:
            return "ERRO_SEM_RETORNO"

        self.build_model()
        self.prob.solve(pulp.PULP_CBC_CMD(msg=0))
        
        if pulp.LpStatus[self.prob.status] == 'Optimal':
            v_res = self.df_voos.loc[[i for i in self.df_voos.index if self.x_v[i].varValue > 0.9]].copy()
            v_res['tipo'] = 'Voo'
            
            c_res = self.df_carros.loc[[j for j in self.df_carros.index if self.x_c[j].varValue > 0.9]].copy()
            c_res['tipo'] = 'Carro'
            c_res = c_res.rename(columns={'local_retirada': 'origem', 'local_entrega': 'destino', 'locadora': 'companhia', 'data_inicio': 'data_ida'})
            
            itinerario = pd.concat([v_res, c_res], ignore_index=True)
            return self.ordenar_itinerario(itinerario)
        return None

    def ordenar_itinerario(self, df):
        ordenado, atual, pool = [], self.config['origem'], df.copy()
        while not pool.empty:
            match = pool[pool['origem'] == atual]
            if match.empty: break
            linha = match.iloc[0]
            ordenado.append(linha)
            atual, pool = linha['destino'], pool.drop(match.index[0])
        return pd.DataFrame(ordenado)