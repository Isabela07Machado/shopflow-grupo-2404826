from datetime import datetime, timedelta, timezone
from decimal import Decimal

from database import EventoORM, PedidoORM, agora_utc
from sqlalchemy import func, or_
from sqlalchemy.orm import Session


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _calcular_taxa(parte: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(parte / total * 100, 2)


def obter_metrics(db: Session) -> dict:
    total_criados = db.query(PedidoORM).count()

    total_cancelados = (
        db.query(PedidoORM).filter(PedidoORM.status == "cancelado").count()
    )

    total_confirmados = (
        db.query(PedidoORM)
        .filter(
            or_(
                PedidoORM.status.in_(["confirmado", "despachado", "entregue"]),
                PedidoORM.confirmado_em.isnot(None),
            )
        )
        .count()
    )

    total_despachados = (
        db.query(PedidoORM)
        .filter(
            or_(
                PedidoORM.despachado_em.isnot(None),
                PedidoORM.status.in_(["despachado", "entregue"]),
            )
        )
        .count()
    )

    total_entregues = (
        db.query(PedidoORM)
        .filter(
            or_(
                PedidoORM.entregue_em.isnot(None),
                PedidoORM.status == "entregue",
            )
        )
        .count()
    )

    bloqueios_fraude = (
        db.query(PedidoORM)
        .filter(PedidoORM.motivo_cancelamento == "fraude_detectada")
        .count()
    )

    gmv_result = (
        db.query(func.coalesce(func.sum(PedidoORM.valor_total), 0))
        .filter(
            or_(
                PedidoORM.status.in_(["confirmado", "despachado", "entregue"]),
                PedidoORM.confirmado_em.isnot(None),
            )
        )
        .scalar()
    )
    gmv = float(gmv_result or 0)

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
    taxa_erro_schema = _calcular_taxa(eventos_descartados, total_recebidos)

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

    pedidos = (
        db.query(PedidoORM)
        .order_by(PedidoORM.criado_em.desc())
        .limit(50)
        .all()
    )
    pedidos_recentes = [
        {
            "pedido_id": p.pedido_id,
            "correlation_id": p.correlation_id,
            "cliente_id": p.cliente_id,
            "status": p.status,
            "valor_total": float(p.valor_total or 0),
            "forma_pagamento": p.forma_pagamento,
            "pagamento_ok": p.pagamento_ok,
            "fraude_ok": p.fraude_ok,
            "criado_em": _iso(p.criado_em),
            "confirmado_em": _iso(p.confirmado_em),
            "cancelado_em": _iso(p.cancelado_em),
            "despachado_em": _iso(p.despachado_em),
            "entregue_em": _iso(p.entregue_em),
            "sla_cumprido": p.sla_cumprido,
        }
        for p in pedidos
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
    for _ in range(10):
        minuto = (agora - timedelta(minutes=9 - _)).replace(second=0, microsecond=0)
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

    pedidos_gmv = (
        db.query(PedidoORM)
        .filter(
            or_(
                PedidoORM.status.in_(["confirmado", "despachado", "entregue"]),
                PedidoORM.confirmado_em.isnot(None),
            )
        )
        .all()
    )
    gmv_por_hora_map: dict[str, Decimal] = {}
    for p in pedidos_gmv:
        ref = p.confirmado_em or p.criado_em
        if ref:
            hora = ref.replace(minute=0, second=0, microsecond=0)
            chave = hora.strftime("%Y-%m-%dT%H:%M:00.000Z")
            gmv_por_hora_map[chave] = gmv_por_hora_map.get(chave, Decimal("0")) + Decimal(
                str(p.valor_total or 0)
            )

    gmv_por_hora = [
        {"hora": k, "gmv": float(v)}
        for k, v in sorted(gmv_por_hora_map.items())
    ]

    return {
        "servico": "pedido",
        "status": "ok",
        "eventos_publicados": eventos_publicados,
        "eventos_descartados": eventos_descartados,
        "taxa_erro_schema": taxa_erro_schema,
        "total_criados": total_criados,
        "total_confirmados": total_confirmados,
        "total_cancelados": total_cancelados,
        "total_despachados": total_despachados,
        "total_entregues": total_entregues,
        "gmv": round(gmv, 2),
        "taxa_conversao": _calcular_taxa(total_confirmados, total_criados),
        "taxa_bloqueio_antifraude": _calcular_taxa(bloqueios_fraude, total_criados),
        "ultimos_eventos": ultimos_eventos,
        "pedidos_recentes": pedidos_recentes,
        "eventos_por_minuto": eventos_por_minuto,
        "gmv_por_hora": gmv_por_hora,
    }
