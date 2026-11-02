from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.modules.institutional.models.user import User
from app.modules.institutional.models.person import Person
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.rbac import Role, UserCompanyRole, Permission
from app.modules.institutional.schemas.auth import TokenResponse, AvailableCompanyContext, CurrentUserContext
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.exceptions import InvalidCredentialsException, PermissionDeniedException, EntityNotFoundException
from app.shared.validators.rut import ChileanRUT


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, username_or_rut: str, password: str) -> User:
        """Autentica a un usuario por su nombre de usuario o por el RUT de su ficha personal."""
        user = self.db.query(User).filter(User.username == username_or_rut.strip(), User.deleted_at.is_(None)).first()

        # Si no lo encuentra por username, intentar por RUT
        if not user:
            cleaned_rut = ChileanRUT.clean(username_or_rut)
            person = self.db.query(Person).filter(Person.rut == cleaned_rut, Person.deleted_at.is_(None)).first()
            if person and person.user:
                user = person.user

        if not user or not user.is_active:
            raise InvalidCredentialsException()

        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsException()

        # Actualizar último inicio de sesión
        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        return user

    def get_user_companies(self, user: User) -> List[AvailableCompanyContext]:
        """Obtiene la lista de sociedades en las que el usuario tiene roles asignados y activos."""
        if user.is_superuser:
            # Superadmin tiene acceso a todas las sociedades activas del sistema
            companies = self.db.query(Company).filter(Company.is_active == True, Company.deleted_at.is_(None)).all()
            return [
                AvailableCompanyContext(
                    id=c.id,
                    rut=c.rut,
                    trade_name=c.trade_name,
                    legal_name=c.legal_name,
                    roles=["SUPERADMIN"],
                )
                for c in companies
            ]

        # Usuarios regulares: consultar asignaciones en core.user_company_roles
        assignments = (
            self.db.query(UserCompanyRole)
            .filter(
                UserCompanyRole.user_id == user.id,
                UserCompanyRole.is_active == True,
                UserCompanyRole.deleted_at.is_(None),
            )
            .all()
        )

        company_map: Dict[str, AvailableCompanyContext] = {}
        for a in assignments:
            if not a.company or not a.company.is_active:
                continue
            cid = a.company.id
            if cid not in company_map:
                company_map[cid] = AvailableCompanyContext(
                    id=a.company.id,
                    rut=a.company.rut,
                    trade_name=a.company.trade_name,
                    legal_name=a.company.legal_name,
                    roles=[],
                )
            if a.role and a.role.is_active:
                company_map[cid].roles.append(a.role.code)

        return list(company_map.values())

    def generate_token_response(self, user: User, requested_company_id: Optional[str] = None) -> TokenResponse:
        """Genera tokens JWT y encapsula el contexto de sociedades disponibles y activa."""
        available_companies = self.get_user_companies(user)

        active_company: Optional[AvailableCompanyContext] = None
        if requested_company_id:
            active_company = next((c for c in available_companies if c.id == requested_company_id), None)
            if not active_company and not user.is_superuser:
                raise PermissionDeniedException("No tiene permisos para operar en la sociedad solicitada.")
        elif available_companies:
            # Seleccionar por defecto la primera sociedad disponible
            active_company = available_companies[0]

        token_payload = {
            "sub": str(user.id),
            "username": user.username,
            "person_id": str(user.person_id),
            "is_superuser": user.is_superuser,
            "company_id": active_company.id if active_company else None,
            "roles": active_company.roles if active_company else [],
        }

        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(str(user.id))

        full_name = user.person.full_name if user.person else user.username

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=str(user.id),
            username=user.username,
            full_name=full_name,
            available_companies=available_companies,
            active_company=active_company,
        )

    def get_current_user_context(self, user: User, company_id: Optional[str] = None) -> CurrentUserContext:
        """Construye el contexto enriquecido del usuario activo para el frontend."""
        available_companies = self.get_user_companies(user)
        active_company = None
        if company_id:
            active_company = next((c for c in available_companies if c.id == company_id), None)
        elif available_companies:
            active_company = available_companies[0]

        roles: List[str] = active_company.roles if active_company else []
        permissions: List[str] = []

        if user.is_superuser:
            permissions.append("*")
        elif active_company:
            # Obtener códigos de permisos asociados a los roles del usuario en esta sociedad
            role_objs = self.db.query(Role).filter(Role.code.in_(roles), Role.is_active == True).all()
            for r in role_objs:
                for p in r.permissions:
                    if p.code not in permissions:
                        permissions.append(p.code)

        return CurrentUserContext(
            user_id=str(user.id),
            username=user.username,
            full_name=user.person.full_name if user.person else user.username,
            is_superuser=user.is_superuser,
            active_company_id=active_company.id if active_company else None,
            active_company_name=active_company.trade_name if active_company else None,
            roles=roles,
            permissions=permissions,
        )
