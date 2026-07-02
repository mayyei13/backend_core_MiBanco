import json
import uuid
from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.data.casos_credito import casos_completos
from app.core.cfg_security import hash_password


def listar() -> list[dict]:
    return casos_completos()


def resumen() -> dict:
    casos = casos_completos()
    return {
        "marca": "MiBanco",
        "core": "FastAPI 8003",
        "bd_mobile": "bd_core_mobile",
        "bd_financiero": "bd_core_financiero",
        "total_casos": len(casos),
        "desembolsados": sum(1 for c in casos if c["decision_comite"] == "aprobado"),
        "condicionados": sum(1 for c in casos if c["decision_comite"] == "condicionado"),
        "rechazados": sum(1 for c in casos if c["decision_comite"] == "rechazado"),
        "monto_solicitado": sum(c["monto_solicitado"] for c in casos),
        "monto_aprobado": sum(c["monto_aprobado"] for c in casos),
    }


def sembrar(db: Session) -> dict:
    asesor = db.execute(
        text(
            """SELECT id, agencia_id
               FROM asesores
               WHERE activo = TRUE
               ORDER BY created_at NULLS LAST
               LIMIT 1"""
        )
    ).mappings().first()
    if asesor is None:
        return {"ok": False, "mensaje": "No existe asesor activo", "creados": 0}

    creados = 0
    omitidos = 0
    for caso in casos_completos():
        exists = db.execute(
            text("SELECT id FROM solicitudes_credito WHERE numero_expediente = :exp"),
            {"exp": caso["numero_expediente"]},
        ).first()
        if exists:
            omitidos += 1
            continue

        cliente_id = _upsert_cliente(db, caso)
        solicitud_id = str(uuid.uuid4())
        estado = caso["estado_final"]
        motivo_rechazo = None
        condicion = None
        if caso["decision_comite"] == "condicionado":
            condicion = "Aprobado con monto reducido segun evaluacion del comite."
        if caso["decision_comite"] == "rechazado":
            motivo_rechazo = _motivo_rechazo(caso)

        db.execute(
            text(
                """INSERT INTO solicitudes_credito
                     (id, numero_expediente, asesor_id, cliente_id, agencia_id,
                      canal, tipo_negocio, nombre_negocio, ingresos_estimados,
                      gastos_mensuales, monto_solicitado, plazo_meses, moneda,
                      tipo_cuota, garantia, destino_credito, cuota_estimada,
                      tea_referencial, estado, monto_aprobado, motivo_rechazo,
                      condicion_adicional, firma_cliente_base64, lat_captura,
                      lng_captura, pendiente_sync)
                   VALUES
                     (:id,:exp,:asesor,:cli,:ag,'cliente',:tn,:nn,:ing,
                      :gastos,:monto,:plazo,'PEN','mensual',:gar,:dest,:cuota,
                      :tea,:estado,:aprobado,:motivo,:condicion,:firma,:lat,
                      :lng,TRUE)"""
            ),
            {
                "id": solicitud_id,
                "exp": caso["numero_expediente"],
                "asesor": asesor["id"],
                "cli": cliente_id,
                "ag": asesor["agencia_id"],
                "tn": caso["tipo_negocio"],
                "nn": caso["nombre_negocio"],
                "ing": caso["ingresos_estimados"],
                "gastos": caso["gastos_mensuales"],
                "monto": caso["monto_solicitado"],
                "plazo": caso["plazo_meses"],
                "gar": caso["garantia"],
                "dest": caso["destino_credito"],
                "cuota": caso["cuota_final"] or caso["cuota_estimada"],
                "tea": caso["tea_referencial"],
                "estado": estado,
                "aprobado": caso["monto_aprobado"] or None,
                "motivo": motivo_rechazo,
                "condicion": condicion,
                "firma": f"firma_demo_caso_{caso['caso']:02d}",
                "lat": caso["lat"],
                "lng": caso["lng"],
            },
        )
        db.execute(
            text(
                """INSERT INTO cartera_diaria
                     (id, asesor_id, cliente_id, agencia_id, fecha_asignacion,
                      tipo_gestion, prioridad, score_prioridad, monto_credito,
                      estado_visita, resultado_visita, observacion_visita,
                      lat_visita, lng_visita)
                   VALUES
                     (:id,:asesor,:cli,:ag,:fecha,'NUEVA_SOLICITUD',:prioridad,
                      :score,:monto,'visitado','visitado',:obs,:lat,:lng)"""
            ),
            {
                "id": str(uuid.uuid4()),
                "asesor": asesor["id"],
                "cli": cliente_id,
                "ag": asesor["agencia_id"],
                "fecha": date.today(),
                "prioridad": caso["prioridad"],
                "score": _score_prioridad(caso),
                "monto": caso["monto_solicitado"],
                "obs": f"Caso {caso['caso']} evaluado en campo.",
                "lat": caso["lat"],
                "lng": caso["lng"],
            },
        )
        db.execute(
            text(
                """INSERT INTO consultas_buro
                     (id, asesor_id, cliente_id, solicitud_id, dni_consultado,
                      calificacion_sbs, entidades_con_deuda, deuda_total_pen,
                      mayor_deuda, dias_mayor_mora, en_lista_negra,
                      motivo_bloqueo, resultado_json, firma_consentimiento_base64)
                   VALUES
                     (:id,:asesor,:cli,:sol,:dni,:sbs,:ent,:deuda,:mayor,:mora,
                      :lista,:motivo,CAST(:json AS jsonb),:firma)"""
            ),
            {
                "id": str(uuid.uuid4()),
                "asesor": asesor["id"],
                "cli": cliente_id,
                "sol": solicitud_id,
                "dni": caso["numero_documento"],
                "sbs": caso["calificacion_sbs"],
                "ent": caso["entidades_con_deuda"],
                "deuda": caso["deuda_total_pen"],
                "mayor": caso["mayor_deuda"],
                "mora": caso["dias_mayor_mora"],
                "lista": caso["en_lista_negra"],
                "motivo": _motivo_rechazo(caso) if caso["en_lista_negra"] else None,
                "json": json.dumps(caso),
                "firma": f"consentimiento_caso_{caso['caso']:02d}",
            },
        )
        db.execute(
            text(
                """INSERT INTO sync_outbox (id, entidad, entidad_id, operacion, payload, estado)
                   VALUES (:id, 'solicitudes_credito', :eid, 'create',
                           CAST(:payload AS jsonb), 'pendiente')"""
            ),
            {
                "id": str(uuid.uuid4()),
                "eid": solicitud_id,
                "payload": json.dumps({
                    "numero_expediente": caso["numero_expediente"],
                    "numero_documento": caso["numero_documento"],
                    "monto_aprobado": caso["monto_aprobado"],
                    "estado": estado,
                }),
            },
        )
        creados += 1

    db.commit()
    return {"ok": True, "creados": creados, "omitidos": omitidos, **resumen()}


