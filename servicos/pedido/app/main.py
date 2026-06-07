import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="ShopFlow - Pedido", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "servico": "pedido"}


@app.get("/")
def root():
    return {
        "servico": "pedido",
        "porta": int(os.getenv("PEDIDO_PORT", "8001")),
        "docs": "/docs",
    }
