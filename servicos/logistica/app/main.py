import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="ShopFlow - Logística", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "servico": "logistica"}


@app.get("/")
def root():
    return {
        "servico": "logistica",
        "porta": int(os.getenv("LOGISTICA_PORT", "8003")),
        "docs": "/docs",
    }
