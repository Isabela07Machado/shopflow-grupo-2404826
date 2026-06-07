import json
import logging
import os
import time

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
            logger.info("[pagamento] Conectado ao RabbitMQ")
            return conexao
        except pika.exceptions.AMQPConnectionError as erro:
            logger.warning(
                "[pagamento] Tentativa %s/%s de conexão falhou: %s",
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
            "[pagamento] %s publicado correlation_id=%s",
            routing_key,
            envelope.get("correlation_id"),
        )
    finally:
        conexao.close()
