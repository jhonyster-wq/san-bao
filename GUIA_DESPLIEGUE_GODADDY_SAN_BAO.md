# Guía de Despliegue en GoDaddy — Sistema Integral San Bao (Frontend + Backend + BD + Login Desarrollo)

> [!IMPORTANT]
> **Paquete Todo-en-Uno Listo para Subir a GoDaddy:**
> Se ha generado en la raíz de tu proyecto el archivo comprimido **[`sanbao_godaddy_deploy.zip`](file:///Users/jsc/Documents/SanBao/sanbao_godaddy_deploy.zip)** que incluye:
> 1. **Frontend Completo** ([`frontend/dist/index.html`](file:///Users/jsc/Documents/SanBao/frontend/dist/index.html) + logos oficiales + **Ingreso de Desarrollo activo en el Login** con los 11 perfiles y los 2 Demos de Academia y Clínica).
> 2. **Backend FastAPI Completo** (`backend/app/...`) con adaptador nativo [`passenger_wsgi.py`](file:///Users/jsc/Documents/SanBao/passenger_wsgi.py) para **GoDaddy cPanel** y soporte Uvicorn/Docker para **GoDaddy VPS**.
> 3. **Base de Datos Pre-poblada Lista para Usar:**
>    - [`sanbao_dev.db`](file:///Users/jsc/Documents/SanBao/sanbao_dev.db) (Base de datos SQLite embebida con las 78 tablas, mallas, alumnos, docentes, tutores, citas, cierres de turno, sobrecupos y solicitudes de pago ya cargadas).
>    - [`database_dump_sanbao.sql`](file:///Users/jsc/Documents/SanBao/database_dump_sanbao.sql) (Respaldo SQL completo por si deseas importarlo en MySQL / phpMyAdmin o PostgreSQL en GoDaddy).

---

## 1. Ingreso de Desarrollo Mantenido en el Login

En la pantalla principal de inicio de sesión (`/` o `/app`), se mantiene **100% habilitado** el bloque **"🛠️ Acceso Rápido Desarrollo (Perfiles y Portales)"**:

- **Credenciales pre-cargadas:** `admin@sanbao.cl` / Contraseña: `SanBao#2026`
- **Combobox de Selección en 1 Clic (`#sso-dev-profile-combobox`):**
  - **Portal Administrativo & Holding:** Superadmin ERP (`admin@sanbao.cl`), Finanzas & SII (`finanzas@sanbao.cl`).
  - **Portales Usuarios Finales:** Alumno (`19.876.543-0`), Docente (`14.112.233-K`), Tutor Clínico (`tutor.clinico@sanbao.cl`), Paciente (`17.123.456-5`).
  - **Portal Académico & Secretaría:** Secretaría (`secretaria.sede@sanbao.cl`), Dirección Académica (`direccion.academica@sanbao.cl`), Gestión Académica (`coordinacion@sanbao.cl`).
  - **Portal Clínico MTC:** Dirección Clínica (`direccion.clinica@sanbao.cl`), Recepción Médica (`recepcion@sanbao.cl`).
  - **Demos Cliente Independientes (incluidos también en el combobox del Login):**
    - `🎓 Demo Cliente Independiente 1: Academia & Matrículas (/demo-academia)`
    - `🩺 Demo Cliente Independiente 2: Clínica & Boxes (/demo-clinica)`
    - `⚡ Desbloquear todos los menús y portales (Modo Desarrollo)`

---

## 2. Opción A: Subir a GoDaddy Web Hosting con cPanel (Hosting Compartido / Deluxe / Ultimate)

Si tu cuenta de GoDaddy tiene **cPanel** (el panel clásico con *Administrador de Archivos* y *Setup Python App*):

### Paso 1: Subir y descomprimir `sanbao_godaddy_deploy.zip`
1. Ingresa a tu cuenta de **GoDaddy** → **Mis Productos** → **Web Hosting** → **Administrar** → **cPanel Admin**.
2. Abre **Administrador de archivos (File Manager)**.
3. En la carpeta raíz de tu usuario (`/home/tu_usuario/`), crea una carpeta llamada **`sanbao`** (por ejemplo: `/home/tu_usuario/sanbao`).
4. Entra a `/home/tu_usuario/sanbao`, haz clic en **Cargar (Upload)** y sube el archivo **[`sanbao_godaddy_deploy.zip`](file:///Users/jsc/Documents/SanBao/sanbao_godaddy_deploy.zip)**.
5. Haz clic derecho sobre `sanbao_godaddy_deploy.zip` → **Extract (Extraer)** dentro de `/home/tu_usuario/sanbao`.

### Paso 2: Configurar la Aplicación Python en cPanel ("Setup Python App")
1. Vuelve al menú principal de **cPanel** y en la sección **Software** abre **Setup Python App** (*Configurar Aplicación Python*).
2. Haz clic en **Create Application** (*Crear Aplicación*) y completa:
   - **Python version:** `3.10`, `3.11` o `3.12` (la más reciente disponible).
   - **Application root:** `sanbao`
   - **Application URL:** Elige tu dominio principal (ej. `tudominio.cl`) o un subdominio/ruta (ej. `sanbao.tudominio.cl`).
   - **Application startup file:** `passenger_wsgi.py`
   - **Application Entry point:** `application`
3. Haz clic en **Create** (arriba a la derecha).

### Paso 3: Instalar dependencias en 1 clic desde cPanel
1. En la misma pantalla de **Setup Python App**, baja hasta la sección **Configuration files**.
2. Escribe `requirements_godaddy.txt` y haz clic en **Add**.
3. Presiona el botón **Run Pip Install**.
4. Haz clic en **Restart** (Reiniciar aplicación).

> [!TIP]
> **¡Listo!** Al abrir tu dominio en el navegador, el sistema cargará automáticamente la base de datos [`sanbao_dev.db`](file:///Users/jsc/Documents/SanBao/sanbao_dev.db) incluida en el paquete (sin que tengas que configurar nada más) y mostrará el **Login con el Ingreso de Desarrollo** activo para trabajar con el cliente.

### (Opcional) Si deseas conectar MySQL de GoDaddy cPanel en vez de SQLite
Si más adelante prefieres usar **MySQL** de cPanel en lugar del archivo `sanbao_dev.db`:
1. En cPanel → **MySQL Database Wizard**, crea una base de datos (ej. `usuario_sanbao`) y un usuario con todos los privilegios.
2. En **Setup Python App** → **Environment variables**, agrega la variable:
   - **Name:** `DATABASE_URL`
   - **Value:** `mysql+pymysql://usuario_db:tu_password@localhost:3306/usuario_sanbao`
3. Al reiniciar la app Python, el backend creará y poblará automáticamente todas las tablas y datos de prueba en MySQL.

---

## 3. Opción B: Subir a GoDaddy VPS Linux (con acceso SSH / Docker)

Si tu plan de GoDaddy es un **Servidor Virtual Privado (VPS Linux)**:

1. Sube el archivo [`sanbao_godaddy_deploy.zip`](file:///Users/jsc/Documents/SanBao/sanbao_godaddy_deploy.zip) por SCP/SFTP a `/opt/sanbao`:
   ```bash
   scp sanbao_godaddy_deploy.zip root@IP_DE_TU_GODADDY:/opt/
   ```
2. Conéctate por SSH a tu servidor GoDaddy y descomprime:
   ```bash
   ssh root@IP_DE_TU_GODADDY
   mkdir -p /opt/sanbao && mv /opt/sanbao_godaddy_deploy.zip /opt/sanbao/
   cd /opt/sanbao && unzip -o sanbao_godaddy_deploy.zip
   ```
3. Levanta todo el entorno (Frontend + Backend + Base de Datos) con el script incluido:
   - **Con Docker Compose (PostgreSQL 16 + Backend + Frontend):**
     ```bash
     docker compose up -d --build
     ```
   - **O directamente con Python + SQLite (`sanbao_dev.db`):**
     ```bash
     python3 -m venv .venv
     ./.venv/bin/pip install -r requirements_godaddy.txt
     ./.venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
     ```

---

## 4. Rutas Disponibles Una Vez Arriba en GoDaddy

| Ruta en tu Dominio GoDaddy | Descripción |
| :--- | :--- |
| `https://tu-dominio.cl/` o `/app` | **Sistema Integral Completo + Pantalla de Login con Ingreso Rápido de Desarrollo** |
| `https://tu-dominio.cl/demo` | **Hub Selector de Demos para Cliente** (Tarjetas separadas Academia vs Clínica) |
| `https://tu-dominio.cl/demo-academia` | **Demo 1: Academia & Control Curricular** (8 pasos guiados + Panel 7 Matrículas) |
| `https://tu-dominio.cl/demo-clinica` | **Demo 2: Clínica & Dirección MTC** (8 pasos guiados + Agenda Hoy + Cierres Turno) |
| `https://tu-dominio.cl/docs` | **Documentación Interactiva OpenAPI / Swagger del Backend** |
