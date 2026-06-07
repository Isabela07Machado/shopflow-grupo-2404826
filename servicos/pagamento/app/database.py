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
    create_engine,
    text,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "PAGAMENTO_DB_URL",
    "postgresql://postgres:postgres@pagamento-db:5432/pagamento",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PagamentoORM(Base):
    __tablename__ = "pagamentos"

    transacao_id = Column(String, primary_key=True)
    pedido_id = Column(String, nullable=False)
    correlation_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    valor_cobrado = Column(Numeric(10, 2))
    forma_pagamento = Column(String)
    motivo_recusa = Column(String)
    criado_em = Column(DateTime)


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
                CREATE TABLE IF NOT EXISTS pagamentos (
                    transacao_id TEXT PRIMARY KEY,
                    pedido_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    valor_cobrado NUMERIC(10,2),
                    forma_pagamento TEXT,
                    motivo_recusa TEXT,
                    criado_em TIMESTAMP
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
            servico="pagamento",
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
