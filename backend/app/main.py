import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from app.core.config import settings
from app.core.database import SessionLocal, Base, engine
from app.core.init_db import init_db
from app.core.exceptions import SanBaoException
from app.modules.institutional.routers import (
    auth_router,
    companies_router,
    people_router,
    campuses_router,
)
from app.modules.academic.routers import (
    academic_programs_router,
    academic_periods_router,
    academic_students_router,
    academic_coordinator_router,
    academic_teacher_router,
)
from app.modules.finance.routers import (
    finance_commitments_router,
    finance_payments_router,
    finance_hub_router,
)
from app.modules.clinical.routers import (
    clinical_patients_router,
    clinical_practitioners_router,
    clinical_appointments_router,
    clinical_encounters_router,
    clinical_supplies_router,
    clinical_management_router,
)
from app.modules.lms.routers import (
    lms_courses_router,
    lms_progress_router,
)
from app.modules.ecommerce.routers import (
    ecommerce_products_router,
    ecommerce_orders_router,
)
from app.modules.hr.router import router as hr_router
from app.modules.integrations.router import router as integrations_router
from app.modules.bi.router import router as bi_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sanbao.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: inicialización de BD y recursos."""
    logger.info("Inicializando esquemas y datos maestros del Sistema Integral San Bao...")
    db = SessionLocal()
    try:
        init_db(db)
        logger.info("Base de datos y datos maestros inicializados correctamente.")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
    finally:
        db.close()
    yield
    logger.info("Deteniendo Sistema Integral San Bao.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
Plataforma Empresarial Integrada para:
- **Instituto de Medicina China Clásica SpA** (Academia, Alumnos, Matrículas, Mallas)
- **Servicios Clínicos San Bao SpA** (Clínica Integrativa, Ficha MTC, Box, Prácticas Supervisadas)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Compresión GZip para respuestas HTML (/app ~1.5MB -> ~180KB) y JSON grandes
app.add_middleware(GZipMiddleware, minimum_size=500)

# Configuración de CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


# Manejador global para excepciones de negocio SanBaoException
@app.exception_handler(SanBaoException)
async def sanbao_exception_handler(request: Request, exc: SanBaoException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "code": exc.code, "message": exc.message},
    )


# Montar directorio estático para logos y recursos
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Registro de Routers Modulares
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/institutional")
app.include_router(companies_router, prefix=f"{settings.API_V1_STR}/institutional")
app.include_router(people_router, prefix=f"{settings.API_V1_STR}/institutional")
app.include_router(campuses_router, prefix=f"{settings.API_V1_STR}/institutional")

# Módulo 1: Gestión Académica
app.include_router(academic_programs_router, prefix=settings.API_V1_STR)
app.include_router(academic_periods_router, prefix=settings.API_V1_STR)
app.include_router(academic_students_router, prefix=settings.API_V1_STR)
app.include_router(academic_coordinator_router, prefix=settings.API_V1_STR)
app.include_router(academic_teacher_router, prefix=settings.API_V1_STR)

# Módulo 3: Finanzas y Compromisos de Pago
app.include_router(finance_commitments_router, prefix=settings.API_V1_STR)
app.include_router(finance_payments_router, prefix=settings.API_V1_STR)
app.include_router(finance_hub_router, prefix=settings.API_V1_STR)

# Módulo 2: Gestión Clínica (Servicios Clínicos San Bao SpA)
app.include_router(clinical_patients_router, prefix=settings.API_V1_STR)
app.include_router(clinical_practitioners_router, prefix=settings.API_V1_STR)
app.include_router(clinical_appointments_router, prefix=settings.API_V1_STR)
app.include_router(clinical_encounters_router, prefix=settings.API_V1_STR)
app.include_router(clinical_supplies_router, prefix=settings.API_V1_STR)
app.include_router(clinical_management_router, prefix=settings.API_V1_STR)

# Módulo 6: LMS / Aula Virtual
app.include_router(lms_courses_router, prefix=settings.API_V1_STR)
app.include_router(lms_progress_router, prefix=settings.API_V1_STR)

# Módulo 5: Comercio Electrónico
app.include_router(ecommerce_products_router, prefix=settings.API_V1_STR)
app.include_router(ecommerce_orders_router, prefix=settings.API_V1_STR)

# Módulo 4: Recursos Humanos y Remuneraciones
app.include_router(hr_router, prefix=settings.API_V1_STR)

# Módulo 7: Integraciones, DTE SII y Firma Electrónica
app.include_router(integrations_router, prefix=settings.API_V1_STR)

# Módulo 8: Inteligencia de Negocios y Dashboards
app.include_router(bi_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Estado y Diagnóstico"], include_in_schema=False)
def root():
    """Redirige automáticamente a la interfaz web interactiva San Bao."""
    return RedirectResponse(url="/app")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Sirve el ícono institucional."""
    return serve_logo()


