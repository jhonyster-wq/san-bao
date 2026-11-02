from typing import Any, Optional
from fastapi import HTTPException, status


class SanBaoException(Exception):
    """Excepción base para errores de reglas de negocio en San Bao."""

    def __init__(self, message: str, code: str = "BUSINESS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class EntityNotFoundException(SanBaoException):
    """Lanzada cuando un recurso solicitado no existe."""

    def __init__(self, entity_name: str, identifier: Any = None):
        if identifier is None:
            message = entity_name
        else:
            message = f"{entity_name} con identificador '{identifier}' no fue encontrado."
        super().__init__(
            message=message,
            code="NOT_FOUND",
        )


class EntityAlreadyExistsException(SanBaoException):
    """Lanzada cuando se intenta crear un registro que viola una restricción de unicidad."""

    def __init__(self, entity_name: str, field: str, value: Any):
        super().__init__(
            message=f"{entity_name} con {field} '{value}' ya se encuentra registrado.",
            code="ALREADY_EXISTS",
        )


class InvalidCredentialsException(SanBaoException):
    """Lanzada cuando las credenciales de autenticación son incorrectas."""

    def __init__(self):
        super().__init__(
            message="Credenciales de acceso incorrectas (usuario o contraseña no válidos).",
            code="INVALID_CREDENTIALS",
        )


class PermissionDeniedException(SanBaoException):
    """Lanzada cuando el usuario no cuenta con los permisos necesarios en la sociedad."""

    def __init__(self, detail: str = "No posee permisos para realizar esta acción."):
        super().__init__(message=detail, code="PERMISSION_DENIED")


class CompanyContextRequiredException(SanBaoException):
    """Lanzada cuando una operación requiere el header o contexto de sociedad activa."""

    def __init__(self):
        super().__init__(
            message="Se requiere especificar una sociedad activa válida para esta operación.",
            code="COMPANY_CONTEXT_REQUIRED",
        )


class InvalidRUTException(SanBaoException):
    """Lanzada cuando un RUT no cumple con el algoritmo Módulo 11."""

    def __init__(self, rut: str):
        super().__init__(
            message=f"El RUT '{rut}' no es válido según el algoritmo chileno de Módulo 11.",
            code="INVALID_RUT",
        )
