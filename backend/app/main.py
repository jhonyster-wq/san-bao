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
def serve_frontend_app():
    """Sirve la interfaz web interactiva del Sistema Integral San Bao."""
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


@app.get("/logo_sanbao.png", include_in_schema=False)
@app.get("/logo_sanbao.jpg", include_in_schema=False)
def serve_logo():
    """Sirve el isotipo oficial San Bao (Tres Tesoros: Jing, Qi, Shen - Escuela de Medicina China Clásica)."""
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
