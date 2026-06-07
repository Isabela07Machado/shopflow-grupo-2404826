"""
Consumer do serviço de Pedido — orquestra a saga.
"""

import json
import logging

from database import (
    PedidoORM,
    agora_utc,
    evento_ja_processado,
    get_db,
    init_db,
    marcar_evento_processado,
    registrar_evento,
)
from models import EnvelopeEvento
from producer import publicar_pedido_cancelado, publicar_pedido_confirmado
from pydantic import ValidationError
from rabbitmq import configurar_fila, conectar, consumir_filas, declarar_exchanges
from schemas import (
    PayloadAprovadoFraude,
    PayloadBloqueadoFraude,
    PayloadPagamentoAprovado,
    PayloadPagamentoRecusado,
    PayloadPedidoDespachado,
    PayloadPedidoEntregue,
)

logger = logging.getLogger(__name__)

FILA_PAGAMENTO = "pedido.pagamento"
FILA_ANTIFRAUDE = "pedido.antifraude"
FILA_LOGISTICA = "pedido.logistica"


def _iso_agora() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _buscar_por_correlation(db, correlation_id: str) -> PedidoORM | None:
    return (
        db.query(PedidoORM)
        .filter(PedidoORM.correlation_id == correlation_id)
        .first()
    )


def _buscar_por_pedido_id(db, pedido_id: str) -> PedidoORM | None:
    return db.query(PedidoORM).filter(PedidoORM.pedido_id == pedido_id).first()


def _tentar_confirmar(db, pedido: PedidoORM) -> None:
    if pedido.status in ("confirmado", "cancelado", "despachado", "entregue"):
        return
    if pedido.pagamento_ok is True and pedido.fraude_ok is True:
        pedido.status = "confirmado"
        pedido.confirmado_em = agora_utc()
        db.commit()

        itens = json.loads(pedido.itens_json or "[]")
        envelope = publicar_pedido_confirmado(
            pedido.correlation_id,
            {
                "pedido_id": pedido.pedido_id,
                "cliente_id": pedido.cliente_id,
                "valor_total": float(pedido.valor_total),
                "confirmado_em": _iso_agora(),
                "itens_atualizados": len(itens),
            },
        )
        registrar_evento(
            db,
            envelope.evento_id,
            "pedido.confirmado",
            pedido.correlation_id,
            "publicado",
        )
        db.commit()
        logger.info(
            "[pedido] pedido.confirmado publicado correlation_id=%s",
            pedido.correlation_id,
        )


def _cancelar(db, pedido: PedidoORM, motivo: str) -> None:
    if pedido.status in ("confirmado", "cancelado", "despachado", "entregue"):
        return
    pedido.status = "cancelado"
    pedido.cancelado_em = agora_utc()
    pedido.motivo_cancelamento = motivo
    db.commit()

    envelope = publicar_pedido_cancelado(
        pedido.correlation_id,
        {
            "pedido_id": pedido.pedido_id,
            "motivo": motivo,
            "valor_total": float(pedido.valor_total),
            "cancelado_em": _iso_agora(),
        },
    )
    registrar_evento(
        db,
        envelope.evento_id,
        "pedido.cancelado",
        pedido.correlation_id,
        "publicado",
    )
    db.commit()
    logger.info(
        "[pedido] pedido.cancelado publicado correlation_id=%s motivo=%s",
        pedido.correlation_id,
        motivo,
    )


