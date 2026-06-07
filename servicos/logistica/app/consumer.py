"""
Esqueleto do consumidor de eventos do serviço de Logística.

No Módulo 3 este módulo escutará eventos como pagamento.aprovado
para iniciar o despacho do pedido.
"""

import json
import os
from typing import Callable

import pika
from dotenv import load_dotenv

load_dotenv()

EXCHANGE_PAGAMENTO = "pagamento.eventos"


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


def declarar_fila(
    channel: pika.channel.Channel,
    nome_fila: str,
    exchange: str,
    routing_keys: list[str],
) -> None:
    """Declara fila e faz bind com a exchange informada."""
    channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
    channel.queue_declare(queue=nome_fila, durable=True)
    for chave in routing_keys:
        channel.queue_bind(queue=nome_fila, exchange=exchange, routing_key=chave)


def processar_mensagem_generica(
    callback: Callable[[dict], None],
    channel: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    _properties: pika.BasicProperties,
    body: bytes,
) -> None:
    """Deserializa o envelope e delega o processamento ao callback informado."""
    try:
        evento = json.loads(body)
        callback(evento)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def iniciar_consumo(
    nome_fila: str,
    exchange: str,
    routing_keys: list[str],
    callback: Callable[[dict], None],
) -> None:
    """Inicia loop de consumo de eventos (uso previsto no Módulo 3)."""
    conexao = pika.BlockingConnection(obter_parametros_conexao())
    canal = conexao.channel()
    declarar_fila(canal, nome_fila, exchange, routing_keys)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(
        queue=nome_fila,
        on_message_callback=lambda ch, method, props, body: processar_mensagem_generica(
            callback, ch, method, props, body
        ),
    )
    canal.start_consuming()
