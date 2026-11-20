from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.institutional.models.rbac import Role, Permission, UserCompanyRole
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException


class RBACService:
    def __init__(self, db: Session):
        self.db = db

    def get_role_by_code(self, code: str) -> Optional[Role]:
        return self.db.query(Role).filter(Role.code == code, Role.deleted_at.is_(None)).first()

    def get_permission_by_code(self, code: str) -> Optional[Permission]:
        return self.db.query(Permission).filter(Permission.code == code, Permission.deleted_at.is_(None)).first()

    def create_permission(self, code: str, name: str, module: str, description: Optional[str] = None) -> Permission:
        existing = self.get_permission_by_code(code)
        if existing:
            return existing
        perm = Permission(code=code, name=name, module=module, description=description)
        self.db.add(perm)
        self.db.commit()
        self.db.refresh(perm)
        return perm

    def create_role(self, code: str, name: str, scope: str = "GLOBAL", description: Optional[str] = None, permissions: List[str] = []) -> Role:
        existing = self.get_role_by_code(code)
        if existing:
            updated = False
            for perm_code in permissions:
                perm = self.get_permission_by_code(perm_code)
                if perm and perm not in existing.permissions:
                    existing.permissions.append(perm)
                    updated = True
            if updated:
                self.db.commit()
                self.db.refresh(existing)
            return existing

        role = Role(code=code, name=name, scope=scope, description=description)
        for perm_code in permissions:
            perm = self.get_permission_by_code(perm_code)
            if perm and perm not in role.permissions:
                role.permissions.append(perm)

        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def assign_user_to_company(self, user_id: str, company_id: str, role_id: str) -> UserCompanyRole:
        """Asigna a un usuario un rol dentro de una sociedad específica."""
        existing = (
            self.db.query(UserCompanyRole)
            .filter(
                UserCompanyRole.user_id == user_id,
                UserCompanyRole.company_id == company_id,
                UserCompanyRole.role_id == role_id,
                UserCompanyRole.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            existing.is_active = True
            self.db.commit()
            return existing

        assignment = UserCompanyRole(
            user_id=user_id,
            company_id=company_id,
            role_id=role_id,
            is_active=True,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def seed_default_roles_and_permissions(self):
        """Crea los roles y permisos iniciales estándar para el Instituto y la Clínica."""
        # Permisos base
        default_permissions = [
            # Institucional
            ("institutional:companies:read", "Ver sociedades", "INSTITUTIONAL"),
            ("institutional:companies:manage", "Gestionar sociedades", "INSTITUTIONAL"),
            ("institutional:users:manage", "Administrar usuarios y accesos", "INSTITUTIONAL"),
            # Académico
            ("academic:students:read", "Ver alumnos y estado académico", "ACADEMIC"),
            ("academic:students:manage", "Gestionar admisiones y matrículas", "ACADEMIC"),
            ("academic:courses:manage", "Gestionar mallas y asignaturas", "ACADEMIC"),
            ("academic:grades:record", "Registrar calificaciones", "ACADEMIC"),
            ("academic:practice_hours:approve", "Aprobar horas de práctica clínica (Tutor)", "ACADEMIC"),
            ("academic:summary:read", "Consultar información académica agregada (Dirección)", "ACADEMIC"),
            # Clínico
            ("clinical:patients:read", "Ver lista de pacientes", "CLINICAL"),
            ("clinical:patients:manage", "Registrar y editar pacientes", "CLINICAL"),
            ("clinical:encounters:create", "Crear atención clínica", "CLINICAL"),
            ("clinical:encounters:sign", "Firmar atención clínica (Tutor/Profesional)", "CLINICAL"),
            ("clinical:records:read", "Consultar ficha clínica y anamnesis sensible (Ley 20.584)", "CLINICAL"),
            ("clinical:practice_hours:read", "Lectura de horas de práctica clínica (Coordinación Académica)", "CLINICAL"),
            ("clinical:summary:read", "Consultar información clínica agregada (Dirección)", "CLINICAL"),
            # Finanzas
            ("finance:invoices:read", "Ver documentos tributarios y obligaciones", "FINANCE"),
            ("finance:invoices:create", "Emitir boletas, facturas y notas de crédito", "FINANCE"),
            ("finance:payments:record", "Registrar recaudación, pagos, reversos y tesorería", "FINANCE"),
            ("finance:summary:read", "Consultar información financiera agregada (Dirección)", "FINANCE"),
        ]

        for code, name, module in default_permissions:
            self.create_permission(code, name, module)

        # Roles institucionales
        self.create_role(
            code="SUPERADMIN",
            name="Superadministrador del Sistema",
            scope="GLOBAL",
            description="Control total sobre ambas sociedades y configuración técnica",
        )
        self.create_role(
            code="DIRECCION",
            name="Dirección Ejecutiva / Gerencia San Bao",
            scope="GLOBAL",
            description="Acceso a información agregada de Finanzas, Académico y Clínica conforme a permisos autorizados",
            permissions=[
                "institutional:companies:read",
                "finance:summary:read",
                "academic:summary:read",
                "clinical:summary:read",
                "academic:students:read",
                "finance:invoices:read",
            ],
        )
        self.create_role(
            code="ADMIN_ACADEMICO",
            name="Administrador Académico",
            scope="ACADEMIC",
            description="Gestión de programas, mallas, admisiones y matrículas del Instituto",
            permissions=["academic:students:read", "academic:students:manage", "academic:courses:manage", "clinical:practice_hours:read"],
        )
        self.create_role(
            code="DIRECCION_ACADEMICA",
            name="Dirección Académica y Docencia",
            scope="ACADEMIC",
            description="Creación y gestión de diplomados, cursos y formación continua, diseño curricular, asignaturas y asignación de docentes",
            permissions=[
                "academic:students:read",
                "academic:students:manage",
                "academic:courses:manage",
                "academic:grades:record",
                "clinical:practice_hours:read",
                "academic:summary:read",
                "clinical:summary:read",
                "finance:summary:read",
            ],
        )
        self.create_role(
            code="COORDINADOR_ACADEMICO",
            name="Coordinador Académico (COORD_ACADÉMICA)",
            scope="ACADEMIC",
            description="Académico: lectura y escritura. Clínica: lectura de horas de práctica.",
            permissions=[
                "academic:students:read",
                "academic:students:manage",
                "academic:courses:manage",
                "academic:grades:record",
                "clinical:practice_hours:read",
            ],
        )
        self.create_role(
            code="DOCENTE",
            name="Docente de Aula Teórica",
            scope="ACADEMIC",
            description="Profesor de asignaturas teóricas del Instituto",
            permissions=["academic:students:read", "academic:grades:record"],
        )
        self.create_role(
            code="TUTOR_CLINICO",
            name="Docente Tutor de Prácticas Clínicas (TUTOR)",
            scope="CLINICAL",
            description="Clínica: acceso autorizado a ficha y evaluación según su responsabilidad",
            permissions=[
                "academic:students:read",
                "academic:practice_hours:approve",
                "clinical:patients:read",
                "clinical:records:read",
                "clinical:encounters:create",
                "clinical:encounters:sign",
            ],
        )
        self.create_role(
            code="TERAPEUTA",
            name="Terapeuta Clínico",
            scope="CLINICAL",
            description="Profesional de salud acreditado de Servicios Clínicos San Bao",
            permissions=[
                "clinical:patients:read",
                "clinical:patients:manage",
                "clinical:records:read",
                "clinical:encounters:create",
                "clinical:encounters:sign",
            ],
        )
        self.create_role(
            code="DIRECCION_CLINICA",
            name="Dirección Clínica y Gestión Asistencial",
            scope="CLINICAL",
            description="Administración de tutores clínicos, valores de sesiones, creación y cierre de turnos, turnero de terapeutas, control de stock y métricas de insumos",
            permissions=[
                "clinical:patients:read",
                "clinical:patients:manage",
                "clinical:records:read",
                "clinical:encounters:create",
                "clinical:encounters:sign",
                "clinical:practice_hours:read",
                "clinical:summary:read",
                "academic:summary:read",
                "finance:summary:read",
            ],
        )
        self.create_role(
            code="SECRETARIA_CLINICA",
            name="Secretaria Clínica y Recepción",
            scope="CLINICAL",
            description="Recepción de pacientes, reserva y confirmación de horas en box clínico por sede (Santiago / Viña del Mar)",
            permissions=[
                "clinical:patients:read",
                "clinical:patients:manage",
            ],
        )
        self.create_role(
            code="ALUMNO",
            name="Alumno Regular",
            scope="ACADEMIC",
            description="Estudiante del Instituto de Medicina China Clásica SpA",
            permissions=["academic:students:read"],
        )
        self.create_role(
            code="ALUMNO_PRACTICA",
            name="Alumno en Práctica Clínica",
            scope="CLINICAL",
            description="Estudiante habilitado para registrar atenciones supervisadas",
            permissions=["clinical:patients:read", "clinical:encounters:create"],
        )
        self.create_role(
            code="ADMIN_FINANZAS",
            name="Administrador de Finanzas y Tesorería",
            scope="FINANCE",
            description="Finanzas: lectura y escritura. Académico: lectura de estado. Clínica: SIN acceso a anamnesis.",
            permissions=[
                "finance:invoices:read",
                "finance:invoices:create",
                "finance:payments:record",
                "academic:students:read",
            ],
        )
