import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="ShopFlow Dashboard", page_icon="🛒", layout="wide")

PEDIDO_URL = os.getenv("PEDIDO_URL", "http://pedido:8001")
PAGAMENTO_URL = os.getenv("PAGAMENTO_URL", "http://pagamento:8002")
LOGISTICA_URL = os.getenv("LOGISTICA_URL", "http://logistica:8003")

DEFAULT_METRICS_PEDIDO = {
    "servico": "pedido",
    "status": "indisponivel",
    "eventos_publicados": 0,
    "eventos_descartados": 0,
    "taxa_erro_schema": 0.0,
    "total_criados": 0,
    "total_confirmados": 0,
    "total_cancelados": 0,
    "total_despachados": 0,
    "total_entregues": 0,
    "gmv": 0.0,
    "taxa_conversao": 0.0,
    "taxa_bloqueio_antifraude": 0.0,
    "ultimos_eventos": [],
    "pedidos_recentes": [],
    "eventos_por_minuto": [],
    "gmv_por_hora": [],
}

DEFAULT_METRICS_PAGAMENTO = {
    "servico": "pagamento",
    "status": "indisponivel",
    "eventos_publicados": 0,
    "eventos_descartados": 0,
    "taxa_erro_schema": 0.0,
    "total_pagamentos": 0,
    "total_aprovados": 0,
    "total_recusados": 0,
    "taxa_aprovacao_pagamentos": 0.0,
    "ultimos_eventos": [],
    "eventos_por_minuto": [],
}

DEFAULT_METRICS_LOGISTICA = {
    "servico": "logistica",
    "status": "indisponivel",
    "eventos_publicados": 0,
    "eventos_descartados": 0,
    "taxa_erro_schema": 0.0,
    "total_entregas": 0,
    "total_despachados": 0,
    "total_entregues": 0,
    "entregues_no_prazo_percentual": 0.0,
    "ultimos_eventos": [],
    "eventos_por_minuto": [],
}


def get_json(url: str, default: dict) -> dict:
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        return response.json()
    except Exception:
        return default


def check_health(base_url: str) -> bool:
    data = get_json(f"{base_url}/health", {})
    return data.get("status") == "ok"


def status_exibicao(ok: bool) -> str:
    return "🟢 OK" if ok else "🔴 Fora"


def encurtar(valor: str | None, tamanho: int = 6) -> str:
    if not valor:
        return "-"
    return valor[:tamanho]


def resolver_status_pedido(p: dict) -> str:
    if p.get("entregue_em") or p.get("status") == "entregue":
        return "entregue"
    if p.get("despachado_em") or p.get("status") == "despachado":
        return "despachado"
    if p.get("confirmado_em") or p.get("status") == "confirmado":
        return "confirmado"
    if p.get("status") == "cancelado" or p.get("cancelado_em"):
        return "cancelado"
    if p.get("status") == "criado":
        return "criado"
    return "em andamento"


def indicador_status(status: str) -> str:
    if status == "entregue":
        return "🟢 entregue"
    if status == "cancelado":
        return "🔴 cancelado"
    return "🟡 andamento"


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def filtrar_por_periodo(
    registros: list[dict],
    campo_data: str,
    periodo: str,
) -> list[dict]:
    if periodo == "Total":
        return registros
    agora = datetime.now(timezone.utc)
    if periodo == "Última hora":
        limite = agora - timedelta(hours=1)
    else:
        limite = agora - timedelta(days=1)

    filtrados = []
    for item in registros:
        dt = parse_iso(item.get(campo_data))
        if dt and dt >= limite:
            filtrados.append(item)
    return filtrados


st_autorefresh(interval=5000, key="shopflow_refresh")

st.title("ShopFlow Dashboard")
st.caption("Monitoramento em tempo real — Grupo 2404826 | atualização a cada 5 segundos")

health_pedido = check_health(PEDIDO_URL)
health_pagamento = check_health(PAGAMENTO_URL)
health_logistica = check_health(LOGISTICA_URL)

metrics_pedido = get_json(
    f"{PEDIDO_URL}/metrics",
    DEFAULT_METRICS_PEDIDO.copy(),
)
metrics_pagamento = get_json(
    f"{PAGAMENTO_URL}/metrics",
    DEFAULT_METRICS_PAGAMENTO.copy(),
)
metrics_logistica = get_json(
    f"{LOGISTICA_URL}/metrics",
    DEFAULT_METRICS_LOGISTICA.copy(),
)

aba1, aba2, aba3 = st.tabs(
    ["Saúde dos Serviços", "Comunicação ao Vivo", "KPIs de Negócio"]
)