def _upsert_cliente(db: Session, caso: dict) -> str:
    row = db.execute(
        text("SELECT id FROM clientes WHERE numero_documento = :doc"),
        {"doc": caso["numero_documento"]},
    ).first()
    if row:
        cliente_id = str(row[0])
        db.execute(
            text(
                """UPDATE clientes
                   SET telefono=:tel, tipo_negocio=:tn, nombre_negocio=:nn,
                       antiguedad_negocio_meses=:ant, ingresos_estimados=:ing,
                       lat=:lat, lng=:lng, calificacion_sbs=:sbs,
                       updated_at=now()
                   WHERE id=:id"""
            ),
            {
                "id": cliente_id,
                "tel": caso["telefono"],
                "tn": caso["tipo_negocio"],
                "nn": caso["nombre_negocio"],
                "ant": caso["antiguedad_negocio_meses"],
                "ing": caso["ingresos_estimados"],
                "lat": caso["lat"],
                "lng": caso["lng"],
                "sbs": caso["calificacion_sbs"],
            },
        )
        _asegurar_usuario_cliente(db, cliente_id, caso["numero_documento"])
        return cliente_id

    cliente_id = str(uuid.uuid4())
    db.execute(
        text(
            """INSERT INTO clientes
                 (id, numero_documento, nombres, apellidos, telefono, direccion,
                  tipo_negocio, nombre_negocio, antiguedad_negocio_meses,
                  ingresos_estimados, lat, lng, calificacion_sbs, es_prospecto)
               VALUES
                 (:id,:doc,:nom,:ape,:tel,:dir,:tn,:nn,:ant,:ing,:lat,:lng,:sbs,TRUE)"""
        ),
        {
            "id": cliente_id,
            "doc": caso["numero_documento"],
            "nom": caso["nombres"],
            "ape": caso["apellidos"],
            "tel": caso["telefono"],
            "dir": caso["distrito"],
            "tn": caso["tipo_negocio"],
            "nn": caso["nombre_negocio"],
            "ant": caso["antiguedad_negocio_meses"],
            "ing": caso["ingresos_estimados"],
            "lat": caso["lat"],
            "lng": caso["lng"],
            "sbs": caso["calificacion_sbs"],
        },
    )
    _asegurar_usuario_cliente(db, cliente_id, caso["numero_documento"])
    return cliente_id


def asegurar_usuarios_clientes(db: Session) -> dict:
    creados = 0
    existentes = 0
    for caso in casos_completos():
        cliente_id = _upsert_cliente(db, caso)
        row = db.execute(
            text("SELECT id FROM usuarios_cliente WHERE username = :dni"),
            {"dni": caso["numero_documento"]},
        ).first()
        if row:
            existentes += 1
        else:
            _asegurar_usuario_cliente(db, cliente_id, caso["numero_documento"])
            creados += 1
    db.commit()
    return {"ok": True, "creados": creados, "existentes": existentes, "clave": "12345"}


def _asegurar_usuario_cliente(db: Session, cliente_id: str, dni: str) -> None:
    db.execute(
        text(
            """INSERT INTO usuarios_cliente (id, cliente_id, username, password_hash, activo)
               VALUES (:id, :cliente_id, :username, :password_hash, TRUE)
               ON CONFLICT (username) DO UPDATE SET
                 cliente_id = EXCLUDED.cliente_id,
                 password_hash = EXCLUDED.password_hash,
                 activo = TRUE,
                 bloqueado = FALSE,
                 intentos_fallidos = 0"""
        ),
        {
            "id": str(uuid.uuid4()),
            "cliente_id": cliente_id,
            "username": dni,
            "password_hash": hash_password("12345"),
        },
    )


def _score_prioridad(caso: dict) -> int:
    if caso["prioridad"] == "alta" or caso["monto_solicitado"] >= 10000:
        return 90
    if caso["prioridad"] == "media" or caso["monto_solicitado"] >= 3000:
        return 65
    return 40


def _motivo_rechazo(caso: dict) -> str:
    if caso["en_lista_negra"]:
        return "Registrado en lista de inhabilitados del sistema financiero."
    if caso["pre_evaluacion"] != "APTO":
        return "Capacidad de pago insuficiente para el monto solicitado."
    return "Calificacion SBS con mora vigente no procede para otorgamiento."
