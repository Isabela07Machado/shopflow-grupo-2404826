import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="ShopFlow - Pagamento", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "servico": "pagamento"}


@app.get("/")
def root():
    return {
        "servico": "pagamento",
        "porta": int(os.getenv("PAGAMENTO_PORT", "8002")),
        "docs": "/docs",
    }
