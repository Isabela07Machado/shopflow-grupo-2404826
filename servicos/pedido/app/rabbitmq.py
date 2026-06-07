import json
import logging
import os
import time
from typing import Callable

import pika
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BROKER_HOST = os.getenv("BROKER_HOST", "rabbitmq")
BROKER_PORT = int(os.getenv("BROKER_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")

EXCHANGES = [
    "pedido.eventos",
    "pagamento.eventos",
    "logistica.eventos",
    "antifraude.eventos",
    "catalogo.eventos",
]


def obter_parametros() -> pika.ConnectionParameters:
    credenciais = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    return pika.ConnectionParameters(
        host=BROKER_HOST,
        port=BROKER_PORT,
        credentials=credenciais,
        heartbeat=600,
        blocked_connection_timeout=300,
    )


def conectar(retries: int = 30, delay: int = 2) -> pika.BlockingConnection:
    for tentativa in range(1, retries + 1):
        try:
            conexao = pika.BlockingConnection(obter_parametros())
            logger.info("[pedido] Conectado ao RabbitMQ")
            return conexao
        except pika.exceptions.AMQPConnectionError as erro:
            logger.warning(
                "[pedido] Tentativa %s/%s de conexão falhou: %s",
                tentativa,
                retries,
                erro,
            )
            time.sleep(delay)
    raise RuntimeError("Não foi possível conectar ao RabbitMQ")


def declarar_exchanges(channel: pika.channel.Channel) -> None:
    for exchange in EXCHANGES:
        channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)


def publicar(exchange: str, routing_key: str, envelope: dict) -> None:
    conexao = conectar()
    try:
        canal = conexao.channel()
        declarar_exchanges(canal)
        canal.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(envelope),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )
        logger.info(
            "[pedido] %s publicado correlation_id=%s",
            routing_key,
            envelope.get("correlation_id"),
        )
    finally:
        conexao.close()


def configurar_fila(
    channel: pika.channel.Channel,
    fila: str,
    exchange: str,
    routing_keys: list[str],
) -> None:
    channel.queue_declare(queue=fila, durable=True)
    for chave in routing_keys:
        channel.queue_bind(queue=fila, exchange=exchange, routing_key=chave)


def consumir_filas(
    filas: list[str],
    callback: Callable[[dict], None],
) -> None:
    while True:
        conexao = None
        try:
            conexao = conectar()
            canal = conexao.channel()
            declarar_exchanges(canal)
            canal.basic_qos(prefetch_count=1)

            def _on_message(ch, method, _props, body):
                try:
                    evento = json.loads(body)
                    callback(evento)
                except json.JSONDecodeError as erro:
                    logger.error("[pedido] Evento inválido (JSON): %s", erro)
                except Exception as erro:
                    logger.error("[pedido] Erro ao processar evento: %s", erro)
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            for fila in filas:
                canal.basic_consume(queue=fila, on_message_callback=_on_message)

            logger.info("[pedido] Consumer aguardando eventos nas filas: %s", filas)
            canal.start_consuming()
        except Exception as erro:
            logger.error("[pedido] Consumer desconectado: %s. Reconectando...", erro)
            time.sleep(5)
        finally:
            if conexao and conexao.is_open:
                conexao.close()
