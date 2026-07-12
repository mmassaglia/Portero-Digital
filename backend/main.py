from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional
import os
import secrets
import psycopg2
import psycopg2.extras

app = FastAPI(title="Portero Digital - Los Gigantes")

# Force deploy

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "portero2024")

security = HTTPBasic()


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    ok_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS viviendas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            telefono VARCHAR(30),
            whatsapp VARCHAR(30),
            activa BOOLEAN DEFAULT FALSE
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS visitas (
            id SERIAL PRIMARY KEY,
            vivienda_id INTEGER REFERENCES viviendas(id),
            canal VARCHAR(20) NOT NULL,
            timestamp TIMESTAMPTZ DEFAULT NOW(),
            ip VARCHAR(50)
        );
    """)
    # Insertar viviendas 1-24 si no existen
    for i in range(1, 25):
        cur.execute("""
            INSERT INTO viviendas (nombre, activa)
            SELECT %s, FALSE
            WHERE NOT EXISTS (SELECT 1 FROM viviendas WHERE nombre = %s)
        """, (f"Vivienda {i}", f"Vivienda {i}"))
    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ---------- Schemas ----------

class VisitaIn(BaseModel):
    vivienda_id: int
    canal: str
    ip: Optional[str] = None


class ViviendaUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    whatsapp: Optional[str] = None
    activa: Optional[bool] = None


# ---------- Endpoints públicos ----------

@app.get("/")
def root():
    return {"status": "ok", "proyecto": "Portero Digital - Los Gigantes"}


@app.get("/viviendas")
def listar_viviendas():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM viviendas WHERE activa = TRUE ORDER BY CAST(regexp_replace(nombre, '[^0-9]', '', 'g') AS INTEGER)")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.post("/visitas")
def registrar_visita(visita: VisitaIn):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM viviendas WHERE id = %s AND activa = TRUE", (visita.vivienda_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Vivienda no encontrada")
    cur.execute(
        "INSERT INTO visitas (vivienda_id, canal, ip) VALUES (%s, %s, %s) RETURNING *",
        (visita.vivienda_id, visita.canal, visita.ip)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return row


# ---------- Endpoints admin (requieren autenticación) ----------

@app.get("/admin/viviendas")
def admin_listar_todas(_=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM viviendas ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.put("/admin/viviendas/{vivienda_id}")
def admin_actualizar(vivienda_id: int, data: ViviendaUpdate, _=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    campos = {k: v for k, v in data.dict().items() if v is not None}
    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    set_clause = ", ".join([f"{k} = %s" for k in campos])
    values = list(campos.values()) + [vivienda_id]
    cur.execute(f"UPDATE viviendas SET {set_clause} WHERE id = %s RETURNING *", values)
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Vivienda no encontrada")
    return row


@app.get("/admin/visitas")
def admin_visitas(limit: int = 100, _=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.id, viv.nombre AS vivienda, v.canal, v.timestamp
        FROM visitas v
        JOIN viviendas viv ON viv.id = v.vivienda_id
        ORDER BY v.timestamp DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.get("/admin/stats")
def admin_stats(_=Depends(require_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE canal = 'llamada') AS llamadas,
            COUNT(*) FILTER (WHERE canal = 'whatsapp') AS whatsapps,
            COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '24 hours') AS ultimas_24h,
            COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '7 days') AS ultima_semana
        FROM visitas
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row
