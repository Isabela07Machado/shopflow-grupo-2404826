"""
Produtor de eventos do serviço de Pagamento.
"""

from datetime import datetime, timezone

from models import EnvelopeEvento
from rabbitmq import publicar

EXCHANGE_PAGAMENTO = "pagamento.eventos"


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
    publicar(EXCHANGE_PAGAMENTO, evento_tipo, envelope.model_dump())
    return envelope


def publicar_pagamento_aprovado(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pagamento.aprovado", correlation_id, payload)


def publicar_pagamento_recusado(correlation_id: str, payload: dict) -> EnvelopeEvento:
    return publicar_evento("pagamento.recusado", correlation_id, payload)
