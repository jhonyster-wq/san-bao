from typing import Any, Dict, List
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import InvalidCredentialsException, PermissionDeniedException
from app.modules.institutional.models.user import User
from app.modules.institutional.schemas.auth import (
    LoginRequest,
    TokenResponse,
    SwitchCompanyRequest,
    CurrentUserContext,
)
from app.modules.institutional.services.auth_service import AuthService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/auth", tags=["Autenticación y Sesión"])


SSO_PORTAL_DIRECTORY: List[Dict[str, Any]] = [
    {
        "username": "admin@sanbao.cl",
        "rut": "10.111.222-3",
        "password": "SanBao#2026",
        "full_name": "Administrador General Holding",
        "avatar": "AD",
        "portal_role": "admin",
        "portal_number": 1,
        "portal_name": "1. Portal Administrativo (Holding & ERP)",
        "role_label": "Superadministrador Holding San Bao",
        "company_scope": "consolidated",
        "default_tab": "dashboard",
        "allowed_tabs": [
            "portals", "dashboard", "finance", "hr", "lms", "integrations",
            "academic-direction", "academic-coordinator", "academic",
            "clinical-management", "clinical", "student", "teacher-portal", "tutor-portal", "patient-portal"
        ],
    },
    {
        "username": "finanzas@sanbao.cl",
        "rut": "12.456.789-0",
        "password": "SanBao#2026",
        "full_name": "Dirección de Finanzas & SII",
        "avatar": "FN",
        "portal_role": "finanzas",
        "portal_number": 1,
        "portal_name": "1. Portal Administrativo (Finanzas & DTE SII)",
        "role_label": "Tesorería, Contabilidad, Cobranza y DTE SII",
        "company_scope": "consolidated",
        "default_tab": "finance",
        "allowed_tabs": ["dashboard", "finance", "hr", "lms", "integrations"],
    },
    {
        "username": "rrhh@sanbao.cl",
        "rut": "13.222.333-4",
        "password": "SanBao#2026",
        "full_name": "Jefatura de Personas & RRHH",
        "avatar": "RH",
        "portal_role": "admin",
        "portal_number": 1,
        "portal_name": "1. Portal Administrativo (Personas & RRHH)",
        "role_label": "Gestión de Personas, Contratos y Remuneraciones",
        "company_scope": "consolidated",
        "default_tab": "hr",
        "allowed_tabs": ["dashboard", "hr", "finance"],
    },
    {
        "username": "direccion.academica@sanbao.cl",
        "rut": "11.345.678-9",
        "password": "SanBao#2026",
        "full_name": "Dra. Marcela Pérez Morales",
        "avatar": "MP",
        "portal_role": "director_academico",
        "portal_number": 2,
        "portal_name": "2. Portal Académico (Dirección Académica)",
        "role_label": "Directora Académica • Escuela San Bao SpA",
        "company_scope": "instituto",
        "default_tab": "academic-direction",
        "allowed_tabs": ["academic-direction", "academic-coordinator"],
    },
    {
        "username": "coordinacion@sanbao.cl",
        "rut": "14.567.890-1",
        "password": "SanBao#2026",
        "full_name": "Lic. Camilo San Martín B.",
        "avatar": "CS",
        "portal_role": "coordinador",
        "portal_number": 2,
        "portal_name": "2. Portal Académico (Gestión Académica)",
        "role_label": "Gestión Académica • Expedientes, Notas y Control Curricular",
        "company_scope": "instituto",
        "default_tab": "academic-coordinator",
        "allowed_tabs": ["academic-coordinator"],
    },
    {
        "username": "secretaria.sede@sanbao.cl",
        "rut": "16.543.210-9",
        "password": "SanBao#2026",
        "full_name": "Carolina Vega Henríquez",
        "avatar": "CV",
        "portal_role": "secretaria_academica",
        "portal_number": 7,
        "portal_name": "7. Portal de Secretaría (Gestión Secretaría)",
        "role_label": "Gestión Secretaría • Consulta Sede, Catálogo y Prácticas Clínicas",
        "company_scope": "instituto",
        "default_tab": "academic",
        "allowed_tabs": ["academic"],
    },
    {
        "username": "direccion.clinica@sanbao.cl",
        "rut": "10.987.654-2",
        "password": "SanBao#2026",
        "full_name": "Dr. Roberto Valenzuela",
        "avatar": "RV",
        "portal_role": "director",
        "portal_number": 3,
        "portal_name": "3. Portal Clínico (Dirección Clínica MTC)",
        "role_label": "Director Clínico • Servicios Clínicos San Bao SpA",
        "company_scope": "clinica",
        "default_tab": "clinical-management",
        "allowed_tabs": ["clinical-management", "clinical"],
    },
    {
        "username": "recepcion@sanbao.cl",
        "rut": "18.234.567-8",
        "password": "SanBao#2026",
        "full_name": "Valentina Morales",
        "avatar": "VM",
        "portal_role": "secretaria",
        "portal_number": 3,
        "portal_name": "3. Portal Clínico (Recepción & Agenda MTC)",
        "role_label": "Secretaria Clínica • Sede Providencia, Santiago",
        "company_scope": "clinica",
        "default_tab": "clinical",
        "allowed_tabs": ["clinical"],
    },
    {
        "username": "diego.valenzuela@alumno.sanbao.cl",
        "rut": "19.876.543-0",
        "password": "SanBao#2026",
        "full_name": "Diego Valenzuela Rojas",
        "avatar": "DV",
        "portal_role": "alumno",
        "portal_number": 4,
        "portal_name": "Portal de Alumnos",
        "role_label": "Alumno Regular (MAT-2026-0001) • Escuela San Bao SpA",
        "company_scope": "instituto",
        "default_tab": "student",
        "allowed_tabs": ["student"],
    },
    {
        "username": "zhiwei.chen@docente.sanbao.cl",
        "rut": "14.112.233-K",
        "password": "SanBao#2026",
        "full_name": "Prof. Zhiwei Chen",
        "avatar": "ZC",
        "portal_role": "docente",
        "portal_number": 5,
        "portal_name": "Portal de Docentes",
        "role_label": "Docente Titular • Escuela San Bao SpA",
        "company_scope": "instituto",
        "default_tab": "teacher-portal",
        "allowed_tabs": ["teacher-portal"],
    },
    {
        "username": "tutor.clinico@sanbao.cl",
        "rut": "12.876.543-1",
        "password": "SanBao#2026",
        "full_name": "Dr. Roberto Gómez Valdés",
        "avatar": "RG",
        "portal_role": "tutor_clinico",
        "portal_number": 8,
        "portal_name": "Portal de Tutores",
        "role_label": "Tutor Clínico Supervisor • Clínica San Bao SpA",
        "company_scope": "clinica",
        "default_tab": "tutor-portal",
        "allowed_tabs": ["tutor-portal"],
    },
    {
        "username": "rodrigo.silva@paciente.cl",
        "rut": "17.123.456-5",
        "password": "SanBao#2026",
        "full_name": "Rodrigo Silva",
        "avatar": "RS",
        "portal_role": "paciente",
        "portal_number": 6,
        "portal_name": "6. Portal de Pacientes",
        "role_label": "Paciente Clínico • Sede Providencia, Santiago",
        "company_scope": "clinica",
        "default_tab": "patient-portal",
        "allowed_tabs": ["patient-portal"],
    },
]


