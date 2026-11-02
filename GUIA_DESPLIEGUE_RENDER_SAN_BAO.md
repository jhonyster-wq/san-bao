# Guía de Despliegue Gratuito en Render.com — Sistema Integral San Bao

> [!IMPORTANT]
> **Repositorio ya configurado para Render.com en 1 clic:**
> He dejado configurados en la raíz del proyecto los archivos que **Render** detecta automáticamente:
> 1. **[`render.yaml`](file:///Users/jsc/Documents/SanBao/render.yaml):** Blueprint oficial de Render para crear el servicio gratuito con Python `3.11.9`, comando de inicio y variables de entorno (manteniendo activo el **Ingreso de Desarrollo en el Login**).
> 2. **[`requirements.txt`](file:///Users/jsc/Documents/SanBao/requirements.txt):** En la raíz del proyecto para que Render instale todas las dependencias automáticamente.
> 3. **[`.gitignore`](file:///Users/jsc/Documents/SanBao/.gitignore):** Actualizado para que Git **SÍ suba** el frontend compilado ([`frontend/dist/index.html`](file:///Users/jsc/Documents/SanBao/frontend/dist/index.html)) y la base de datos pre-poblada ([`sanbao_dev.db`](file:///Users/jsc/Documents/SanBao/sanbao_dev.db)).
> 4. **[`backend/app/core/database.py`](file:///Users/jsc/Documents/SanBao/backend/app/core/database.py):** Configurado para funcionar de inmediato con la base de datos incluida (`sanbao_dev.db`) o con **Render PostgreSQL Free** (convirtiendo automáticamente `postgres://` a `postgresql+psycopg2://`).

---

## Paso 1: Subir el Proyecto a tu GitHub (Desde tu Terminal)

Render se conecta directamente a un repositorio de **GitHub** (puede ser privado o público). Ejecuta estos comandos en la carpeta `/Users/jsc/Documents/SanBao`:

```bash
cd /Users/jsc/Documents/SanBao
git init
git add .
git commit -m "Despliegue Sistema Integral San Bao en Render (Frontend + Backend + BD + Login Dev)"
git branch -M main
# Reemplaza la URL por la de un repositorio nuevo (vacío) creado en tu cuenta de GitHub:
git remote add origin https://github.com/TU_USUARIO/san-bao.git
git push -u origin main
```

---

## Paso 2: Crear el Servicio Gratuito en Render.com

Tienes **dos formas** de crearlo en https://dashboard.render.com:

### Forma A — Automática en 1 Clic (Blueprint `render.yaml`)
1. En el panel de **Render**, haz clic en **New +** → **Blueprint**.
2. Conecta tu repositorio `san-bao` de GitHub.
3. Render leerá automáticamente el archivo [`render.yaml`](file:///Users/jsc/Documents/SanBao/render.yaml) y creará el servicio web gratuito listo para usar.

### Forma B — Manual desde "New Web Service"
1. En el panel de **Render**, haz clic en **New +** → **Web Service** y selecciona tu repositorio `san-bao`.
2. Completa los campos exactamente así:
   - **Language / Runtime:** `Python 3`
   - **Region:** `Oregon (US West)` o `Ohio (US East)`
   - **Branch:** `main`
   - **Root Directory:** *(déjalo vacío)*
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** **`Free` ($0 / month)**
3. En **Environment Variables** (opcional, recomendable para fijar versión de Python), agrega:
   - `PYTHON_VERSION` = `3.11.9`
   - `ENABLE_DEV_LOGIN` = `True`
4. Haz clic en **Deploy Web Service**.

---

## Paso 3: Base de Datos en Render (2 Modalidades Disponibles)

### Modalidad 1: Inmediata con la Base de Datos Incluida (`sanbao_dev.db`) — *Sin configurar nada extra*
- Al desplegar el Web Service, el sistema utiliza automáticamente [`sanbao_dev.db`](file:///Users/jsc/Documents/SanBao/sanbao_dev.db) y ejecuta [`init_db.py`](file:///Users/jsc/Documents/SanBao/backend/app/core/init_db.py), dejando cargados todos los alumnos, programas, docentes, tutores, citas clínicas, cierres de turno, sobrecupos y solicitudes de pago.

### Modalidad 2 (Opcional): Conectar PostgreSQL Gratuito de Render
Si deseas además una base de datos **PostgreSQL 16** dedicada en Render:
1. En Render haz clic en **New +** → **Postgres** → elige el plan **Free** y créala.
2. Copia la **Internal Database URL** que te entrega Render (empieza con `postgres://...` o `postgresql://...`).
3. En tu Web Service de Render → **Environment**, agrega la variable:
   - **Key:** `DATABASE_URL`
   - **Value:** *(pega la Internal Database URL de Render)*
4. Al reiniciar, el backend creará automáticamente los **10 esquemas relacionales (3NF/BCNF)**, las **78 tablas** y poblará todos los datos iniciales de prueba.

---

## URLs Listas para Trabajar con tu Cliente en Render

Una vez que Render termine el despliegue (aprox. 2 minutos), te dará una URL gratuita tipo `https://sistema-integral-san-bao.onrender.com`:

- **Login con Ingreso Rápido de Desarrollo (11 Perfiles + Demos en el Combobox):**
  `https://sistema-integral-san-bao.onrender.com/app`
- **Selector de Demos Independientes para Cliente:**
  `https://sistema-integral-san-bao.onrender.com/demo`
- **Demo 1 — Solo Academia & Matrículas:**
  `https://sistema-integral-san-bao.onrender.com/demo-academia`
- **Demo 2 — Solo Clínica & Agenda de Boxes:**
  `https://sistema-integral-san-bao.onrender.com/demo-clinica`
