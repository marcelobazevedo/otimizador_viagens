import streamlit as st
from backend.engine import TripOptimizerEngine
from backend.data_mock import get_mock_data
from backend.preprocessor import sanitize_data

st.title("🏆 World Cup 2026 Trip Optimizer")

# Sidebar para inputs do usuário
budget = st.sidebar.number_input("Orçamento Máximo (R$)", value=15000)
alpha = st.sidebar.slider("Prioridade: Custo", 0.0, 1.0, 0.7)
beta = 1.0 - alpha

if st.button("Otimizar Roteiro"):
    raw_data = get_mock_data() # Ou chamada ao seu Crawler
    sanitized = sanitize_data(raw_data, budget, alpha, beta)
    
    engine = TripOptimizerEngine(sanitized['flights'], sanitized['events'], sanitized['config'])
    itinerary = engine.solve()
    
    if itinerary:
        st.success("Itinerário Ótimo Encontrado!")
        st.table(itinerary)
    else:
        st.error("Nenhuma solução viável encontrada para as restrições informadas.")