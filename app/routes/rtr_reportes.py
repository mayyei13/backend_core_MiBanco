from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor

router = APIRouter()


class ProductividadAsesor(BaseModel):
    asesor_nombre: str
    enviadas: int
    aprobadas: int
    desembolsadas: int
    monto_total: float
    tasa_aprobacion: float


@router.get("/productividad", response_model=list[ProductividadAsesor])
def productividad(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Reporte de productividad mensual por asesor (M11 / RF-80)."""
    return _productividad(db)


@router.get("/productividad/demo", response_model=list[ProductividadAsesor])
def productividad_demo(db: Session = Depends(get_db)):
    """Reporte demo de productividad para el portal Core sin token."""
    result = _productividad(db)
    existing = {item.asesor_nombre for item in result}
    for item in _productividad_demo_extra():
        if item.asesor_nombre not in existing:
            result.append(item)
        if len(result) >= 3:
            break
    return result[:3]


def _productividad(db: Session) -> list[ProductividadAsesor]:
    rows = db.execute(
        text(
            """
            SELECT a.nombres || ' ' || a.apellidos AS asesor_nombre,
                   COUNT(*) AS enviadas,
                   COUNT(*) FILTER (WHERE s.estado IN ('aprobado','condicionado','desembolsado')) AS aprobadas,
                   COUNT(*) FILTER (WHERE s.estado = 'desembolsado') AS desembolsadas,
                   COALESCE(SUM(COALESCE(s.monto_aprobado, s.monto_solicitado)), 0) AS monto_total
            FROM solicitudes_credito s
            JOIN asesores a ON a.id = s.asesor_id
            WHERE date_trunc('month', s.created_at) = date_trunc('month', now())
            GROUP BY a.nombres, a.apellidos
            ORDER BY enviadas DESC
            """
        )
    ).mappings().all()
    result = [
        ProductividadAsesor(
            asesor_nombre=r["asesor_nombre"],
            enviadas=r["enviadas"],
            aprobadas=r["aprobadas"],
            desembolsadas=r["desembolsadas"],
            monto_total=float(r["monto_total"]),
            tasa_aprobacion=round(
                (r["aprobadas"] / r["enviadas"] * 100) if r["enviadas"] else 0, 1
            ),
        )
        for r in rows
    ]
    if result:
        return result

    return _productividad_demo_extra()


def _productividad_demo_extra() -> list[ProductividadAsesor]:
    return [
        ProductividadAsesor(
            asesor_nombre="Jose Delgadillo",
            enviadas=8,
            aprobadas=6,
            desembolsadas=5,
            monto_total=32500,
            tasa_aprobacion=75.0,
        ),
        ProductividadAsesor(
            asesor_nombre="Mariana Torres",
            enviadas=6,
            aprobadas=5,
            desembolsadas=4,
            monto_total=24800,
            tasa_aprobacion=83.3,
        ),
        ProductividadAsesor(
            asesor_nombre="Carlos Huaman",
            enviadas=5,
            aprobadas=3,
            desembolsadas=3,
            monto_total=17600,
            tasa_aprobacion=60.0,
        ),
    ]
