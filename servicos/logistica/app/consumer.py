"""
Consumer do serviço de Logística.
"""

import json
import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone

from database import (
    EntregaORM,
    agora_utc,
    evento_ja_processado,
    get_db,
    init_db,
    marcar_evento_processado,
    registrar_evento,
)
from models import EnvelopeEvento
from producer import publicar_pedido_despachado, publicar_pedido_entregue
from pydantic import ValidationError
from rabbitmq import conectar, declarar_exchanges
from schemas import PayloadPedidoConfirmado

logger = logging.getLogger(__name__)

FILA = "logistica.pedido.confirmado"
EXCHANGE_PEDIDO = "pedido.eventos"
_contador_rastreio = 0


def _iso_agora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _gerar_codigo_rastreio() -> str:
    global _contador_rastreio
    _contador_rastreio += 1
    return f"SF{_contador_rastreio:06d}BR"


def _agendar_entrega(
    correlation_id: str,
    pedido_id: str,
    codigo_rastreio: str,
    previsao_entrega: datetime,
) -> None:
    def _entregar():
        delay = random.randint(5, 15)
        time.sleep(delay)
        entregue_em = agora_utc()
        sla_cumprido = entregue_em <= previsao_entrega

        db = get_db()
        try:
            entrega = db.query(EntregaORM).filter(EntregaORM.pedido_id == pedido_id).first()
            if entrega:
                entrega.status = "entregue"
                entrega.entregue_em = entregue_em
                entrega.sla_cumprido = sla_cumprido
                db.commit()

            env = publicar_pedido_entregue(
                correlation_id,
                {
                    "pedido_id": pedido_id,
                    "codigo_rastreio": codigo_rastreio,
                    "entregue_em": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%S.000Z"
                    ),
                    "sla_cumprido": sla_cumprido,
                },
            )
            registrar_evento(
                db, env.evento_id, "pedido.entregue", correlation_id, "publicado"
            )
            db.commit()
        except Exception as erro:
            logger.error("[logistica] Erro ao publicar entrega: %s", erro)
            db.rollback()
        finally:
            db.close()

    thread = threading.Thread(target=_entregar, daemon=True)
    thread.start()


def processar_evento(evento_dict: dict) -> None:
    db = get_db()
    try:
        envelope = EnvelopeEvento.model_validate(evento_dict)
    except ValidationError as erro:
        logger.error("[logistica] Envelope inválido descartado: %s", erro)
        registrar_evento(db, None, "invalido", None, "consumido", valido=False)
        db.commit()
        return

    if envelope.evento_tipo != "pedido.confirmado":
        return

    if evento_ja_processado(db, envelope.evento_id):
        logger.info(
            "[logistica] Evento duplicado ignorado evento_id=%s",
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
        payload = PayloadPedidoConfirmado.model_validate(envelope.payload)
        codigo_rastreio = _gerar_codigo_rastreio()
        despachado_em = agora_utc()
        previsao_entrega = despachado_em + timedelta(days=3)

        entrega = EntregaORM(
            pedido_id=payload.pedido_id,
            correlation_id=envelope.correlation_id,
            codigo_rastreio=codigo_rastreio,
            transportadora="ShopFlow Logistica",
            status="despachado",
            previsao_entrega=previsao_entrega,
            despachado_em=despachado_em,
        )
        db.add(entrega)
        db.commit()

        env_despacho = publicar_pedido_despachado(
            envelope.correlation_id,
            {
                "pedido_id": payload.pedido_id,
                "codigo_rastreio": codigo_rastreio,
                "transportadora": "ShopFlow Logistica",
                "previsao_entrega": previsao_entrega.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "despachado_em": _iso_agora(),
            },
        )
        registrar_evento(
            db,
            env_despacho.evento_id,
            "pedido.despachado",
            envelope.correlation_id,
            "publicado",
        )
        marcar_evento_processado(db, envelope.evento_id)
        db.commit()

        _agendar_entrega(
            envelope.correlation_id,
            payload.pedido_id,
            codigo_rastreio,
            previsao_entrega,
        )

    except ValidationError as erro:
        logger.error("[logistica] Payload inválido descartado: %s", erro)
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
        logger.error("[logistica] Erro ao processar evento: %s", erro)
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
                routing_key="pedido.confirmado",
            )
            canal.basic_qos(prefetch_count=1)

            def _on_message(ch, method, _props, body):
                try:
                    evento = json.loads(body)
                    processar_evento(evento)
                except json.JSONDecodeError as erro:
                    logger.error("[logistica] JSON inválido: %s", erro)
                except Exception as erro:
                    logger.error("[logistica] Erro no callback: %s", erro)
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            canal.basic_consume(queue=FILA, on_message_callback=_on_message)
            logger.info("[logistica] Aguardando pedido.confirmado na fila %s", FILA)
            canal.start_consuming()
        except Exception as erro:
            logger.error("[logistica] Consumer desconectado: %s. Reconectando...", erro)
            time.sleep(5)
        finally:
            if conexao and conexao.is_open:
                conexao.close()
