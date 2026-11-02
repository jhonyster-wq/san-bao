from datetime import date, datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.clinical.models.supply import ClinicalSupply, ShiftSupplyDispatch, ShiftSupplyItem
from app.modules.clinical.models.practitioner import Practitioner
from app.modules.clinical.schemas.supply import (
    ClinicalSupplyCreate,
    ShiftSupplyDispatchCreate,
    ShiftSupplyReturnUpdate,
)
from app.core.exceptions import EntityNotFoundException, SanBaoException


OFFICIAL_SANBAO_SUPPLIES = [
    # 1. Agujas Corporales y Especiales (14 medidas oficiales)
    ("INS-AGU-2525", "Agujas 25 x 25", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-2530", "Agujas 25 x 30", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-2540", "Agujas 25 x 40", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-3030", "Agujas 30 x 30", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-3040", "Agujas 30 x 40", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-1613", "Agujas 16 x 13", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-1813", "Agujas 18 x 13", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-2013", "Agujas 20 x 13", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-2240", "Agujas 22 x 40", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-1825", "Agujas 18 x 25", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-2575", "Agujas 25 x 75", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-3075", "Agujas 30 x 75", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-30100", "Agujas 30 x 100", "AGUJAS", "UNIDAD", False),
    ("INS-AGU-35125", "Agujas 35 x 125", "AGUJAS", "UNIDAD", False),

    # 2. Moxibustión (2 tipos)
    ("INS-MOX-HUMO", "Moxa c/humo", "MOXA", "UNIDAD", False),
    ("INS-MOX-SHUMO", "Moxa s/humo", "MOXA", "UNIDAD", False),

    # 3. Auriculoterapia & Microdosis (3 tipos)
    ("INS-AUR-SEM", "Semillas", "AURICULO", "SOBRE", False),
    ("INS-AUR-CHI", "Chinchetas", "AURICULO", "SOBRE", False),
    ("INS-AUR-IMA", "Imanes", "AURICULO", "SOBRE", False),

    # 4. Descartables & Bioseguridad (5 tipos)
    ("INS-CLI-HIPO", "Agujas hipodérmicas", "DESCARTABLE", "UNIDAD", False),
    ("INS-CLI-LANC", "Lancetas", "DESCARTABLE", "UNIDAD", False),
    ("INS-CLI-SABA", "Sabanilla", "DESCARTABLE", "PLIEGO", False),
    ("INS-CLI-GUAN", "Guantes", "DESCARTABLE", "PAR", False),
    ("INS-CLI-VENT", "Ventosas plásticas", "DESCARTABLE", "SET", False),

    # 5. Equipamiento de Box Retornable (3 tipos)
    ("INS-EQU-ELEC", "Electro", "EQUIPAMIENTO", "EQUIPO", True),
    ("INS-EQU-ENCE", "Encendedor", "EQUIPAMIENTO", "UNIDAD", True),
    ("INS-EQU-PARL", "Parlante + cable", "EQUIPAMIENTO", "SET", True),
]


DEFAULT_INITIAL_STOCK = {
    "Agujas 25 x 25": 1400,
    "Agujas 25 x 30": 1800,
    "Agujas 25 x 40": 3500,
    "Agujas 30 x 30": 1100,
    "Agujas 30 x 40": 2600,
    "Agujas 16 x 13": 850,
    "Agujas 18 x 13": 2200,
    "Agujas 20 x 13": 1950,
    "Agujas 22 x 40": 2400,
    "Agujas 18 x 25": 1300,
    "Agujas 25 x 75": 750,
    "Agujas 30 x 75": 2100,
    "Agujas 30 x 100": 600,
    "Agujas 35 x 125": 450,
    "Agujas hipodérmicas": 1200,
    "Moxa c/humo": 8,
    "Moxa s/humo": 25,
    "Semillas": 65,
    "Chinchetas": 75,
    "Imanes": 120,
    "Lancetas": 40,
    "Sabanilla": 4,
    "Guantes": 80,
    "Ventosas plásticas": 12,
    "Electro": 6,
    "Encendedor": 8,
    "Parlante + cable": 6,
}


