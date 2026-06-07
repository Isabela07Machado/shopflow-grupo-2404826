from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class PayloadBase(BaseModel):
    pedido_id: str | None = None
    transportadora: str | None = None
    codigo_rastreio: str | None = None


class EnvelopeEvento(BaseModel):
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


class ItemPedido(BaseModel):
    produto_id: str
    quantidade: int
    preco_unitario: Decimal


class EnderecoEntrega(BaseModel):
    cep: str
    cidade: str
    uf: str


class PayloadPedidoCriado(BaseModel):
    pedido_id: str
    cliente_id: str
    itens: list[ItemPedido]
    valor_total: Decimal
    forma_pagamento: str
    endereco_entrega: EnderecoEntrega
    timestamp_pedido: str


class PayloadPagamentoAprovado(BaseModel):
    pedido_id: str
    transacao_id: str
    valor_cobrado: Decimal
    forma_pagamento: str
    aprovado_em: str


class PayloadPagamentoRecusado(BaseModel):
    pedido_id: str
    transacao_id: str
    motivo_recusa: str
    recusado_em: str


class PayloadAprovadoFraude(BaseModel):
    pedido_id: str
    decisao: Literal["aprovado"]
    avaliado_em: str


class PayloadBloqueadoFraude(BaseModel):
    pedido_id: str
    decisao: Literal["bloqueado"]
    motivo: str
    avaliado_em: str


class PayloadPedidoConfirmado(BaseModel):
    pedido_id: str
    cliente_id: str
    valor_total: Decimal
    confirmado_em: str


class PayloadPedidoCancelado(BaseModel):
    pedido_id: str
    motivo: str
    valor_total: Decimal
    cancelado_em: str


class PayloadPedidoDespachado(BaseModel):
    pedido_id: str
    codigo_rastreio: str
    transportadora: str
    previsao_entrega: str
    despachado_em: str


class PayloadPedidoEntregue(BaseModel):
    pedido_id: str
    codigo_rastreio: str
    entregue_em: str
    sla_cumprido: bool


class PayloadEstoqueAtualizado(BaseModel):
    pedido_id: str
    itens_atualizados: int
    atualizado_em: str
