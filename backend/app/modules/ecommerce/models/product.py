import uuid
from sqlalchemy import Column, String, Boolean, Integer, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.audit import AuditMixin


class Product(Base, AuditMixin):
    """
    Producto o Curso ofertado en el catálogo público de comercio electrónico San Bao.
    Puede estar vinculado a un aula virtual (`lms.lms_courses.id`) para enrolamiento automático al comprar.
    """

    __tablename__ = "products"
    __table_args__ = {"schema": "ecommerce"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    lms_course_id = Column(String(36), ForeignKey("lms.lms_courses.id", ondelete="SET NULL"), nullable=True, index=True, comment="Aula virtual asociada para matriculación automática")
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    price_clp = Column(Numeric(12, 0), nullable=False, comment="Precio en pesos chilenos")
    promotional_price_clp = Column(Numeric(12, 0), nullable=True)
    is_digital = Column(Boolean, default=True, nullable=False)
    stock = Column(Integer, nullable=True, comment="NULL = cupos ilimitados")
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company")
    lms_course = relationship("LMSCourse")

    def __repr__(self):
        return f"<Product {self.sku}: {self.name} (${self.price_clp} CLP)>"


class EcommercePromotion(Base, AuditMixin):
    """
    Promoción, Cupón de Descuento o Actividad Comercial del E-Commerce San Bao.
    Soporta cupones promocionales (EARLYBIRD, ALUMNO15, SEMINARIOVIP), becas parciales,
    campañas comerciales y actividades promocionales (Webinars / Clases Magistrales Abiertas).
    """

    __tablename__ = "promotions"
    __table_args__ = {"schema": "ecommerce"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("core.companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True, comment="Código de cupón o actividad (ej: SANBAO2026)")
    title = Column(String(255), nullable=False)
    activity_type = Column(
        String(50),
        default="CUPON_DESCUENTO",
        nullable=False,
        comment="CUPON_DESCUENTO, CAMPANA_EARLY_BIRD, BECA_COMERCIAL, WEBINAR_GRATUITO, SEMINARIO_PROMOCIONAL",
    )
    discount_type = Column(String(20), default="PERCENTAGE", nullable=False, comment="PERCENTAGE, FIXED_CLP")
    discount_value = Column(Numeric(12, 0), default=15, nullable=False, comment="% de descuento o monto CLP fijo")
    applies_to_category = Column(String(80), default="TODOS", nullable=False, comment="TODOS, SEMINARIO, FORMACION_CONTINUA, CURSO, DIPLOMADO")
    valid_from = Column(String(30), nullable=True)
    valid_until = Column(String(30), nullable=True)
    max_uses = Column(Integer, default=100, nullable=False)
    used_count = Column(Integer, default=0, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    company = relationship("Company")

    def __repr__(self):
        return f"<EcommercePromotion {self.code}: {self.title} ({self.discount_value})>"

