from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os
import psycopg2
import psycopg2.extras

app = FastAPI(title="Portero Digital - Los Gigantes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS viviendas (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            telefono VARCHAR(30),
            whatsapp VARCHAR(30),
            activa BOOLEAN DEFAULT TRUE
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
    cur.execute("""
        INSERT INTO viviendas (nombre, telefono, whatsapp, activa)
        SELECT nombre, telefono, whatsapp, activa FROM (VALUES
            ('Vivienda 1', '', '', TRUE),
            ('Vivienda 2', '', '', TRUE),
            ('Vivienda 3', '', '', TRUE),
            ('Vivienda 4', '', '', TRUE)
        ) AS v(nombre, telefono, whatsapp, activa)
        WHERE NOT EXISTS (SELECT 1 FROM viviendas LIMIT 1);
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ---------- Schemas ----------

class VisitaIn(BaseModel):
    vivienda_id: int
    canal: str  # "llamada" | "whatsapp"
    ip: Optional[str] = None


class ViviendaUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    whatsapp: Optional[str] = None
    activa: Optional[bool] = None


# ---------- Endpoints ----------

@app.get("/")
def root():
    return {"status": "ok", "proyecto": "Portero Digital - Los Gigantes"}


@app.get("/viviendas")
def listar_viviendas():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM viviendas WHERE activa = TRUE ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.put("/viviendas/{vivienda_id}")
def actualizar_vivienda(vivienda_id: int, data: ViviendaUpdate):
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


@app.get("/visitas")
def listar_visitas(limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.id, viv.nombre AS vivienda, v.canal, v.timestamp, v.ip
        FROM visitas v
        JOIN viviendas viv ON viv.id = v.vivienda_id
        ORDER BY v.timestamp DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.get("/visitas/stats")
def stats_visitas():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE canal = 'llamada') AS llamadas,
            COUNT(*) FILTER (WHERE canal = 'whatsapp') AS whatsapps,
            COUNT(*) FILTER (WHERE timestamp > NOW() - INTERVAL '24 hours') AS ultimas_24h
        FROM visitas
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row
