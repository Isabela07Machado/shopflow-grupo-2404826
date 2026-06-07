import streamlit as st

st.set_page_config(page_title="ShopFlow Dashboard", page_icon="🛒", layout="wide")

st.title("ShopFlow Dashboard")
st.write("Dashboard em construção")

st.subheader("Serviços planejados")

servicos = [
    "Pedido — gerencia criação e confirmação de pedidos",
    "Pagamento — processa cobranças e aprovações",
    "Logística — controla despacho e entrega",
    "Antifraude (mock) — simula análise de risco",
    "Catálogo (mock) — simula atualização de estoque",
]

for servico in servicos:
    st.markdown(f"- {servico}")

st.info(
    "No Módulo 3 este dashboard exibirá métricas, status dos pedidos "
    "e integração com os microsserviços."
)
