from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.services import svc_promocion

router = APIRouter()


@router.post("/promover")
def promover(
    entidad_id: str | None = None,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Promueve las solicitudes pendientes al nucleo bancario (bd_core_financiero)."""
    return svc_promocion.promover(db, entidad_id)


@router.get("/outbox")
def outbox(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Estado de la cola de sincronizacion al core."""
    rows = db.execute(
        text(
            """SELECT entidad, operacion, estado, core_ref, intentos, ultimo_error,
                      created_at, procesado_at
               FROM sync_outbox ORDER BY created_at DESC LIMIT 50"""
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/outbox/demo")
def outbox_demo(db: Session = Depends(get_db)):
    """Vista demo de la cola de sincronizacion sin token para la practica."""
    rows = db.execute(
        text(
            """SELECT entidad, entidad_id, operacion, estado, payload,
                      created_at, procesado_at
               FROM sync_outbox ORDER BY created_at DESC LIMIT 20"""
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@router.post("/reconciliar-solicitudes-clientes")
def reconciliar_solicitudes_clientes(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Reasigna solicitudes web pendientes al asesor demo 0001."""
    if asesor.get("perfil", "").lower() not in {"supervisor", "administrador"}:
        raise HTTPException(status_code=403, detail="Operacion solo para supervisores")

    destino = db.execute(
        text(
            """SELECT id, agencia_id FROM asesores
               WHERE codigo_empleado = '0001' AND activo = TRUE"""
        )
    ).mappings().first()
    if destino is None:
        raise HTTPException(status_code=404, detail="Asesor 0001 no encontrado")

    solicitudes = db.execute(
        text(
            """UPDATE solicitudes_credito
               SET asesor_id = :asesor, agencia_id = :agencia, updated_at = now()
               WHERE canal = 'cliente'
                 AND estado IN ('enviado', 'recibido_comite')
                 AND asesor_id <> :asesor
               RETURNING cliente_id"""
        ),
        {"asesor": destino["id"], "agencia": destino["agencia_id"]},
    ).all()
    clientes = [str(row[0]) for row in solicitudes]
    for cliente_id in clientes:
        db.execute(
            text(
                """UPDATE cartera_diaria
                   SET asesor_id = :asesor, agencia_id = :agencia
                   WHERE cliente_id = :cliente_id
                     AND fecha_asignacion = CURRENT_DATE"""
            ),
            {
                "asesor": destino["id"],
                "agencia": destino["agencia_id"],
                "cliente_id": cliente_id,
            },
        )
    db.commit()
    return {"status": "ok", "solicitudes_reasignadas": len(clientes)}
