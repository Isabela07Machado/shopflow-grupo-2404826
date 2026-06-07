"""
Consumer do serviço de Pagamento.
"""

import json
import logging
import random
import time
from decimal import Decimal
from uuid import uuid4

from database import (
    PagamentoORM,
    agora_utc,
    evento_ja_processado,
    get_db,
    init_db,
    marcar_evento_processado,
    registrar_evento,
)
from models import EnvelopeEvento
from producer import publicar_pagamento_aprovado, publicar_pagamento_recusado
from pydantic import ValidationError
from rabbitmq import conectar, declarar_exchanges
from schemas import PayloadPedidoCriado

logger = logging.getLogger(__name__)

FILA = "pagamento.pedido.criado"
EXCHANGE_PEDIDO = "pedido.eventos"
MOTIVOS_RECUSA = ["saldo_insuficiente", "cartao_invalido", "risco_alto"]


def _iso_agora() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _decidir_pagamento(valor_total: Decimal) -> tuple[bool, str | None]:
    if valor_total > Decimal("1500"):
        return False, "risco_alto"
    if random.random() < 0.8:
        return True, None
    return False, random.choice(["saldo_insuficiente", "cartao_invalido"])


def processar_evento(evento_dict: dict) -> None:
    db = get_db()
    try:
        envelope = EnvelopeEvento.model_validate(evento_dict)
    except ValidationError as erro:
        logger.error("[pagamento] Envelope inválido descartado: %s", erro)
        registrar_evento(db, None, "invalido", None, "descartado", valido=False)
        db.commit()
        return

    if envelope.evento_tipo != "pedido.criado":
        return

    if evento_ja_processado(db, envelope.evento_id):
        logger.info(
            "[pagamento] Evento duplicado ignorado evento_id=%s",
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
        payload = PayloadPedidoCriado.model_validate(envelope.payload)
        transacao_id = str(uuid4())
        aprovado, motivo = _decidir_pagamento(payload.valor_total)

        pagamento = PagamentoORM(
            transacao_id=transacao_id,
            pedido_id=payload.pedido_id,
            correlation_id=envelope.correlation_id,
            status="aprovado" if aprovado else "recusado",
            valor_cobrado=payload.valor_total,
            forma_pagamento=payload.forma_pagamento,
            motivo_recusa=motivo,
            criado_em=agora_utc(),
        )
        db.add(pagamento)
        db.commit()

        if aprovado:
            env = publicar_pagamento_aprovado(
                envelope.correlation_id,
                {
                    "pedido_id": payload.pedido_id,
                    "transacao_id": transacao_id,
                    "valor_cobrado": float(payload.valor_total),
                    "forma_pagamento": payload.forma_pagamento,
                    "aprovado_em": _iso_agora(),
                },
            )
            registrar_evento(
                db, env.evento_id, "pagamento.aprovado", envelope.correlation_id, "publicado"
            )
        else:
            env = publicar_pagamento_recusado(
                envelope.correlation_id,
                {
                    "pedido_id": payload.pedido_id,
                    "transacao_id": transacao_id,
                    "motivo_recusa": motivo,
                    "recusado_em": _iso_agora(),
                },
            )
            registrar_evento(
                db, env.evento_id, "pagamento.recusado", envelope.correlation_id, "publicado"
            )

        marcar_evento_processado(db, envelope.evento_id)
        db.commit()

    except ValidationError as erro:
        logger.error("[pagamento] Payload inválido descartado: %s", erro)
        registrar_evento(
            db,
            envelope.evento_id,
            envelope.evento_tipo,
            envelope.correlation_id,
            "descartado",
            valido=False,
        )
        marcar_evento_processado(db, envelope.evento_id)
        db.commit()
    except Exception as erro:
        logger.error("[pagamento] Erro ao processar evento: %s", erro)
        db.rollback()
    finally:
        db.close()


def iniciar_consumer() -> None:
    init_db()
    while True:
        conexao = None
        try:
            conexao = conectar()
            canal = conexao.channel()
            declarar_exchanges(canal)
            canal.queue_declare(queue=FILA, durable=True)
            canal.queue_bind(
                queue=FILA,
                exchange=EXCHANGE_PEDIDO,
                routing_key="pedido.criado",
            )
            canal.basic_qos(prefetch_count=1)

            def _on_message(ch, method, _props, body):
                try:
                    evento = json.loads(body)
                    processar_evento(evento)
                except json.JSONDecodeError as erro:
                    logger.error("[pagamento] JSON inválido: %s", erro)
                except Exception as erro:
                    logger.error("[pagamento] Erro no callback: %s", erro)
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            canal.basic_consume(queue=FILA, on_message_callback=_on_message)
            logger.info("[pagamento] Aguardando pedido.criado na fila %s", FILA)
            canal.start_consuming()
        except Exception as erro:
            logger.error("[pagamento] Consumer desconectado: %s. Reconectando...", erro)
            time.sleep(5)
        finally:
            if conexao and conexao.is_open:
                conexao.close()
