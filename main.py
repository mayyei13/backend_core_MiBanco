from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.cfg_config import settings
from app.routes import (
    rtr_auth, rtr_cartera, rtr_ficha, rtr_cobranza, rtr_preeval, rtr_buro,
    rtr_solicitudes, rtr_reportes, rtr_alertas, rtr_campanas, rtr_sync,
    rtr_cliente, rtr_casos,
)

APP_VERSION = "1.0.4"

app = FastAPI(
    title="Core Mobile - MiBanco",
    description="Capa operacional MiBanco para canales moviles: fuerza de ventas en campo "
                "y app de clientes. Alimenta al core bd_core_financiero.",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rtr_auth.router,    prefix="/auth",     tags=["Auth"])
app.include_router(rtr_cartera.router, prefix="/cartera",  tags=["Cartera"])
app.include_router(rtr_ficha.router,   prefix="/clientes", tags=["Ficha"])
app.include_router(rtr_cobranza.router, prefix="/cobranza", tags=["Cobranza"])
app.include_router(rtr_preeval.router, prefix="/pre-evaluar", tags=["PreEvaluacion"])
app.include_router(rtr_buro.router,    prefix="/buro",      tags=["Buro"])
app.include_router(rtr_solicitudes.router, prefix="/solicitudes", tags=["Solicitudes"])
app.include_router(rtr_reportes.router, prefix="/reportes", tags=["Reportes"])
app.include_router(rtr_alertas.router, prefix="/alertas", tags=["Alertas"])
app.include_router(rtr_campanas.router, prefix="/campanas", tags=["Campanas"])
app.include_router(rtr_sync.router, prefix="/sync", tags=["Sync (Puente al Core)"])
app.include_router(rtr_casos.router, prefix="/casos", tags=["Casos PDF"])

# App de clientes (appbanco / Flutter clientes) — login DNI + productos
app.include_router(rtr_cliente.router, prefix="/cliente", tags=["Cliente (App)"])

@app.get("/")
def root():
    return {"sistema": "Core Mobile MiBanco", "version": APP_VERSION, "status": "ok"}


@app.get("/health", tags=["Health"])
def health():
    """Endpoint liviano para health checks del proveedor cloud."""
    return {
        "status": "ok",
        "service": "mibanco-core-mobile",
        "version": APP_VERSION,
    }
