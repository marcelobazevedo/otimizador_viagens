import pandas as pd
import sqlite3
import numpy as np
import re
from math import radians, cos, sin, asin, sqrt
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import Problem
from pymoo.optimize import minimize
from pymoo.operators.crossover.pntx import TwoPointCrossover
from pymoo.operators.mutation.bitflip import BitflipMutation
from pymoo.operators.sampling.rnd import BinaryRandomSampling
from pymoo.termination import get_termination
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

class TripOptimizationProblem(Problem):
    """Problema de otimização de viagens usando NSGA-II"""
    
    def __init__(self, df_voos, df_carros, config):
        self.df_voos = df_voos
        self.df_carros = df_carros
        self.config = config
        
        # Total de variáveis binárias: uma para cada voo + uma para cada carro
        n_vars = len(df_voos) + len(df_carros)
        
        # Problema com objetivo único ponderado: alpha*custo + (1-alpha)*tempo
        # Ainda mantemos 2 objetivos para gerar Pareto Front, mas com alpha como preferência
        # n_constr = número de restrições
        super().__init__(n_var=n_vars, n_obj=2, n_constr=1, xl=0, xu=1, type_var=bool)
        
    def _decode_solution(self, x):
        """Decodifica solução binária em voos e carros selecionados"""
        n_voos = len(self.df_voos)
        voos_sel = x[:n_voos]
        carros_sel = x[n_voos:]
        return voos_sel, carros_sel
    
    def _calculate_objectives(self, voos_sel, carros_sel):
        """Calcula custo e tempo total"""
        custo = 0
        tempo = 0
        
        for i, selected in enumerate(voos_sel):
            if selected:
                custo += self.df_voos.iloc[i]['preco_numerico']
                tempo += self.df_voos.iloc[i]['duracao_min']
        
        for j, selected in enumerate(carros_sel):
            if selected:
                custo += self.df_carros.iloc[j]['preco_numerico']
                tempo += self.df_carros.iloc[j]['duracao_min']
        
        return custo, tempo
    
    def _check_constraints(self, voos_sel, carros_sel):
        """Verifica se a solução respeita as restrições - retorna penalidade"""
        origem = self.config['origem']
        destinos = self.config['destinos']
        budget = self.config['budget']
        
        # Calcular custo total
        custo_total, _ = self._calculate_objectives(voos_sel, carros_sel)
        
        # Penalidade por exceder orçamento (peso grande)
        budget_violation = max(0, custo_total - budget) * 10
        
        # Para gerar diversidade no Pareto Front, vamos relaxar as restrições
        # e apenas garantir que o custo não exceda muito o orçamento
        # As outras restrições serão tratadas na filtragem final
        
        return budget_violation
    
    def _evaluate(self, x, out, *args, **kwargs):
        """Avalia uma população de soluções considerando alpha do usuário"""
        f1 = []  # Custo
        f2 = []  # Tempo
        g1 = []  # Restrições
        
        # Coletar todos custos e tempos para normalização
        custos_raw = []
        tempos_raw = []
        
        for solution in x:
            voos_sel, carros_sel = self._decode_solution(solution)
            custo, tempo = self._calculate_objectives(voos_sel, carros_sel)
            custos_raw.append(custo)
            tempos_raw.append(tempo)
        
        # Normalizar
        min_c = min(custos_raw) if custos_raw else 1
        max_c = max(custos_raw) if custos_raw else 1
        min_t = min(tempos_raw) if tempos_raw else 1
        max_t = max(tempos_raw) if tempos_raw else 1
        
        range_c = max_c - min_c if max_c > min_c else 1
        range_t = max_t - min_t if max_t > min_t else 1
        
        alpha = self.config.get('alpha', 0.5)
        
        for i, solution in enumerate(x):
            voos_sel, carros_sel = self._decode_solution(solution)
            custo = custos_raw[i]
            tempo = tempos_raw[i]
            constraint_violation = self._check_constraints(voos_sel, carros_sel)
            
            # Normalizar
            custo_norm = (custo - min_c) / range_c if range_c > 0 else 0
            tempo_norm = (tempo - min_t) / range_t if range_t > 0 else 0
            
            # Aplicar alpha: quanto maior alpha, mais peso no custo
            # F1: objetivo ponderado pelo alpha (PRINCIPAL)
            # F2: mantemos objetivos separados para visualização do Pareto
            obj_ponderado = alpha * custo_norm + (1 - alpha) * tempo_norm
            
            f1.append(obj_ponderado * 1000)  # Multiplicar para escala
            f2.append(tempo)  # Manter tempo real para segunda dimensão
            g1.append(constraint_violation)
        
        out["F"] = np.column_stack([f1, f2])
        out["G"] = np.column_stack([g1])


