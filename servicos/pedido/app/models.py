from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PayloadBase(BaseModel):
    """Schema base para payloads de eventos do serviço de pedido."""

    pedido_id: str | None = None
    cliente_id: str | None = None


class EnvelopeEvento(BaseModel):
    """Envelope padrão para publicação e consumo de eventos via RabbitMQ."""

    evento_id: str = Field(default_factory=lambda: str(uuid4()))
    evento_tipo: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
    )
    correlation_id: str
    versao_schema: str = "1.0"
    payload: dict[str, Any] = Field(default_factory=dict)
