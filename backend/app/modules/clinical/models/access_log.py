import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from app.core.database import Base


class ClinicalAccessLog(Base):
    """
    Registro inmutable de trazabilidad y auditoría médica.
    Exigido por la Ley N° 20.584 (Chile) para resguardar la privacidad del paciente.
    Registra cada consulta, apertura, firma o exportación de una ficha clínica.
    """

    __tablename__ = "access_logs"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), nullable=False, index=True)
    encounter_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True, comment="VIEW_RECORD, VIEW_ENCOUNTER, CREATE_ENCOUNTER, SIGN_ENCOUNTER, EXPORT_PDF")
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def __repr__(self):
        return f"<ClinicalAccessLog {self.action} on patient {self.patient_id} by user {self.user_id}>"
