import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Order(Base, AuditMixin):
    """
    Orden de compra generada en la tienda online de San Bao.
    Al confirmarse el pago:
    1. Registra el pago en finanzas.
    2. Si el comprador no tiene cuenta, crea su persona y usuario digital.
    3. Si los productos son cursos LMS, matricula al usuario de inmediato.
    """

    __tablename__ = "orders"
    __table_args__ = {"schema": "ecommerce"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_person_id = Column(String(36), ForeignKey("core.people.id", ondelete="SET NULL"), nullable=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True, comment="Correlativo web ej: ORD-2026-0001")
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False, index=True)
    customer_rut = Column(String(12), nullable=False, index=True)
    customer_phone = Column(String(50), nullable=True)
    total_amount = Column(Numeric(12, 0), nullable=False)
    payment_status = Column(String(50), default="PENDING", nullable=False, comment="PENDING, PAID, FAILED, REFUNDED")
    payment_gateway = Column(String(50), default="WEBPAY_PLUS", nullable=False, comment="WEBPAY_PLUS, FLOW, MERCADOPAGO")
    paid_at = Column(DateTime(timezone=True), nullable=True)

    company = relationship("Company")
    customer = relationship("Person", foreign_keys=[customer_person_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    transactions = relationship("GatewayTransaction", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.order_number} Total=${self.total_amount} Status={self.payment_status}>"


class OrderItem(Base, AuditMixin):
    """Detalle de producto comprado dentro de la orden."""

    __tablename__ = "order_items"
    __table_args__ = {"schema": "ecommerce"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("ecommerce.orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("ecommerce.products.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(12, 0), nullable=False)
    subtotal = Column(Numeric(12, 0), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class GatewayTransaction(Base, AuditMixin):
    """Registro de la respuesta de la pasarela de pago (Transbank / Flow / MercadoPago)."""

    __tablename__ = "gateway_transactions"
    __table_args__ = {"schema": "ecommerce"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("ecommerce.orders.id", ondelete="CASCADE"), nullable=False, index=True)
    gateway = Column(String(50), nullable=False)
    transaction_id = Column(String(100), nullable=False, index=True)
    authorization_code = Column(String(100), nullable=True)
    amount = Column(Numeric(12, 0), nullable=False)
    status = Column(String(50), nullable=False, comment="SUCCESS, REJECTED, ERROR")
    raw_response = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="transactions")
