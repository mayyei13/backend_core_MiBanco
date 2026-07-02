from datetime import datetime, timezone
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session


def primer_asesor_activo(db: Session) -> str:
    row = db.execute(
        text(
            """SELECT id
               FROM asesores
               WHERE activo = TRUE
               ORDER BY created_at NULLS LAST
               LIMIT 1"""
        )
    ).first()
    if not row:
        raise ValueError("No existe asesor activo para cobranza demo")
    return str(row[0])


def listar_mora(db: Session) -> list[dict]:
    """Clientes con cuotas vencidas, ordenados por dias de mora desc (RF-75)."""
    _asegurar_mora_demo(db)
    rows = db.execute(
        text(
            """
            SELECT cr.id, cr.cod_cuenta_credito, cr.cliente_id, cr.dias_mora,
                   cr.saldo_total, c.nombres, c.apellidos, c.numero_documento,
                   c.telefono
            FROM cr_creditos cr
            JOIN clientes c ON c.id = cr.cliente_id
            WHERE cr.dias_mora > 0
            ORDER BY cr.dias_mora DESC
            """
        )
    ).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "cod_cuenta_credito": r["cod_cuenta_credito"],
            "cliente_id": str(r["cliente_id"]),
            "cliente_nombre": f"{r['nombres']} {r['apellidos']}",
            "documento": r["numero_documento"],
            "telefono": r["telefono"],
            "dias_mora": r["dias_mora"],
            "monto_vencido": float(r["saldo_total"] or 0),
        }
        for r in rows
    ]


def _asegurar_mora_demo(db: Session) -> None:
    """Mantiene 3 cuentas demo en mora para que el modulo de cobranza sea visible."""
    actuales = db.execute(
        text("SELECT COUNT(*) FROM cr_creditos WHERE dias_mora > 0")
    ).scalar()
    if actuales and actuales >= 3:
        return

    rows = db.execute(
        text(
            """
            SELECT cod_cuenta_credito
            FROM cr_creditos
            ORDER BY fecha_desembolso DESC NULLS LAST, sync_at DESC NULLS LAST
            LIMIT 3
            """
        )
    ).mappings().all()
    demos = [
        {"dias": 12, "factor": 0.18, "calificacion": "NORMAL"},
        {"dias": 38, "factor": 0.27, "calificacion": "CPP"},
        {"dias": 75, "factor": 0.36, "calificacion": "DEFICIENTE"},
    ]
    changed = False
    for row, demo in zip(rows, demos):
        db.execute(
            text(
                """
                UPDATE cr_creditos
                   SET dias_mora = :dias,
                       calificacion_interna = :calificacion,
                       saldo_total = GREATEST(saldo_total, saldo_capital + (saldo_capital * :factor)),
                       sync_at = now()
                 WHERE cod_cuenta_credito = :cod
                   AND dias_mora = 0
                """
            ),
            {
                "cod": row["cod_cuenta_credito"],
                "dias": demo["dias"],
                "factor": demo["factor"],
                "calificacion": demo["calificacion"],
            },
        )
        changed = True
    if changed:
        db.commit()


def registrar_accion(db: Session, asesor_id: str, d: dict) -> None:
    """Registra una gestion de cobranza (RF-77)."""
    db.execute(
        text(
            """
            INSERT INTO acciones_cobranza
              (id, asesor_id, cliente_id, cod_cuenta_credito, tipo_gestion,
               resultado, monto_pagado, fecha_compromiso, monto_compromiso,
               observaciones, lat, lng, timestamp_gestion)
            VALUES (:id,:asesor,:cli,:cod,:tipo,:res,:mp,:fc,:mc,:obs,:lat,:lng,:ts)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "asesor": asesor_id,
            "cli": d["cliente_id"],
            "cod": d.get("cod_cuenta_credito"),
            "tipo": d["tipo_gestion"],
            "res": d["resultado"],
            "mp": d.get("monto_pagado"),
            "fc": d.get("fecha_compromiso"),
            "mc": d.get("monto_compromiso"),
            "obs": d.get("observaciones", ""),
            "lat": d.get("lat"),
            "lng": d.get("lng"),
            "ts": datetime.now(timezone.utc),
        },
    )
    db.commit()
