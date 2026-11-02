from typing import Optional, List
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import InvalidCredentialsException, PermissionDeniedException, CompanyContextRequiredException
from app.modules.institutional.models.user import User
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.rbac import UserCompanyRole, Role, Permission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/institutional/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extrae y valida el usuario activo a partir del token JWT Bearer."""
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise InvalidCredentialsException()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id, User.is_active == True, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_active_company(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[Company]:
    """
    Obtiene la sociedad activa en base al header 'X-Company-ID'.
    Valida que la sociedad exista y que el usuario tenga acceso a ella (a menos que sea superusuario).
    """
    if not x_company_id:
        return None

    company = db.query(Company).filter(Company.id == x_company_id, Company.is_active == True, Company.deleted_at.is_(None)).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sociedad con ID '{x_company_id}' no existe o se encuentra inactiva",
        )

    if not current_user.is_superuser:
        has_role = (
            db.query(UserCompanyRole)
            .filter(
                UserCompanyRole.user_id == current_user.id,
                UserCompanyRole.company_id == company.id,
                UserCompanyRole.is_active == True,
                UserCompanyRole.deleted_at.is_(None),
            )
            .first()
        )
        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No cuenta con autorización para operar en esta sociedad",
            )

    return company


def require_company_context(
    company: Optional[Company] = Depends(get_current_active_company),
) -> Company:
    """Dependencia estricta que exige que la petición contenga un contexto de sociedad válido."""
    if not company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe especificar la cabecera 'X-Company-ID' con una sociedad válida para esta operación",
        )
    return company


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """Restringe el acceso únicamente a superadministradores de plataforma."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a superadministradores de la plataforma San Bao",
        )
    return current_user


def require_permission(permission_code: str):
    """
    Fábrica de dependencias que valida si el usuario cuenta con un permiso específico
    dentro de la sociedad activa actual.
    """

    def permission_checker(
        current_user: User = Depends(get_current_user),
        company: Optional[Company] = Depends(get_current_active_company),
        db: Session = Depends(get_db),
    ) -> bool:
        if current_user.is_superuser:
            return True

        if not company:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere especificar la cabecera 'X-Company-ID' para verificar permisos de módulo",
            )

        # Buscar roles del usuario en esta sociedad
        user_roles = (
            db.query(UserCompanyRole)
            .filter(
                UserCompanyRole.user_id == current_user.id,
                UserCompanyRole.company_id == company.id,
                UserCompanyRole.is_active == True,
                UserCompanyRole.deleted_at.is_(None),
            )
            .all()
        )

        role_ids = [ur.role_id for ur in user_roles]
        if not role_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No posee roles asignados en esta sociedad",
            )

        # Verificar si alguno de sus roles posee el permiso requerido
        has_perm = (
            db.query(Role)
            .join(Role.permissions)
            .filter(
                Role.id.in_(role_ids),
                Role.is_active == True,
                Permission.code == permission_code,
            )
            .first()
        )

        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso insuficiente. Requiere '{permission_code}'",
            )

        return True

    return permission_checker