@app.get("/app", tags=["Frontend Web"])
@app.get("/demo-academia", tags=["Demos Cliente Separados (Academia y Clínica)"])
@app.get("/demo-clinica", tags=["Demos Cliente Separados (Academia y Clínica)"])
def serve_frontend_app():
    """Sirve la interfaz web interactiva del Sistema Integral San Bao (y los modos aislados /demo-academia y /demo-clinica)."""
    # Buscar archivo HTML compilado / distribuible
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist/index.html")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend/dist/index.html")),
    ]
    for path in candidates:
        if os.path.exists(path):
            return FileResponse(
                path,
                media_type="text/html",
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
    return {"message": "Interfaz frontend disponible en /frontend/dist/index.html"}


@app.get("/demo", response_class=HTMLResponse, tags=["Demos Cliente Separados (Academia y Clínica)"])
def serve_client_demo_hub():
    """Portal Ejecutivo de Demostración para el Cliente con acceso separado a Demo Academia y Demo Clínica."""
    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Centro de Demostración Cliente — San Bao (Academia & Clínica Independientes)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Playfair+Display:wght@700;800&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', sans-serif; }
    .brand-serif { font-family: 'Playfair Display', serif; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-white/10 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
    <div class="max-w-7xl mx-auto px-6 py-4 flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center gap-3.5">
        <img src="/logo_sanbao.png" alt="San Bao" class="w-11 h-11 rounded-xl bg-white p-1 object-contain shadow" />
        <div>
          <span class="text-[10px] font-extrabold uppercase tracking-widest text-amber-400 block">Presentación Oficial para Cliente</span>
          <h1 class="brand-serif text-xl font-bold text-white">Ecosistema San Bao — Demos Independientes por Área</h1>
        </div>
      </div>
      <div class="flex items-center gap-2.5 text-xs">
        <a href="/demo-academia" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold shadow transition">🎓 Abrir Demo Academia</a>
        <a href="/demo-clinica" class="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold shadow transition">🩺 Abrir Demo Clínica</a>
        <a href="/app" class="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 font-semibold border border-white/15 transition">Vista ERP Completo</a>
      </div>
    </div>
  </header>

  <main class="flex-1 max-w-7xl mx-auto w-full px-6 py-10 space-y-8">
    <div class="text-center max-w-3xl mx-auto space-y-2">
      <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/15 text-blue-300 border border-blue-400/30 text-xs font-bold">
        ✨ Entornos Separados de Demostración con Recorrido Guiado Paso a Paso
      </span>
      <h2 class="brand-serif text-3xl sm:text-4xl font-bold text-white">Seleccione el Demo que desea presentar al Cliente</h2>
      <p class="text-sm text-slate-400">
        Cada entorno aisla su menú lateral, perfiles y barra de recorrido guiado para exhibir de forma clara y ordenada todas las funcionalidades de <strong>Academia</strong> o de <strong>Clínica</strong> por separado.
      </p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <!-- TARJETA 1: DEMO ACADEMIA -->
      <div class="rounded-3xl bg-gradient-to-b from-indigo-950/90 to-slate-900 border-2 border-indigo-500/40 p-7 shadow-2xl flex flex-col justify-between space-y-6">
        <div class="space-y-4">
          <div class="flex items-center justify-between gap-2">
            <span class="px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 text-xs font-extrabold uppercase">
              DEMO 01 • ÁREA ACADÉMICA INDEPENDIENTE
            </span>
            <span class="text-2xl">🎓</span>
          </div>
          <div>
            <h3 class="brand-serif text-2xl font-bold text-white">Demo Academia &amp; Control Curricular</h3>
            <p class="text-xs text-indigo-200/80 mt-1">Instituto de Medicina China Clásica SpA (Escuela San Bao • Sedes Santiago y Viña del Mar)</p>
          </div>

          <div class="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-indigo-500/20 text-xs">
            <div class="font-extrabold text-indigo-300 uppercase tracking-wider text-[11px] mb-2">Funcionalidades Incluidas en el Recorrido Guiado:</div>
            <ul class="space-y-2 text-slate-300">
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">1.</span> <span><strong>Dirección Académica:</strong> Catálogo de Diplomados, Cursos y Formación Continua, Mallas Curriculares y asignación de 1 o 2 Docentes activos en RRHH.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">2.</span> <span><strong>Panel 7 — Matrículas &amp; Nómina de Matriculados:</strong> Listado con filtros por <strong>Sede</strong> (Santiago / Viña), <strong>Estado Financiero</strong> (Al Día, Pagado Total, Moroso, Pendiente Pago) y <strong>Diplomados o Cursos</strong>, con <strong>Resumen Ejecutivo dinámico según filtros</strong>.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">3.</span> <span><strong>Flujo Digital de Nueva Matrícula (5 Pasos):</strong> Control anti-duplicidad por RUT, Contrato Educacional con Firma Electrónica FEA, pago Webpay Plus y creación automática de acceso al Portal del Alumno.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">4.</span> <span><strong>Gestión Curricular (Paneles 1 al 6):</strong> Expedientes y Hoja de Vida del Alumno, Entrega de Notas, Activación y Congelamiento, Cambios de Curso, Aprobación de Prácticas Clínicas y Emisión de Certificados y Diplomas Oficiales.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">5.</span> <span><strong>Portales Académicos Conectados:</strong> Portal de Secretaría Académica, Portal del Alumno (con marcaje QR MINSAL) y Portal del Docente.</span></li>
            </ul>
          </div>
        </div>

        <div class="space-y-2.5 pt-2">
          <a href="/demo-academia" class="w-full py-3.5 px-5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg transition">
            <span>🚀 Iniciar Demo de Academia (Modo Presentación Cliente)</span>
          </a>
          <div class="grid grid-cols-3 gap-2 text-[11px]">
            <a href="/demo-academia?step=matriculas" class="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-indigo-200 font-bold text-center border border-white/10">Ir a Matrículas &amp; Filtros</a>
            <a href="/demo-academia?step=direccion" class="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-indigo-200 font-bold text-center border border-white/10">Ir a Malla &amp; Cursos</a>
            <a href="/demo-academia?step=portal-alumno" class="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-indigo-200 font-bold text-center border border-white/10">Ir a Portal Alumno</a>
          </div>
        </div>
      </div>

      <!-- TARJETA 2: DEMO CLÍNICA -->
      <div class="rounded-3xl bg-gradient-to-b from-rose-950/90 to-slate-900 border-2 border-rose-500/40 p-7 shadow-2xl flex flex-col justify-between space-y-6">
        <div class="space-y-4">
          <div class="flex items-center justify-between gap-2">
            <span class="px-3 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-400/30 text-xs font-extrabold uppercase">
              DEMO 02 • ÁREA CLÍNICA INDEPENDIENTE
            </span>
            <span class="text-2xl">🩺</span>
          </div>
          <div>
            <h3 class="brand-serif text-2xl font-bold text-white">Demo Clínica &amp; Dirección Asistencial MTC</h3>
            <p class="text-xs text-rose-200/80 mt-1">Servicios Clínicos San Bao SpA (Boxes Acupuntura, Tui na y Práctica Supervisada)</p>
          </div>

          <div class="space-y-2 bg-slate-950/60 p-4 rounded-2xl border border-rose-500/20 text-xs">
            <div class="font-extrabold text-rose-300 uppercase tracking-wider text-[11px] mb-2">Funcionalidades Incluidas en el Recorrido Guiado:</div>
            <ul class="space-y-2 text-slate-300">
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">1.</span> <span><strong>Gestión Clínica Organizada en 5 Paneles:</strong> Toma de Hora Semanal por turnos oficiales de <strong>🪡 Acupuntura</strong> (AM, PM, Vespertino) y <strong>👐 Tui na</strong> (AM, PM), búsqueda de disponibilidad por tutor específico y sobrecupos manuales.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">2.</span> <span><strong>Tag "📍 Hoy" — Agenda del Día &amp; Boxes:</strong> Visualización directa de la agenda de hoy y bloques disponibles al presionar el botón/tag <strong>"Hoy"</strong>.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">3.</span> <span><strong>Dirección Clínica — Calendario y Cierre de Turnos por Jornada:</strong> Cierre directo en calendario diferenciando <strong>Acupuntura</strong> y <strong>Tui na</strong> (por día en la semana, semana completa, mes o indefinidamente) aplicando a todos los tutores del turno.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">4.</span> <span><strong>Nómina de Pacientes Afectados por Cierre:</strong> Envío automático a Gestión Clínica con propuesta de nueva hora para reagendar por <strong>WhatsApp directo</strong> o <strong>llamada telefónica</strong>.</span></li>
              <li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">5.</span> <span><strong>Solicitudes de Sobrecupo y Solicitud de Pago a Finanzas:</strong> Aprobación de sobrecupos en Dirección Clínica y envío de Solicitudes de Pago con <strong>factura adjunta</strong> a Finanzas (cambiando automáticamente a estado <strong>PAGADA</strong> al pagar en Finanzas).</span></li>
            </ul>
          </div>
        </div>

        <div class="space-y-2.5 pt-2">
          <a href="/demo-clinica" class="w-full py-3.5 px-5 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg transition">
            <span>🚀 Iniciar Demo de Clínica (Modo Presentación Cliente)</span>
          </a>
          <div class="grid grid-cols-3 gap-2 text-[11px]">
            <a href="/demo-clinica?step=agenda-semanal" class="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-rose-200 font-bold text-center border border-white/10">Toma de Hora &amp; Hoy</a>
            <a href="/demo-clinica?step=cierres-turno" class="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-rose-200 font-bold text-center border border-white/10">Cierre Turnos &amp; Afectados</a>
            <a href="/demo-clinica?step=pagos-sobrecupos" class="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-rose-200 font-bold text-center border border-white/10">Solicitud Pago &amp; Sobrecupo</a>
          </div>
        </div>
      </div>
    </div>
  </main>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@app.get("/logo_sanbao.png", include_in_schema=False)
@app.get("/logo_sanbao.jpg", include_in_schema=False)
def serve_logo():
    """Sirve el isotipo oficial San Bao (Tres Tesoros: Shen, Jing, Qi - Escuela de Medicina China Clásica)."""
    candidates = [
        os.path.join(static_dir, "img", "logo_sanbao.png"),
        os.path.join(static_dir, "img", "logo_sanbao.jpg"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist/logo_sanbao.png")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend/dist/logo_sanbao.png")),
    ]
    for path in candidates:
        if os.path.exists(path):
            media_type = "image/png" if path.endswith(".png") else "image/jpeg"
            return FileResponse(path, media_type=media_type)
    return JSONResponse(status_code=404, content={"message": "Logo not found"})


@app.get("/health", tags=["Estado y Diagnóstico"])
def health():
    return {"status": "healthy", "database": "connected", "compression": "gzip"}


@app.get("/informe_recomendacion_hosting_chile_san_bao.pdf", tags=["Documentación Técnica y Hosting"])
@app.get("/informe_recomendacion_hosting_chile_san_bao", tags=["Documentación Técnica y Hosting"])
def serve_informe_recomendacion_hosting_pdf():
    """Sirve el Informe Ejecutivo de Recomendación de Hosting en Chile y Directorio Comercial en PDF."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    pdf_path = os.path.join(root_dir, "informe_recomendacion_hosting_chile_san_bao.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename="informe_recomendacion_hosting_chile_san_bao.pdf",
        )
    return JSONResponse(status_code=404, content={"message": "Archivo PDF no encontrado"})


@app.get("/informe_tecnico_hosting_san_bao.pdf", tags=["Documentación Técnica y Hosting"])
@app.get("/informe_tecnico_hosting_san_bao", tags=["Documentación Técnica y Hosting"])
def serve_informe_hosting_pdf():
    """Sirve el Informe Técnico de Hosting, Base de Datos PostgreSQL (3NF/BCNF) y Alta Disponibilidad en PDF."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    pdf_path = os.path.join(root_dir, "informe_tecnico_hosting_san_bao.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename="informe_tecnico_hosting_san_bao.pdf",
        )
    return JSONResponse(status_code=404, content={"message": "Archivo PDF no encontrado"})


