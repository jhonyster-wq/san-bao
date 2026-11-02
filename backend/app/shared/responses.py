from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Estructura estándar de respuesta para los endpoints de la API San Bao."""

    success: bool = True
    message: str = "Operación realizada exitosamente"
    data: Optional[T] = None
    error: Optional[Any] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Estructura de respuesta paginada con metadatos de conteo y navegación."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
