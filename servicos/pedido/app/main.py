import json
import logging
import os
import threading
from decimal import Decimal
from uuid import uuid4

from consumer import iniciar_consumer
from database import (
    PedidoORM,
    agora_utc,
    get_db,
    init_db,
    registrar_evento,
)
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from metrics import obter_metrics
from producer import publicar_pedido_criado
from schemas import PedidoCreate, PedidoResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ShopFlow - Pedido", version="2.0.0")


def _iso_agora() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _calcular_total(itens) -> Decimal:
    total = sum(
        (item.quantidade * item.preco_unitario for item in itens),
        Decimal("0"),
    )
    return total.quantize(Decimal("0.01"))


def _pedido_para_response(pedido: PedidoORM) -> PedidoResponse:
    itens = json.loads(pedido.itens_json or "[]")
    endereco = json.loads(pedido.endereco_json or "{}")
    return PedidoResponse(
        pedido_id=pedido.pedido_id,
        correlation_id=pedido.correlation_id,
        cliente_id=pedido.cliente_id,
        status=pedido.status,
        pagamento_ok=pedido.pagamento_ok,
        fraude_ok=pedido.fraude_ok,
        valor_total=Decimal(str(pedido.valor_total)),
        forma_pagamento=pedido.forma_pagamento,
        itens=itens,
        endereco_entrega=endereco,
        criado_em=pedido.criado_em,
        confirmado_em=pedido.confirmado_em,
        cancelado_em=pedido.cancelado_em,
        motivo_cancelamento=pedido.motivo_cancelamento,
        despachado_em=pedido.despachado_em,
        entregue_em=pedido.entregue_em,
        sla_cumprido=pedido.sla_cumprido,
    )


@app.on_event("startup")
def startup():
    init_db()
    thread = threading.Thread(target=iniciar_consumer, daemon=True)
    thread.start()
    logger.info("[pedido] Serviço iniciado — consumer em thread separada")


@app.get("/health")
def health():
    return {"status": "ok", "servico": "pedido"}


@app.get("/metrics")
def metrics():
    db = get_db()
    try:
        return obter_metrics(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "servico": "pedido",
        "porta": int(os.getenv("PEDIDO_PORT", "8001")),
        "docs": "/docs",
    }


@app.post("/pedidos", response_model=PedidoResponse, status_code=201)
def criar_pedido(dados: PedidoCreate):
    pedido_id = str(uuid4())
    correlation_id = str(uuid4())
    cliente_id = dados.cliente_id or str(uuid4())
    valor_total = _calcular_total(dados.itens)
    agora = agora_utc()

    db = get_db()
    try:
        pedido = PedidoORM(
            pedido_id=pedido_id,
            correlation_id=correlation_id,
            cliente_id=cliente_id,
            status="criado",
            pagamento_ok=None,
            fraude_ok=None,
            valor_total=valor_total,
            forma_pagamento=dados.forma_pagamento,
            itens_json=json.dumps([item.model_dump(mode="json") for item in dados.itens]),
            endereco_json=json.dumps(dados.endereco_entrega.model_dump()),
            criado_em=agora,
        )
        db.add(pedido)
        db.commit()

        payload_evento = {
            "pedido_id": pedido_id,
            "cliente_id": cliente_id,
            "itens": [item.model_dump(mode="json") for item in dados.itens],
            "valor_total": float(valor_total),
            "forma_pagamento": dados.forma_pagamento,
            "endereco_entrega": dados.endereco_entrega.model_dump(),
            "timestamp_pedido": _iso_agora(),
        }

        envelope = publicar_pedido_criado(correlation_id, payload_evento)
        registrar_evento(
            db,
            envelope.evento_id,
            "pedido.criado",
            correlation_id,
            "publicado",
        )
        db.commit()

        logger.info(
            "[pedido] pedido.criado publicado correlation_id=%s pedido_id=%s",
            correlation_id,
            pedido_id,
        )

        return _pedido_para_response(pedido)
    except Exception as erro:
        db.rollback()
        logger.error("[pedido] Erro ao criar pedido: %s", erro)
        raise HTTPException(status_code=500, detail=str(erro)) from erro
    finally:
        db.close()


@app.get("/pedidos/{pedido_id}", response_model=PedidoResponse)
def obter_pedido(pedido_id: str):
    db = get_db()
    try:
        pedido = db.query(PedidoORM).filter(PedidoORM.pedido_id == pedido_id).first()
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        return _pedido_para_response(pedido)
    finally:
        db.close()