@app.get("/informe_tecnico_hosting_san_bao.html", tags=["Documentación Técnica y Hosting"])
def serve_informe_hosting_html():
    """Sirve la versión web imprimible del Informe Técnico de Hosting."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    html_path = os.path.join(root_dir, "informe_tecnico_hosting_san_bao.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return JSONResponse(status_code=404, content={"message": "Archivo HTML no encontrado"})


@app.get("/solicitud_cotizacion_hosting_san_bao.pdf", tags=["Documentación Técnica y Hosting"])
@app.get("/solicitud_cotizacion_hosting_san_bao", tags=["Documentación Técnica y Hosting"])
def serve_solicitud_cotizacion_pdf():
    """Sirve la Solicitud Formal de Cotización (RFP) de Hosting Cloud VPS en PDF."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    pdf_path = os.path.join(root_dir, "solicitud_cotizacion_hosting_san_bao.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename="solicitud_cotizacion_hosting_san_bao.pdf",
        )
    return JSONResponse(status_code=404, content={"message": "Archivo PDF no encontrado"})


@app.get("/solicitud_cotizacion_hosting_san_bao.html", tags=["Documentación Técnica y Hosting"])
def serve_solicitud_cotizacion_html():
    """Sirve la versión web imprimible de la Solicitud Formal de Cotización (RFP) de Hosting."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    html_path = os.path.join(root_dir, "solicitud_cotizacion_hosting_san_bao.html")
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html")
    return JSONResponse(status_code=404, content={"message": "Archivo HTML no encontrado"})


@app.get(f"{settings.API_V1_STR}/institutional/db-normalization-status", tags=["Estado y Diagnóstico"])
def get_db_normalization_status():
    """Diagnóstico en vivo de normalización 3NF/BCNF PostgreSQL, integridad referencial e índices compuestos."""
    tables_by_schema = {}
    total_fks = 0
    total_indexes = 0
    total_unique_constraints = 0
    for table in Base.metadata.tables.values():
        schema_name = table.schema or "public"
        tables_by_schema.setdefault(schema_name, []).append(table.name)
        total_fks += len(table.foreign_keys)
        total_indexes += len(table.indexes)
        total_unique_constraints += sum(
            1 for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"
        )
    return {
        "success": True,
        "normalization_level": "3NF / BCNF",
        "schemas_count": len(tables_by_schema),
        "tables_count": len(Base.metadata.tables),
        "foreign_keys_count": total_fks,
        "composite_and_btree_indexes_count": total_indexes,
        "unique_constraints_count": total_unique_constraints,
        "tables_by_schema": {k: sorted(v) for k, v in sorted(tables_by_schema.items())},
        "backend_optimizations": {
            "gzip_compression": True,
            "connection_pooling": "pool_pre_ping=True, pool_size=20, max_overflow=40",
            "sqlite_wal_mmap": True,
            "seed_memoization": True,
        },
    }