with aba1:
    st.subheader("Status operacional")
    col1, col2, col3 = st.columns(3)
    col1.metric("Pedido", status_exibicao(health_pedido))
    col2.metric("Pagamento", status_exibicao(health_pagamento))
    col3.metric("Logística", status_exibicao(health_logistica))

    st.subheader("Eventos publicados")
    col4, col5, col6 = st.columns(3)
    col4.metric("Pedido", metrics_pedido.get("eventos_publicados", 0))
    col5.metric("Pagamento", metrics_pagamento.get("eventos_publicados", 0))
    col6.metric("Logística", metrics_logistica.get("eventos_publicados", 0))

    st.subheader("Taxa de erro por schema inválido (%)")
    col7, col8, col9 = st.columns(3)
    col7.metric("Pedido", f"{metrics_pedido.get('taxa_erro_schema', 0):.2f}%")
    col8.metric("Pagamento", f"{metrics_pagamento.get('taxa_erro_schema', 0):.2f}%")
    col9.metric("Logística", f"{metrics_logistica.get('taxa_erro_schema', 0):.2f}%")

    st.subheader("Últimos 10 eventos (todos os serviços)")
    todos_eventos = []
    for nome, metrics in [
        ("pedido", metrics_pedido),
        ("pagamento", metrics_pagamento),
        ("logistica", metrics_logistica),
    ]:
        for ev in metrics.get("ultimos_eventos", []):
            todos_eventos.append(
                {
                    "timestamp": ev.get("timestamp"),
                    "evento_tipo": ev.get("evento_tipo"),
                    "correlation_id": encurtar(ev.get("correlation_id")),
                    "servico": ev.get("servico", nome),
                }
            )

    if todos_eventos:
        df_eventos = pd.DataFrame(todos_eventos)
        df_eventos = df_eventos.sort_values("timestamp", ascending=False).head(10)
        st.dataframe(df_eventos, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum evento registrado ainda.")

with aba2:
    st.subheader("Throughput — eventos por minuto (últimos 10 minutos)")

    dfs_throughput = []
    for nome, metrics in [
        ("Pedido", metrics_pedido),
        ("Pagamento", metrics_pagamento),
        ("Logística", metrics_logistica),
    ]:
        dados = metrics.get("eventos_por_minuto", [])
        if dados:
            df = pd.DataFrame(dados)
            df = df.rename(columns={"quantidade": nome})
            df = df.set_index("minuto")
            dfs_throughput.append(df[[nome]])

    if dfs_throughput:
        df_chart = pd.concat(dfs_throughput, axis=1).fillna(0)
        st.line_chart(df_chart)
    else:
        st.info("Nenhum dado de throughput disponível.")

    st.subheader("Contadores de pedidos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Criados", metrics_pedido.get("total_criados", 0))
    c2.metric("Confirmados", metrics_pedido.get("total_confirmados", 0))
    c3.metric("Cancelados", metrics_pedido.get("total_cancelados", 0))
    c4.metric("Entregues", metrics_pedido.get("total_entregues", 0))

    st.subheader("Saga — 50 pedidos mais recentes")
    pedidos = metrics_pedido.get("pedidos_recentes", [])
    if pedidos:
        linhas = []
        for p in pedidos:
            status = resolver_status_pedido(p)
            linhas.append(
                {
                    "indicador": indicador_status(status),
                    "pedido_id": encurtar(p.get("pedido_id"), 8),
                    "correlation_id": encurtar(p.get("correlation_id")),
                    "status": status,
                    "valor_total": p.get("valor_total"),
                    "forma_pagamento": p.get("forma_pagamento"),
                    "pagamento_ok": p.get("pagamento_ok"),
                    "fraude_ok": p.get("fraude_ok"),
                    "criado_em": p.get("criado_em"),
                    "confirmado_em": p.get("confirmado_em"),
                    "despachado_em": p.get("despachado_em"),
                    "entregue_em": p.get("entregue_em"),
                }
            )
        df_pedidos = pd.DataFrame(linhas)
        st.dataframe(df_pedidos, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum pedido registrado. Execute o gerador de carga.")

with aba3:
    periodo = st.selectbox("Período", ["Última hora", "Último dia", "Total"])

    pedidos_filtrados = filtrar_por_periodo(
        metrics_pedido.get("pedidos_recentes", []),
        "criado_em",
        periodo,
    )
    gmv_filtrado = filtrar_por_periodo(
        metrics_pedido.get("gmv_por_hora", []),
        "hora",
        periodo,
    )

    if periodo != "Total" and pedidos_filtrados:
        confirmados = sum(
            1
            for p in pedidos_filtrados
            if resolver_status_pedido(p) in ("confirmado", "despachado", "entregue")
        )
        criados = len(pedidos_filtrados)
        gmv = sum(
            p.get("valor_total", 0)
            for p in pedidos_filtrados
            if resolver_status_pedido(p) in ("confirmado", "despachado", "entregue")
        )
        bloqueios = sum(
            1 for p in pedidos_filtrados if resolver_status_pedido(p) == "cancelado"
        )
        taxa_conversao = round(confirmados / criados * 100, 2) if criados else 0.0
        taxa_bloqueio = round(bloqueios / criados * 100, 2) if criados else 0.0
    else:
        gmv = metrics_pedido.get("gmv", 0)
        taxa_conversao = metrics_pedido.get("taxa_conversao", 0)
        taxa_bloqueio = metrics_pedido.get("taxa_bloqueio_antifraude", 0)

    st.subheader("KPIs de negócio")
    k1, k2, k3 = st.columns(3)
    k4, k5 = st.columns(2)

    k1.metric("GMV (R$)", f"{gmv:,.2f}")
    k2.metric(
        "Taxa aprovação pagamentos (%)",
        f"{metrics_pagamento.get('taxa_aprovacao_pagamentos', 0):.2f}",
    )
    k3.metric("Taxa de conversão (%)", f"{taxa_conversao:.2f}")
    k4.metric("Taxa bloqueio antifraude (%)", f"{taxa_bloqueio:.2f}")
    k5.metric(
        "Entregues no prazo (%)",
        f"{metrics_logistica.get('entregues_no_prazo_percentual', 0):.2f}",
    )

    st.subheader("GMV acumulado por hora")
    if gmv_filtrado:
        df_gmv = pd.DataFrame(gmv_filtrado)
        df_gmv = df_gmv.set_index("hora")
        st.line_chart(df_gmv[["gmv"]])
    elif metrics_pedido.get("gmv_por_hora"):
        df_gmv = pd.DataFrame(metrics_pedido["gmv_por_hora"])
        df_gmv = df_gmv.set_index("hora")
        st.line_chart(df_gmv[["gmv"]])
    else:
        st.info("Nenhum dado disponível para o período selecionado.")
