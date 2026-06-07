"""
Produtor de eventos do serviço de Logística.
"""

from datetime import datetime, timezone

from models import EnvelopeEvento
from rabbitmq import publicar

EXCHANGE_LOGISTICA = "logistica.eventos"


def publicar_evento(
    evento_tipo: str,
    correlation_id: str,
    payload: dict,
) -> EnvelopeEvento:
    envelope = EnvelopeEvento(
        evento_tipo=evento_tipo,
        correlation_id=correlation_id,
        payload=payload,
    )
    publicar(EXCHANGE_LOGISTICA, evento_tipo, envelope.model_dump())
    return envelope


def publicar_pedido_despachado(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pedido.despachado", correlation_id, payload)


def publicar_pedido_entregue(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pedido.entregue", correlation_id, payload)