@router.post("/login", response_model=APIResponse[TokenResponse], summary="Iniciar sesión con credenciales")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Autentica al usuario mediante usuario/RUT y contraseña.
    Retorna el token JWT con expiración, datos de la persona y lista de sociedades en las que tiene roles.
    """
    service = AuthService(db)
    try:
        user = service.authenticate_user(payload.username, payload.password)
        token_data = service.generate_token_response(user)
        return APIResponse(message="Inicio de sesión exitoso", data=token_data)
    except InvalidCredentialsException as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


@router.post("/token", response_model=Dict[str, Any] if False else Any, summary="Endpoint compatible con Swagger OAuth2")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Endpoint estándar compatible con OpenAPI Swagger UI (Authorize)."""
    service = AuthService(db)
    try:
        user = service.authenticate_user(form_data.username, form_data.password)
        token_data = service.generate_token_response(user)
        return {
            "access_token": token_data.access_token,
            "token_type": "bearer",
            "refresh_token": token_data.refresh_token,
        }
    except InvalidCredentialsException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/switch-company", response_model=APIResponse[TokenResponse], summary="Conmutar contexto de sociedad activa")
def switch_company(
    payload: SwitchCompanyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permite a un usuario con roles en múltiples sociedades alternar su contexto de trabajo activo
    (ej: cambiar entre Instituto de Medicina China Clásica SpA y Servicios Clínicos San Bao SpA).
    """
    service = AuthService(db)
    try:
        token_data = service.generate_token_response(current_user, requested_company_id=payload.company_id)
        return APIResponse(message="Contexto de sociedad conmutado exitosamente", data=token_data)
    except PermissionDeniedException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)


@router.get("/me", response_model=APIResponse[CurrentUserContext], summary="Obtener perfil y permisos del usuario activo")
def get_me(
    company_id: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna los datos de identidad, roles y permisos efectivos del usuario actual en la sociedad solicitada."""
    service = AuthService(db)
    context = service.get_current_user_context(current_user, company_id=company_id)
    return APIResponse(data=context)


@router.get("/sso-test-users", summary="Directorio de usuarios de prueba para Login Único SSO de los 6 Portales")
def list_sso_test_users():
    return APIResponse(
        message="Usuarios de prueba habilitados para el Ingreso Único (SSO) por Portal",
        data=SSO_PORTAL_DIRECTORY,
    )


@router.post("/sso-portal-login", summary="Ingreso Único (SSO) que autentica y enruta automáticamente al Portal según el Rol")
def sso_portal_login(payload: Dict[str, Any], db: Session = Depends(get_db)):
    identifier = str(payload.get("identifier") or payload.get("username") or payload.get("rut") or "").strip().lower()
    password = str(payload.get("password") or "").strip()

    if not identifier or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe ingresar su RUT / Correo Electrónico y Contraseña.",
        )

    clean_id = identifier.replace(".", "").replace(" ", "")

    for entry in SSO_PORTAL_DIRECTORY:
        entry_user = entry["username"].lower()
        entry_rut = entry["rut"].lower()
        entry_rut_clean = entry_rut.replace(".", "")

        if identifier in (entry_user, entry_rut) or clean_id == entry_rut_clean:
            if password != entry["password"] and password != "SanBao#2026!":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Contraseña incorrecta para el usuario indicado.",
                )
            token_hash = hashlib.sha256(f"{entry['rut']}:{datetime.utcnow().isoformat()}".encode()).hexdigest()
            return APIResponse(
                message=f"Bienvenido(a) {entry['full_name']} • Redirigiendo a {entry['portal_name']}",
                data={
                    **entry,
                    "session_token": f"JWT-SSO-{token_hash[:24].upper()}",
                    "authenticated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )

    # También permitir alumnos creados dinámicamente en el proceso de matrícula / E-Commerce
    try:
        from app.modules.academic.services.coordinator_service import CoordinatorService
        from app.modules.institutional.models.company import Company

        comp = db.query(Company).first()
        if comp:
            coord_svc = CoordinatorService(db)
            st_auth = coord_svc.authenticate_student_portal(comp.id, identifier, password)
            st = st_auth.get("student", {})
            st_name = st.get("student_name", "Alumno Regular San Bao")
            initials = "".join([w[0] for w in st_name.split()[:2]]).upper() or "AL"
            return APIResponse(
                message=f"Bienvenido(a) {st_name} • Redirigiendo a 4. Portal de Alumnos",
                data={
                    "username": st.get("email", identifier),
                    "rut": st.get("rut", identifier),
                    "full_name": st_name,
                    "avatar": initials,
                    "portal_role": "alumno",
                    "portal_number": 4,
                    "portal_name": "4. Portal de Alumnos",
                    "role_label": f"Alumno Regular ({st.get('student_number', 'MAT-2026')})",
                    "company_scope": "instituto",
                    "default_tab": "student",
                    "allowed_tabs": ["student"],
                    "session_token": st_auth.get("session_token", "JWT-STUDENT-SSO"),
                    "authenticated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales no reconocidas. Verifique su RUT / Correo y Contraseña o seleccione un usuario de prueba.",
    )
