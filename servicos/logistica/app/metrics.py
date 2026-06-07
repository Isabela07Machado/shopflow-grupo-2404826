from datetime import timedelta

from database import EntregaORM, EventoORM, agora_utc
from sqlalchemy import or_
from sqlalchemy.orm import Session


def _iso(dt) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _calcular_taxa(parte: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(parte / total * 100, 2)


def obter_metrics(db: Session) -> dict:
    total_entregas = db.query(EntregaORM).count()
    total_despachados = (
        db.query(EntregaORM).filter(EntregaORM.despachado_em.isnot(None)).count()
    )
    total_entregues = (
        db.query(EntregaORM).filter(EntregaORM.entregue_em.isnot(None)).count()
    )
    entregues_no_prazo = (
        db.query(EntregaORM)
        .filter(
            EntregaORM.entregue_em.isnot(None),
            EntregaORM.sla_cumprido.is_(True),
        )
        .count()
    )

    eventos_publicados = (
        db.query(EventoORM).filter(EventoORM.direcao == "publicado").count()
    )
    eventos_descartados = (
        db.query(EventoORM)
        .filter(
            or_(
                EventoORM.direcao == "descartado",
                EventoORM.valido.is_(False),
            )
        )
        .count()
    )
    total_recebidos = (
        db.query(EventoORM)
        .filter(EventoORM.direcao.in_(["consumido", "descartado"]))
        .count()
    )

    ultimos = (
        db.query(EventoORM)
        .order_by(EventoORM.timestamp.desc())
        .limit(10)
        .all()
    )
    ultimos_eventos = [
        {
            "timestamp": _iso(e.timestamp),
            "evento_tipo": e.evento_tipo,
            "correlation_id": e.correlation_id,
            "servico": e.servico,
        }
        for e in ultimos
    ]

    agora = agora_utc()
    dez_min_atras = agora - timedelta(minutes=10)
    eventos_recentes = (
        db.query(EventoORM)
        .filter(EventoORM.timestamp >= dez_min_atras)
        .order_by(EventoORM.timestamp.asc())
        .all()
    )
    eventos_por_minuto_map: dict[str, int] = {}
    for i in range(10):
        minuto = (agora - timedelta(minutes=9 - i)).replace(second=0, microsecond=0)
        chave = minuto.strftime("%Y-%m-%dT%H:%M:00.000Z")
        eventos_por_minuto_map[chave] = 0

    for ev in eventos_recentes:
        if ev.timestamp:
            minuto = ev.timestamp.replace(second=0, microsecond=0)
            chave = minuto.strftime("%Y-%m-%dT%H:%M:00.000Z")
            if chave in eventos_por_minuto_map:
                eventos_por_minuto_map[chave] += 1

    eventos_por_minuto = [
        {"minuto": k, "quantidade": v}
        for k, v in sorted(eventos_por_minuto_map.items())
    ]

    return {
        "servico": "logistica",
        "status": "ok",
        "eventos_publicados": eventos_publicados,
        "eventos_descartados": eventos_descartados,
        "taxa_erro_schema": _calcular_taxa(eventos_descartados, total_recebidos),
        "total_entregas": total_entregas,
        "total_despachados": total_despachados,
        "total_entregues": total_entregues,
        "entregues_no_prazo_percentual": _calcular_taxa(
            entregues_no_prazo, total_entregues
        ),
        "ultimos_eventos": ultimos_eventos,
        "eventos_por_minuto": eventos_por_minuto,
    }
