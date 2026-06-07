from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class PayloadBase(BaseModel):
    pedido_id: str | None = None
    cliente_id: str | None = None


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
    quantidade: int = Field(ge=1)
    preco_unitario: Decimal = Field(ge=0)

    @field_validator("preco_unitario")
    @classmethod
    def duas_casas(cls, valor: Decimal) -> Decimal:
        return Decimal(str(valor)).quantize(Decimal("0.01"))


class EnderecoEntrega(BaseModel):
    cep: str
    cidade: str
    uf: str


class PayloadPedidoCriado(BaseModel):
    pedido_id: str
    cliente_id: str
    itens: list[ItemPedido]
    valor_total: Decimal
    forma_pagamento: Literal["cartao_credito", "pix", "boleto"]
    endereco_entrega: EnderecoEntrega
    timestamp_pedido: str

    @model_validator(mode="after")
    def validar_total(self) -> "PayloadPedidoCriado":
        calculado = sum(
            (item.quantidade * item.preco_unitario for item in self.itens),
            Decimal("0"),
        ).quantize(Decimal("0.01"))
        if calculado != self.valor_total.quantize(Decimal("0.01")):
            raise ValueError("valor_total deve ser a soma de quantidade x preco_unitario")
        if len(self.itens) < 1:
            raise ValueError("Deve ter no mínimo 1 item")
        return self


class PayloadPagamentoAprovado(BaseModel):
    pedido_id: str
    transacao_id: str
    valor_cobrado: Decimal
    forma_pagamento: str
    aprovado_em: str


class PayloadPagamentoRecusado(BaseModel):
    pedido_id: str
    transacao_id: str
    motivo_recusa: Literal["saldo_insuficiente", "cartao_invalido", "risco_alto"]
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
    motivo: Literal["pagamento_recusado", "fraude_detectada"]
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


class PedidoCreate(BaseModel):
    cliente_id: str | None = None
    itens: list[ItemPedido]
    forma_pagamento: Literal["cartao_credito", "pix", "boleto"]
    endereco_entrega: EnderecoEntrega

    @model_validator(mode="after")
    def validar_itens(self) -> "PedidoCreate":
        if len(self.itens) < 1:
            raise ValueError("Deve ter no mínimo 1 item")
        return self


class PedidoResponse(BaseModel):
    pedido_id: str
    correlation_id: str
    cliente_id: str
    status: str
    pagamento_ok: bool | None = None
    fraude_ok: bool | None = None
    valor_total: Decimal
    forma_pagamento: str
    itens: list[ItemPedido]
    endereco_entrega: EnderecoEntrega
    criado_em: datetime | None = None
    confirmado_em: datetime | None = None
    cancelado_em: datetime | None = None
    motivo_cancelamento: str | None = None
    despachado_em: datetime | None = None
    entregue_em: datetime | None = None
    sla_cumprido: bool | None = None

    model_config = {"from_attributes": True}
