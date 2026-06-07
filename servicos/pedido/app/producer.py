"""
Produtor de eventos do serviço de Pedido.
"""

from datetime import datetime, timezone

from models import EnvelopeEvento
from rabbitmq import publicar

EXCHANGE_PEDIDO = "pedido.eventos"


def _iso_agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


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
    publicar(EXCHANGE_PEDIDO, evento_tipo, envelope.model_dump())
    return envelope


def publicar_pedido_criado(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pedido.criado", correlation_id, payload)


def publicar_pedido_confirmado(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pedido.confirmado", correlation_id, payload)


def publicar_pedido_cancelado(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pedido.cancelado", correlation_id, payload)