class SupplyService:
    def __init__(self, db: Session):
        self.db = db

    def seed_official_supplies(self, company_id: str) -> List[ClinicalSupply]:
        """Inicializa los 27 insumos oficiales del inventario clínico de San Bao."""
        created = []
        for code, name, category, unit, is_returnable in OFFICIAL_SANBAO_SUPPLIES:
            existing = (
                self.db.query(ClinicalSupply)
                .filter(ClinicalSupply.company_id == company_id, ClinicalSupply.code == code, ClinicalSupply.deleted_at.is_(None))
                .first()
            )
            if not existing:
                item = ClinicalSupply(
                    company_id=company_id,
                    code=code,
                    name=name,
                    category=category,
                    unit=unit,
                    is_returnable=is_returnable,
                    stock_minimum=2000 if category == "AGUJAS" or "aguja" in name.lower() else (5 if "sabanilla" in name.lower() else (10 if "moxa" in name.lower() else (100 if any(k in name.lower() for k in ["guante", "semilla", "iman", "chincheta"]) else (50 if "lanceta" in name.lower() else 5)))),
                    current_stock=DEFAULT_INITIAL_STOCK.get(name, 100),
                    is_active=True,
                )
                self.db.add(item)
                created.append(item)
        if created:
            self.db.commit()
            for c in created:
                self.db.refresh(c)
        return self.list_supplies(company_id)

    def list_supplies(self, company_id: str, category: Optional[str] = None) -> List[ClinicalSupply]:
        q = self.db.query(ClinicalSupply).filter(
            ClinicalSupply.company_id == company_id,
            ClinicalSupply.deleted_at.is_(None),
            ClinicalSupply.is_active == True,
        )
        if category:
            q = q.filter(ClinicalSupply.category == category.upper())
        return q.order_by(ClinicalSupply.category, ClinicalSupply.name).all()

    def create_shift_dispatch(
        self,
        data: ShiftSupplyDispatchCreate,
        dispatcher_user_id: str,
        company_id: str,
    ) -> ShiftSupplyDispatch:
        """Registra la entrega de insumos por la Secretaria Clínica al Terapeuta para su turno."""
        practitioner = (
            self.db.query(Practitioner)
            .filter(Practitioner.id == data.practitioner_id, Practitioner.deleted_at.is_(None))
            .first()
        )
        if not practitioner:
            raise EntityNotFoundException("Terapeuta", data.practitioner_id)

        shift_date = data.shift_date or date.today()
        date_str = shift_date.strftime("%Y%m%d")
        count = self.db.query(ShiftSupplyDispatch).filter(
            ShiftSupplyDispatch.company_id == company_id,
            ShiftSupplyDispatch.shift_date == shift_date,
        ).count()
        dispatch_code = f"ENT-{date_str}-{count + 1:04d}"

        dispatch = ShiftSupplyDispatch(
            company_id=company_id,
            campus_id=data.campus_id,
            practitioner_id=data.practitioner_id,
            dispatcher_user_id=dispatcher_user_id,
            room_id=data.room_id,
            dispatch_code=dispatch_code,
            shift_date=shift_date,
            shift_type=data.shift_type,
            status="DISPATCHED",
            delivered_at=datetime.utcnow(),
            notes=data.notes,
        )
        self.db.add(dispatch)
        self.db.flush()

        # Registrar los items entregados
        for item_data in data.items:
            supply = self.db.query(ClinicalSupply).filter(
                ClinicalSupply.id == item_data.supply_id,
                ClinicalSupply.deleted_at.is_(None),
            ).first()
            if not supply:
                raise EntityNotFoundException("Insumo Clínico", item_data.supply_id)

            item = ShiftSupplyItem(
                dispatch_id=dispatch.id,
                supply_id=supply.id,
                quantity_delivered=item_data.quantity_delivered,
                quantity_used=0,
                quantity_returned=0,
                condition_notes=item_data.condition_notes,
            )
            self.db.add(item)

        self.db.commit()
        self.db.refresh(dispatch)
        return dispatch

    def record_shift_return(
        self,
        dispatch_id: str,
        data: ShiftSupplyReturnUpdate,
        verifier_user_id: str,
    ) -> ShiftSupplyDispatch:
        """Registra la devolución de insumos y equipos al finalizar el turno."""
        dispatch = (
            self.db.query(ShiftSupplyDispatch)
            .filter(ShiftSupplyDispatch.id == dispatch_id, ShiftSupplyDispatch.deleted_at.is_(None))
            .first()
        )
        if not dispatch:
            raise EntityNotFoundException("Despacho de Turno", dispatch_id)

        for ret in data.items:
            item = (
                self.db.query(ShiftSupplyItem)
                .filter(ShiftSupplyItem.id == ret.item_id, ShiftSupplyItem.dispatch_id == dispatch.id)
                .first()
            )
            if item:
                item.quantity_used = ret.quantity_used
                item.quantity_returned = ret.quantity_returned
                if ret.condition_notes:
                    item.condition_notes = ret.condition_notes

        dispatch.status = "RETURNED"
        dispatch.returned_at = datetime.utcnow()
        dispatch.return_verified_by_user_id = verifier_user_id
        if data.notes:
            dispatch.notes = f"{dispatch.notes or ''} | Retorno: {data.notes}".strip()

        self.db.commit()
        self.db.refresh(dispatch)
        return dispatch

    def list_shift_dispatches(
        self,
        company_id: str,
        campus_id: Optional[str] = None,
        shift_date: Optional[date] = None,
        practitioner_id: Optional[str] = None,
    ) -> List[ShiftSupplyDispatch]:
        q = self.db.query(ShiftSupplyDispatch).filter(
            ShiftSupplyDispatch.company_id == company_id,
            ShiftSupplyDispatch.deleted_at.is_(None),
        )
        if campus_id:
            q = q.filter(ShiftSupplyDispatch.campus_id == campus_id)
        if shift_date:
            q = q.filter(ShiftSupplyDispatch.shift_date == shift_date)
        if practitioner_id:
            q = q.filter(ShiftSupplyDispatch.practitioner_id == practitioner_id)

        return q.order_by(ShiftSupplyDispatch.delivered_at.desc()).all()