class TripOptimizerEngine:
    def __init__(self, db_path, config):
        self.db_path = db_path
        self.config = config  # {origem: 'BSB', destinos: ['ATL'], budget: 15000, alpha: 0.7}
        # Carregar coordenadas para estimativa de carros
        try:
            self.df_airports = pd.read_csv('utils/br-us-airports.csv', sep=';')
        except:
            self.df_airports = pd.DataFrame()
    
    def _validate_itinerary(self, itinerario):
        """Valida se o itinerário é válido (visita todos os destinos)"""
        if itinerario.empty:
            return False
        
        origem = self.config['origem']
        destinos = set(self.config['destinos'])
        
        # Verificar se começa na origem
        if itinerario.iloc[0]['origem'] != origem:
            return False
        
        # Verificar se visita todos os destinos
        cidades_visitadas = set()
        for _, row in itinerario.iterrows():
            if row['destino'] != origem:
                cidades_visitadas.add(row['destino'])
            # Também contar destinos intermediários
            if row['origem'] != origem and row['origem'] in destinos:
                cidades_visitadas.add(row['origem'])
        
        if not destinos.issubset(cidades_visitadas):
            return False
        
        # NÃO exigir que termine na origem (permitir rotas lineares)
        # A rota pode ser linear (sem retorno) se não houver dados para retorno
        
        return True

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
            return "4h 00m", 240  # Default de segurança

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

    def solve(self):
        self.load_and_filter_data()
        
        # Verificar se há dados
        if self.df_voos.empty:
            return "ERRO_SEM_DADOS"
        
        if self.df_voos[self.df_voos['destino'] == self.config['origem']].empty:
            return "ERRO_SEM_RETORNO"

        # Ao invés de usar NSGA-II que pode convergir para uma única solução,
        # vamos gerar múltiplas soluções manualmente explorando diferentes combinações
        solutions = self._generate_alternative_routes()
        
        # Se não conseguimos gerar alternativas manualmente, tentar com NSGA-II
        if not solutions or len(solutions) < 2:
            solutions_ga = self._solve_with_nsga2()
            if solutions_ga:
                solutions.extend(solutions_ga)
        
        # Remover duplicatas e ordenar por custo E TEMPO (Pareto Front)
        if solutions:
            print(f"DEBUG: Total de soluções antes de remover duplicatas: {len(solutions)}")
            
            # Criar uma chave única baseada em TODAS as características relevantes
            unique_solutions = []
            seen_routes = set()
            
            for sol in solutions:
                # Criar chave única baseada em múltiplos campos para evitar falsos positivos
                route_parts = []
                for _, row in sol['itinerario'].iterrows():
                    # Incluir mais campos para diferenciar rotas similares
                    part = (
                        row.get('origem', ''),
                        row.get('destino', ''),
                        row.get('tipo', ''),
                        row.get('companhia', ''),
                        row.get('data_ida', ''),
                        row.get('ida_duracao', ''),
                        row.get('volta_duracao', ''),
                        round(row.get('preco_numerico', 0), 2)
                    )
                    route_parts.append(part)
                
                route_key = tuple(route_parts)
                
                if route_key not in seen_routes:
                    seen_routes.add(route_key)
                    unique_solutions.append(sol)
            
            print(f"DEBUG: Soluções únicas após remover duplicatas exatas: {len(unique_solutions)}")
            
            # FILTRAR soluções que excedem o orçamento máximo
            budget_max = self.config['budget']
            within_budget = [sol for sol in unique_solutions if sol['custo'] <= budget_max]
            
            if not within_budget:
                print(f"⚠️ AVISO: Nenhuma solução encontrada dentro do orçamento de R$ {budget_max:.2f}")
                print(f"Solução mais barata custa R$ {min(s['custo'] for s in unique_solutions):.2f}")
                # Retornar None quando não há soluções dentro do orçamento
                return None
            else:
                print(f"DEBUG: {len(within_budget)} soluções dentro do orçamento de R$ {budget_max:.2f}")
                unique_solutions = within_budget
            
            # CALCULAR PARETO FRONT - Soluções não dominadas
            def domina(sol1, sol2):
                """Verifica se sol1 domina sol2 (é melhor em pelo menos um objetivo e não pior em nenhum)"""
                melhor_custo = sol1['custo'] <= sol2['custo']
                melhor_tempo = sol1['tempo'] <= sol2['tempo']
                estritamente_melhor = sol1['custo'] < sol2['custo'] or sol1['tempo'] < sol2['tempo']
                return melhor_custo and melhor_tempo and estritamente_melhor
            
            # Encontrar soluções não dominadas (Pareto Front)
            pareto_front = []
            for sol in unique_solutions:
                is_dominated = False
                for other_sol in unique_solutions:
                    if domina(other_sol, sol):
                        is_dominated = True
                        break
                if not is_dominated:
                    pareto_front.append(sol)
            
            print(f"\nDEBUG: Pareto Front tem {len(pareto_front)} soluções não-dominadas")
            
            # Se Pareto Front for muito pequeno, adicionar soluções próximas
            if len(pareto_front) < 20:
                # Adicionar soluções com pequena dominância
                # Usar IDs para evitar comparação de DataFrames
                pareto_ids = set(id(s) for s in pareto_front)
                remaining = [s for s in unique_solutions if id(s) not in pareto_ids]
                
                # Ordenar por distância ao Pareto Front (soma normalizada de custo e tempo)
                if pareto_front:
                    min_custo = min(s['custo'] for s in pareto_front)
                    max_custo = max(s['custo'] for s in pareto_front)
                    min_tempo = min(s['tempo'] for s in pareto_front)
                    max_tempo = max(s['tempo'] for s in pareto_front)
                    
                    range_custo = max_custo - min_custo if max_custo > min_custo else 1
                    range_tempo = max_tempo - min_tempo if max_tempo > min_tempo else 1
                    
                    def distancia_pareto(sol):
                        # Normalizar e calcular distância
                        custo_norm = (sol['custo'] - min_custo) / range_custo
                        tempo_norm = (sol['tempo'] - min_tempo) / range_tempo
                        return custo_norm + tempo_norm
                    
                    remaining.sort(key=distancia_pareto)
                    pareto_front.extend(remaining[:30])
            
            # Agrupar por padrão de tipos para garantir diversidade
            from collections import defaultdict
            solutions_by_pattern = defaultdict(list)
            
            for sol in pareto_front:
                # Criar padrão de tipos
                pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                solutions_by_pattern[pattern].append(sol)
            
            print(f"\nDEBUG: Padrões de tipo encontrados: {len(solutions_by_pattern)}")
            for pattern, sols in sorted(solutions_by_pattern.items(), key=lambda x: min(s['custo'] for s in x[1])):
                if sols:
                    custos = [s['custo'] for s in sols]
                    tempos = [s['tempo'] for s in sols]
                    print(f"  {pattern}: {len(sols)} soluções")
                    print(f"    Custo: R$ {min(custos):.2f} - R$ {max(custos):.2f}")
                    print(f"    Tempo: {min(tempos):.0f} - {max(tempos):.0f} min")
            
            # NOVA ABORDAGEM: Selecionar baseado em TODAS as soluções globalmente
            # Não processar por padrão, processar tudo junto para respeitar o alpha
            all_solutions = pareto_front  # Usar todas as soluções do Pareto Front
            
            alpha = self.config.get('alpha', 0.5)
            
            # Calcular ranges globais
            if all_solutions:
                min_c_all = min(s['custo'] for s in all_solutions)
                max_c_all = max(s['custo'] for s in all_solutions)
                min_t_all = min(s['tempo'] for s in all_solutions)
                max_t_all = max(s['tempo'] for s in all_solutions)
                
                range_c_all = max_c_all - min_c_all if max_c_all > min_c_all else 1
                range_t_all = max_t_all - min_t_all if max_t_all > min_t_all else 1
                
                print(f"\nDEBUG: Ranges globais para seleção (alpha={alpha:.2f}):")
                print(f"  Custo: R$ {min_c_all:.2f} - R$ {max_c_all:.2f}")
                print(f"  Tempo: {min_t_all:.0f} - {max_t_all:.0f} min")
                
                # Calcular score baseado em alpha para TODAS as soluções
                for sol in all_solutions:
                    custo_norm = (sol['custo'] - min_c_all) / range_c_all
                    tempo_norm = (sol['tempo'] - min_t_all) / range_t_all
                    sol['_alpha_score'] = alpha * custo_norm + (1-alpha) * tempo_norm
                
                # Selecionar soluções baseado no alpha
                # Pegar mais soluções para garantir diversidade
                if alpha >= 0.7:
                    # FOCO EM ECONOMIA: Ordenar por custo
                    print(f"DEBUG: Modo ECONOMIA (alpha={alpha:.2f}) - Ordenando por CUSTO")
                    balanced_solutions = sorted(all_solutions, key=lambda x: x['custo'])[:50]
                
                elif alpha <= 0.3:
                    # FOCO EM VELOCIDADE: Ordenar por tempo
                    print(f"DEBUG: Modo VELOCIDADE (alpha={alpha:.2f}) - Ordenando por TEMPO")
                    balanced_solutions = sorted(all_solutions, key=lambda x: x['tempo'])[:50]
                    
                    # DEBUG: Mostrar as primeiras soluções
                    print(f"DEBUG: 10 soluções mais RÁPIDAS disponíveis:")
                    for i, sol in enumerate(balanced_solutions[:10]):
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i+1}. {str(pattern)[:40]:<40} - Custo: R$ {sol['custo']:>8,.2f} | Tempo: {sol['tempo']:>6.0f}min")
                
                else:
                    # BALANCEADO: Ordenar por score alpha
                    print(f"DEBUG: Modo BALANCEADO (alpha={alpha:.2f}) - Ordenando por SCORE")
                    balanced_solutions = sorted(all_solutions, key=lambda x: x['_alpha_score'])[:50]
                
                print(f"DEBUG: Selecionadas {len(balanced_solutions)} soluções após aplicar alpha={alpha:.2f}")
            else:
                balanced_solutions = []
            
            
            # ORDENAÇÃO FINAL com alpha
            # Só recalcular se ainda não tiver sido calculado
            if balanced_solutions:
                # Calcular ranges globais para normalização
                all_custos = [s['custo'] for s in balanced_solutions]
                all_tempos = [s['tempo'] for s in balanced_solutions]
                
                min_c_global = min(all_custos)
                max_c_global = max(all_custos)
                min_t_global = min(all_tempos)
                max_t_global = max(all_tempos)
                
                range_c_global = max_c_global - min_c_global if max_c_global > min_c_global else 1
                range_t_global = max_t_global - min_t_global if max_t_global > min_t_global else 1
                
                # A ordenação já foi feita acima baseada no alpha
                # Não reordenar aqui
                
                alpha = self.config.get('alpha', 0.5)
                print(f"\nDEBUG: Verificação de ordenação (alpha={alpha:.2f}):")
                print(f"DEBUG: Range de custos: R$ {min_c_global:.2f} - R$ {max_c_global:.2f}")
                print(f"DEBUG: Range de tempos: {min_t_global:.0f} - {max_t_global:.0f} min")
                
                if alpha <= 0.3:
                    # Mostrar que está ordenado por TEMPO
                    print(f"DEBUG: ORDENADO POR TEMPO (mais rápido primeiro):")
                    print(f"DEBUG: Primeiras 5 soluções:")
                    for i, sol in enumerate(balanced_solutions[:5]):
                        tempo_pct = (sol['tempo']-min_t_global)/(max_t_global-min_t_global)*100 if max_t_global > min_t_global else 0
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i+1}. {str(pattern)[:30]:<30} Tempo: {sol['tempo']:>6.0f}min ({tempo_pct:5.1f}%) | Custo: R$ {sol['custo']:>8,.2f}")
                    
                    print(f"DEBUG: Últimas 3 soluções (mais lentas):")
                    for i, sol in enumerate(balanced_solutions[-3:], len(balanced_solutions)-2):
                        tempo_pct = (sol['tempo']-min_t_global)/(max_t_global-min_t_global)*100 if max_t_global > min_t_global else 0
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i}. {str(pattern)[:30]:<30} Tempo: {sol['tempo']:>6.0f}min ({tempo_pct:5.1f}%) | Custo: R$ {sol['custo']:>8,.2f}")
                
                elif alpha >= 0.7:
                    # Mostrar que está ordenado por CUSTO
                    print(f"DEBUG: ORDENADO POR CUSTO (mais barato primeiro):")
                    print(f"DEBUG: Primeiras 5 soluções:")
                    for i, sol in enumerate(balanced_solutions[:5]):
                        custo_pct = (sol['custo']-min_c_global)/(max_c_global-min_c_global)*100 if max_c_global > min_c_global else 0
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i+1}. {str(pattern)[:30]:<30} Custo: R$ {sol['custo']:>8,.2f} ({custo_pct:5.1f}%) | Tempo: {sol['tempo']:>6.0f}min")
                    
                    print(f"DEBUG: Últimas 3 soluções (mais caras):")
                    for i, sol in enumerate(balanced_solutions[-3:], len(balanced_solutions)-2):
                        custo_pct = (sol['custo']-min_c_global)/(max_c_global-min_c_global)*100 if max_c_global > min_c_global else 0
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i}. {str(pattern)[:30]:<30} Custo: R$ {sol['custo']:>8,.2f} ({custo_pct:5.1f}%) | Tempo: {sol['tempo']:>6.0f}min")
                
                else:
                    # BALANCEADO
                    print(f"DEBUG: ORDENADO POR SCORE BALANCEADO:")
                    print(f"DEBUG: Primeiras 5 soluções:")
                    for i, sol in enumerate(balanced_solutions[:5]):
                        custo_pct = (sol['custo']-min_c_global)/(max_c_global-min_c_global)*100 if max_c_global > min_c_global else 0
                        tempo_pct = (sol['tempo']-min_t_global)/(max_t_global-min_t_global)*100 if max_t_global > min_t_global else 0
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i+1}. {str(pattern)[:30]:<30} R$ {sol['custo']:>8,.2f} ({custo_pct:5.1f}%) | {sol['tempo']:>6.0f}min ({tempo_pct:5.1f}%)")
                    
                    print(f"DEBUG: Últimas 3 soluções:")
                    for i, sol in enumerate(balanced_solutions[-3:], len(balanced_solutions)-2):
                        custo_pct = (sol['custo']-min_c_global)/(max_c_global-min_c_global)*100 if max_c_global > min_c_global else 0
                        tempo_pct = (sol['tempo']-min_t_global)/(max_t_global-min_t_global)*100 if max_t_global > min_t_global else 0
                        pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                        print(f"  {i}. {str(pattern)[:30]:<30} R$ {sol['custo']:>8,.2f} ({custo_pct:5.1f}%) | {sol['tempo']:>6.0f}min ({tempo_pct:5.1f}%)")
            
            final_solutions = balanced_solutions[:50] if balanced_solutions else None
            print(f"DEBUG: Retornando {len(final_solutions) if final_solutions else 0} soluções")
            
            # Mostrar primeiras 20 para debug com CUSTO E TEMPO
            if final_solutions:
                print(f"\nDEBUG: Primeiras 20 soluções mostrando trade-off CUSTO vs TEMPO:")
                print(f"{'#':<4} {'Padrão':<30} {'Custo':<15} {'Tempo':<12} {'Foco':<15}")
                print("-"*80)
                
                alpha = self.config.get('alpha', 0.5)
                for i, sol in enumerate(final_solutions[:20]):
                    pattern = tuple(row['tipo'] for _, row in sol['itinerario'].iterrows())
                    pattern_str = str(pattern)
                    
                    # Determinar foco baseado em posição relativa
                    all_same_pattern = [s for s in final_solutions if tuple(row['tipo'] for _, row in s['itinerario'].iterrows()) == pattern]
                    if len(all_same_pattern) > 1:
                        custos_pattern = [s['custo'] for s in all_same_pattern]
                        tempos_pattern = [s['tempo'] for s in all_same_pattern]
                        
                        is_cheapest = sol['custo'] == min(custos_pattern)
                        is_fastest = sol['tempo'] == min(tempos_pattern)
                        
                        if is_cheapest and is_fastest:
                            foco = "MELHOR GERAL"
                        elif is_cheapest:
                            foco = "ECONOMIA"
                        elif is_fastest:
                            foco = "RAPIDEZ"
                        else:
                            foco = "BALANCEADO"
                    else:
                        foco = "ÚNICA"
                    
                    print(f"{i+1:<4} {pattern_str:<30} R$ {sol['custo']:>10,.2f}  {sol['tempo']:>6} min  {foco:<15}")
            
            return final_solutions
        
        return None
    
    def _generate_alternative_routes(self):
        """Gera múltiplas rotas alternativas explorando TODAS as opções de cada segmento"""
        origem = self.config['origem']
        destinos = self.config['destinos']
        budget = self.config['budget']
        alpha = self.config.get('alpha', 0.5)
        solutions = []
        
        print(f"\n{'='*80}")
        print(f"🔧 OTIMIZADOR INICIADO - ALPHA = {alpha:.2f}")
        print(f"   Alpha = 1.0 -> Foco ECONOMIA (custo)")
        print(f"   Alpha = 0.0 -> Foco VELOCIDADE (tempo)")
        print(f"   Budget máximo: R$ {budget:,.2f}")
        print(f"{'='*80}\n")
        
        from itertools import permutations, product
        
        # NOVA ABORDAGEM: Construir rotas baseadas nas conexões disponíveis
        # Não forçar rota circular se não houver dados
        
        # Primeiro, mapear todas as conexões disponíveis
        conexoes_disponiveis = set()
        for _, row in self.df_voos.iterrows():
            conexoes_disponiveis.add((row['origem'], row['destino']))
        for _, row in self.df_carros.iterrows():
            conexoes_disponiveis.add((row['local_retirada'], row['local_entrega']))
        
        print(f"\nDEBUG: Conexões disponíveis no banco:")
        for orig, dest in sorted(conexoes_disponiveis):
            voos = len(self.df_voos[(self.df_voos['origem']==orig) & (self.df_voos['destino']==dest)])
            carros = len(self.df_carros[(self.df_carros['local_retirada']==orig) & (self.df_carros['local_entrega']==dest)])
            print(f"  {orig} -> {dest}: {voos} voos, {carros} carros")
        
        # Tentar construir rotas viáveis
        viable_routes = []
        
        # Gerar todas as permutações de destinos
        for dest_order in permutations(destinos):
            # Tentar rota circular: origem -> dest1 -> dest2 -> ... -> origem
            rota_circular = [origem] + list(dest_order) + [origem]
            
            # Verificar se TODOS os segmentos da rota circular existem
            circular_viable = True
            for i in range(len(rota_circular) - 1):
                if (rota_circular[i], rota_circular[i+1]) not in conexoes_disponiveis:
                    circular_viable = False
                    break
            
            if circular_viable:
                viable_routes.append(rota_circular)
                print(f"\nDEBUG: Rota circular viável: {' -> '.join(rota_circular)}")
            else:
                # Se rota circular não é viável, tentar rota linear (sem retorno)
                rota_linear = [origem] + list(dest_order)
                
                linear_viable = True
                for i in range(len(rota_linear) - 1):
                    if (rota_linear[i], rota_linear[i+1]) not in conexoes_disponiveis:
                        linear_viable = False
                        break
                
                if linear_viable:
                    viable_routes.append(rota_linear)
                    print(f"\nDEBUG: Rota linear viável: {' -> '.join(rota_linear)}")
        
        if not viable_routes:
            print("\n⚠️  ERRO: Nenhuma rota viável encontrada com os dados disponíveis!")
            print("Verifique se há dados para todos os segmentos necessários.")
            return []
        
        # Para cada rota viável, gerar soluções
        for rota in viable_routes:
            print(f"\nDEBUG: Processando rota: {' -> '.join(rota)}")
            
            # Para cada segmento da rota, encontrar opções de voo e carro
            segments_options = []
            
            for i in range(len(rota) - 1):
                from_city = rota[i]
                to_city = rota[i + 1]
                
                # Buscar voos para este segmento
                voos_seg = self.df_voos[
                    (self.df_voos['origem'] == from_city) & 
                    (self.df_voos['destino'] == to_city)
                ].copy()
                
                # Buscar carros para este segmento
                carros_seg = self.df_carros[
                    (self.df_carros['local_retirada'] == from_city) & 
                    (self.df_carros['local_entrega'] == to_city)
                ].copy()
                
                # Combinar voos e carros em uma lista de opções
                opcoes_seg = []
                
                for idx, voo in voos_seg.iterrows():
                    opcoes_seg.append({
                        'tipo': 'voo',
                        'index': idx,
                        'data': voo
                    })
                
                for idx, carro in carros_seg.iterrows():
                    opcoes_seg.append({
                        'tipo': 'carro',
                        'index': idx,
                        'data': carro
                    })
                
                # ORDENAR opções por ALPHA (prioridade do usuário)
                # alpha = 1.0 -> priorizar custo (mais barato)
                # alpha = 0.0 -> priorizar tempo (mais rápido)
                alpha = self.config.get('alpha', 0.5)
                
                if opcoes_seg:
                    # Normalizar valores para ordenação
                    custos = [opt['data']['preco_numerico'] for opt in opcoes_seg]
                    tempos = [opt['data']['duracao_min'] for opt in opcoes_seg]
                    
                    min_c = min(custos)
                    max_c = max(custos)
                    min_t = min(tempos)
                    max_t = max(tempos)
                    
                    range_c = max_c - min_c if max_c > min_c else 1
                    range_t = max_t - min_t if max_t > min_t else 1
                    
                    # Calcular score baseado em alpha
                    for opt in opcoes_seg:
                        custo_norm = (opt['data']['preco_numerico'] - min_c) / range_c
                        tempo_norm = (opt['data']['duracao_min'] - min_t) / range_t
                        opt['score'] = alpha * custo_norm + (1 - alpha) * tempo_norm
                    
                    # Ordenar por score (menor é melhor)
                    opcoes_seg.sort(key=lambda x: x['score'])
                    
                    # DEBUG: Mostrar como as opções foram ordenadas
                    print(f"    Segmento {from_city} -> {to_city} (alpha={alpha:.2f}):")
                    print(f"      Total de {len(opcoes_seg)} opções ordenadas por score")
                    if len(opcoes_seg) <= 5:
                        for i, opt in enumerate(opcoes_seg[:5]):
                            print(f"        {i+1}. {opt['tipo']:6} R$ {opt['data']['preco_numerico']:6.2f} | {opt['data']['duracao_min']:4.0f}min | score={opt['score']:.3f}")
                
                if not opcoes_seg:
                    # Sem opções para este segmento (não deveria acontecer se rota é viável)
                    segments_options = None
                    break
                
                segments_options.append(opcoes_seg)
            
            # Se conseguimos opções para todos os segmentos
            if segments_options:
                print(f"DEBUG: Analisando rota {rota}")
                for i, seg_opts in enumerate(segments_options):
                    voos_count = sum(1 for opt in seg_opts if opt['tipo'] == 'voo')
                    carros_count = sum(1 for opt in seg_opts if opt['tipo'] == 'carro')
                    print(f"  Segmento {i} ({rota[i]} -> {rota[i+1]}): {voos_count} voos, {carros_count} carros")
                
                # ESTRATÉGIA: Garantir que CADA TIPO (voo/carro) de CADA SEGMENTO apareça
                
                # Criar templates de tipos (ex: [voo, voo, carro] ou [carro, voo, voo])
                tipo_options_per_segment = []
                for seg_opts in segments_options:
                    tipos_disponiveis = set()
                    if any(opt['tipo'] == 'voo' for opt in seg_opts):
                        tipos_disponiveis.add('voo')
                    if any(opt['tipo'] == 'carro' for opt in seg_opts):
                        tipos_disponiveis.add('carro')
                    tipo_options_per_segment.append(list(tipos_disponiveis))
                
                print(f"  Tipos disponíveis por segmento: {tipo_options_per_segment}")
                
                # Gerar todas as combinações de TIPOS
                from math import prod
                tipo_combos = list(product(*tipo_options_per_segment))
                print(f"  Total de padrões de tipo: {len(tipo_combos)}")
                
                # Para cada padrão de tipo, pegar TODAS as opções específicas
                for tipo_pattern in tipo_combos:
                    print(f"    Gerando soluções para padrão: {tipo_pattern}")
                    
                    # Filtrar opções de cada segmento pelo tipo do padrão
                    # E pegar apenas as TOP N opções segundo alpha (já estão ordenadas)
                    filtered_segments = []
                    max_options_per_segment = 10  # Limitar para evitar explosão combinatória
                    
                    for seg_idx, tipo_desejado in enumerate(tipo_pattern):
                        opcoes_filtradas = [
                            opt for opt in segments_options[seg_idx] 
                            if opt['tipo'] == tipo_desejado
                        ]
                        # Pegar apenas as melhores opções (já ordenadas por alpha)
                        opcoes_filtradas = opcoes_filtradas[:max_options_per_segment]
                        filtered_segments.append(opcoes_filtradas)
                    
                    # Gerar TODAS as combinações para este padrão de tipo
                    total_combos = prod(len(seg) for seg in filtered_segments)
                    print(f"      Combinações possíveis: {total_combos}")
                    
                    # Limitar apenas se houver muitas combinações
                    if total_combos <= 100:
                        # Gerar todas
                        for combo in product(*filtered_segments):
                            solutions.extend(self._create_solution_from_combo(combo, budget))
                    else:
                        # Gerar uma amostra: mais baratas, mais caras, e algumas do meio
                        all_combos = list(product(*filtered_segments))
                        
                        # Ordenar por custo
                        all_combos_with_cost = []
                        for combo in all_combos:
                            custo = sum(seg['data']['preco_numerico'] for seg in combo)
                            all_combos_with_cost.append((custo, combo))
                        all_combos_with_cost.sort(key=lambda x: x[0])  # Ordenar apenas por custo
                        
                        # Pegar 20 mais baratas, 10 mais caras, e 20 do meio
                        samples = []
                        samples.extend(all_combos_with_cost[:20])  # 20 mais baratas
                        if len(all_combos_with_cost) > 40:
                            meio = len(all_combos_with_cost) // 2
                            samples.extend(all_combos_with_cost[meio-10:meio+10])  # 20 do meio
                            samples.extend(all_combos_with_cost[-10:])  # 10 mais caras
                        
                        for custo, combo in samples:
                            solutions.extend(self._create_solution_from_combo(combo, budget))
                        
                        print(f"      Gerando amostra de {len(samples)} combinações")
                
                print(f"  Total de soluções geradas para esta rota: {len(solutions)}")
        
        print(f"\nDEBUG: Total de soluções geradas: {len(solutions)}")
        return solutions
    
    def _create_solution_from_combo(self, combo, budget):
        """Cria solução a partir de uma combinação de segmentos"""
        # Calcular custo e tempo total
        custo_total = sum(seg['data']['preco_numerico'] for seg in combo)
        tempo_total = sum(seg['data']['duracao_min'] for seg in combo)
        
        # Verificar orçamento (permitir até 20% acima para mais opções)
        if custo_total > budget * 1.2:
            return []
        
        # Construir itinerário
        itinerario_rows = []
        
        for seg in combo:
            if seg['tipo'] == 'voo':
                row = seg['data'].copy()
                row['tipo'] = 'Voo'
                itinerario_rows.append(row)
            else:
                row = seg['data'].copy()
                row['tipo'] = 'Carro'
                row['origem'] = row['local_retirada']
                row['destino'] = row['local_entrega']
                row['companhia'] = row['locadora']
                row['data_ida'] = row.get('data_inicio', '')
                itinerario_rows.append(row)
        
        if itinerario_rows:
            itinerario = pd.DataFrame(itinerario_rows)
            return [{
                'itinerario': itinerario,
                'custo': custo_total,
                'tempo': tempo_total
            }]
        
        return []
    
    def _solve_with_nsga2(self):
        """Fallback: resolver com NSGA-II se geração manual falhar"""
        try:
            # Criar problema de otimização
            problem = TripOptimizationProblem(self.df_voos, self.df_carros, self.config)
            
            # Configurar NSGA-II com parâmetros para maior diversidade
            algorithm = NSGA2(
                pop_size=200,  # População maior para mais diversidade
                sampling=BinaryRandomSampling(),
                crossover=TwoPointCrossover(),
                mutation=BitflipMutation(prob=0.05),  # Taxa de mutação para exploração
                eliminate_duplicates=True
            )
            
            # Critério de parada - mais gerações para convergência
            termination = get_termination("n_gen", 200)
            
            # Executar otimização
            res = minimize(
                problem,
                algorithm,
                termination,
                seed=None,  # Sem seed fixo para mais diversidade
                verbose=False,
                save_history=False
            )
            
            solutions = []
            
            # Pegar toda a população final e identificar o Pareto Front (rank 0)
            pop = res.pop if hasattr(res, 'pop') and res.pop is not None else None
            
            if pop is not None and len(pop) > 1:
                # Extrair objetivos e soluções da população
                F = pop.get("F")
                X = pop.get("X")
                
                # Fazer ordenação não-dominada para pegar apenas rank 0 (Pareto Front)
                nds = NonDominatedSorting()
                fronts = nds.do(F, only_non_dominated_front=False)
                
                # Pegar apenas a primeira frente (Pareto Front)
                pareto_indices = fronts[0]
                
                # Se há múltiplas soluções no Pareto Front
                if len(pareto_indices) > 1:
                    pareto_solutions = X[pareto_indices]
                    pareto_objectives = F[pareto_indices]
                    
                    # Ordenar soluções por custo (primeiro objetivo)
                    sorted_indices = np.argsort(pareto_objectives[:, 0])
                    pareto_solutions = pareto_solutions[sorted_indices]
                    pareto_objectives = pareto_objectives[sorted_indices]
                    
                    # Limitar a no máximo 10 soluções mais diversas
                    n_solutions = min(10, len(pareto_solutions))
                    
                    # Selecionar soluções espaçadas ao longo do Pareto Front
                    if n_solutions > 1:
                        indices = np.linspace(0, len(pareto_solutions) - 1, n_solutions, dtype=int)
                    else:
                        indices = [0]
                    
                    for idx in indices:
                        solution = pareto_solutions[idx]
                        objectives = pareto_objectives[idx]
                        
                        # Decodificar solução
                        n_voos = len(self.df_voos)
                        voos_sel = solution[:n_voos]
                        carros_sel = solution[n_voos:]
                        
                        # Criar itinerário
                        v_res = self.df_voos.loc[[i for i, sel in enumerate(voos_sel) if sel]].copy()
                        v_res['tipo'] = 'Voo'
                        
                        c_res = self.df_carros.loc[[j for j, sel in enumerate(carros_sel) if sel]].copy()
                        c_res['tipo'] = 'Carro'
                        c_res = c_res.rename(columns={
                            'local_retirada': 'origem',
                            'local_entrega': 'destino',
                            'locadora': 'companhia',
                            'data_inicio': 'data_ida'
                        })
                        
                        if not v_res.empty or not c_res.empty:
                            itinerario = pd.concat([v_res, c_res], ignore_index=True)
                            itinerario_ordenado = self.ordenar_itinerario(itinerario)
                            
                            # Validar se o itinerário é válido antes de adicionar
                            if self._validate_itinerary(itinerario_ordenado):
                                solutions.append({
                                    'itinerario': itinerario_ordenado,
                                    'custo': objectives[0],
                                    'tempo': objectives[1]
                                })
                else:
                    # Apenas uma solução no Pareto Front
                    pareto_idx = pareto_indices[0]
                    solution = X[pareto_idx]
                    objectives = F[pareto_idx]
                    
                    n_voos = len(self.df_voos)
                    voos_sel = solution[:n_voos]
                    carros_sel = solution[n_voos:]
                    
                    v_res = self.df_voos.loc[[i for i, sel in enumerate(voos_sel) if sel]].copy()
                    v_res['tipo'] = 'Voo'
                    
                    c_res = self.df_carros.loc[[j for j, sel in enumerate(carros_sel) if sel]].copy()
                    c_res['tipo'] = 'Carro'
                    c_res = c_res.rename(columns={
                        'local_retirada': 'origem',
                        'local_entrega': 'destino',
                        'locadora': 'companhia',
                        'data_inicio': 'data_ida'
                    })
                    
                    if not v_res.empty or not c_res.empty:
                        itinerario = pd.concat([v_res, c_res], ignore_index=True)
                        itinerario_ordenado = self.ordenar_itinerario(itinerario)
                        
                        # Validar se o itinerário é válido antes de adicionar
                        if self._validate_itinerary(itinerario_ordenado):
                            solutions.append({
                                'itinerario': itinerario_ordenado,
                                'custo': objectives[0],
                                'tempo': objectives[1]
                            })
            else:
                # Fallback: Se não conseguimos pegar da população, usar res.X e res.F
                if hasattr(res, 'F') and res.F is not None:
                    solution = res.X if len(res.X.shape) == 1 else res.X[0]
                    objectives = res.F if len(res.F.shape) == 1 else res.F[0]
                    
                    n_voos = len(self.df_voos)
                    voos_sel = solution[:n_voos]
                    carros_sel = solution[n_voos:]
                    
                    v_res = self.df_voos.loc[[i for i, sel in enumerate(voos_sel) if sel]].copy()
                    v_res['tipo'] = 'Voo'
                    
                    c_res = self.df_carros.loc[[j for j, sel in enumerate(carros_sel) if sel]].copy()
                    c_res['tipo'] = 'Carro'
                    c_res = c_res.rename(columns={
                        'local_retirada': 'origem',
                        'local_entrega': 'destino',
                        'locadora': 'companhia',
                        'data_inicio': 'data_ida'
                    })
                    
                    if not v_res.empty or not c_res.empty:
                        itinerario = pd.concat([v_res, c_res], ignore_index=True)
                        itinerario_ordenado = self.ordenar_itinerario(itinerario)
                        
                        # Validar se o itinerário é válido antes de adicionar
                        if self._validate_itinerary(itinerario_ordenado):
                            solutions.append({
                                'itinerario': itinerario_ordenado,
                                'custo': objectives[0],
                                'tempo': objectives[1]
                            })
            
            return solutions
        except Exception as e:
            print(f"Erro no NSGA-II: {e}")
            return []

    def ordenar_itinerario(self, df):
        ordenado, atual, pool = [], self.config['origem'], df.copy()
        while not pool.empty:
            match = pool[pool['origem'] == atual]
            if match.empty:
                break
            linha = match.iloc[0]
            ordenado.append(linha)
            atual, pool = linha['destino'], pool.drop(match.index[0])
        return pd.DataFrame(ordenado)