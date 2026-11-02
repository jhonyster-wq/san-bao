import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, Integer, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class ClinicalSupply(Base, AuditMixin):
    """
    Catálogo maestro de insumos clínicos de Medicina Tradicional China.
    Incluye agujas de diferentes calibres, moxas, insumos de auriculoterapia,
    descartables y equipamiento de box retornable.
    """

    __tablename__ = "clinical_supplies"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, comment="AGUJAS, MOXA, AURICULO, DESCARTABLE, EQUIPAMIENTO")
    unit = Column(String(30), default="UNIDAD", nullable=False)
    is_returnable = Column(Boolean, default=False, nullable=False, comment="True para equipos como electro, parlante, encendedor")
    stock_minimum = Column(Integer, default=10, nullable=False)
    current_stock = Column(Integer, default=100, nullable=False, comment="Stock disponible consolidado en bodega central")
    last_restock_date = Column(Date, nullable=True, comment="Fecha de la última reposición o ingreso de stock")
    last_restock_quantity = Column(Integer, nullable=True, comment="Cantidad ingresada en la última reposición")
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company")


class SupplyRestockRecord(Base, AuditMixin):
    """
    Registro histórico de reposiciones e ingresos de insumos a bodega de Dirección Clínica.
    Registra cantidad, fecha de ingreso, responsable y notas.
    """

    __tablename__ = "supply_restock_records"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    supply_id = Column(String(36), ForeignKey("clinical.clinical_supplies.id"), nullable=False, index=True)

    quantity = Column(Integer, nullable=False, comment="Cantidad del movimiento")
    movement_type = Column(String(30), default="INGRESO", nullable=False, comment="INGRESO o EGRESO")
    reason = Column(String(100), nullable=True, comment="REPOSICION, COMPRA, MERMA, VENCIMIENTO, TRASLADO, AJUSTE, USO_CLINICO")
    restock_date = Column(Date, default=date.today, nullable=False, comment="Fecha de movimiento/ingreso a bodega")
    previous_stock = Column(Integer, default=0, nullable=False)
    new_stock = Column(Integer, default=0, nullable=False)
    invoice_or_batch_number = Column(String(100), nullable=True, comment="N° de factura, guía o lote")
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    supply = relationship("ClinicalSupply")



class ShiftSupplyDispatch(Base, AuditMixin):
    """
    Registro del despacho de insumos entregados por la Secretaria Clínica al Terapeuta
    al inicio de su turno, y control de devolución al cierre de turno.
    """

    __tablename__ = "shift_supply_dispatches"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id"), nullable=False, index=True)
    campus_id = Column(String(36), ForeignKey("core.campuses.id"), nullable=False, index=True)
    practitioner_id = Column(String(36), ForeignKey("clinical.practitioners.id"), nullable=False, index=True)
    dispatcher_user_id = Column(String(36), ForeignKey("core.users.id"), nullable=False, comment="Secretaria que despacha")
    room_id = Column(String(36), ForeignKey("core.rooms.id"), nullable=True, comment="Box clínico asignado")
    
    dispatch_code = Column(String(50), unique=True, nullable=False, index=True)
    shift_date = Column(Date, default=date.today, nullable=False)
    shift_type = Column(String(30), default="MANANA", nullable=False, comment="MANANA, TARDE, COMPLETO")
    status = Column(String(30), default="DISPATCHED", nullable=False, comment="DISPATCHED, RETURNED, CLOSED")
    
    delivered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    returned_at = Column(DateTime, nullable=True)
    return_verified_by_user_id = Column(String(36), ForeignKey("core.users.id"), nullable=True)
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    campus = relationship("Campus")
    practitioner = relationship("Practitioner")
    dispatcher = relationship("User", foreign_keys=[dispatcher_user_id])
    return_verifier = relationship("User", foreign_keys=[return_verified_by_user_id])
    room = relationship("Room")
    items = relationship("ShiftSupplyItem", back_populates="dispatch", cascade="all, delete-orphan")


class ShiftSupplyItem(Base, AuditMixin):
    """
    Detalle de cantidad entregada, usada y devuelta para un insumo en el turno.
    """

    __tablename__ = "shift_supply_items"
    __table_args__ = {"schema": "clinical"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispatch_id = Column(String(36), ForeignKey("clinical.shift_supply_dispatches.id", ondelete="CASCADE"), nullable=False, index=True)
    supply_id = Column(String(36), ForeignKey("clinical.clinical_supplies.id"), nullable=False, index=True)
    
    quantity_delivered = Column(Integer, default=1, nullable=False)
    quantity_used = Column(Integer, default=0, nullable=False)
    quantity_returned = Column(Integer, default=0, nullable=False)
    condition_notes = Column(String(255), nullable=True)

    dispatch = relationship("ShiftSupplyDispatch", back_populates="items")
    supply = relationship("ClinicalSupply")
