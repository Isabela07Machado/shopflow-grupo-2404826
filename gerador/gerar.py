#!/usr/bin/env python3
"""
Gerador de carga para o ShopFlow.

Uso:
    python gerador/gerar.py --total 20 --taxa 2
"""

import argparse
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import requests

FORMAS_PAGAMENTO = ["cartao_credito", "pix", "boleto"]
CIDADES = [
    ("01310-100", "Sao Paulo", "SP"),
    ("30130-010", "Belo Horizonte", "MG"),
    ("80010-000", "Curitiba", "PR"),
    ("90010-150", "Porto Alegre", "RS"),
]
API_URL = "http://localhost:8001/pedidos"


def gerar_pedido() -> dict:
    itens = []
    num_itens = random.randint(1, 3)
    for _ in range(num_itens):
        quantidade = random.randint(1, 5)
        preco = Decimal(str(random.uniform(20.0, 500.0))).quantize(Decimal("0.01"))
        itens.append(
            {
                "produto_id": str(uuid4()),
                "quantidade": quantidade,
                "preco_unitario": float(preco),
            }
        )

    cep, cidade, uf = random.choice(CIDADES)

    return {
        "cliente_id": str(uuid4()),
        "itens": itens,
        "forma_pagamento": random.choice(FORMAS_PAGAMENTO),
        "endereco_entrega": {
            "cep": cep,
            "cidade": cidade,
            "uf": uf,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerador de carga ShopFlow")
    parser.add_argument("--total", type=int, required=True, help="Número total de pedidos")
    parser.add_argument("--taxa", type=float, default=1.0, help="Pedidos por segundo")
    args = parser.parse_args()

    intervalo = 1.0 / args.taxa if args.taxa > 0 else 1.0
    criados = 0
    erros = 0

    print(
        f"[gerador] Iniciando — total={args.total} taxa={args.taxa}/s "
        f"({datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')})"
    )

    for i in range(args.total):
        pedido = gerar_pedido()
        try:
            resposta = requests.post(API_URL, json=pedido, timeout=30)
            resposta.raise_for_status()
            dados = resposta.json()
            criados += 1
            print(
                f"[gerador] pedido criado pedido_id={dados['pedido_id']} "
                f"correlation_id={dados['correlation_id']} "
                f"({i + 1}/{args.total})"
            )
        except requests.RequestException as erro:
            erros += 1
            print(f"[gerador] ERRO ao criar pedido {i + 1}: {erro}")

        if i < args.total - 1:
            time.sleep(intervalo)

    print(f"[gerador] Finalizado — criados={criados} erros={erros}")


if __name__ == "__main__":
    main()
