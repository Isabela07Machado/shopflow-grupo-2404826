"""
Esqueleto do produtor de eventos do serviço de Logística.

No Módulo 3 este módulo publicará eventos como pedido.despachado
e pedido.entregue na exchange logistica.eventos.
"""

import os

import pika
from dotenv import load_dotenv

from models import EnvelopeEvento

load_dotenv()

EXCHANGE_LOGISTICA = "logistica.eventos"


def obter_parametros_conexao() -> pika.ConnectionParameters:
    """Retorna parâmetros de conexão com o broker RabbitMQ."""
    credenciais = pika.PlainCredentials(
        os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
        os.getenv("RABBITMQ_DEFAULT_PASS", "guest"),
    )
    return pika.ConnectionParameters(
        host=os.getenv("BROKER_HOST", "rabbitmq"),
        port=int(os.getenv("BROKER_PORT", "5672")),
        credentials=credenciais,
    )


def declarar_exchange(channel: pika.channel.Channel) -> None:
    """Declara a exchange de eventos do serviço de logística."""
    channel.exchange_declare(
        exchange=EXCHANGE_LOGISTICA,
        exchange_type="topic",
        durable=True,
    )


def publicar_evento(
    channel: pika.channel.Channel,
    routing_key: str,
    envelope: EnvelopeEvento,
) -> None:
    """Publica um evento no formato de envelope padrão."""
    channel.basic_publish(
        exchange=EXCHANGE_LOGISTICA,
        routing_key=routing_key,
        body=envelope.model_dump_json(),
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
        ),
    )


def criar_canal() -> tuple[pika.BlockingConnection, pika.channel.Channel]:
    """Abre conexão e canal com o RabbitMQ, declarando a exchange."""
    conexao = pika.BlockingConnection(obter_parametros_conexao())
    canal = conexao.channel()
    declarar_exchange(canal)
    return conexao, canal
