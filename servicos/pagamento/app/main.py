import logging
import os
import threading

from consumer import iniciar_consumer
from database import get_db, init_db
from dotenv import load_dotenv
from fastapi import FastAPI
from metrics import obter_metrics

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ShopFlow - Pagamento", version="2.0.0")


@app.on_event("startup")
def startup():
    init_db()
    thread = threading.Thread(target=iniciar_consumer, daemon=True)
    thread.start()
    logger.info("[pagamento] Serviço iniciado — consumer em thread separada")


@app.get("/health")
def health():
    return {"status": "ok", "servico": "pagamento"}


@app.get("/metrics")
def metrics():
    db = get_db()
    try:
        return obter_metrics(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "servico": "pagamento",
        "porta": int(os.getenv("PAGAMENTO_PORT", "8002")),
        "docs": "/docs",
    }
