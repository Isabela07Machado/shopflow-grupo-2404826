import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "PEDIDO_DB_URL",
    "postgresql://postgres:postgres@pedido-db:5432/pedido",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PedidoORM(Base):
    __tablename__ = "pedidos"

    pedido_id = Column(String, primary_key=True)
    correlation_id = Column(String, nullable=False)
    cliente_id = Column(String)
    status = Column(String, nullable=False)
    pagamento_ok = Column(Boolean)
    fraude_ok = Column(Boolean)
    valor_total = Column(Numeric(10, 2))
    forma_pagamento = Column(String)
    itens_json = Column(Text)
    endereco_json = Column(Text)
    criado_em = Column(DateTime)
    confirmado_em = Column(DateTime)
    cancelado_em = Column(DateTime)
    motivo_cancelamento = Column(String)
    despachado_em = Column(DateTime)
    entregue_em = Column(DateTime)
    sla_cumprido = Column(Boolean)


class EventoProcessadoORM(Base):
    __tablename__ = "eventos_processados"

    evento_id = Column(String, primary_key=True)
    processado_em = Column(DateTime, nullable=False)


class EventoORM(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evento_id = Column(String)
    evento_tipo = Column(String, nullable=False)
    correlation_id = Column(String)
    servico = Column(String, nullable=False)
    direcao = Column(String, nullable=False)
    valido = Column(Boolean, default=True)
    timestamp = Column(DateTime)


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pedidos (
                    pedido_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL,
                    cliente_id TEXT,
                    status TEXT NOT NULL,
                    pagamento_ok BOOLEAN,
                    fraude_ok BOOLEAN,
                    valor_total NUMERIC(10,2),
                    forma_pagamento TEXT,
                    itens_json TEXT,
                    endereco_json TEXT,
                    criado_em TIMESTAMP,
                    confirmado_em TIMESTAMP,
                    cancelado_em TIMESTAMP,
                    motivo_cancelamento TEXT,
                    despachado_em TIMESTAMP,
                    entregue_em TIMESTAMP,
                    sla_cumprido BOOLEAN
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS eventos_processados (
                    evento_id TEXT PRIMARY KEY,
                    processado_em TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS eventos (
                    id SERIAL PRIMARY KEY,
                    evento_id TEXT,
                    evento_tipo TEXT NOT NULL,
                    correlation_id TEXT,
                    servico TEXT NOT NULL,
                    direcao TEXT NOT NULL,
                    valido BOOLEAN DEFAULT TRUE,
                    timestamp TIMESTAMP
                )
                """
            )
        )


def get_db() -> Session:
    return SessionLocal()


def agora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def registrar_evento(
    db: Session,
    evento_id: str | None,
    evento_tipo: str,
    correlation_id: str | None,
    direcao: str,
    valido: bool = True,
) -> None:
    db.add(
        EventoORM(
            evento_id=evento_id,
            evento_tipo=evento_tipo,
            correlation_id=correlation_id,
            servico="pedido",
            direcao=direcao,
            valido=valido,
            timestamp=agora_utc(),
        )
    )


def evento_ja_processado(db: Session, evento_id: str) -> bool:
    return (
        db.query(EventoProcessadoORM)
        .filter(EventoProcessadoORM.evento_id == evento_id)
        .first()
        is not None
    )


def marcar_evento_processado(db: Session, evento_id: str) -> None:
    db.add(
        EventoProcessadoORM(
            evento_id=evento_id,
            processado_em=agora_utc(),
        )
    )