def processar_evento(evento_dict: dict) -> None:
    db = get_db()
    try:
        envelope = EnvelopeEvento.model_validate(evento_dict)
    except ValidationError as erro:
        logger.error("[pedido] Envelope inválido descartado: %s", erro)
        registrar_evento(db, None, "invalido", None, "consumido", valido=False)
        db.commit()
        return

    if evento_ja_processado(db, envelope.evento_id):
        logger.info(
            "[pedido] Evento duplicado ignorado evento_id=%s",
            envelope.evento_id,
        )
        return

    registrar_evento(
        db,
        envelope.evento_id,
        envelope.evento_tipo,
        envelope.correlation_id,
        "consumido",
    )

    try:
        pedido = _buscar_por_correlation(db, envelope.correlation_id)
        if not pedido and envelope.payload.get("pedido_id"):
            pedido = _buscar_por_pedido_id(db, envelope.payload["pedido_id"])

        if not pedido:
            logger.warning(
                "[pedido] Pedido não encontrado correlation_id=%s",
                envelope.correlation_id,
            )
            marcar_evento_processado(db, envelope.evento_id)
            db.commit()
            return

        if envelope.evento_tipo == "pagamento.aprovado":
            PayloadPagamentoAprovado.model_validate(envelope.payload)
            if pedido.status not in ("cancelado", "confirmado", "despachado", "entregue"):
                pedido.pagamento_ok = True
                db.commit()
                _tentar_confirmar(db, pedido)

        elif envelope.evento_tipo == "pagamento.recusado":
            PayloadPagamentoRecusado.model_validate(envelope.payload)
            pedido.pagamento_ok = False
            db.commit()
            _cancelar(db, pedido, "pagamento_recusado")

        elif envelope.evento_tipo == "pedido.aprovado_fraude":
            PayloadAprovadoFraude.model_validate(envelope.payload)
            if pedido.status not in ("cancelado", "confirmado", "despachado", "entregue"):
                pedido.fraude_ok = True
                db.commit()
                _tentar_confirmar(db, pedido)

        elif envelope.evento_tipo == "pedido.bloqueado_fraude":
            PayloadBloqueadoFraude.model_validate(envelope.payload)
            pedido.fraude_ok = False
            db.commit()
            _cancelar(db, pedido, "fraude_detectada")

        elif envelope.evento_tipo == "pedido.despachado":
            PayloadPedidoDespachado.model_validate(envelope.payload)
            if pedido.status not in ("cancelado",):
                pedido.status = "despachado"
                pedido.despachado_em = agora_utc()
                db.commit()
                logger.info(
                    "[pedido] Status atualizado para despachado pedido_id=%s",
                    pedido.pedido_id,
                )

        elif envelope.evento_tipo == "pedido.entregue":
            payload = PayloadPedidoEntregue.model_validate(envelope.payload)
            if pedido.status not in ("cancelado",):
                pedido.status = "entregue"
                pedido.entregue_em = agora_utc()
                pedido.sla_cumprido = payload.sla_cumprido
                db.commit()
                logger.info(
                    "[pedido] Status atualizado para entregue pedido_id=%s",
                    pedido.pedido_id,
                )

        marcar_evento_processado(db, envelope.evento_id)
        db.commit()

    except ValidationError as erro:
        logger.error(
            "[pedido] Payload inválido descartado evento_tipo=%s: %s",
            envelope.evento_tipo,
            erro,
        )
        registrar_evento(
            db,
            envelope.evento_id,
            envelope.evento_tipo,
            envelope.correlation_id,
            "consumido",
            valido=False,
        )
        marcar_evento_processado(db, envelope.evento_id)
        db.commit()
    except Exception as erro:
        logger.error("[pedido] Erro ao processar evento: %s", erro)
        db.rollback()
    finally:
        db.close()


def _configurar_filas() -> list[str]:
    conexao = conectar()
    canal = conexao.channel()
    declarar_exchanges(canal)

    configurar_fila(
        canal,
        FILA_PAGAMENTO,
        "pagamento.eventos",
        ["pagamento.aprovado", "pagamento.recusado"],
    )
    configurar_fila(
        canal,
        FILA_ANTIFRAUDE,
        "antifraude.eventos",
        ["pedido.aprovado_fraude", "pedido.bloqueado_fraude"],
    )
    configurar_fila(
        canal,
        FILA_LOGISTICA,
        "logistica.eventos",
        ["pedido.despachado", "pedido.entregue"],
    )
    conexao.close()
    return [FILA_PAGAMENTO, FILA_ANTIFRAUDE, FILA_LOGISTICA]


def iniciar_consumer() -> None:
    init_db()
    filas = _configurar_filas()
    consumir_filas(filas, processar_evento)
