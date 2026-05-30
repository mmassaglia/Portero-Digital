# Portero Digital — Complejo Los Gigantes

Sistema de portero digital con QR. Visitante escanea el QR → elige vivienda → llama o manda WhatsApp. Cada toque queda registrado en PostgreSQL.

---

## Estructura del proyecto

```
portero-digital/
├── backend/          ← FastAPI + Python
│   ├── main.py
│   ├── requirements.txt
│   ├── Procfile
│   └── railway.toml
└── frontend/         ← HTML estático servido con Nginx
    ├── index.html
    ├── nginx.conf
    ├── Dockerfile
    └── railway.toml
```

---

## Deploy en Railway

### 1. Crear el proyecto

1. Entrá a [railway.app](https://railway.app) → **New Project**
2. Elegí **Empty Project**

### 2. Agregar PostgreSQL

En el proyecto → **+ New** → **Database** → **PostgreSQL**  
Railway crea la base y genera `DATABASE_URL` automáticamente.

### 3. Deploy del Backend

1. **+ New** → **GitHub Repo** → seleccioná el repo, carpeta `backend/`
2. En **Variables** del servicio agregá:
   ```
   DATABASE_URL  → (referenciar la variable del add-on Postgres)
   ```
   Railway permite usar `${{Postgres.DATABASE_URL}}` como referencia.
3. El servicio arranca con `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Anotá la URL pública del backend (ej: `https://portero-backend.up.railway.app`)

### 4. Deploy del Frontend

1. **+ New** → **GitHub Repo** → seleccioná el repo, carpeta `frontend/`
2. En **Variables** del servicio agregá:
   ```
   BACKEND_URL  → https://portero-backend.up.railway.app
   ```
   > **Importante**: editá `index.html` y reemplazá la línea:
   > ```js
   > const BACKEND_URL = window.BACKEND_URL || 'http://localhost:8000';
   > ```
   > por:
   > ```js
   > const BACKEND_URL = 'https://TU-BACKEND.up.railway.app';
   > ```
   > O mejor aún, usá un script de build que inyecte la variable.

3. La URL pública del frontend es la que va en el QR.

---

## Cargar los números de las viviendas

Una vez desplegado, usá la API para actualizar cada vivienda:

```bash
curl -X PUT https://TU-BACKEND.up.railway.app/viviendas/1 \
  -H "Content-Type: application/json" \
  -d '{"telefono": "+5493512345678", "whatsapp": "5493512345678"}'
```

Repetí para viviendas 2, 3 y 4 cambiando el ID y el número.

> El `telefono` lleva `+` para el link `tel:`.  
> El `whatsapp` va sin `+` para el link `wa.me/`.

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/viviendas` | Lista viviendas activas |
| PUT | `/viviendas/{id}` | Actualiza nombre/teléfono/whatsapp |
| POST | `/visitas` | Registra un toque (llamada o WA) |
| GET | `/visitas` | Historial de visitas (últimas 50) |
| GET | `/visitas/stats` | Totales: llamadas, WA, últimas 24h |

Documentación interactiva automática: `https://TU-BACKEND.up.railway.app/docs`

---

## Generar el QR

Con la URL del frontend lista, generá el QR en [qr-code-generator.com](https://www.qr-code-generator.com) o en Python:

```bash
pip install qrcode[pil]
python -c "import qrcode; qrcode.make('https://TU-FRONTEND.up.railway.app').save('portero_qr.png')"
```

Imprimí el QR en A4 o cartón y colocalo en la entrada del complejo.
