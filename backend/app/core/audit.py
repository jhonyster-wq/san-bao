import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID


def get_utc_now():
    """Retorna la fecha y hora actual en UTC."""
    return datetime.now(timezone.utc)


class AuditMixin:
    """
    Mixin transversal para auditoría y trazabilidad en todas las entidades del sistema.
    Cumple con el requerimiento de registro de fechas UTC, usuario responsable y soft-delete.
    """

    created_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        comment="Fecha y hora de creación del registro en UTC",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
        comment="Fecha y hora de última modificación en UTC",
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
        comment="Fecha de eliminación lógica (soft-delete). NULL si está activo",
    )

    def soft_delete(self):
        """Marca la entidad como eliminada lógicamente."""
        self.deleted_at = get_utc_now()

    def restore(self):
        """Restaura una entidad previamente eliminada lógicamente."""
        self.deleted_at = None

    @property
    def is_deleted(self) -> bool:
        """Indica si el registro fue eliminado lógicamente."""
        return self.deleted_at is not None
