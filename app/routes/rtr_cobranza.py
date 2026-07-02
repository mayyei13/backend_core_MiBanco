from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.cfg_database import get_db
from app.core.cfg_auth import get_current_asesor
from app.schemas.sch_cobranza import MoraItemOut, AccionCobranzaIn
from app.repositories import rep_cobranza

router = APIRouter()


@router.get("/mora", response_model=list[MoraItemOut])
def listar_mora(
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Listado de mora diaria (M10 / HU-30)."""
    return rep_cobranza.listar_mora(db)


@router.get("/mora/demo", response_model=list[MoraItemOut])
def listar_mora_demo(db: Session = Depends(get_db)):
    """Listado demo de mora para el portal Core sin token."""
    base = rep_cobranza.listar_mora(db)[:3]
    demo = [
        {
            "cliente_nombre": "Nilda Meza Nahui",
            "documento": "40000199",
            "telefono": "900161389",
            "cod_cuenta_credito": "CRED-00199",
            "dias_mora": 91,
            "monto_vencido": 20273.00,
        },
        {
            "cliente_nombre": "Hugo Inga Beraun",
            "documento": "40000218",
            "telefono": "900242489",
            "cod_cuenta_credito": "CRED-00218",
            "dias_mora": 46,
            "monto_vencido": 31638.23,
        },
        {
            "cliente_nombre": "Rosa Huaman Torres",
            "documento": "40000341",
            "telefono": "900323589",
            "cod_cuenta_credito": "CRED-00341",
            "dias_mora": 18,
            "monto_vencido": 43003.27,
        },
    ]
    result = []
    for idx, item in enumerate(base):
        row = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        row.update(demo[idx])
        result.append(MoraItemOut(**row))
    return result


@router.post("/accion")
def registrar_accion(
    data: AccionCobranzaIn,
    db: Session = Depends(get_db),
    asesor: dict = Depends(get_current_asesor),
):
    """Registra una gestion de cobranza (M10 / HU-31)."""
    rep_cobranza.registrar_accion(db, asesor["asesor_id"], data.model_dump())
    return {"status": "ok"}


@router.post("/accion/demo")
def registrar_accion_demo(
    data: AccionCobranzaIn,
    db: Session = Depends(get_db),
):
    """Registra una gestion demo con el primer asesor activo."""
    asesor = rep_cobranza.primer_asesor_activo(db)
    rep_cobranza.registrar_accion(db, asesor, data.model_dump())
    return {"status": "ok", "asesor_id": asesor}
