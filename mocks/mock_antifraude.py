"""
Mock do serviço de Antifraude.

Consome pedido.criado e publica pedido.aprovado_fraude (~90%)
ou pedido.bloqueado_fraude (~10%).
"""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

import pika
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mock-antifraude] %(message)s",
)
logger = logging.getLogger(__name__)

BROKER_HOST = os.getenv("BROKER_HOST", "rabbitmq")
BROKER_PORT = int(os.getenv("BROKER_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
_taxa_env = float(os.getenv("TAXA_ANTIFRAUDE", "0.9"))
# Valor 1 no .env significa mock ativo; taxa padrão de aprovação é 90%
TAXA_APROVACAO = 0.9 if _taxa_env >= 1 else _taxa_env

EXCHANGE_PEDIDO = "pedido.eventos"
EXCHANGE_ANTIFRAUDE = "antifraude.eventos"
FILA_ENTRADA = "mock.antifraude.pedido.criado"
ROUTING_KEY_ENTRADA = "pedido.criado"

EXCHANGES = [
    "pedido.eventos",
    "pagamento.eventos",
    "logistica.eventos",
    "antifraude.eventos",
    "catalogo.eventos",
]


def criar_envelope(evento_tipo: str, correlation_id: str, payload: dict | None = None) -> dict:
    """Monta o envelope padrão de eventos do ShopFlow."""
    return {
        "evento_id": str(uuid4()),
        "evento_tipo": evento_tipo,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "correlation_id": correlation_id,
        "versao_schema": "1.0",
        "payload": payload or {},
    }


def conectar_rabbitmq(retries: int = 30, delay: int = 2) -> pika.BlockingConnection:
    """Conecta ao RabbitMQ com retentativas para aguardar o broker subir."""
    credenciais = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parametros = pika.ConnectionParameters(
        host=BROKER_HOST,
        port=BROKER_PORT,
        credentials=credenciais,
        heartbeat=600,
        blocked_connection_timeout=300,
    )

    for tentativa in range(1, retries + 1):
        try:
            conexao = pika.BlockingConnection(parametros)
            logger.info("Conectado ao RabbitMQ em %s:%s", BROKER_HOST, BROKER_PORT)
            return conexao
        except pika.exceptions.AMQPConnectionError as erro:
            logger.warning(
                "Tentativa %s/%s de conexão falhou: %s",
                tentativa,
                retries,
                erro,
            )
            time.sleep(delay)

    raise RuntimeError("Não foi possível conectar ao RabbitMQ após várias tentativas.")


def declarar_exchanges(channel: pika.channel.Channel) -> None:
    """Declara todas as exchanges topic do projeto."""
    for exchange in EXCHANGES:
        channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
        logger.info("Exchange declarada: %s", exchange)


def configurar_consumo(channel: pika.channel.Channel) -> None:
    """Configura fila e bind para consumir pedido.criado."""
    channel.queue_declare(queue=FILA_ENTRADA, durable=True)
    channel.queue_bind(
        queue=FILA_ENTRADA,
        exchange=EXCHANGE_PEDIDO,
        routing_key=ROUTING_KEY_ENTRADA,
    )
    channel.basic_qos(prefetch_count=1)


def processar_mensagem(
    channel: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    _properties: pika.BasicProperties,
    body: bytes,
) -> None:
    """Processa pedido.criado e publica resultado da análise antifraude."""
    try:
        evento = json.loads(body)
        correlation_id = evento.get("correlation_id", str(uuid4()))
        payload_entrada = evento.get("payload", {})

        aprovado = random.random() < TAXA_APROVACAO
        evento_tipo = "pedido.aprovado_fraude" if aprovado else "pedido.bloqueado_fraude"

        resposta = criar_envelope(
            evento_tipo=evento_tipo,
            correlation_id=correlation_id,
            payload={
                "pedido_id": payload_entrada.get("pedido_id", correlation_id),
                "resultado": "aprovado" if aprovado else "bloqueado",
                "origem": "mock-antifraude",
            },
        )

        channel.basic_publish(
            exchange=EXCHANGE_ANTIFRAUDE,
            routing_key=evento_tipo,
            body=json.dumps(resposta),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
        )

        logger.info(
            "Publicado evento: %s | correlation_id=%s | payload=%s",
            evento_tipo,
            correlation_id,
            resposta["payload"],
        )
    except Exception as erro:
        logger.error("Erro ao processar mensagem: %s", erro)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    """Ponto de entrada do mock de antifraude."""
    conexao = conectar_rabbitmq()
    canal = conexao.channel()
    declarar_exchanges(canal)
    configurar_consumo(canal)

    canal.basic_consume(
        queue=FILA_ENTRADA,
        on_message_callback=processar_mensagem,
    )

    logger.info("Aguardando eventos '%s' na fila %s...", ROUTING_KEY_ENTRADA, FILA_ENTRADA)
    canal.start_consuming()


if __name__ == "__main__":
    main()
