-- Esquema minimo del puente bd_core_mobile -> bd_core_financiero.
-- El servicio FastAPI ejecuta las mismas sentencias de forma idempotente.

CREATE TABLE IF NOT EXISTS dcliente (
    pkcliente BIGSERIAL PRIMARY KEY,
    codcliente VARCHAR(12) UNIQUE NOT NULL,
    nomcliente VARCHAR(100) NOT NULL,
    pkclasepersona INTEGER,
    codclasepersona VARCHAR(10),
    desclasepersona VARCHAR(100),
    fechaingresocaja DATE,
    pktipodocumentoidentidad INTEGER,
    codtipodocumentoidentidad VARCHAR(10),
    destipodocumentoidentidad VARCHAR(100),
    numerodocumentoidentidad VARCHAR(20) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS dsolicitud (
    pksolicitud BIGSERIAL PRIMARY KEY,
    codsolicitud VARCHAR(20) UNIQUE NOT NULL,
    pkcliente BIGINT NOT NULL REFERENCES dcliente(pkcliente),
    pksolicitudestado INTEGER NOT NULL,
    pkmoneda INTEGER NOT NULL,
    pkproducto INTEGER NOT NULL,
    montosolicitudcredito NUMERIC(14, 2) NOT NULL,
    nrocuotasolicitud INTEGER NOT NULL,
    plazosolicitudcredito INTEGER NOT NULL,
    fechasolicitudcredito DATE NOT NULL,
    pkagencia INTEGER,
    pkasesor INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
