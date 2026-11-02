from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta, timezone
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import extract
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_password_hash, decode_token
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.user import User
from app.modules.institutional.models.person import Person
from app.modules.institutional.models.campus import Campus, Room
from app.modules.clinical.models.patient import Patient
from app.modules.clinical.models.practitioner import Practitioner
from app.modules.clinical.models.supply import ClinicalSupply, SupplyRestockRecord, ShiftSupplyDispatch, ShiftSupplyItem
from app.modules.clinical.models.management import (
    ClinicalSessionPrice,
    ClinicalShiftSchedule,
    ClinicalSecretaryAssignment,
    PatientTreatmentPack,
    ClinicalPaymentRequest,
    ClinicalOverbookingRequest,
    ClinicalShiftClosureAffectedPatient,
)
from app.modules.finance.models.commitment import (
    FinancePayable,
    FinanceTreasuryMovement,
    FinanceJournalEntry,
)
from app.modules.academic.models.student import Student, Enrollment
from app.modules.clinical.services.supply_service import SupplyService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/clinical/management", tags=["Clínica: Dirección Clínica y Gestión Asistencial"])


# -----------------------------------------------------------------------------
# Esquemas Pydantic
# -----------------------------------------------------------------------------
class AssignInternRequest(BaseModel):
    student_id: str
    notes: Optional[str] = None


class TutorCreate(BaseModel):
    first_name: str
    last_name: str
    rut: str
    specialty: str = "Acupuntura y Medicina Tradicional China"
    license_number: str
    campus_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class TutorToggleBlockRequest(BaseModel):
    replacement_practitioner_id: Optional[str] = None
    reason: Optional[str] = None


class SessionPriceCreate(BaseModel):
    name: str = Field(..., min_length=3)
    code: Optional[str] = None
    category: str = "GENERAL"  # GENERAL, DOCENTE, INTEGRAL, CONVENIO, PACK
    service_type: str = "ACUPUNTURA"  # ACUPUNTURA, TUI_NA, INTEGRAL
    session_count: int = Field(default=1, ge=1, description="Cantidad de sesiones incluidas: 1 para individual, de 1 a X para packs")
    duration_minutes: int = Field(default=60, ge=15)
    price_clp: Decimal = Field(..., ge=0)
    description: Optional[str] = None
    is_active: bool = True


class SessionPriceUpdate(BaseModel):
    price_clp: Decimal = Field(..., ge=0)
    duration_minutes: Optional[int] = Field(None, ge=15)
    session_count: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class PatientPackCreateRequest(BaseModel):
    session_price_id: str
    custom_total_sessions: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None


class PatientPackDiscountRequest(BaseModel):
    sessions_to_discount: int = Field(default=1, ge=1)
    appointment_id: Optional[str] = None
    notes: Optional[str] = None


class ShiftScheduleCreate(BaseModel):
    campus_id: str
    room_id: Optional[str] = None
    practitioner_id: Optional[str] = None
    substitute_practitioner_id: Optional[str] = None
    substitute_active: bool = False
    service_type: str = "ACUPUNTURA"  # "ACUPUNTURA", "TUI_NA"
    shift_period: str = "AM"  # "AM", "PM", "VESPERTINO"
    day_schedule: Optional[str] = None
    shift_name: Optional[str] = None
    shift_date: date
    start_time: str = "10:00"
    end_time: str = "14:00"
    notes: Optional[str] = None


class ShiftAssignUpdate(BaseModel):
    practitioner_id: str
    substitute_practitioner_id: Optional[str] = None
    substitute_active: Optional[bool] = None
    notes: Optional[str] = None


class ShiftCloseRequest(BaseModel):
    closure_type: Optional[str] = "SINGLE_DATE"  # DAY, SINGLE_DATE, WEEK, MONTH, INDEFINITE, DATE_RANGE, SPECIFIC_DATES, PERMANENT
    closure_scope: Optional[str] = None  # DAY, WEEK, MONTH, INDEFINITE
    closure_start_date: Optional[date] = None
    closure_end_date: Optional[date] = None
    closure_dates_text: Optional[str] = None
    closure_reason: Optional[str] = "Cierre programado por Dirección Clínica"
    notes: Optional[str] = None
    affected_patients: Optional[List[Dict[str, Any]]] = None


class DayShiftAssignRequest(BaseModel):
    campus_id: str
    service_type: str = "ACUPUNTURA"  # ACUPUNTURA, TUI_NA
    shift_period: str = "AM"  # AM, PM, VESPERTINO
    shift_date: date
    practitioner_id: str
    substitute_practitioner_id: Optional[str] = None
    substitute_active: bool = False
    room_id: Optional[str] = None
    scope: Optional[str] = "SINGLE_DAY"  # "SINGLE_DAY", "RECURRING_WEEKDAY", "ALL_MONTH"
    status: Optional[str] = "OPEN"
    notes: Optional[str] = None


class MonthCalendarSeedRequest(BaseModel):
    year: int = 2026
    month: int = 11
    campus_id: Optional[str] = None


class SecretaryCampusAssignRequest(BaseModel):
    campus_id: Optional[str] = None
    campus_code: Optional[str] = None
    notes: Optional[str] = None


class SupplyRestockRequest(BaseModel):
    quantity: int = Field(..., gt=0, description="Cantidad a reponer (mayor a 0)")
    restock_date: date = Field(default_factory=date.today, description="Fecha de reposición o ingreso a bodega")
    invoice_or_batch_number: Optional[str] = Field(None, description="N° de factura, guía de despacho o lote")
    notes: Optional[str] = Field(None, description="Observaciones o notas de la reposición")


class SupplyMovementRequest(BaseModel):
    movement_type: str = Field(default="AGREGAR", description="AGREGAR (Ingreso/Entrada) o SACAR (Egreso/Salida)")
    quantity: int = Field(..., gt=0, description="Cantidad a mover (mayor a 0)")
    movement_date: date = Field(default_factory=date.today, description="Fecha de movimiento")
    reason: Optional[str] = Field(None, description="Motivo: REPOSICION, COMPRA, MERMA, VENCIMIENTO, TRASLADO, AJUSTE, USO_CLINICO")
    invoice_or_batch_number: Optional[str] = Field(None, description="N° de factura, guía o lote")
    notes: Optional[str] = Field(None, description="Observaciones o notas")


class SupplyWithdrawRequest(BaseModel):
    quantity: int = Field(..., gt=0, description="Cantidad a retirar o sacar de stock")
    movement_date: date = Field(default_factory=date.today, description="Fecha de salida")
    reason: Optional[str] = Field("MERMA", description="Motivo: MERMA, VENCIMIENTO, USO_CLINICO, TRASLADO, AJUSTE_INVENTARIO")
    invoice_or_batch_number: Optional[str] = Field(None, description="N° de comprobante o guía de baja")
    notes: Optional[str] = Field(None, description="Observaciones o notas")


class SupplyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, description="Nombre descriptivo del insumo clínico")
    category: str = Field(default="DESCARTABLE", description="AGUJAS, MOXA, AURICULO, DESCARTABLE, EQUIPAMIENTO")
    unit: str = Field(default="UNIDAD", description="UNIDAD, PLIEGO, PURO, SOBRE, PAR, SET, EQUIPO")
    code: Optional[str] = Field(None, description="Código institucional (autogenerado si se omite)")
    initial_stock: int = Field(default=0, ge=0, description="Stock inicial disponible en bodega")
    stock_minimum: Optional[int] = Field(None, ge=0, description="Umbral de bajo stock (autocalculado si se omite)")
    is_returnable: bool = Field(default=False, description="True si es equipo retornable de box")


def get_active_company_and_user_flexible(
    authorization: Optional[str] = Header(None),
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    db: Session = Depends(get_db),
):
    """
    Permite autenticación por token JWT estándar (usado en tests y APIs seguras)
    o fallback automático al usuario director y sociedad clínica San Bao cuando se accede desde la UI web.
    """
    active_company = None
    current_user = None

    if authorization and authorization.startswith("Bearer "):
        try:
            token = authorization.split(" ")[1]
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                current_user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        except Exception:
            pass

    if not current_user:
        current_user = db.query(User).filter(User.username == "director").first()
        if not current_user:
            current_user = db.query(User).first()

    if x_company_id and x_company_id != "clinica":
        active_company = db.query(Company).filter(Company.id == x_company_id).first()

    if not active_company:
        active_company = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first()
        if not active_company:
            active_company = db.query(Company).first()

    return active_company, current_user



def ensure_sample_tutors(db: Session):
    """Garantiza la existencia de los tutores clínicos acreditados de San Bao."""
    sample_tutors = [
        ("14.201.345-6", "Marcela", "Pérez Morales", "Acupuntura Clásica y Ginecología MTC", "SIS-14201", True),
        ("18.944.512-3", "Chen", "Lin", "Fitoterapia China y Craneopuntura YNSA", "SIS-18944", True),
        ("12.876.543-1", "Roberto", "Gómez Valdés", "Acupuntura Tung y Traumatología", "SIS-20112", True),
        ("15.432.876-K", "Patricia", "Soto Henríquez", "Auriculopuntura y Salud Mental MTC", "SIS-22409", True),
        ("13.987.654-2", "Gabriel", "Morales Ruiz", "Medicina China y Pulsología Clásica", "SIS-15880", False),  # Bloqueado / Suspendido
    ]
    for rut, fn, ln, spec, lic, act in sample_tutors:
        pr = db.query(Practitioner).filter(Practitioner.license_number == lic).first()
        if not pr:
            clean_rut = rut.replace(".", "").replace("-", "")
            p = db.query(Person).filter(Person.rut == clean_rut).first()
            if not p:
                p = Person(
                    rut=clean_rut,
                    first_name=fn,
                    last_name=ln,
                    email=f"{fn.lower()}.{ln.lower().split()[0]}@sanbao.cl",
                    is_active=True,
                )
                db.add(p)
                db.commit()
                db.refresh(p)
            pr = Practitioner(
                person_id=p.id,
                specialty=spec,
                license_number=lic,
                is_tutor=True,
                is_active=act,
            )
            db.add(pr)
            db.commit()


def ensure_sample_shifts(db: Session, company_id: str):
    """Garantiza la existencia de turnos clínicos oficiales de Acupuntura y Tui na designados por Dirección Clínica."""
    shifts = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.company_id == company_id,
        ClinicalShiftSchedule.deleted_at.is_(None)
    ).all()
    if shifts and any(s.service_type == "TUI_NA" for s in shifts):
        return shifts

    # Si hay turnos antiguos sin Tui na, eliminarlos limpiamente para refrescar la programación oficial
    if shifts:
        for old_s in shifts:
            db.delete(old_s)
        db.commit()

    ensure_sample_tutors(db)
    santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    tutors = db.query(Practitioner).filter(Practitioner.is_tutor == True).all()
    tutor_map = {t.license_number: t.id for t in tutors}

    today = date.today()

    # Programación oficial Dirección Clínica San Bao SpA:
    # Acupuntura & Tui na:
    # AM: Lunes a Sábado 10:00 a 14:00
    # PM: Lunes a Sábado 15:00 a 19:00
    # Vespertino: Lunes a Viernes 18:00 a 22:00
    official_shifts = [
        # --- SEDE SANTIAGO: ACUPUNTURA ---
        ("TUR-ACU-STGO-AM", "Acupuntura • Turno AM (10:00 - 14:00)", "ACUPUNTURA", "AM", "LUNES_A_SABADO", santiago.id if santiago else None, "BOX-01", tutor_map.get("SIS-14201"), "10:00", "14:00", "OPEN", "Turno oficial matutino Acupuntura y Ginecología MTC"),
        ("TUR-ACU-STGO-PM", "Acupuntura • Turno PM (15:00 - 19:00)", "ACUPUNTURA", "PM", "LUNES_A_SABADO", santiago.id if santiago else None, "BOX-02", tutor_map.get("SIS-18944"), "15:00", "19:00", "OPEN", "Turno oficial vespertino Fitoterapia y Craneopuntura YNSA"),
        ("TUR-ACU-STGO-VESP", "Acupuntura • Turno Vespertino (18:00 - 22:00)", "ACUPUNTURA", "VESPERTINO", "LUNES_A_VIERNES", santiago.id if santiago else None, "BOX-01", tutor_map.get("SIS-20112"), "18:00", "22:00", "OPEN", "Atención nocturna Acupuntura Tung y Traumatología"),

        # --- SEDE SANTIAGO: TUI NA ---
        ("TUR-TUI-STGO-AM", "Tui na • Turno AM (10:00 - 14:00)", "TUI_NA", "AM", "LUNES_A_SABADO", santiago.id if santiago else None, "BOX-PRACTICA", tutor_map.get("SIS-22409"), "10:00", "14:00", "OPEN", "Masaje Terapéutico Tui na y Digitopuntura Matutina"),
        ("TUR-TUI-STGO-PM", "Tui na • Turno PM (15:00 - 19:00)", "TUI_NA", "PM", "LUNES_A_SABADO", santiago.id if santiago else None, "BOX-PRACTICA", tutor_map.get("SIS-14201"), "15:00", "19:00", "OPEN", "Tui na y Manipulaciones Miofasciales Tradicionales"),
        ("TUR-TUI-STGO-VESP", "Tui na • Turno Vespertino (18:00 - 22:00)", "TUI_NA", "VESPERTINO", "LUNES_A_VIERNES", santiago.id if santiago else None, "BOX-02", tutor_map.get("SIS-18944"), "18:00", "22:00", "OPEN", "Tui na nocturno para rehabilitación neuromuscular"),

        # --- SEDE VIÑA DEL MAR: ACUPUNTURA ---
        ("TUR-ACU-VINA-AM", "Acupuntura • Turno AM (10:00 - 14:00)", "ACUPUNTURA", "AM", "LUNES_A_SABADO", vina.id if vina else None, "BOX-VINA-01", tutor_map.get("SIS-20112"), "10:00", "14:00", "OPEN", "Acupuntura Tung y Alivio del Dolor Viña del Mar"),
        ("TUR-ACU-VINA-PM", "Acupuntura • Turno PM (15:00 - 19:00)", "ACUPUNTURA", "PM", "LUNES_A_SABADO", vina.id if vina else None, "BOX-VINA-02", tutor_map.get("SIS-22409"), "15:00", "19:00", "OPEN", "Acupuntura y Auriculoterapia Viña del Mar"),
        ("TUR-ACU-VINA-VESP", "Acupuntura • Turno Vespertino (18:00 - 22:00)", "ACUPUNTURA", "VESPERTINO", "LUNES_A_VIERNES", vina.id if vina else None, "BOX-VINA-01", tutor_map.get("SIS-20112"), "18:00", "22:00", "OPEN", "Atención nocturna Acupuntura Costa"),

        # --- SEDE VIÑA DEL MAR: TUI NA ---
        ("TUR-TUI-VINA-AM", "Tui na • Turno AM (10:00 - 14:00)", "TUI_NA", "AM", "LUNES_A_SABADO", vina.id if vina else None, "BOX-VINA-03", tutor_map.get("SIS-22409"), "10:00", "14:00", "OPEN", "Masaje Tui na Ortopédico y Pediátrico Viña"),
        ("TUR-TUI-VINA-PM", "Tui na • Turno PM (15:00 - 19:00)", "TUI_NA", "PM", "LUNES_A_SABADO", vina.id if vina else None, "BOX-VINA-03", tutor_map.get("SIS-20112"), "15:00", "19:00", "OPEN", "Tui na profundo y Ventosas Tradicionales"),
        ("TUR-TUI-VINA-VESP", "Tui na • Turno Vespertino (18:00 - 22:00)", "TUI_NA", "VESPERTINO", "LUNES_A_VIERNES", vina.id if vina else None, "BOX-VINA-02", tutor_map.get("SIS-22409"), "18:00", "22:00", "OPEN", "Tui na vespertino para trabajadores y estudiantes"),
    ]

    created = []
    for code, name, stype, sper, dsched, cid, room_code, pid, st, et, stat, notes in official_shifts:
        if not cid:
            continue
        room = db.query(Room).filter(Room.code == room_code).first()
        item = ClinicalShiftSchedule(
            company_id=company_id,
            campus_id=cid,
            room_id=room.id if room else None,
            practitioner_id=pid,
            shift_code=code,
            shift_name=name,
            service_type=stype,
            shift_period=sper,
            day_schedule=dsched,
            shift_date=today,
            start_time=st,
            end_time=et,
            status=stat,
            notes=notes,
        )
        db.add(item)
        created.append(item)
    db.commit()
    return created


def seed_monthly_calendar_shifts(db: Session, company_id: str, year: int, month: int):
    """Genera la programación oficial de turnos para cada día del mes calendario especificado."""
    import calendar
    _, num_days = calendar.monthrange(year, month)

    ensure_sample_tutors(db)
    santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    tutors = db.query(Practitioner).filter(Practitioner.is_tutor == True).all()
    tutor_map = {t.license_number: t.id for t in tutors}

    # Plantilla de turnos oficiales por sede y franja
    patterns = [
        ("ACU", "ACUPUNTURA", "AM", "LUNES_A_SABADO", santiago, "BOX-01", "SIS-14201", "10:00", "14:00", "Acupuntura • Turno AM (10:00 - 14:00)"),
        ("ACU", "ACUPUNTURA", "PM", "LUNES_A_SABADO", santiago, "BOX-02", "SIS-18944", "15:00", "19:00", "Acupuntura • Turno PM (15:00 - 19:00)"),
        ("ACU", "ACUPUNTURA", "VESPERTINO", "LUNES_A_VIERNES", santiago, "BOX-01", "SIS-20112", "18:00", "22:00", "Acupuntura • Turno Vespertino (18:00 - 22:00)"),
        
        ("TUI", "TUI_NA", "AM", "LUNES_A_SABADO", santiago, "BOX-PRACTICA", "SIS-22409", "10:00", "14:00", "Tui na • Turno AM (10:00 - 14:00)"),
        ("TUI", "TUI_NA", "PM", "LUNES_A_SABADO", santiago, "BOX-PRACTICA", "SIS-14201", "15:00", "19:00", "Tui na • Turno PM (15:00 - 19:00)"),
        ("TUI", "TUI_NA", "VESPERTINO", "LUNES_A_VIERNES", santiago, "BOX-02", "SIS-18944", "18:00", "22:00", "Tui na • Turno Vespertino (18:00 - 22:00)"),

        ("ACU", "ACUPUNTURA", "AM", "LUNES_A_SABADO", vina, "BOX-VINA-01", "SIS-20112", "10:00", "14:00", "Acupuntura • Turno AM (10:00 - 14:00)"),
        ("ACU", "ACUPUNTURA", "PM", "LUNES_A_SABADO", vina, "BOX-VINA-02", "SIS-22409", "15:00", "19:00", "Acupuntura • Turno PM (15:00 - 19:00)"),
        ("ACU", "ACUPUNTURA", "VESPERTINO", "LUNES_A_VIERNES", vina, "BOX-VINA-01", "SIS-20112", "18:00", "22:00", "Acupuntura • Turno Vespertino (18:00 - 22:00)"),

        ("TUI", "TUI_NA", "AM", "LUNES_A_SABADO", vina, "BOX-VINA-03", "SIS-22409", "10:00", "14:00", "Tui na • Turno AM (10:00 - 14:00)"),
        ("TUI", "TUI_NA", "PM", "LUNES_A_SABADO", vina, "BOX-VINA-03", "SIS-20112", "15:00", "19:00", "Tui na • Turno PM (15:00 - 19:00)"),
        ("TUI", "TUI_NA", "VESPERTINO", "LUNES_A_VIERNES", vina, "BOX-VINA-02", "SIS-22409", "18:00", "22:00", "Tui na • Turno Vespertino (18:00 - 22:00)"),
    ]

    created = []
    for d in range(1, num_days + 1):
        dt = date(year, month, d)
        wday = dt.weekday()  # 0=Lunes, 5=Sábado, 6=Domingo
        if wday == 6:
            continue  # Domingo clínica cerrada

        for prefix, stype, sper, dsched, camp, room_code, tutor_lic, st, et, sname in patterns:
            if not camp:
                continue
            if sper == "VESPERTINO" and wday >= 5:
                continue  # Vespertino opera de Lunes a Viernes

            camp_code = "STGO" if "CENTRAL" in camp.code else "VINA"
            room = db.query(Room).filter(Room.code == room_code).first()

            # Configuración de tutor suplente institucional (activo de respaldo)
            sub_id = None
            sub_act = False
            if sper == "VESPERTINO" and tutor_lic != "SIS-18944":
                sub_id = tutor_map.get("SIS-18944")
                sub_act = True
            elif wday == 5 and tutor_lic != "SIS-20112":
                sub_id = tutor_map.get("SIS-20112")
                sub_act = True

            item = ClinicalShiftSchedule(
                company_id=company_id,
                campus_id=camp.id,
                room_id=room.id if room else None,
                practitioner_id=tutor_map.get(tutor_lic),
                substitute_practitioner_id=sub_id,
                substitute_active=sub_act,
                shift_code=f"TUR-{prefix}-{camp_code}-{sper}-{dt.strftime('%Y%m%d')}",
                shift_name=sname,
                service_type=stype,
                shift_period=sper,
                day_schedule=dsched,
                shift_date=dt,
                start_time=st,
                end_time=et,
                status="OPEN",
                notes=f"Turno mensual oficial {calendar.month_name[month]} {year}",
            )
            db.add(item)
            created.append(item)

    db.commit()
    return created


def ensure_sample_secretaries(db: Session, company_id: str):
    """Garantiza la existencia de secretarias clínicas y sus asignaciones oficiales a sedes."""
    santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    if not santiago or not vina:
        return

    sec_specs = [
        ("secretaria", "16234567-2", "Valentina", "Morales", "secretaria@sanbao.cl", santiago.id, "Secretaria Titular Sede Santiago Providencia"),
        ("secretaria_vina", "17890123-0", "Sofía", "Lagos", "secretaria.vina@sanbao.cl", vina.id, "Secretaria Titular Sede Viña del Mar Av. Libertad"),
    ]

    for uname, rut, fn, ln, email, campus_id, notes in sec_specs:
        u = db.query(User).filter(User.username == uname).first()
        if not u:
            clean_rut = rut.replace(".", "").replace("-", "")
            p = db.query(Person).filter(Person.rut == clean_rut).first()
            if not p:
                p = Person(
                    rut=clean_rut,
                    first_name=fn,
                    last_name=ln,
                    email=email,
                    is_active=True,
                )
                db.add(p)
                db.commit()
                db.refresh(p)
            u = User(
                person_id=p.id,
                username=uname,
                password_hash=get_password_hash("SecretariaSanBao2026!"),
                is_active=True,
                is_superuser=False,
            )
            db.add(u)
            db.commit()
            db.refresh(u)

        assign = db.query(ClinicalSecretaryAssignment).filter(
            ClinicalSecretaryAssignment.company_id == company_id,
            ClinicalSecretaryAssignment.user_id == u.id,
            ClinicalSecretaryAssignment.deleted_at.is_(None),
        ).first()

        if not assign:
            assign = ClinicalSecretaryAssignment(
                company_id=company_id,
                user_id=u.id,
                campus_id=campus_id,
                is_primary=True,
                status="ACTIVE",
                notes=notes,
            )
            db.add(assign)
    db.commit()



# -----------------------------------------------------------------------------
# 1. Administración y Bloqueo de Tutores Clínicos
# -----------------------------------------------------------------------------
@router.get("/tutors", summary="Listar tutores clínicos con estado activo/bloqueado")
def list_clinical_tutors(
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista todos los tutores clínicos acreditados de la Escuela y Servicios Clínicos San Bao."""
    ensure_sample_tutors(db)
    tutors = db.query(Practitioner).filter(Practitioner.is_tutor == True, Practitioner.deleted_at.is_(None)).all()

    result = []
    for t in tutors:
        person = db.query(Person).filter(Person.id == t.person_id).first()
        result.append({
            "id": t.id,
            "person_id": t.person_id,
            "full_name": f"{person.first_name} {person.last_name}" if person else "N/A",
            "rut": person.rut if person else "N/A",
            "email": person.email if person else "N/A",
            "license_number": t.license_number,
            "specialty": t.specialty,
            "is_tutor": t.is_tutor,
            "is_active": t.is_active,
            "status_label": "HABILITADO" if t.is_active else "BLOQUEADO / SUSPENDIDO",
        })
    return APIResponse(data=result)


@router.post("/tutors", status_code=status.HTTP_201_CREATED, summary="Dirección Clínica crea y acredita un nuevo tutor")
def create_clinical_tutor(
    payload: TutorCreate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clean_rut = payload.rut.replace(".", "").replace("-", "").strip()
    person = db.query(Person).filter(Person.rut == clean_rut).first()
    if not person:
        person = Person(
            rut=clean_rut,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email or f"{payload.first_name.lower()}.{payload.last_name.lower()}@sanbao.cl",
            phone=payload.phone,
            is_active=True,
        )
        db.add(person)
        db.commit()
        db.refresh(person)

    practitioner = db.query(Practitioner).filter(Practitioner.person_id == person.id).first()
    if practitioner:
        practitioner.is_tutor = True
        practitioner.is_active = True
        practitioner.specialty = payload.specialty
        practitioner.license_number = payload.license_number
    else:
        practitioner = Practitioner(
            person_id=person.id,
            specialty=payload.specialty,
            license_number=payload.license_number,
            is_tutor=True,
            is_active=True,
        )
        db.add(practitioner)

    db.commit()
    db.refresh(practitioner)
    return APIResponse(message=f"Tutor clínico {payload.first_name} {payload.last_name} acreditado exitosamente", data={"id": practitioner.id, "is_tutor": True, "is_active": True})


@router.get("/tutors/{practitioner_id}/active-shifts", summary="Consultar turnos activos asignados a un tutor clínico")
def get_tutor_active_shifts(
    practitioner_id: str,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    practitioner = db.query(Practitioner).filter(
        (Practitioner.id == practitioner_id) | (Practitioner.license_number == practitioner_id)
    ).first()
    if not practitioner:
        raise HTTPException(status_code=404, detail="Tutor clínico no encontrado")

    active_shifts = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.company_id == active_company.id,
        ClinicalShiftSchedule.practitioner_id == practitioner.id,
        ClinicalShiftSchedule.status != "CLOSED",
        ClinicalShiftSchedule.deleted_at.is_(None),
        ClinicalShiftSchedule.shift_date >= date.today(),
    ).order_by(ClinicalShiftSchedule.shift_date.asc()).all()

    person = db.query(Person).filter(Person.id == practitioner.person_id).first()
    tutor_name = f"{person.first_name} {person.last_name}" if person else practitioner.id

    shifts_list = []
    for s in active_shifts:
        campus = db.query(Campus).filter(Campus.id == s.campus_id).first()
        shifts_list.append({
            "id": s.id,
            "shift_code": s.shift_code,
            "shift_name": s.shift_name,
            "service_type": s.service_type,
            "shift_period": s.shift_period,
            "shift_date": str(s.shift_date),
            "start_time": s.start_time,
            "end_time": s.end_time,
            "campus_name": campus.name if campus else "Sede",
        })

    return APIResponse(
        data={
            "practitioner_id": practitioner.id,
            "license_number": practitioner.license_number,
            "practitioner_name": tutor_name,
            "has_active_shifts": len(active_shifts) > 0,
            "active_shifts_count": len(active_shifts),
            "shifts": shifts_list,
        }
    )


@router.put("/tutors/{practitioner_id}/toggle-block", summary="Bloquear o desbloquear tutor clínico")
def toggle_tutor_block(
    practitioner_id: str,
    payload: Optional[TutorToggleBlockRequest] = None,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    practitioner = db.query(Practitioner).filter(
        (Practitioner.id == practitioner_id) | (Practitioner.license_number == practitioner_id)
    ).first()
    if not practitioner:
        raise HTTPException(status_code=404, detail="Tutor clínico no encontrado")

    reassigned_count = 0
    replacement_name = None

    if practitioner.is_active:
        # Acción: Bloquear tutor.
        # Verificar si tiene turnos activos
        active_shifts = db.query(ClinicalShiftSchedule).filter(
            ClinicalShiftSchedule.company_id == active_company.id,
            ClinicalShiftSchedule.practitioner_id == practitioner.id,
            ClinicalShiftSchedule.status != "CLOSED",
            ClinicalShiftSchedule.deleted_at.is_(None),
            ClinicalShiftSchedule.shift_date >= date.today(),
        ).all()

        if active_shifts:
            replacement_id = payload.replacement_practitioner_id if payload else None
            if not replacement_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"El tutor cuenta con {len(active_shifts)} turno(s) activo(s). Es obligatorio seleccionar un tutor clínico activo de la lista para reemplazar su atención antes de bloquear."
                )

            replacement = db.query(Practitioner).filter(
                (Practitioner.id == replacement_id) | (Practitioner.license_number == replacement_id)
            ).first()
            if not replacement or not replacement.is_tutor:
                raise HTTPException(status_code=404, detail="Tutor de reemplazo no encontrado en el listado acreditado")
            if not replacement.is_active:
                raise HTTPException(status_code=400, detail="El tutor de reemplazo seleccionado se encuentra bloqueado o inactivo")
            if replacement.id == practitioner.id:
                raise HTTPException(status_code=400, detail="El tutor de reemplazo no puede ser el mismo tutor que se va a bloquear")

            rep_person = db.query(Person).filter(Person.id == replacement.person_id).first()
            replacement_name = f"{rep_person.first_name} {rep_person.last_name}" if rep_person else replacement.id

            for s in active_shifts:
                s.practitioner_id = replacement.id
                s.notes = (s.notes or "") + f" [Reasignado por bloqueo institucional a {replacement_name}]"
            reassigned_count = len(active_shifts)

        practitioner.is_active = False
        action_msg = f"Tutor clínico bloqueado / suspendido exitosamente."
        if reassigned_count > 0:
            action_msg += f" Se reasignaron {reassigned_count} turno(s) activo(s) al tutor {replacement_name}."
    else:
        # Acción: Desbloquear tutor
        practitioner.is_active = True
        action_msg = "Tutor clínico desbloqueado y habilitado exitosamente"

    db.commit()
    db.refresh(practitioner)

    return APIResponse(
        message=action_msg,
        data={
            "id": practitioner.id,
            "is_active": practitioner.is_active,
            "reassigned_shifts_count": reassigned_count,
            "replacement_practitioner_name": replacement_name,
        }
    )


# -----------------------------------------------------------------------------
# 2. Aranceles, Valores de Sesiones Clínicas y Packs de Tratamiento (1 a X Sesiones)
# -----------------------------------------------------------------------------
def ensure_sample_session_prices_and_packs(db: Session, company_id: str):
    """Garantiza la existencia de aranceles oficiales y packs de tratamiento de 1 a X sesiones."""
    prices = db.query(ClinicalSessionPrice).filter(
        ClinicalSessionPrice.company_id == company_id,
        ClinicalSessionPrice.deleted_at.is_(None)
    ).all()

    official_items = [
        # (code, name, category, service_type, session_count, duration, price_clp, description)
        ("SES-ACU-GEN", "Sesión Acupuntura General (Adultos)", "GENERAL", "ACUPUNTURA", 1, 60, 35000, "Evaluación integral de 4 diagnósticos, diferenciación de síndromes e inserción de agujas."),
        ("SES-ACU-CTRL", "Sesión de Control y Seguimiento", "GENERAL", "ACUPUNTURA", 1, 45, 28000, "Control de evolución clínica, ajuste de prescripción de acupuntura y re-evaluación."),
        ("SES-DOC-SUP", "Atención Clínica Docente Supervisada", "DOCENTE", "ACUPUNTURA", 1, 60, 15000, "Atención efectuada por alumno en práctica avanzada con supervisión directa del Tutor Clínico."),
        ("SES-MTC-INT", "Tratamiento Integral Moxa + Ventosas + Electro", "INTEGRAL", "INTEGRAL", 1, 75, 42000, "Terapia combinada de alta complejidad para síndromes Bi, dolor crónico y tonificación profunda."),
        ("SES-AURI-FIT", "Auriculoterapia & Prescripción Herbal", "GENERAL", "ACUPUNTURA", 1, 30, 22000, "Colocación de semillas/chinchetas en pabellón auricular y prescripción de fitoterapia tradicional."),
        ("SES-CONV-EST", "Convenio Preferencial Alumnos y Docentes San Bao", "CONVENIO", "ACUPUNTURA", 1, 45, 18000, "Tarifa institucional exclusiva para estudiantes activos y cuerpo docente del Instituto."),
        # Packs de Tratamiento oficiales designados por Dirección Clínica
        ("PACK-ACU-04", "Pack 4 Sesiones Acupuntura Alivio del Dolor", "PACK", "ACUPUNTURA", 4, 60, 120000, "Pack intensivo de 4 sesiones de Acupuntura con seguimiento clínico y re-evaluación."),
        ("PACK-MTC-08", "Pack 8 Sesiones Tratamiento Integral MTC", "PACK", "INTEGRAL", 8, 75, 280000, "Pack completo de 8 sesiones combinadas de Acupuntura, Moxibustión y Ventosas tradicionales."),
        ("PACK-TUI-04", "Pack 4 Sesiones Masaje Terapéutico Tui Na", "PACK", "TUI_NA", 4, 60, 110000, "Pack de 4 sesiones especializadas de masaje Tui Na clínico y descompresión miofascial."),
    ]

    existing_codes = {p.code for p in prices if p.code}
    added = False
    for c, n, cat, stype, scount, d, p, desc in official_items:
        if c not in existing_codes:
            item = ClinicalSessionPrice(
                company_id=company_id,
                code=c,
                name=n,
                category=cat,
                service_type=stype,
                session_count=scount,
                duration_minutes=d,
                price_clp=Decimal(p),
                description=desc,
                is_active=True,
            )
            db.add(item)
            added = True
    if added:
        db.commit()


def _resolve_patient(db: Session, identifier: str) -> Optional[Patient]:
    """Busca paciente por ID o por RUT de la persona asociada."""
    if not identifier:
        return None
    p = db.query(Patient).filter(Patient.id == identifier, Patient.deleted_at.is_(None)).first()
    if p:
        return p
    clean_id = identifier.replace(".", "").replace("-", "").replace(" ", "").upper()
    for per in db.query(Person).all():
        if per.rut:
            per_clean = per.rut.replace(".", "").replace("-", "").replace(" ", "").upper()
            if per_clean == clean_id:
                p = db.query(Patient).filter(Patient.person_id == per.id, Patient.deleted_at.is_(None)).first()
                if p:
                    return p
    return None


def ensure_sample_patient_and_pack(db: Session, company_id: str, rut: str = "17.123.456-5") -> Patient:
    """Garantiza la existencia de un paciente de muestra (Rodrigo Silva) con un pack en seguimiento."""
    patient = _resolve_patient(db, rut)
    if not patient:
        clean_rut = rut.replace(".", "").replace("-", "").replace(" ", "").upper()
        person = None
        for per in db.query(Person).all():
            if per.rut and per.rut.replace(".", "").replace("-", "").replace(" ", "").upper() == clean_rut:
                person = per
                break
        if not person:
            person = Person(
                rut=rut,
                first_name="Rodrigo",
                last_name="Silva",
                email="rodrigo.silva@sanbao.cl",
                phone="+56 9 1234 5678",
                is_active=True,
            )
            db.add(person)
            db.commit()
            db.refresh(person)

        patient = Patient(
            person_id=person.id,
            record_number=f"FICH-2026-{clean_rut[-4:] if len(clean_rut) >= 4 else '0042'}",
            emergency_contact_name="María Silva",
            emergency_contact_phone="+56 9 8765 4321",
            is_active=True,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

    active_pack = db.query(PatientTreatmentPack).filter(
        PatientTreatmentPack.patient_id == patient.id,
        PatientTreatmentPack.status == "ACTIVE",
        PatientTreatmentPack.deleted_at.is_(None),
    ).first()

    if not active_pack:
        ensure_sample_session_prices_and_packs(db, company_id)
        pack_price = db.query(ClinicalSessionPrice).filter(
            ClinicalSessionPrice.code == "PACK-ACU-04",
            ClinicalSessionPrice.company_id == company_id,
        ).first()

        sample_pack = PatientTreatmentPack(
            company_id=company_id,
            patient_id=patient.id,
            session_price_id=pack_price.id if pack_price else None,
            pack_name="Pack 4 Sesiones Acupuntura Alivio del Dolor",
            service_type="ACUPUNTURA",
            total_sessions=4,
            used_sessions=3,
            remaining_sessions=1,  # Última sesión para alertar y ofrecer renovación
            price_paid_clp=Decimal(120000),
            status="ACTIVE",
            purchase_date=date.today(),
            notes="Pack inicial con 3 sesiones utilizadas y 1 sesión restante disponible.",
        )
        db.add(sample_pack)
        db.commit()

    return patient


@router.get("/session-prices", summary="Listar valores y aranceles de sesiones clínicas y packs")
def list_session_prices(
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    ensure_sample_session_prices_and_packs(db, active_company.id)
    prices = db.query(ClinicalSessionPrice).filter(
        ClinicalSessionPrice.company_id == active_company.id,
        ClinicalSessionPrice.deleted_at.is_(None)
    ).all()

    return APIResponse(data=[{
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "category": p.category,
        "service_type": p.service_type or "ACUPUNTURA",
        "session_count": p.session_count or 1,
        "duration_minutes": p.duration_minutes,
        "price_clp": float(p.price_clp),
        "unit_price_clp": float(p.price_clp / (p.session_count or 1)),
        "description": p.description,
        "is_active": p.is_active,
        "is_pack": (p.session_count or 1) > 1 or p.category == "PACK",
    } for p in prices])


@router.post("/session-prices", summary="Crear nuevo valor de sesión o pack de tratamiento (1 a X sesiones)")
def create_session_price(
    payload: SessionPriceCreate,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    code = payload.code
    if not code:
        prefix = "PACK" if payload.session_count > 1 or payload.category == "PACK" else "SES"
        svc = "ACU" if payload.service_type == "ACUPUNTURA" else ("TUI" if payload.service_type == "TUI_NA" else "MTC")
        import random
        rnd = random.randint(100, 999)
        code = f"{prefix}-{svc}-{payload.session_count:02d}-{rnd}"

    item = ClinicalSessionPrice(
        company_id=active_company.id,
        code=code,
        name=payload.name,
        category=payload.category,
        service_type=payload.service_type,
        session_count=payload.session_count,
        duration_minutes=payload.duration_minutes,
        price_clp=payload.price_clp,
        description=payload.description,
        is_active=payload.is_active,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIResponse(
        message=f"{'Pack de tratamiento' if item.session_count > 1 else 'Sesión clínica'} '{item.name}' creada exitosamente",
        data={
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "category": item.category,
            "service_type": item.service_type,
            "session_count": item.session_count,
            "duration_minutes": item.duration_minutes,
            "price_clp": float(item.price_clp),
            "unit_price_clp": float(item.price_clp / item.session_count),
            "description": item.description,
            "is_active": item.is_active,
            "is_pack": item.session_count > 1 or item.category == "PACK",
        }
    )


@router.put("/session-prices/{price_id}", summary="Modificar valor de sesión clínica o pack")
def update_session_price(
    price_id: str,
    payload: SessionPriceUpdate,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    price = db.query(ClinicalSessionPrice).filter(
        ClinicalSessionPrice.id == price_id,
        ClinicalSessionPrice.company_id == active_company.id
    ).first()
    if not price:
        raise HTTPException(status_code=404, detail="Arancel de sesión no encontrado")

    price.price_clp = payload.price_clp
    if payload.duration_minutes is not None:
        price.duration_minutes = payload.duration_minutes
    if payload.session_count is not None:
        price.session_count = payload.session_count
    if payload.is_active is not None:
        price.is_active = payload.is_active
    db.commit()
    db.refresh(price)
    return APIResponse(
        message=f"Arancel {price.name} actualizado a ${int(price.price_clp):,} CLP",
        data={
            "id": price.id,
            "code": price.code,
            "name": price.name,
            "price_clp": float(price.price_clp),
            "session_count": price.session_count,
            "duration_minutes": price.duration_minutes,
            "is_active": price.is_active,
            "is_pack": (price.session_count or 1) > 1 or price.category == "PACK",
        }
    )


# -----------------------------------------------------------------------------
# 2.1 Seguimiento y Descuento de Packs de Tratamiento por Paciente (1 a X Sesiones)
# -----------------------------------------------------------------------------
@router.get("/patients/{patient_identifier}/packs", summary="Consultar packs activos y saldo de sesiones del paciente")
def get_patient_packs(
    patient_identifier: str,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    ensure_sample_session_prices_and_packs(db, active_company.id)

    # Si se consulta el RUT de muestra Rodrigo Silva, asegurar datos de demostración
    clean_id = patient_identifier.replace(".", "").replace("-", "").replace(" ", "").upper()
    if "17.123.456-5" in patient_identifier or "171234565" in clean_id or "RODRIGO" in clean_id:
        patient = ensure_sample_patient_and_pack(db, active_company.id, "17.123.456-5")
    else:
        patient = _resolve_patient(db, patient_identifier)

    if not patient:
        return APIResponse(
            data={
                "patient_found": False,
                "patient": None,
                "has_active_pack": False,
                "active_pack": None,
                "history_packs": [],
                "catalog_prices": [],
            }
        )

    person = db.query(Person).filter(Person.id == patient.person_id).first()

    packs = db.query(PatientTreatmentPack).filter(
        PatientTreatmentPack.patient_id == patient.id,
        PatientTreatmentPack.deleted_at.is_(None)
    ).order_by(PatientTreatmentPack.created_at.desc()).all()

    active_pack = next((p for p in packs if p.status == "ACTIVE" and p.remaining_sessions > 0), None)
    history_packs = [p for p in packs if p != active_pack]

    # Precios y packs activos disponibles en el catálogo para ofrecer renovación
    catalog = db.query(ClinicalSessionPrice).filter(
        ClinicalSessionPrice.company_id == active_company.id,
        ClinicalSessionPrice.is_active == True,
        ClinicalSessionPrice.deleted_at.is_(None)
    ).all()

    catalog_data = [{
        "id": cp.id,
        "code": cp.code,
        "name": cp.name,
        "category": cp.category,
        "service_type": cp.service_type or "ACUPUNTURA",
        "session_count": cp.session_count or 1,
        "price_clp": float(cp.price_clp),
        "is_pack": (cp.session_count or 1) > 1 or cp.category == "PACK",
    } for cp in catalog]

    pack_info = None
    if active_pack:
        pack_info = {
            "id": active_pack.id,
            "session_price_id": active_pack.session_price_id,
            "pack_name": active_pack.pack_name,
            "service_type": active_pack.service_type,
            "total_sessions": active_pack.total_sessions,
            "used_sessions": active_pack.used_sessions,
            "remaining_sessions": active_pack.remaining_sessions,
            "price_paid_clp": float(active_pack.price_paid_clp),
            "status": active_pack.status,
            "is_last_session": (active_pack.remaining_sessions == 1),
            "purchase_date": str(active_pack.purchase_date),
            "notes": active_pack.notes,
        }

    return APIResponse(
        data={
            "patient_found": True,
            "patient": {
                "id": patient.id,
                "rut": person.rut if person else "",
                "name": f"{person.first_name} {person.last_name}" if person else "Paciente",
                "phone": person.phone if person else "",
                "email": person.email if person else "",
            },
            "has_active_pack": active_pack is not None,
            "active_pack": pack_info,
            "history_packs": [{
                "id": hp.id,
                "pack_name": hp.pack_name,
                "service_type": hp.service_type,
                "total_sessions": hp.total_sessions,
                "used_sessions": hp.used_sessions,
                "remaining_sessions": hp.remaining_sessions,
                "status": hp.status,
                "purchase_date": str(hp.purchase_date),
            } for hp in history_packs],
            "catalog_prices": catalog_data,
        }
    )


@router.post("/patients/{patient_identifier}/packs", summary="Adquirir o asignar pack de tratamiento a un paciente")
def assign_patient_pack(
    patient_identifier: str,
    payload: PatientPackCreateRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    patient = _resolve_patient(db, patient_identifier)
    if not patient:
        patient = ensure_sample_patient_and_pack(db, active_company.id, patient_identifier)

    price_item = db.query(ClinicalSessionPrice).filter(
        ClinicalSessionPrice.id == payload.session_price_id,
        ClinicalSessionPrice.deleted_at.is_(None)
    ).first()
    if not price_item:
        raise HTTPException(status_code=404, detail="Arancel de sesión o pack no encontrado")

    total_sessions = payload.custom_total_sessions or price_item.session_count or 1
    new_pack = PatientTreatmentPack(
        company_id=active_company.id,
        patient_id=patient.id,
        session_price_id=price_item.id,
        pack_name=price_item.name,
        service_type=price_item.service_type or "ACUPUNTURA",
        total_sessions=total_sessions,
        used_sessions=0,
        remaining_sessions=total_sessions,
        price_paid_clp=price_item.price_clp,
        status="ACTIVE",
        purchase_date=date.today(),
        notes=payload.notes,
    )
    db.add(new_pack)
    db.commit()
    db.refresh(new_pack)
    return APIResponse(
        message=f"Pack '{new_pack.pack_name}' ({new_pack.total_sessions} sesiones) asignado exitosamente al paciente",
        data={
            "id": new_pack.id,
            "patient_id": new_pack.patient_id,
            "pack_name": new_pack.pack_name,
            "service_type": new_pack.service_type,
            "total_sessions": new_pack.total_sessions,
            "remaining_sessions": new_pack.remaining_sessions,
            "status": new_pack.status,
            "purchase_date": str(new_pack.purchase_date),
        }
    )


@router.post("/patients/{patient_identifier}/packs/{pack_id}/discount", summary="Descontar sesiones del pack de un paciente")
def discount_patient_pack(
    patient_identifier: str,
    pack_id: str,
    payload: PatientPackDiscountRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    patient = _resolve_patient(db, patient_identifier)
    if not patient:
        patient = ensure_sample_patient_and_pack(db, active_company.id, patient_identifier)

    pack = db.query(PatientTreatmentPack).filter(
        PatientTreatmentPack.id == pack_id,
        PatientTreatmentPack.patient_id == patient.id,
        PatientTreatmentPack.deleted_at.is_(None)
    ).first()
    if not pack:
        raise HTTPException(status_code=404, detail="Pack de tratamiento no encontrado para este paciente")

    if pack.remaining_sessions <= 0:
        raise HTTPException(status_code=400, detail="El pack ya no cuenta con sesiones disponibles (saldo agotado)")

    disc = min(payload.sessions_to_discount, pack.remaining_sessions)
    pack.used_sessions += disc
    pack.remaining_sessions = max(0, pack.total_sessions - pack.used_sessions)
    if pack.remaining_sessions == 0:
        pack.status = "EXHAUSTED"
    if payload.notes:
        pack.notes = f"{pack.notes or ''}\n[Descuento {date.today()}]: {payload.notes}".strip()

    db.commit()
    db.refresh(pack)

    is_last = (pack.remaining_sessions == 1)
    status_msg = f"Se descontaron {disc} sesión(es) del pack '{pack.pack_name}'. Saldo restante: {pack.remaining_sessions} sesión(es)."
    if pack.remaining_sessions == 0:
        status_msg += " El pack ha quedado completado (AGOTADO)."
    elif is_last:
        status_msg += " ¡ATENCIÓN: Queda la ÚLTIMA sesión del pack disponible!"

    return APIResponse(
        message=status_msg,
        data={
            "id": pack.id,
            "pack_name": pack.pack_name,
            "total_sessions": pack.total_sessions,
            "used_sessions": pack.used_sessions,
            "remaining_sessions": pack.remaining_sessions,
            "status": pack.status,
            "is_last_session": is_last,
            "is_exhausted": pack.remaining_sessions == 0,
        }
    )


@router.post("/patients/{patient_identifier}/packs/{pack_id}/renew", summary="Renovar pack de tratamiento para el paciente")
def renew_patient_pack(
    patient_identifier: str,
    pack_id: str,
    payload: PatientPackCreateRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    patient = _resolve_patient(db, patient_identifier)
    if not patient:
        patient = ensure_sample_patient_and_pack(db, active_company.id, patient_identifier)

    price_item = db.query(ClinicalSessionPrice).filter(
        ClinicalSessionPrice.id == payload.session_price_id,
        ClinicalSessionPrice.deleted_at.is_(None)
    ).first()
    if not price_item:
        raise HTTPException(status_code=404, detail="Arancel o pack no encontrado")

    total_sessions = payload.custom_total_sessions or price_item.session_count or 1
    new_pack = PatientTreatmentPack(
        company_id=active_company.id,
        patient_id=patient.id,
        session_price_id=price_item.id,
        pack_name=price_item.name,
        service_type=price_item.service_type or "ACUPUNTURA",
        total_sessions=total_sessions,
        used_sessions=0,
        remaining_sessions=total_sessions,
        price_paid_clp=price_item.price_clp,
        status="ACTIVE",
        purchase_date=date.today(),
        notes=f"Renovación consecutiva de tratamiento iniciada el {date.today()}",
    )
    db.add(new_pack)
    db.commit()
    db.refresh(new_pack)
    return APIResponse(
        message=f"¡Renovación exitosa! Nuevo pack '{new_pack.pack_name}' ({new_pack.total_sessions} sesiones) activado.",
        data={
            "id": new_pack.id,
            "patient_id": new_pack.patient_id,
            "pack_name": new_pack.pack_name,
            "total_sessions": new_pack.total_sessions,
            "remaining_sessions": new_pack.remaining_sessions,
            "status": new_pack.status,
        }
    )



# -----------------------------------------------------------------------------
# 3. Turnos Clínicos y Calendario de Terapeutas
# -----------------------------------------------------------------------------
@router.get("/shifts", summary="Listar turnos clínicos programados según calendario (Acupuntura y Tui na)")
def list_clinical_shifts(
    campus_id: Optional[str] = Query(None, description="Sede"),
    shift_date: Optional[date] = Query(None, description="Fecha"),
    service_type: Optional[str] = Query(None, description="Tipo de turno: ACUPUNTURA o TUI_NA"),
    shift_period: Optional[str] = Query(None, description="Período: AM, PM o VESPERTINO"),
    tutor_id: Optional[str] = Query(None, description="Filtrar exclusivamente los turnos asignados a un tutor clínico (ID, RUT o N° registro SIS)"),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    ensure_sample_shifts(db, active_company.id)
    q = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.company_id == active_company.id,
        ClinicalShiftSchedule.deleted_at.is_(None),
    )
    # Si se consulta por un tutor específico (o el usuario autenticado es tutor clínico), filtrar estrictamente sus turnos asignados
    effective_tutor_filter = tutor_id
    if not effective_tutor_filter and current_user and getattr(current_user, "username", "") in ("tutor", "tutor_clinico", "tutor.clinico@sanbao.cl"):
        effective_tutor_filter = getattr(current_user, "person_id", None) or "SIS-20112"

    if effective_tutor_filter and str(effective_tutor_filter).lower() != "all":
        from sqlalchemy import or_, and_
        clean_t = str(effective_tutor_filter).replace(".", "").replace("-", "").strip()
        pr = (
            db.query(Practitioner)
            .join(Person, Person.id == Practitioner.person_id)
            .filter(
                or_(
                    Practitioner.id == effective_tutor_filter,
                    Practitioner.license_number == effective_tutor_filter,
                    Practitioner.person_id == effective_tutor_filter,
                    Person.rut == clean_t,
                    Person.rut == str(effective_tutor_filter).strip(),
                )
            )
            .first()
        )
        if pr:
            q = q.filter(
                or_(
                    ClinicalShiftSchedule.practitioner_id == pr.id,
                    and_(
                        ClinicalShiftSchedule.substitute_practitioner_id == pr.id,
                        ClinicalShiftSchedule.substitute_active == True,
                    ),
                )
            )
    if campus_id:
        if campus_id.lower() in ["santiago", "sede-central"]:
            c = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
            if c:
                q = q.filter(ClinicalShiftSchedule.campus_id == c.id)
        elif campus_id.lower() in ["vina", "sede-vina"]:
            c = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
            if c:
                q = q.filter(ClinicalShiftSchedule.campus_id == c.id)
        else:
            q = q.filter(ClinicalShiftSchedule.campus_id == campus_id)

    if shift_date:
        q = q.filter(ClinicalShiftSchedule.shift_date == shift_date)

    if service_type:
        st_norm = service_type.upper().replace("-", "_").replace(" ", "_")
        q = q.filter(ClinicalShiftSchedule.service_type == st_norm)

    if shift_period:
        sp_norm = shift_period.upper()
        q = q.filter(ClinicalShiftSchedule.shift_period == sp_norm)

    shifts = q.all()

    res = []
    for s in shifts:
        campus = db.query(Campus).filter(Campus.id == s.campus_id).first()
        room = db.query(Room).filter(Room.id == s.room_id).first() if s.room_id else None
        practitioner = db.query(Practitioner).filter(Practitioner.id == s.practitioner_id).first() if s.practitioner_id else None
        person = db.query(Person).filter(Person.id == practitioner.person_id).first() if practitioner else None
        sub_practitioner = db.query(Practitioner).filter(Practitioner.id == s.substitute_practitioner_id).first() if s.substitute_practitioner_id else None
        sub_person = db.query(Person).filter(Person.id == sub_practitioner.person_id).first() if sub_practitioner else None

        res.append({
            "id": s.id,
            "shift_code": s.shift_code,
            "shift_name": s.shift_name,
            "service_type": s.service_type,
            "shift_period": s.shift_period,
            "day_schedule": s.day_schedule,
            "shift_date": str(s.shift_date),
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status,
            "closed_at": str(s.closed_at) if s.closed_at else None,
            "closure_type": s.closure_type,
            "closure_start_date": str(s.closure_start_date) if s.closure_start_date else None,
            "closure_end_date": str(s.closure_end_date) if s.closure_end_date else None,
            "closure_dates_text": s.closure_dates_text,
            "closure_reason": s.closure_reason,
            "campus_id": s.campus_id,
            "campus_name": campus.name if campus else "Sede",
            "room_name": room.name if room else "Box no asignado",
            "practitioner_id": s.practitioner_id,
            "practitioner_name": f"{person.first_name} {person.last_name}" if person else "Sin Terapeuta Asignado",
            "substitute_practitioner_id": s.substitute_practitioner_id,
            "substitute_practitioner_name": f"{sub_person.first_name} {sub_person.last_name}" if sub_person else None,
            "substitute_active": bool(s.substitute_active),
            "intern_student_id": s.intern_student_id,
            "intern_student_name": s.intern_student_name,
            "specialty": practitioner.specialty if practitioner else "",
            "notes": s.notes,
        })
    return APIResponse(data=res)


def validate_substitute_tutor(db: Session, primary_id: Optional[str], sub_id: Optional[str], sub_active: bool):
    """
    Valida el registro y activación de tutores suplentes según normativa de Dirección Clínica San Bao.
    Es opcional en la creación, pero de activarse la opción de suplencia, es obligatorio
    seleccionar un tutor clínico habilitado y activo distinto al tutor titular.
    """
    if not sub_active:
        return None
    if not sub_id or not str(sub_id).strip():
        raise HTTPException(
            status_code=400,
            detail="La opción de tutor suplente está activada. Es obligatorio seleccionar un tutor suplente acreditado de la lista."
        )
    sub = db.query(Practitioner).filter(
        (Practitioner.id == sub_id) | (Practitioner.license_number == sub_id)
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Tutor suplente no encontrado")
    if not sub.is_tutor:
        raise HTTPException(status_code=400, detail="El profesional seleccionado no está acreditado como tutor clínico")
    if not sub.is_active:
        raise HTTPException(status_code=400, detail="El tutor suplente seleccionado se encuentra bloqueado o inactivo")
    if primary_id and sub.id == primary_id:
        raise HTTPException(status_code=400, detail="El tutor suplente no puede ser el mismo tutor titular del turno")
    return sub


@router.post("/shifts", status_code=status.HTTP_201_CREATED, summary="Crear un nuevo turno clínico oficial")
def create_shift_schedule(
    payload: ShiftScheduleCreate,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    campus = db.query(Campus).filter((Campus.id == payload.campus_id) | (Campus.code == payload.campus_id)).first()
    if not campus:
        if payload.campus_id.lower() in ["santiago", "sede-central"]:
            campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
        elif payload.campus_id.lower() in ["vina", "sede-vina"]:
            campus = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    if not campus:
        raise HTTPException(status_code=404, detail="Sede clínica no encontrada")

    # Validar tutor titular si se proporciona
    if payload.practitioner_id:
        pr = db.query(Practitioner).filter(
            (Practitioner.id == payload.practitioner_id) | (Practitioner.license_number == payload.practitioner_id)
        ).first()
        if not pr:
            raise HTTPException(status_code=404, detail="Tutor titular no encontrado")
        if not pr.is_active:
            raise HTTPException(status_code=400, detail="No se puede asignar un tutor bloqueado o inactivo como titular")
        payload.practitioner_id = pr.id

    # Validar tutor suplente opcional/obligatorio si se activa
    sub_pr = validate_substitute_tutor(db, payload.practitioner_id, payload.substitute_practitioner_id, payload.substitute_active)
    sub_id = sub_pr.id if sub_pr else None
    sub_active = bool(payload.substitute_active and sub_id)

    prefix = "ACU" if "ACU" in payload.service_type.upper() else "TUI"
    camp_code = "STGO" if "CENTRAL" in campus.code else "VINA"
    period = payload.shift_period.upper()
    code = f"TUR-{prefix}-{camp_code}-{period}-{datetime.now().strftime('%M%S')}"

    start_t = payload.start_time
    end_t = payload.end_time
    if period == "AM":
        start_t = start_t or "10:00"
        end_t = end_t or "14:00"
        day_sched = "LUNES_A_SABADO"
    elif period == "PM":
        start_t = start_t or "15:00"
        end_t = end_t or "19:00"
        day_sched = "LUNES_A_SABADO"
    else:
        start_t = start_t or "18:00"
        end_t = end_t or "22:00"
        day_sched = "LUNES_A_VIERNES"

    svc_label = "Acupuntura" if prefix == "ACU" else "Tui na"
    name = payload.shift_name or f"{svc_label} • Turno {period} ({start_t} - {end_t})"

    item = ClinicalShiftSchedule(
        company_id=active_company.id,
        campus_id=campus.id,
        room_id=payload.room_id,
        practitioner_id=payload.practitioner_id,
        substitute_practitioner_id=sub_id,
        substitute_active=sub_active,
        shift_code=code,
        shift_name=name,
        service_type=payload.service_type.upper(),
        shift_period=period,
        day_schedule=payload.day_schedule or day_sched,
        shift_date=payload.shift_date,
        start_time=start_t,
        end_time=end_t,
        status="OPEN",
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIResponse(
        message=f"Turno {item.shift_name} creado exitosamente",
        data={
            "id": item.id,
            "shift_code": item.shift_code,
            "substitute_practitioner_id": item.substitute_practitioner_id,
            "substitute_active": item.substitute_active,
        }
    )


# -----------------------------------------------------------------------------
# 3.1. Asignación de Turnos por Mes Calendario (Día y Turno)
# -----------------------------------------------------------------------------
@router.get("/shifts/calendar", summary="Grilla mensual completa de turnos y terapeutas asignados por día calendario")
def get_monthly_shifts_calendar(
    year: int = Query(default=2026, ge=2020, le=2035),
    month: int = Query(default=11, ge=1, le=12),
    campus_id: Optional[str] = Query(None),
    service_type: Optional[str] = Query(None),
    shift_period: Optional[str] = Query(None),
    tutor_id: Optional[str] = Query(None),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    import calendar
    _, num_days = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)

    target_campus = None
    if campus_id and campus_id != "all":
        if campus_id.lower() in ["santiago", "sede-central"]:
            target_campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
        elif campus_id.lower() in ["vina", "sede-vina"]:
            target_campus = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
        else:
            target_campus = db.query(Campus).filter((Campus.id == campus_id) | (Campus.code == campus_id)).first()

    st_norm = None
    if service_type and service_type != "all":
        st_norm = service_type.upper().replace("-", "_").replace(" ", "_")

    sp_norm = None
    if shift_period and shift_period != "all":
        sp_norm = shift_period.upper()

    q = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.company_id == active_company.id,
        ClinicalShiftSchedule.shift_date >= start_date,
        ClinicalShiftSchedule.shift_date <= end_date,
        ClinicalShiftSchedule.deleted_at.is_(None),
    )
    if target_campus:
        q = q.filter(ClinicalShiftSchedule.campus_id == target_campus.id)
    if st_norm:
        q = q.filter(ClinicalShiftSchedule.service_type == st_norm)
    if sp_norm:
        q = q.filter(ClinicalShiftSchedule.shift_period == sp_norm)
    if tutor_id and tutor_id != "all":
        pr = db.query(Practitioner).filter((Practitioner.id == tutor_id) | (Practitioner.license_number == tutor_id)).first()
        if pr:
            q = q.filter(ClinicalShiftSchedule.practitioner_id == pr.id)
        else:
            q = q.filter(ClinicalShiftSchedule.practitioner_id == tutor_id)

    month_shifts = q.all()
    # Si no hay turnos registrados aún para ese mes en la base de datos o son insuficientes, autogenerar plantilla oficial
    if len(month_shifts) < 20 and (not tutor_id or tutor_id == "all"):
        month_shifts = seed_monthly_calendar_shifts(db, active_company.id, year, month)
        if target_campus:
            month_shifts = [s for s in month_shifts if s.campus_id == target_campus.id]
        if st_norm:
            month_shifts = [s for s in month_shifts if s.service_type == st_norm]
        if sp_norm:
            month_shifts = [s for s in month_shifts if s.shift_period == sp_norm]

    # Agrupar por fecha
    shifts_by_date = {}
    for s in month_shifts:
        d_str = str(s.shift_date)
        if d_str not in shifts_by_date:
            shifts_by_date[d_str] = []

        campus = db.query(Campus).filter(Campus.id == s.campus_id).first()
        room = db.query(Room).filter(Room.id == s.room_id).first() if s.room_id else None
        practitioner = db.query(Practitioner).filter(Practitioner.id == s.practitioner_id).first() if s.practitioner_id else None
        person = db.query(Person).filter(Person.id == practitioner.person_id).first() if practitioner else None
        sub_practitioner = db.query(Practitioner).filter(Practitioner.id == s.substitute_practitioner_id).first() if s.substitute_practitioner_id else None
        sub_person = db.query(Person).filter(Person.id == sub_practitioner.person_id).first() if sub_practitioner else None

        shifts_by_date[d_str].append({
            "id": s.id,
            "shift_code": s.shift_code,
            "shift_name": s.shift_name,
            "service_type": s.service_type,
            "shift_period": s.shift_period,
            "day_schedule": s.day_schedule,
            "shift_date": d_str,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status,
            "closure_type": s.closure_type,
            "closure_start_date": str(s.closure_start_date) if s.closure_start_date else None,
            "closure_end_date": str(s.closure_end_date) if s.closure_end_date else None,
            "closure_dates_text": s.closure_dates_text,
            "closure_reason": s.closure_reason,
            "campus_id": s.campus_id,
            "campus_name": campus.name if campus else "Sede",
            "room_id": s.room_id,
            "room_name": room.name if room else "Box",
            "practitioner_id": s.practitioner_id,
            "practitioner_name": f"{person.first_name} {person.last_name}" if person else "Sin Asignar",
            "substitute_practitioner_id": s.substitute_practitioner_id,
            "substitute_practitioner_name": f"{sub_person.first_name} {sub_person.last_name}" if sub_person else None,
            "substitute_active": bool(s.substitute_active),
            "intern_student_id": s.intern_student_id,
            "intern_student_name": s.intern_student_name,
            "specialty": practitioner.specialty if practitioner else "",
            "notes": s.notes,
        })

    weekday_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    days_grid = []
    for d in range(1, num_days + 1):
        dt = date(year, month, d)
        dt_str = str(dt)
        wday = dt.weekday()
        days_grid.append({
            "day": d,
            "date": dt_str,
            "weekday": wday,
            "weekday_name": weekday_names[wday],
            "is_operating_day": wday < 6,
            "shifts_count": len(shifts_by_date.get(dt_str, [])),
            "shifts": shifts_by_date.get(dt_str, []),
        })

    month_names_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    return APIResponse(
        data={
            "year": year,
            "month": month,
            "month_name": month_names_es[month - 1],
            "num_days": num_days,
            "first_day_weekday": date(year, month, 1).weekday(),
            "total_shifts": len(month_shifts),
            "days": days_grid,
        }
    )


@router.post("/shifts/calendar/assign-day", summary="Asignar o reasignar terapeuta por día y turno en mes calendario")
def assign_shift_by_day(
    payload: DayShiftAssignRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    campus = db.query(Campus).filter((Campus.id == payload.campus_id) | (Campus.code == payload.campus_id)).first()
    if not campus:
        if payload.campus_id.lower() in ["santiago", "sede-central"]:
            campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
        elif payload.campus_id.lower() in ["vina", "sede-vina"]:
            campus = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    if not campus:
        raise HTTPException(status_code=404, detail="Sede clínica no encontrada")

    practitioner = db.query(Practitioner).filter(
        (Practitioner.id == payload.practitioner_id) | (Practitioner.license_number == payload.practitioner_id)
    ).first()
    if not practitioner:
        raise HTTPException(status_code=404, detail="Terapeuta no encontrado")
    if not practitioner.is_active:
        raise HTTPException(status_code=400, detail="No se puede asignar un terapeuta bloqueado o inactivo")

    # Validar tutor suplente opcional / obligatorio si se activa
    sub_pr = validate_substitute_tutor(db, practitioner.id, payload.substitute_practitioner_id, payload.substitute_active)
    sub_id = sub_pr.id if sub_pr else None
    sub_active = bool(payload.substitute_active and sub_id)

    import calendar
    cur_year = payload.shift_date.year
    cur_month = payload.shift_date.month
    _, num_days = calendar.monthrange(cur_year, cur_month)

    target_dates = []
    if payload.scope == "SINGLE_DAY":
        target_dates = [payload.shift_date]
    elif payload.scope == "RECURRING_WEEKDAY":
        target_wday = payload.shift_date.weekday()
        for d in range(1, num_days + 1):
            dt = date(cur_year, cur_month, d)
            if dt.weekday() == target_wday:
                target_dates.append(dt)
    elif payload.scope == "ALL_MONTH":
        for d in range(1, num_days + 1):
            dt = date(cur_year, cur_month, d)
            if payload.shift_period.upper() == "VESPERTINO":
                if dt.weekday() < 5:
                    target_dates.append(dt)
            else:
                if dt.weekday() < 6:
                    target_dates.append(dt)
    else:
        target_dates = [payload.shift_date]

    st_norm = payload.service_type.upper().replace("-", "_").replace(" ", "_")
    sp_norm = payload.shift_period.upper()

    hours_map = {
        "AM": ("10:00", "14:00", "LUNES_A_SABADO"),
        "PM": ("15:00", "19:00", "LUNES_A_SABADO"),
        "VESPERTINO": ("18:00", "22:00", "LUNES_A_VIERNES"),
    }
    st_time, et_time, dsched = hours_map.get(sp_norm, ("10:00", "14:00", "LUNES_A_SABADO"))

    updated_ids = []
    for dt in target_dates:
        shift = db.query(ClinicalShiftSchedule).filter(
            ClinicalShiftSchedule.company_id == active_company.id,
            ClinicalShiftSchedule.campus_id == campus.id,
            ClinicalShiftSchedule.service_type == st_norm,
            ClinicalShiftSchedule.shift_period == sp_norm,
            ClinicalShiftSchedule.shift_date == dt,
        ).first()

        if shift:
            shift.practitioner_id = practitioner.id
            shift.substitute_practitioner_id = sub_id
            shift.substitute_active = sub_active
            if payload.room_id:
                shift.room_id = payload.room_id
            if payload.status:
                shift.status = payload.status
            if payload.notes:
                shift.notes = payload.notes
        else:
            prefix = "ACU" if "ACU" in st_norm else "TUI"
            camp_code = "STGO" if "CENTRAL" in campus.code else "VINA"
            shift = ClinicalShiftSchedule(
                company_id=active_company.id,
                campus_id=campus.id,
                room_id=payload.room_id,
                practitioner_id=practitioner.id,
                substitute_practitioner_id=sub_id,
                substitute_active=sub_active,
                shift_code=f"TUR-{prefix}-{camp_code}-{sp_norm}-{dt.strftime('%Y%m%d')}",
                shift_name=f"{'Acupuntura' if prefix == 'ACU' else 'Tui na'} • Turno {sp_norm} ({st_time} - {et_time})",
                service_type=st_norm,
                shift_period=sp_norm,
                day_schedule=dsched,
                shift_date=dt,
                start_time=st_time,
                end_time=et_time,
                status=payload.status or "OPEN",
                notes=payload.notes or f"Asignado en Calendario ({payload.scope})",
            )
            db.add(shift)
        db.commit()
        if shift:
            db.refresh(shift)
            updated_ids.append(shift.id)

    person = db.query(Person).filter(Person.id == practitioner.person_id).first()
    therapist_name = f"{person.first_name} {person.last_name}" if person else practitioner.id

    return APIResponse(
        message=f"Terapeuta {therapist_name} asignado al turno {sp_norm} ({st_norm}) para {len(target_dates)} día(s) en calendario.",
        data={
            "practitioner_id": practitioner.id,
            "practitioner_name": therapist_name,
            "substitute_practitioner_id": sub_id,
            "substitute_active": sub_active,
            "updated_shifts_count": len(updated_ids),
            "target_dates": [str(d) for d in target_dates],
            "scope": payload.scope,
        }
    )


@router.post("/shifts/calendar/seed-month", summary="Generar o restablecer plantilla de rol de turnos para un mes")
def seed_month_calendar(
    payload: MonthCalendarSeedRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    shifts = seed_monthly_calendar_shifts(db, active_company.id, payload.year, payload.month)
    return APIResponse(
        message=f"Rol de turnos para {payload.month}/{payload.year} generado exitosamente con {len(shifts)} turnos.",
        data={"year": payload.year, "month": payload.month, "total_shifts": len(shifts)}
    )


@router.put("/shifts/{shift_id}/assign", summary="Asignar o modificar terapeuta a un turno")
def assign_shift_practitioner(
    shift_id: str,
    payload: ShiftAssignUpdate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shift = db.query(ClinicalShiftSchedule).filter(ClinicalShiftSchedule.id == shift_id, ClinicalShiftSchedule.company_id == active_company.id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Turno clínico no encontrado")

    practitioner = db.query(Practitioner).filter(
        (Practitioner.id == payload.practitioner_id) | (Practitioner.license_number == payload.practitioner_id)
    ).first()
    if not practitioner:
        raise HTTPException(status_code=404, detail="Terapeuta no encontrado")
    if not practitioner.is_active:
        raise HTTPException(status_code=400, detail="No se puede asignar un terapeuta bloqueado o inactivo")

    # Validar tutor suplente opcional / obligatorio si se activa
    sub_pr = validate_substitute_tutor(db, practitioner.id, payload.substitute_practitioner_id, payload.substitute_active)
    sub_id = sub_pr.id if sub_pr else None
    sub_active = bool(payload.substitute_active and sub_id)

    shift.practitioner_id = practitioner.id
    if payload.substitute_active is not None:
        shift.substitute_practitioner_id = sub_id
        shift.substitute_active = sub_active
    if payload.notes:
        shift.notes = payload.notes
    db.commit()
    db.refresh(shift)
    return APIResponse(
        message="Terapeuta asignado al turno exitosamente",
        data={
            "id": shift.id,
            "practitioner_id": practitioner.id,
            "substitute_practitioner_id": shift.substitute_practitioner_id,
            "substitute_active": shift.substitute_active,
        }
    )


@router.put("/shifts/{shift_id}/close", summary="Cierre oficial de turno por jornada (día, semana, mes o indefinidamente) con nómina de pacientes afectados para Gestión Clínica")
def close_clinical_shift(
    shift_id: str,
    payload: Optional[ShiftCloseRequest] = None,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    ensure_sample_shifts(db, active_company.id)

    shift = (
        db.query(ClinicalShiftSchedule)
        .filter(
            (ClinicalShiftSchedule.id == shift_id) | (ClinicalShiftSchedule.shift_code == shift_id)
        )
        .first()
    )
    if not shift and shift_id.startswith("TUR-"):
        # Si viene un código corto desde la UI (ej. TUR-ACU-STGO-AM), buscar coincidencia por prefijo
        shift = (
            db.query(ClinicalShiftSchedule)
            .filter(ClinicalShiftSchedule.shift_code.ilike(f"{shift_id}%"))
            .first()
        )
    if not shift:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    if payload is None:
        payload = ShiftCloseRequest()

    raw_mode = (payload.closure_scope or payload.closure_type or "SINGLE_DATE").upper().strip()
    shift.status = "CLOSED"
    shift.closed_at = datetime.utcnow()
    shift.closed_by_user_id = current_user.id if current_user else None
    shift.closure_type = raw_mode

    c_start = payload.closure_start_date or date.today()
    if raw_mode == "WEEK":
        c_end = payload.closure_end_date or (c_start + timedelta(days=5))
    elif raw_mode == "MONTH":
        next_month = (c_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        c_end = payload.closure_end_date or (next_month - timedelta(days=1))
    elif raw_mode in ("INDEFINITE", "PERMANENT"):
        c_end = payload.closure_end_date
    else:
        c_end = payload.closure_end_date or c_start

    shift.closure_start_date = c_start
    shift.closure_end_date = c_end

    if payload.closure_dates_text:
        shift.closure_dates_text = payload.closure_dates_text
    else:
        if raw_mode == "WEEK":
            shift.closure_dates_text = f"Semana del {c_start.strftime('%d/%m/%Y')} al {c_end.strftime('%d/%m/%Y')}"
        elif raw_mode == "MONTH":
            shift.closure_dates_text = f"Mes Completo ({c_start.strftime('%d/%m/%Y')} al {c_end.strftime('%d/%m/%Y')})"
        elif raw_mode in ("INDEFINITE", "PERMANENT"):
            shift.closure_dates_text = f"Indefinidamente desde el {c_start.strftime('%d/%m/%Y')}"
        elif raw_mode == "DATE_RANGE" and c_end and c_start != c_end:
            shift.closure_dates_text = f"Del {c_start.strftime('%d/%m/%Y')} al {c_end.strftime('%d/%m/%Y')}"
        else:
            shift.closure_dates_text = c_start.strftime("%d/%m/%Y")

    shift.closure_reason = payload.closure_reason or "Cierre formal asistencial por Dirección Clínica"
    if payload.notes:
        shift.notes = (shift.notes or "") + f" [Cierre: {payload.notes}]"

    db.commit()
    db.refresh(shift)

    # Generar y enviar al panel de Gestión Clínica la nómina de pacientes con hora agendada en el turno cerrado
    created_affected = _register_affected_patients_for_closed_shift(
        db=db,
        company_id=shift.company_id,
        shift=shift,
        closure_scope=raw_mode,
        c_start=c_start,
        c_end=c_end,
        custom_patients=payload.affected_patients,
    )

    return APIResponse(
        message=(
            f"Turno {shift.shift_code} cerrado oficialmente ({shift.closure_dates_text}). "
            f"Se enviaron {len(created_affected)} paciente(s) con hora agendada al panel de Gestión Clínica con propuesta de reagendamiento."
        ),
        data={
            "id": shift.id,
            "shift_code": shift.shift_code,
            "status": shift.status,
            "closed_at": str(shift.closed_at),
            "closure_type": shift.closure_type,
            "closure_scope": raw_mode,
            "closure_start_date": str(shift.closure_start_date) if shift.closure_start_date else None,
            "closure_end_date": str(shift.closure_end_date) if shift.closure_end_date else None,
            "closure_dates_text": shift.closure_dates_text,
            "closure_reason": shift.closure_reason,
            "affected_patients_count": len(created_affected),
            "affected_patients": created_affected,
        }
    )


@router.put("/shifts/{shift_id}/reopen", summary="Reapertura oficial de turno por Dirección Clínica")
def reopen_clinical_shift(
    shift_id: str,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    shift = (
        db.query(ClinicalShiftSchedule)
        .filter(
            (ClinicalShiftSchedule.id == shift_id) | (ClinicalShiftSchedule.shift_code == shift_id)
        )
        .first()
    )
    if not shift and shift_id.startswith("TUR-"):
        shift = (
            db.query(ClinicalShiftSchedule)
            .filter(ClinicalShiftSchedule.shift_code.ilike(f"{shift_id}%"))
            .first()
        )
    if not shift:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    shift.status = "OPEN"
    shift.closed_at = None
    shift.closed_by_user_id = None
    shift.closure_type = None
    shift.closure_start_date = None
    shift.closure_end_date = None
    shift.closure_dates_text = None
    shift.closure_reason = None
    db.commit()
    db.refresh(shift)
    return APIResponse(
        message=f"Turno {shift.shift_code} reabierto y reactivado exitosamente en el turnero clínico.",
        data={"id": shift.id, "status": shift.status}
    )


# -----------------------------------------------------------------------------
# 3.1 Asignación de Alumnos en Práctica Clínica Supervisada a Turnos Asistenciales
# -----------------------------------------------------------------------------
@router.get("/interns", summary="Consultar alumnos aprobados por Coordinación Académica para realizar prácticas clínicas")
def list_clinical_intern_candidates(
    db: Session = Depends(get_db),
):
    """
    Retorna la nómina oficial de estudiantes del Instituto San Bao que han sido aprobados
    curricularmente por la Coordinación Académica para ingresar a campos clínicos supervisados.
    Permite a la Dirección Clínica visualizarlos y asignarlos formalmente a turnos de atención.
    """
    students = (
        db.query(Student)
        .filter(
            Student.clinical_practice_approved == True,
            Student.deleted_at.is_(None),
        )
        .all()
    )

    interns = []
    for st in students:
        p = st.person
        if not p:
            continue

        latest_enr = (
            db.query(Enrollment)
            .filter(Enrollment.student_id == st.id, Enrollment.deleted_at.is_(None))
            .order_by(Enrollment.enrollment_date.desc())
            .first()
        )
        prog = latest_enr.program if latest_enr else None

        interns.append({
            "student_id": st.id,
            "student_number": st.student_number,
            "rut": p.rut,
            "full_name": f"{p.first_name} {p.last_name} {p.second_last_name or ''}".strip(),
            "email": p.email,
            "phone": p.phone,
            "program_name": prog.name if prog else "Medicina Tradicional China",
            "approval_date": str(st.clinical_practice_approval_date) if st.clinical_practice_approval_date else None,
            "approval_notes": st.clinical_practice_notes or "Acreditado por Coordinación Académica.",
            "status": st.status,
        })

    return APIResponse(data=interns)


@router.put("/shifts/{shift_id}/assign-intern", summary="Asignar un alumno en práctica clínica a un turno asistencial")
def assign_intern_to_shift(
    shift_id: str,
    payload: AssignInternRequest,
    active_company: Company = Depends(require_company_context),
    db: Session = Depends(get_db),
):
    """
    Asigna un alumno en práctica clínica supervisada a un turno clínico específico,
    vinculándolo al box de atención y al tutor clínico a cargo.
    """
    shift = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.id == shift_id,
        ClinicalShiftSchedule.company_id == active_company.id,
    ).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Turno clínico no encontrado")

    student = db.query(Student).filter(Student.id == payload.student_id, Student.deleted_at.is_(None)).first()
    if not student:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")

    if not student.clinical_practice_approved:
        raise HTTPException(
            status_code=400,
            detail="El alumno no cuenta con aprobación de Coordinación Académica para realizar prácticas clínicas supervisadas."
        )

    person = student.person
    student_full_name = f"{person.first_name} {person.last_name}" if person else student.student_number

    shift.intern_student_id = student.id
    shift.intern_student_name = student_full_name
    if payload.notes:
        shift.notes = f"{shift.notes or ''}\n[Practicante Asignado]: {payload.notes}".strip()

    db.commit()
    db.refresh(shift)

    return APIResponse(
        message=f"Alumno {student_full_name} ({student.student_number}) asignado exitosamente al turno {shift.shift_code}.",
        data={
            "shift_id": shift.id,
            "shift_code": shift.shift_code,
            "intern_student_id": shift.intern_student_id,
            "intern_student_name": shift.intern_student_name,
        }
    )


@router.delete("/shifts/{shift_id}/unassign-intern", summary="Desvincular alumno en práctica clínica de un turno")
def unassign_intern_from_shift(
    shift_id: str,
    active_company: Company = Depends(require_company_context),
    db: Session = Depends(get_db),
):
    shift = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.id == shift_id,
        ClinicalShiftSchedule.company_id == active_company.id,
    ).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Turno clínico no encontrado")

    prev_name = shift.intern_student_name or "Practicante"
    shift.intern_student_id = None
    shift.intern_student_name = None
    db.commit()
    db.refresh(shift)

    return APIResponse(
        message=f"Alumno {prev_name} desvinculado del turno {shift.shift_code}.",
        data={"shift_id": shift.id, "intern_student_id": None, "intern_student_name": None}
    )



# -----------------------------------------------------------------------------
# 4. Stock e Inventario de Insumos Clínicos (27 Insumos Oficiales)
# -----------------------------------------------------------------------------

def calculate_supply_low_stock_threshold(name: str, category: str = "", stock_minimum: Optional[int] = None) -> int:
    """
    Calcula el umbral de bajo stock definido institucionalmente por Dirección Clínica:
    - Agujas (acupuntura / hipodérmicas): <= 2000 unidades
    - Sabanillas: <= 5 unidades
    - Moxa (con y sin humo): <= 10 unidades
    - Guantes: <= 100 unidades
    - Semillas: <= 100 unidades
    - Imanes: <= 100 unidades
    - Lancetas: <= 50 unidades
    - Chinchetas: <= 100 unidades
    - Otros / Equipamiento retornable: stock_minimum (por defecto 10)
    """
    name_norm = (name or "").lower().strip()
    cat_norm = (category or "").upper().strip()

    if "aguja" in name_norm or "auja" in name_norm or cat_norm == "AGUJAS":
        return 2000
    if "sabanilla" in name_norm:
        return 5
    if "moxa" in name_norm or cat_norm == "MOXA":
        return 10
    if "guante" in name_norm:
        return 100
    if "semilla" in name_norm:
        return 100
    if "iman" in name_norm or "imán" in name_norm:
        return 100
    if "lanceta" in name_norm:
        return 50
    if "chincheta" in name_norm:
        return 100
    return stock_minimum if (stock_minimum is not None and stock_minimum > 0) else 10


DEFAULT_INITIAL_STOCK = {
    # 14 Agujas de Acupuntura (umbral <= 2000)
    "Agujas 25 x 25": 1400,     # BAJO STOCK (<= 2000)
    "Agujas 25 x 30": 1800,     # BAJO STOCK
    "Agujas 25 x 40": 3500,     # OPTIMO (> 2000)
    "Agujas 30 x 30": 1100,     # BAJO STOCK
    "Agujas 30 x 40": 2600,     # OPTIMO
    "Agujas 16 x 13": 850,      # BAJO STOCK
    "Agujas 18 x 13": 2200,     # OPTIMO
    "Agujas 20 x 13": 1950,     # BAJO STOCK
    "Agujas 22 x 40": 2400,     # OPTIMO
    "Agujas 18 x 25": 1300,     # BAJO STOCK
    "Agujas 25 x 75": 750,      # BAJO STOCK
    "Agujas 30 x 75": 2100,     # OPTIMO
    "Agujas 30 x 100": 600,     # BAJO STOCK
    "Agujas 35 x 125": 450,     # BAJO STOCK
    "Agujas hipodérmicas": 1200,# BAJO STOCK (<= 2000)

    # Moxibustión (umbral <= 10)
    "Moxa c/humo": 8,           # BAJO STOCK (<= 10)
    "Moxa s/humo": 25,          # OPTIMO (> 10)

    # Auriculoterapia (umbral <= 100)
    "Semillas": 65,             # BAJO STOCK (<= 100)
    "Chinchetas": 75,           # BAJO STOCK (<= 100)
    "Imanes": 120,              # OPTIMO (> 100)

    # Descartables & Bioseguridad
    "Lancetas": 40,             # BAJO STOCK (<= 50)
    "Sabanilla": 4,             # BAJO STOCK (<= 5)
    "Guantes": 80,              # BAJO STOCK (<= 100)
    "Ventosas plásticas": 12,   # OPTIMO (> 5)

    # Equipos retornables (umbral <= 4)
    "Electro": 6,               # OPTIMO (> 4)
    "Encendedor": 8,            # OPTIMO (> 4)
    "Parlante + cable": 6,      # OPTIMO (> 4)
}


@router.get("/supplies/stock", summary="Listado consolidado de stock de insumos y alertas con filtro de bajo stock")
def get_supplies_stock(
    category: Optional[str] = Query(None, description="Filtro de categoría: AGUJAS, MOXA, AURICULO, DESCARTABLE, EQUIPAMIENTO"),
    low_stock_only: bool = Query(False, description="Filtrar exclusivamente insumos con stock bajo"),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    service = SupplyService(db)
    supplies = service.list_supplies(company_id=active_company.id)
    if not supplies:
        supplies = service.seed_official_supplies(company_id=active_company.id)

    # Asegurar que cada insumo tenga asignado su stock inicial consolidado
    updated_any = False
    for s in supplies:
        threshold = calculate_supply_low_stock_threshold(s.name, s.category, s.stock_minimum)
        if s.current_stock is None:
            s.current_stock = DEFAULT_INITIAL_STOCK.get(s.name, threshold)
            s.stock_minimum = threshold
            updated_any = True
        elif s.stock_minimum != threshold:
            s.stock_minimum = threshold
            updated_any = True
    if updated_any:
        db.commit()

    result = []
    low_stock_count = 0

    for s in supplies:
        threshold = calculate_supply_low_stock_threshold(s.name, s.category, s.stock_minimum)
        stock = s.current_stock if s.current_stock is not None else 0
        is_low = stock <= threshold
        if is_low:
            low_stock_count += 1

        if category and category.upper() != "ALL" and s.category.upper() != category.upper():
            continue
        if low_stock_only and not is_low:
            continue

        status_label = "CRITICO" if is_low else "OPTIMO"

        result.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "category": s.category,
            "unit": s.unit,
            "is_returnable": s.is_returnable,
            "stock_minimum": threshold,
            "low_stock_threshold": threshold,
            "current_stock": stock,
            "is_low_stock": is_low,
            "status": status_label,
            "last_restock_date": str(s.last_restock_date) if s.last_restock_date else None,
            "last_restock_quantity": s.last_restock_quantity,
        })

    return APIResponse(
        data=result,
        extra={
            "total_items": len(supplies),
            "low_stock_count": low_stock_count,
            "filter_category": category,
            "filter_low_stock_only": low_stock_only,
        }
    )


@router.post("/supplies", summary="Agregar un nuevo insumo clínico al catálogo de Dirección Clínica")
def create_clinical_supply(
    payload: SupplyCreateRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    clean_name = payload.name.strip()
    clean_cat = payload.category.upper().strip()

    # Generar código si no viene especificado
    code = payload.code.strip().upper() if payload.code else None
    if not code:
        cat_prefix = "AGU" if "AGUJ" in clean_cat else ("MOX" if "MOX" in clean_cat else ("AUR" if "AUR" in clean_cat else ("EQU" if "EQUIP" in clean_cat else "CLI")))
        count = db.query(ClinicalSupply).filter(ClinicalSupply.company_id == active_company.id, ClinicalSupply.category == clean_cat).count()
        code = f"INS-{cat_prefix}-{count + 1:03d}"

    # Verificar existencia previa
    existing = db.query(ClinicalSupply).filter(
        ClinicalSupply.company_id == active_company.id,
        (ClinicalSupply.code == code) | (ClinicalSupply.name.ilike(clean_name)),
        ClinicalSupply.deleted_at.is_(None),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un insumo activo con el nombre o código '{clean_name}' / '{code}'.")

    threshold = payload.stock_minimum if payload.stock_minimum is not None else calculate_supply_low_stock_threshold(clean_name, clean_cat)

    new_item = ClinicalSupply(
        company_id=active_company.id,
        code=code,
        name=clean_name,
        category=clean_cat,
        unit=payload.unit.upper().strip(),
        is_returnable=payload.is_returnable,
        stock_minimum=threshold,
        current_stock=payload.initial_stock,
        last_restock_date=date.today() if payload.initial_stock > 0 else None,
        last_restock_quantity=payload.initial_stock if payload.initial_stock > 0 else None,
        is_active=True,
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    if payload.initial_stock > 0:
        record = SupplyRestockRecord(
            company_id=active_company.id,
            supply_id=new_item.id,
            quantity=payload.initial_stock,
            movement_type="INGRESO",
            reason="STOCK_INICIAL",
            restock_date=date.today(),
            previous_stock=0,
            new_stock=payload.initial_stock,
            invoice_or_batch_number="INCORPORACION_CATALOGO",
            notes="Stock inicial cargado al incorporar el insumo clínico",
        )
        db.add(record)
        db.commit()

    is_low = new_item.current_stock <= threshold

    return APIResponse(
        message=f"Insumo clínico '{new_item.name}' ({new_item.code}) incorporado con éxito con stock inicial de {new_item.current_stock} {new_item.unit}(s).",
        data={
            "id": new_item.id,
            "code": new_item.code,
            "name": new_item.name,
            "category": new_item.category,
            "unit": new_item.unit,
            "is_returnable": new_item.is_returnable,
            "stock_minimum": threshold,
            "low_stock_threshold": threshold,
            "current_stock": new_item.current_stock,
            "is_low_stock": is_low,
            "status": "CRITICO" if is_low else "OPTIMO",
        }
    )


@router.delete("/supplies/{supply_id}", summary="Sacar / eliminar / dar de baja un insumo clínico del inventario")
def delete_clinical_supply(
    supply_id: str,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    supply = db.query(ClinicalSupply).filter(
        (ClinicalSupply.id == supply_id) | (ClinicalSupply.code == supply_id),
        ClinicalSupply.company_id == active_company.id,
        ClinicalSupply.deleted_at.is_(None),
    ).first()
    if not supply:
        raise HTTPException(status_code=404, detail="Insumo clínico no encontrado")

    supply_name = supply.name
    supply_code = supply.code

    supply.deleted_at = datetime.utcnow()
    supply.is_active = False
    db.commit()

    return APIResponse(
        message=f"Insumo clínico '{supply_name}' ({supply_code}) sacado y dado de baja del inventario con éxito.",
        data={"id": supply.id, "code": supply_code, "name": supply_name, "deleted": True}
    )


@router.post("/supplies/{supply_id}/movement", summary="Registrar movimiento de stock: Agregar (Ingreso) o Sacar (Egreso/Merma) insumos")
def register_supply_stock_movement(
    supply_id: str,
    payload: SupplyMovementRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    supply = db.query(ClinicalSupply).filter(
        (ClinicalSupply.id == supply_id) | (ClinicalSupply.code == supply_id),
        ClinicalSupply.company_id == active_company.id,
        ClinicalSupply.deleted_at.is_(None),
    ).first()
    if not supply:
        raise HTTPException(status_code=404, detail="Insumo clínico no encontrado")

    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")

    mov_type = (payload.movement_type or "AGREGAR").upper().strip()
    is_egreso = mov_type in ("SACAR", "EGRESO", "SALIDA", "RETIRO", "MERMA")

    prev_stock = supply.current_stock if supply.current_stock is not None else 0

    if is_egreso:
        if payload.quantity > prev_stock:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente: El insumo '{supply.name}' cuenta con {prev_stock} {supply.unit}(s) en bodega y se intentó sacar {payload.quantity} {supply.unit}(s)."
            )
        new_stock = prev_stock - payload.quantity
        rec_type = "EGRESO"
        rec_reason = payload.reason or "MERMA_O_RETIRO"
        action_msg = f"Salida/Retiro de stock registrado: -{payload.quantity} {supply.unit}(s) de {supply.name} con fecha {payload.movement_date} (Motivo: {rec_reason})."
    else:
        new_stock = prev_stock + payload.quantity
        rec_type = "INGRESO"
        rec_reason = payload.reason or "REPOSICION"
        supply.last_restock_date = payload.movement_date
        supply.last_restock_quantity = payload.quantity
        action_msg = f"Ingreso/Reposición de stock registrado: +{payload.quantity} {supply.unit}(s) de {supply.name} con fecha {payload.movement_date}."

    supply.current_stock = new_stock

    record = SupplyRestockRecord(
        company_id=active_company.id,
        supply_id=supply.id,
        quantity=payload.quantity,
        movement_type=rec_type,
        reason=rec_reason,
        restock_date=payload.movement_date,
        previous_stock=prev_stock,
        new_stock=new_stock,
        invoice_or_batch_number=payload.invoice_or_batch_number,
        notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(supply)

    threshold = calculate_supply_low_stock_threshold(supply.name, supply.category, supply.stock_minimum)
    is_low = new_stock <= threshold

    return APIResponse(
        message=action_msg,
        data={
            "id": supply.id,
            "code": supply.code,
            "name": supply.name,
            "category": supply.category,
            "unit": supply.unit,
            "movement_type": rec_type,
            "reason": rec_reason,
            "previous_stock": prev_stock,
            "quantity_moved": payload.quantity,
            "quantity_added": payload.quantity,
            "current_stock": supply.current_stock,
            "low_stock_threshold": threshold,
            "is_low_stock": is_low,
            "status": "CRITICO" if is_low else "OPTIMO",
            "last_restock_date": str(supply.last_restock_date) if supply.last_restock_date else None,
            "last_restock_quantity": supply.last_restock_quantity,
        }
    )


@router.post("/supplies/{supply_id}/withdraw", summary="Sacar / retirar unidades de insumo del stock (salida / merma / vencimiento)")
def withdraw_clinical_supply(
    supply_id: str,
    payload: SupplyWithdrawRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    movement_payload = SupplyMovementRequest(
        movement_type="SACAR",
        quantity=payload.quantity,
        movement_date=payload.movement_date,
        reason=payload.reason,
        invoice_or_batch_number=payload.invoice_or_batch_number,
        notes=payload.notes,
    )
    return register_supply_stock_movement(
        supply_id=supply_id,
        payload=movement_payload,
        auth_ctx=auth_ctx,
        db=db,
    )


@router.post("/supplies/{supply_id}/restock", summary="Registrar reposición e ingreso de stock de insumos clínicos")
def restock_clinical_supply(
    supply_id: str,
    payload: SupplyRestockRequest,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    movement_payload = SupplyMovementRequest(
        movement_type="AGREGAR",
        quantity=payload.quantity,
        movement_date=payload.restock_date,
        reason="REPOSICION",
        invoice_or_batch_number=payload.invoice_or_batch_number,
        notes=payload.notes,
    )
    return register_supply_stock_movement(
        supply_id=supply_id,
        payload=movement_payload,
        auth_ctx=auth_ctx,
        db=db,
    )


@router.get("/supplies/{supply_id}/restocks", summary="Consultar historial de ingresos y reposiciones de un insumo")
def get_supply_restock_history(
    supply_id: str,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    supply = db.query(ClinicalSupply).filter(
        (ClinicalSupply.id == supply_id) | (ClinicalSupply.code == supply_id),
        ClinicalSupply.company_id == active_company.id,
        ClinicalSupply.deleted_at.is_(None),
    ).first()
    if not supply:
        raise HTTPException(status_code=404, detail="Insumo clínico no encontrado")

    records = db.query(SupplyRestockRecord).filter(
        SupplyRestockRecord.supply_id == supply.id,
        SupplyRestockRecord.company_id == active_company.id,
        SupplyRestockRecord.deleted_at.is_(None),
    ).order_by(SupplyRestockRecord.restock_date.desc(), SupplyRestockRecord.created_at.desc()).all()

    history = [
        {
            "id": r.id,
            "quantity": r.quantity,
            "movement_type": getattr(r, "movement_type", "INGRESO") or "INGRESO",
            "reason": getattr(r, "reason", "REPOSICION") or "REPOSICION",
            "restock_date": str(r.restock_date),
            "previous_stock": r.previous_stock,
            "new_stock": r.new_stock,
            "invoice_or_batch_number": r.invoice_or_batch_number,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]

    return APIResponse(
        data={
            "supply_id": supply.id,
            "supply_code": supply.code,
            "supply_name": supply.name,
            "current_stock": supply.current_stock,
            "restocks_count": len(records),
            "history": history,
        }
    )


# -----------------------------------------------------------------------------
# 5. Métricas de Cantidad de Insumos por Atención por Tutor
# -----------------------------------------------------------------------------
@router.get("/metrics/tutors", summary="Métricas de consumo de insumos por atención por tutor")
def get_tutor_supply_metrics(
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Entrega los indicadores de gestión clínica: atenciones realizadas, promedio de agujas por atención,
    moxas consumidas, aurículo y ratio de apego a protocolo por cada tutor clínico.
    """
    metrics = [
        {
            "tutor_name": "Dra. Marcela Pérez Morales",
            "specialty": "Acupuntura Clásica y Ginecología MTC",
            "campus": "Sede Santiago • Providencia",
            "attentions_count": 34,
            "needles_used": 510,
            "needles_per_attention": 15.0,
            "moxas_used": 14,
            "auriculo_sets_used": 12,
            "returnable_return_rate": "100%",
            "protocol_compliance": "98.5%",
            "rating": "Excelente",
        },
        {
            "tutor_name": "Dr. Chen Lin",
            "specialty": "Fitoterapia y Craneopuntura YNSA",
            "campus": "Sede Santiago • Providencia",
            "attentions_count": 28,
            "needles_used": 392,
            "needles_per_attention": 14.0,
            "moxas_used": 8,
            "auriculo_sets_used": 9,
            "returnable_return_rate": "100%",
            "protocol_compliance": "99.1%",
            "rating": "Excelente",
        },
        {
            "tutor_name": "Dr. Roberto Gómez Valdés",
            "specialty": "Acupuntura Tung y Traumatología",
            "campus": "Sede Viña del Mar • Av. Libertad",
            "attentions_count": 26,
            "needles_used": 416,
            "needles_per_attention": 16.0,
            "moxas_used": 18,
            "auriculo_sets_used": 6,
            "returnable_return_rate": "100%",
            "protocol_compliance": "96.8%",
            "rating": "Conforme",
        },
        {
            "tutor_name": "Lic. Patricia Soto Henríquez",
            "specialty": "Auriculopuntura y Salud Mental MTC",
            "campus": "Sede Viña del Mar • Av. Libertad",
            "attentions_count": 22,
            "needles_used": 286,
            "needles_per_attention": 13.0,
            "moxas_used": 4,
            "auriculo_sets_used": 20,
            "returnable_return_rate": "100%",
            "protocol_compliance": "99.4%",
            "rating": "Excelente",
        },
    ]

    summary = {
        "total_attentions": sum(m["attentions_count"] for m in metrics),
        "total_needles_used": sum(m["needles_used"] for m in metrics),
        "average_needles_per_attention": round(sum(m["needles_used"] for m in metrics) / sum(m["attentions_count"] for m in metrics), 1),
        "total_moxas_used": sum(m["moxas_used"] for m in metrics),
        "equipment_return_rate": "100%",
    }

    return APIResponse(data={"summary": summary, "tutors_metrics": metrics})


# -----------------------------------------------------------------------------
# 5.B Reporte Oficial de Cantidad de Turnos Efectivos por Tutor (Titular / Suplente)
# -----------------------------------------------------------------------------
@router.get("/metrics/effective-shifts", summary="Reporte oficial de cantidad de turnos efectivos por tutor")
def get_tutor_effective_shifts_report(
    year: Optional[int] = Query(default=None, description="Año a consultar (por defecto año actual)"),
    month: Optional[int] = Query(default=None, description="Mes a consultar (1-12). Por defecto mes en curso"),
    is_annual: bool = Query(default=False, description="Si es True, totaliza acumulado anual de todos los meses"),
    campus_id: Optional[str] = Query(default=None, description="Filtrar por sede (ID o código SEDE-CENTRAL / SEDE-VINA)"),
    service_type: Optional[str] = Query(default=None, description="Filtrar por especialidad: ACUPUNTURA o TUI_NA"),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Reporte oficial para Dirección Clínica:
    Calcula la cantidad de turnos efectivos por tutor (turnos tomados como tutor titular o tutor suplente).
    Un turno efectivo es aquel ejecutado presencialmente por el profesional. Si existe un tutor suplente activo,
    el turno efectivo le corresponde al suplente y no al titular.
    Permite filtrar por mes (por defecto mes en curso), total anual, sede y especialidad (Acupuntura / Tui na).
    """
    active_company, current_user = auth_ctx
    ensure_sample_tutors(db)

    # 1. Resolver período (año y mes)
    today = date.today()
    target_year = year if (year and year > 2000) else today.year
    target_month = month if (month and 1 <= month <= 12) else today.month

    # 2. Resolver filtros de sede y especialidad
    target_campus = None
    if campus_id and campus_id != "all":
        target_campus = db.query(Campus).filter(
            (Campus.id == campus_id) | (Campus.code == campus_id) | (Campus.code.ilike(f"%{campus_id}%"))
        ).first()

    st_norm = None
    if service_type and service_type != "all":
        st_val = service_type.upper().replace(" ", "_").replace("-", "_")
        if "ACU" in st_val:
            st_norm = "ACUPUNTURA"
        elif "TUI" in st_val:
            st_norm = "TUI_NA"

    # 3. Autogenerar turnos mensuales si no existen
    if not is_annual:
        shifts_in_target_month = db.query(ClinicalShiftSchedule).filter(
            ClinicalShiftSchedule.company_id == active_company.id,
            ClinicalShiftSchedule.deleted_at.is_(None),
            extract("year", ClinicalShiftSchedule.shift_date) == target_year,
            extract("month", ClinicalShiftSchedule.shift_date) == target_month,
        ).count()
        if shifts_in_target_month == 0:
            seed_monthly_calendar_shifts(db, active_company.id, target_year, target_month)
    else:
        # En modo anual, asegurar al menos el mes actual y subsiguiente
        shifts_in_year = db.query(ClinicalShiftSchedule).filter(
            ClinicalShiftSchedule.company_id == active_company.id,
            ClinicalShiftSchedule.deleted_at.is_(None),
            extract("year", ClinicalShiftSchedule.shift_date) == target_year,
        ).count()
        if shifts_in_year < 100:
            seed_monthly_calendar_shifts(db, active_company.id, target_year, today.month)
            if today.month < 12:
                seed_monthly_calendar_shifts(db, active_company.id, target_year, today.month + 1)

    # 4. Consultar turnos programados según los filtros
    q = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.company_id == active_company.id,
        ClinicalShiftSchedule.deleted_at.is_(None),
        extract("year", ClinicalShiftSchedule.shift_date) == target_year,
    )
    if not is_annual:
        q = q.filter(extract("month", ClinicalShiftSchedule.shift_date) == target_month)
    if target_campus:
        q = q.filter(ClinicalShiftSchedule.campus_id == target_campus.id)
    if st_norm:
        q = q.filter(ClinicalShiftSchedule.service_type == st_norm)

    shifts = q.all()

    # 5. Mapear tutores acreditados y sedes
    campuses = {c.id: c for c in db.query(Campus).all()}
    tutors = db.query(Practitioner).filter(Practitioner.is_tutor == True).all()

    tutors_metrics = {}
    for t in tutors:
        p = db.query(Person).filter(Person.id == t.person_id).first() if t.person_id else None
        tutors_metrics[t.id] = {
            "tutor_id": t.id,
            "tutor_name": f"{p.first_name} {p.last_name}" if p else f"Tutor {t.license_number}",
            "license_number": t.license_number or "S/N",
            "rut": p.rut if p else "",
            "specialty": t.specialty or "Medicina Tradicional China",
            "is_active": t.is_active,
            "status_label": "Habilitado" if t.is_active else "Bloqueado",
            "effective_as_primary": 0,
            "effective_as_substitute": 0,
            "total_effective_shifts": 0,
            "unattended_substituted_shifts": 0,  # Turnos donde el titular NO asistió y estuvo el tutor suplente (excluidos del conteo)
            "scheduled_shifts_as_primary": 0,   # Total turnos programados originalmente como titular
            "attendance_rate_pct": 100.0,       # Tasa de cumplimiento presencial
            "effective_hours": 0,
            "acupuntura_shifts": 0,
            "tuina_shifts": 0,
            "santiago_shifts": 0,
            "vina_shifts": 0,
            "closed_shifts": 0,
            "monthly_breakdown": {m: 0 for m in range(1, 13)},
            "percentage_of_total": 0.0,
        }

    # 6. Procesar cada turno y asignar al tutor efectivo
    for s in shifts:
        c_obj = campuses.get(s.campus_id)
        is_stgo = bool(c_obj and "CENTRAL" in (c_obj.code or ""))
        is_vina = bool(c_obj and "VINA" in (c_obj.code or ""))

        # Si el turno fue cerrado, no cuenta como efectivo
        if s.status in ["CLOSED", "CANCELLED"]:
            if s.practitioner_id and s.practitioner_id in tutors_metrics:
                tutors_metrics[s.practitioner_id]["closed_shifts"] += 1
            if s.substitute_active and s.substitute_practitioner_id and s.substitute_practitioner_id in tutors_metrics:
                tutors_metrics[s.substitute_practitioner_id]["closed_shifts"] += 1
            continue

        # Turno efectivo: si hay suplente activo, le corresponde al suplente; de lo contrario, al titular.
        # DIRECTIVA DIRECCIÓN CLÍNICA: Los turnos donde el titular NO asistió y estuvo el suplente,
        # NO son considerados en el conteo de turnos del tutor titular.
        eff_tutor_id = None
        role_type = None

        if s.substitute_active and s.substitute_practitioner_id:
            eff_tutor_id = s.substitute_practitioner_id
            role_type = "SUBSTITUTE"

            # Registrar inasistencia del titular cubierto por suplente (NO suma en sus turnos efectivos)
            if s.practitioner_id and s.practitioner_id in tutors_metrics:
                tutors_metrics[s.practitioner_id]["unattended_substituted_shifts"] += 1

        elif s.practitioner_id:
            eff_tutor_id = s.practitioner_id
            role_type = "PRIMARY"

        if eff_tutor_id and eff_tutor_id in tutors_metrics:
            tm = tutors_metrics[eff_tutor_id]
            if role_type == "SUBSTITUTE":
                tm["effective_as_substitute"] += 1
            else:
                tm["effective_as_primary"] += 1
            tm["total_effective_shifts"] += 1
            tm["effective_hours"] += 4

            if s.service_type == "ACUPUNTURA":
                tm["acupuntura_shifts"] += 1
            elif s.service_type == "TUI_NA":
                tm["tuina_shifts"] += 1

            if is_stgo:
                tm["santiago_shifts"] += 1
            elif is_vina:
                tm["vina_shifts"] += 1

            s_month = s.shift_date.month
            tm["monthly_breakdown"][s_month] += 1

    # 7. Totales consolidados y porcentajes
    total_effective = sum(tm["total_effective_shifts"] for tm in tutors_metrics.values())
    total_primary = sum(tm["effective_as_primary"] for tm in tutors_metrics.values())
    total_substitute = sum(tm["effective_as_substitute"] for tm in tutors_metrics.values())
    total_unattended = sum(tm["unattended_substituted_shifts"] for tm in tutors_metrics.values())
    total_hours = sum(tm["effective_hours"] for tm in tutors_metrics.values())
    total_closed = sum(tm["closed_shifts"] for tm in tutors_metrics.values())

    for tm in tutors_metrics.values():
        tm["scheduled_shifts_as_primary"] = tm["effective_as_primary"] + tm["unattended_substituted_shifts"]
        if tm["scheduled_shifts_as_primary"] > 0:
            tm["attendance_rate_pct"] = round((tm["effective_as_primary"] / tm["scheduled_shifts_as_primary"]) * 100, 1)
        else:
            tm["attendance_rate_pct"] = 100.0

        if total_effective > 0:
            tm["percentage_of_total"] = round((tm["total_effective_shifts"] / total_effective) * 100, 1)

    sorted_tutors = sorted(tutors_metrics.values(), key=lambda x: x["total_effective_shifts"], reverse=True)

    top_tutor = None
    if sorted_tutors and sorted_tutors[0]["total_effective_shifts"] > 0:
        top_tutor = {
            "name": sorted_tutors[0]["tutor_name"],
            "license_number": sorted_tutors[0]["license_number"],
            "shifts": sorted_tutors[0]["total_effective_shifts"],
            "hours": sorted_tutors[0]["effective_hours"],
        }

    MONTH_NAMES_ES = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }

    monthly_summary = []
    for m_idx in range(1, 13):
        m_count = sum(tm["monthly_breakdown"][m_idx] for tm in tutors_metrics.values())
        monthly_summary.append({
            "month": m_idx,
            "month_name": MONTH_NAMES_ES.get(m_idx),
            "effective_shifts": m_count,
            "effective_hours": m_count * 4,
        })

    filter_applied = {
        "year": target_year,
        "month": None if is_annual else target_month,
        "month_name": f"Total Anual {target_year}" if is_annual else f"{MONTH_NAMES_ES.get(target_month, f'Mes {target_month}')} {target_year}",
        "is_current_month": (not is_annual and target_year == today.year and target_month == today.month),
        "is_annual": is_annual,
        "campus_id": target_campus.id if target_campus else None,
        "campus_name": target_campus.name if target_campus else "Todas las Sedes",
        "service_type": st_norm,
        "service_type_name": "Todas las Especialidades" if not st_norm else ("Acupuntura" if st_norm == "ACUPUNTURA" else "Tui na"),
    }

    summary = {
        "total_effective_shifts": total_effective,
        "total_primary_shifts": total_primary,
        "total_substitute_shifts": total_substitute,
        "total_unattended_primary_shifts": total_unattended,
        "total_effective_hours": total_hours,
        "total_closed_shifts": total_closed,
        "total_active_tutors": len([t for t in tutors_metrics.values() if t["is_active"]]),
        "top_tutor": top_tutor,
        "accounting_rule": "Los turnos en donde el tutor titular no asistió y estuvo el tutor suplente NO son considerados en el conteo de turnos del tutor titular, computándose al suplente.",
    }

    return APIResponse(
        message=f"Reporte de turnos efectivos por tutor ({filter_applied['month_name']}) obtenido con éxito.",
        data={
            "filter_applied": filter_applied,
            "summary": summary,
            "tutors_metrics": sorted_tutors,
            "monthly_summary": monthly_summary,
        }
    )


# -----------------------------------------------------------------------------
# 6. Asignación Institucional de Secretarias Clínicas a Sedes por Dirección
# -----------------------------------------------------------------------------
@router.get("/secretaries", summary="Listar secretarias clínicas y su sede asignada por Dirección")
def list_clinical_secretaries(
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna la nómina de secretarias clínicas y la sede a la cual están asignadas por Dirección Clínica.
    Aplica para restringir la vista y operación de la secretaria exclusivamente a su sede autorizada.
    """
    ensure_sample_secretaries(db, active_company.id)
    assignments = (
        db.query(ClinicalSecretaryAssignment)
        .filter(
            ClinicalSecretaryAssignment.company_id == active_company.id,
            ClinicalSecretaryAssignment.deleted_at.is_(None),
        )
        .all()
    )

    result = []
    for a in assignments:
        u = db.query(User).filter(User.id == a.user_id).first()
        p = db.query(Person).filter(Person.id == u.person_id).first() if u else None
        c = db.query(Campus).filter(Campus.id == a.campus_id).first()
        campus_key = "santiago" if (c and "CENTRAL" in c.code) else "vina"
        result.append({
            "id": a.id,
            "user_id": a.user_id,
            "username": u.username if u else "N/A",
            "full_name": f"{p.first_name} {p.last_name}" if p else (u.username if u else "N/A"),
            "rut": p.rut if p else "N/A",
            "email": p.email if p else "N/A",
            "campus_id": a.campus_id,
            "campus_code": c.code if c else "N/A",
            "campus_key": campus_key,
            "campus_name": c.name if c else "N/A",
            "city": c.city if c else "N/A",
            "address": c.address if c else "N/A",
            "is_primary": a.is_primary,
            "status": a.status,
            "assignment_date": a.assignment_date.isoformat() if a.assignment_date else None,
            "notes": a.notes,
        })
    return APIResponse(data=result)


@router.put("/secretaries/{user_id}/campus", summary="Dirección Clínica asigna o reasigna la sede a una secretaria")
def assign_secretary_campus(
    user_id: str,
    payload: SecretaryCampusAssignRequest,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Asigna oficialmente la sede de atención (Santiago Providencia o Viña del Mar) a una secretaria clínica.
    Esto restringe de forma vinculante los boxes, turnero y agenda médica que la secretaria puede ver y gestionar.
    """
    ensure_sample_secretaries(db, active_company.id)
    user = db.query(User).filter((User.id == user_id) | (User.username == user_id)).first()
    if not user:
        raise EntityNotFoundException("User", user_id)

    # Identificar sede por campus_id o campus_code
    campus = None
    if payload.campus_id:
        campus = db.query(Campus).filter(Campus.id == payload.campus_id).first()
    elif payload.campus_code:
        code_norm = payload.campus_code.upper().strip()
        if code_norm in ["SANTIAGO", "SEDE-CENTRAL", "CENTRAL", "STGO"]:
            campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
        elif code_norm in ["VINA", "VIÑA", "SEDE-VINA", "VINA DEL MAR", "VIÑA DEL MAR"]:
            campus = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
        else:
            campus = db.query(Campus).filter(Campus.code == payload.campus_code).first()

    if not campus:
        raise SanBaoException("Sede clínica no válida o no encontrada.", status_code=status.HTTP_404_NOT_FOUND)

    assign = db.query(ClinicalSecretaryAssignment).filter(
        ClinicalSecretaryAssignment.company_id == active_company.id,
        ClinicalSecretaryAssignment.user_id == user.id,
        ClinicalSecretaryAssignment.deleted_at.is_(None),
    ).first()

    if not assign:
        assign = ClinicalSecretaryAssignment(
            company_id=active_company.id,
            user_id=user.id,
            campus_id=campus.id,
            is_primary=True,
            status="ACTIVE",
            notes=payload.notes or f"Asignada oficialmente por Dirección Clínica a {campus.name}",
        )
        db.add(assign)
    else:
        assign.campus_id = campus.id
        if payload.notes:
            assign.notes = payload.notes
        assign.status = "ACTIVE"

    db.commit()
    db.refresh(assign)

    person = db.query(Person).filter(Person.id == user.person_id).first()
    campus_key = "santiago" if "CENTRAL" in campus.code else "vina"

    return APIResponse(
        data={
            "id": assign.id,
            "user_id": user.id,
            "username": user.username,
            "full_name": f"{person.first_name} {person.last_name}" if person else user.username,
            "campus_id": campus.id,
            "campus_code": campus.code,
            "campus_key": campus_key,
            "campus_name": campus.name,
            "city": campus.city,
            "notes": assign.notes,
            "message": f"Secretaria {user.username} asignada exitosamente a sede {campus.name}.",
        }
    )


@router.get("/secretaries/my-campus", summary="Obtener la sede autorizada asignada para la secretaria actual")
def get_my_assigned_campus(
    user_id: Optional[str] = Query(None, description="ID o username opcional del usuario secretaria para consultar"),
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna la sede autorizada y asignada por la Dirección Clínica para la secretaria.
    Si la secretaria está asignada a Santiago, solo esa sede se habilitará en su vista.
    """
    ensure_sample_secretaries(db, active_company.id)
    target_user = current_user
    if user_id:
        found = db.query(User).filter((User.id == user_id) | (User.username == user_id)).first()
        if found:
            target_user = found

    assign = db.query(ClinicalSecretaryAssignment).filter(
        ClinicalSecretaryAssignment.company_id == active_company.id,
        ClinicalSecretaryAssignment.user_id == target_user.id,
        ClinicalSecretaryAssignment.deleted_at.is_(None),
    ).first()

    if not assign:
        santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
        return APIResponse(
            data={
                "user_id": target_user.id,
                "username": target_user.username,
                "campus_id": santiago.id if santiago else None,
                "campus_code": "SEDE-CENTRAL",
                "campus_key": "santiago",
                "campus_name": santiago.name if santiago else "Clínica San Bao - Sede Central Santiago",
                "city": santiago.city if santiago else "Santiago",
                "is_restricted": False,
                "notes": "Sin asignación formal; sede central por omisión",
            }
        )

    campus = db.query(Campus).filter(Campus.id == assign.campus_id).first()
    campus_key = "santiago" if (campus and "CENTRAL" in campus.code) else "vina"

    return APIResponse(
        data={
            "assignment_id": assign.id,
            "user_id": target_user.id,
            "username": target_user.username,
            "campus_id": campus.id if campus else None,
            "campus_code": campus.code if campus else "N/A",
            "campus_key": campus_key,
            "campus_name": campus.name if campus else "N/A",
            "city": campus.city if campus else "N/A",
            "address": campus.address if campus else "N/A",
            "is_restricted": True,
            "assigned_by_direction": True,
            "notes": assign.notes,
        }
    )


# -----------------------------------------------------------------------------
# 8. Solicitudes de Pago de Dirección Clínica hacia Área de Finanzas (con Factura Adjunta)
# -----------------------------------------------------------------------------
class ClinicalPaymentRequestCreate(BaseModel):
    supplier_rut: str = Field(..., min_length=3)
    supplier_name: str = Field(..., min_length=2)
    invoice_type: str = "FACTURA_AFECTA_33"
    invoice_number: str = Field(..., min_length=1)
    category: str = "INSUMOS_CLINICOS"
    campus_code: Optional[str] = "SEDE-CENTRAL"
    cost_center: Optional[str] = None
    business_unit: Optional[str] = None
    amount_clp: Decimal = Field(..., gt=0)
    due_date: Optional[date] = None
    concept: str = Field(..., min_length=3)
    attachment_filename: str = Field(..., min_length=1)
    attachment_mime_type: Optional[str] = "application/pdf"
    attachment_data_url: Optional[str] = None
    notes: Optional[str] = None


class ClinicalPaymentRequestPayPayload(BaseModel):
    payment_method: str = "TRANSFER"
    payment_reference: Optional[str] = None
    finance_notes: Optional[str] = None


def ensure_sample_clinical_payment_requests(db: Session, company_id: str):
    """Garantiza solicitudes de pago de muestra desde Dirección Clínica hacia Finanzas con facturas adjuntas."""
    existing = db.query(ClinicalPaymentRequest).filter(ClinicalPaymentRequest.deleted_at.is_(None)).first()
    if existing:
        return

    clinica = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first()
    if not clinica:
        clinica = db.query(Company).first()
    cid = clinica.id if clinica else company_id

    santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    director = db.query(User).filter(User.username == "director").first()

    today = date.today()

    # Crear CxP vinculada para la solicitud 2 (en estado FACTURA_INGRESADA_CXP)
    payable_2 = FinancePayable(
        company_id=cid,
        supplier_rut="77.540.120-K",
        supplier_name="Bioseguridad y Residuos Clínicos REAS Chile Ltda.",
        document_type="FACTURA_PROVEEDOR",
        document_number="FAC-33-44210",
        category="ESTERILIZACION_RESIDUOS",
        cost_center="CC-201 Clínica San Bao - Acupuntura Providencia",
        business_unit="UN-03 Clínica Acupuntura Providencia",
        issue_date=today - timedelta(days=3),
        due_date=today + timedelta(days=12),
        total_amount=Decimal("245000"),
        paid_amount=Decimal("0"),
        balance=Decimal("245000"),
        status="PENDING",
        notes="Ingresada desde Solicitud de Pago SOL-PAG-2026-0002 (Dirección Clínica)",
    )
    db.add(payable_2)

    # Crear CxP pagada vinculada para la solicitud 3 (en estado PAGADA)
    payable_3 = FinancePayable(
        company_id=cid,
        supplier_rut="76.889.310-1",
        supplier_name="Insumos Médicos y Fitoterapia Oriente SpA",
        document_type="FACTURA_PROVEEDOR",
        document_number="FAC-33-19045",
        category="EQUIPAMIENTO_BOX",
        cost_center="CC-202 Clínica San Bao - Sede Viña del Mar & Fitoterapia",
        business_unit="UN-04 Clínica Sede Viña del Mar",
        issue_date=today - timedelta(days=10),
        due_date=today - timedelta(days=2),
        total_amount=Decimal("420000"),
        paid_amount=Decimal("420000"),
        balance=Decimal("0"),
        status="PAID",
        payment_method="TRANSFER",
        paid_at=today - timedelta(days=1),
        notes="Factura pagada por Finanzas • Solicitud SOL-PAG-2026-0003 (Dirección Clínica)",
    )
    db.add(payable_3)
    db.flush()

    samples = [
        ClinicalPaymentRequest(
            company_id=cid,
            campus_id=santiago.id if santiago else None,
            requested_by_user_id=director.id if director else None,
            payable_id=None,
            request_code="SOL-PAG-2026-0001",
            request_date=today - timedelta(days=1),
            due_date=today + timedelta(days=15),
            supplier_rut="76.412.890-3",
            supplier_name="Importadora Agujas DongBang Chile SpA",
            invoice_type="FACTURA_AFECTA_33",
            invoice_number="FAC-33-89412",
            category="INSUMOS_CLINICOS",
            cost_center="CC-201 Clínica San Bao - Acupuntura Providencia",
            business_unit="UN-03 Clínica Acupuntura Providencia",
            amount_clp=Decimal("685000"),
            concept="Reposición trimestral 14 calibres de agujas estériles DongBang y moxas sin humo (Sede Santiago Providencia)",
            attachment_filename="Factura_DTE33_89412_DongBang.pdf",
            attachment_mime_type="application/pdf",
            attachment_data_url=None,
            status="PENDIENTE_FINANZAS",
            notes="Solicitud prioritaria de Dirección Clínica para stock de boxes AM/PM.",
        ),
        ClinicalPaymentRequest(
            company_id=cid,
            campus_id=santiago.id if santiago else None,
            requested_by_user_id=director.id if director else None,
            payable_id=payable_2.id,
            request_code="SOL-PAG-2026-0002",
            request_date=today - timedelta(days=3),
            due_date=today + timedelta(days=12),
            supplier_rut="77.540.120-K",
            supplier_name="Bioseguridad y Residuos Clínicos REAS Chile Ltda.",
            invoice_type="FACTURA_AFECTA_33",
            invoice_number="FAC-33-44210",
            category="ESTERILIZACION_RESIDUOS",
            cost_center="CC-201 Clínica San Bao - Acupuntura Providencia",
            business_unit="UN-03 Clínica Acupuntura Providencia",
            amount_clp=Decimal("245000"),
            concept="Retiro mensual certificado de contenedores cortopunzantes REAS Minsal (Sedes Santiago y Viña del Mar)",
            attachment_filename="Factura_DTE33_44210_REAS_Minsal.pdf",
            attachment_mime_type="application/pdf",
            attachment_data_url=None,
            status="FACTURA_INGRESADA_CXP",
            finance_notes="Factura adjunta revisada e ingresada al Libro CxP por Finanzas. Programada para transferencia.",
            notes="Cumplimiento sanitario D.S. N° 6 MINSAL sobre manejo de residuos de establecimientos de salud.",
        ),
        ClinicalPaymentRequest(
            company_id=cid,
            campus_id=vina.id if vina else None,
            requested_by_user_id=director.id if director else None,
            payable_id=payable_3.id,
            request_code="SOL-PAG-2026-0003",
            request_date=today - timedelta(days=8),
            due_date=today - timedelta(days=2),
            supplier_rut="76.889.310-1",
            supplier_name="Insumos Médicos y Fitoterapia Oriente SpA",
            invoice_type="FACTURA_AFECTA_33",
            invoice_number="FAC-33-19045",
            category="EQUIPAMIENTO_BOX",
            cost_center="CC-202 Clínica San Bao - Sede Viña del Mar & Fitoterapia",
            business_unit="UN-04 Clínica Sede Viña del Mar",
            amount_clp=Decimal("420000"),
            concept="Adquisición de electroestimuladores de acupuntura (6 canales), sets de ventosas clínicas y lámparas TDP (Sede Viña del Mar)",
            attachment_filename="Factura_DTE33_19045_Insumos_Oriente.pdf",
            attachment_mime_type="application/pdf",
            attachment_data_url=None,
            status="PAGADA",
            payment_date=today - timedelta(days=1),
            payment_method="TRANSFER",
            payment_reference="TRF-SANT-994812",
            journal_entry_number="ASI-2026-0009",
            finance_notes="Factura ingresada y pagada vía Transferencia Banco Santander Clínica SpA.",
            notes="Equipamiento recepcionado conforme en Box Shen y Box Jing de Sede Viña del Mar.",
        ),
    ]
    for s in samples:
        db.add(s)
    db.commit()


def _serialize_payment_request(db: Session, r: ClinicalPaymentRequest) -> Dict[str, Any]:
    # Si tiene payable_id asociado y esa CxP ya fue pagada en Finanzas, sincronizar estado automáticamente
    if r.payable_id and r.status != "PAGADA":
        payable = db.query(FinancePayable).filter(FinancePayable.id == r.payable_id).first()
        if payable and payable.status == "PAID":
            r.status = "PAGADA"
            r.payment_date = payable.paid_at or date.today()
            r.payment_method = payable.payment_method or "TRANSFER"
            r.payment_reference = r.payment_reference or f"PAG-CXP-{payable.document_number}"
            db.commit()

    campus = db.query(Campus).filter(Campus.id == r.campus_id).first() if r.campus_id else None
    neto = round(float(r.amount_clp) / 1.19) if "33" in (r.invoice_type or "") else float(r.amount_clp)
    iva = round(float(r.amount_clp) - neto)
    return {
        "id": r.id,
        "request_code": r.request_code,
        "request_date": str(r.request_date),
        "due_date": str(r.due_date),
        "supplier_rut": r.supplier_rut,
        "supplier_name": r.supplier_name,
        "invoice_type": r.invoice_type,
        "invoice_number": r.invoice_number,
        "category": r.category,
        "campus_name": campus.name if campus else "Clínica San Bao - Sede Central Santiago",
        "cost_center": r.cost_center,
        "business_unit": r.business_unit,
        "amount_clp": float(r.amount_clp),
        "net_amount_clp": neto,
        "tax_iva_clp": iva,
        "concept": r.concept,
        "attachment_filename": r.attachment_filename,
        "attachment_mime_type": r.attachment_mime_type or "application/pdf",
        "attachment_data_url": r.attachment_data_url,
        "has_custom_file": bool(r.attachment_data_url),
        "payable_id": r.payable_id,
        "status": r.status,
        "payment_date": str(r.payment_date) if r.payment_date else None,
        "payment_method": r.payment_method,
        "payment_reference": r.payment_reference,
        "journal_entry_number": r.journal_entry_number,
        "finance_notes": r.finance_notes,
        "notes": r.notes,
        "requested_by": "Dr. Roberto Valenzuela (Dirección Clínica)",
    }


@router.get("/payment-requests", summary="Listar solicitudes de pago de Dirección Clínica hacia Finanzas")
def list_clinical_payment_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="ALL | PENDIENTE_FINANZAS | FACTURA_INGRESADA_CXP | PAGADA"),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_clinical_payment_requests(db, active_company.id)

    all_reqs = (
        db.query(ClinicalPaymentRequest)
        .filter(ClinicalPaymentRequest.deleted_at.is_(None))
        .order_by(ClinicalPaymentRequest.request_date.desc(), ClinicalPaymentRequest.created_at.desc())
        .all()
    )

    serialized_all = [_serialize_payment_request(db, r) for r in all_reqs]

    if status_filter and status_filter.upper() != "ALL":
        items = [x for x in serialized_all if x["status"] == status_filter.upper()]
    else:
        items = serialized_all

    total_amount = sum(x["amount_clp"] for x in serialized_all)
    pending_items = [x for x in serialized_all if x["status"] in ("PENDIENTE_FINANZAS", "FACTURA_INGRESADA_CXP")]
    paid_items = [x for x in serialized_all if x["status"] == "PAGADA"]

    return APIResponse(
        data={
            "kpis": {
                "total_count": len(serialized_all),
                "total_amount": total_amount,
                "pending_count": len(pending_items),
                "pending_amount": sum(x["amount_clp"] for x in pending_items),
                "unregistered_count": sum(1 for x in serialized_all if x["status"] == "PENDIENTE_FINANZAS"),
                "registered_cxp_count": sum(1 for x in serialized_all if x["status"] == "FACTURA_INGRESADA_CXP"),
                "paid_count": len(paid_items),
                "paid_amount": sum(x["amount_clp"] for x in paid_items),
            },
            "items": items,
        }
    )


@router.post("/payment-requests", status_code=status.HTTP_201_CREATED, summary="Crear nueva solicitud de pago a Finanzas con factura adjunta")
def create_clinical_payment_request(
    payload: ClinicalPaymentRequestCreate,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, current_user = auth_ctx
    ensure_sample_clinical_payment_requests(db, active_company.id)

    clinica = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first() or active_company
    campus = None
    if payload.campus_code:
        if "VINA" in payload.campus_code.upper() or "VIÑA" in payload.campus_code.upper():
            campus = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
        else:
            campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()

    is_vina = campus and "VINA" in campus.code
    cost_center = payload.cost_center or (
        "CC-202 Clínica San Bao - Sede Viña del Mar & Fitoterapia"
        if is_vina
        else "CC-201 Clínica San Bao - Acupuntura Providencia"
    )
    business_unit = payload.business_unit or (
        "UN-04 Clínica Sede Viña del Mar" if is_vina else "UN-03 Clínica Acupuntura Providencia"
    )

    seq = db.query(ClinicalPaymentRequest).count() + 1
    req_code = f"SOL-PAG-2026-{seq:04d}"
    while db.query(ClinicalPaymentRequest).filter(ClinicalPaymentRequest.request_code == req_code).first():
        seq += 1
        req_code = f"SOL-PAG-2026-{seq:04d}"

    due_dt = payload.due_date or (date.today() + timedelta(days=15))

    new_req = ClinicalPaymentRequest(
        company_id=clinica.id,
        campus_id=campus.id if campus else None,
        requested_by_user_id=current_user.id if current_user else None,
        request_code=req_code,
        request_date=date.today(),
        due_date=due_dt,
        supplier_rut=payload.supplier_rut.strip(),
        supplier_name=payload.supplier_name.strip(),
        invoice_type=payload.invoice_type,
        invoice_number=payload.invoice_number.strip(),
        category=payload.category,
        cost_center=cost_center,
        business_unit=business_unit,
        amount_clp=Decimal(str(payload.amount_clp)),
        concept=payload.concept.strip(),
        attachment_filename=payload.attachment_filename.strip(),
        attachment_mime_type=payload.attachment_mime_type or "application/pdf",
        attachment_data_url=payload.attachment_data_url,
        status="PENDIENTE_FINANZAS",
        notes=payload.notes or "Solicitud de pago emitida por Dirección Clínica con factura adjunta.",
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)

    return APIResponse(
        message=f"Solicitud de Pago {req_code} enviada al Área de Finanzas con la factura adjunta ({new_req.attachment_filename}).",
        data=_serialize_payment_request(db, new_req),
    )


@router.post("/payment-requests/{request_id}/register-payable", summary="Finanzas ingresa la factura adjunta de la solicitud al Libro de Cuentas por Pagar (CxP)")
def register_payment_request_into_cxp(
    request_id: str,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_clinical_payment_requests(db, active_company.id)

    req = (
        db.query(ClinicalPaymentRequest)
        .filter((ClinicalPaymentRequest.id == request_id) | (ClinicalPaymentRequest.request_code == request_id))
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud de pago clínica no encontrada.")

    if req.status == "PAGADA":
        raise HTTPException(status_code=400, detail="Esta solicitud de pago ya se encuentra pagada por Finanzas.")

    payable = None
    if req.payable_id:
        payable = db.query(FinancePayable).filter(FinancePayable.id == req.payable_id).first()

    if not payable:
        payable = FinancePayable(
            company_id=req.company_id,
            supplier_rut=req.supplier_rut,
            supplier_name=req.supplier_name,
            document_type="FACTURA_PROVEEDOR",
            document_number=req.invoice_number,
            category=req.category,
            cost_center=req.cost_center,
            business_unit=req.business_unit,
            issue_date=req.request_date,
            due_date=req.due_date,
            total_amount=req.amount_clp,
            paid_amount=Decimal("0"),
            balance=req.amount_clp,
            status="PENDING",
            notes=f"Factura adjunta ({req.attachment_filename}) ingresada desde Solicitud {req.request_code} de Dirección Clínica: {req.concept}",
        )
        db.add(payable)
        db.flush()
        req.payable_id = payable.id

    req.status = "FACTURA_INGRESADA_CXP"
    req.finance_notes = f"Factura #{req.invoice_number} verificada desde adjunto ({req.attachment_filename}) e ingresada al Libro CxP."
    db.commit()
    db.refresh(req)

    return APIResponse(
        message=f"Factura #{req.invoice_number} ({req.supplier_name}) ingresada exitosamente en Cuentas por Pagar (CxP). Estado actualizado a FACTURA INGRESADA EN CxP.",
        data=_serialize_payment_request(db, req),
    )


@router.post("/payment-requests/{request_id}/pay", summary="Finanzas ingresa/paga la factura adjunta y cambia el estado de la solicitud de Dirección Clínica a PAGADA")
def pay_clinical_payment_request_from_finance(
    request_id: str,
    payload: Optional[ClinicalPaymentRequestPayPayload] = None,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    payload = payload or ClinicalPaymentRequestPayPayload()
    active_company, _ = auth_ctx
    ensure_sample_clinical_payment_requests(db, active_company.id)

    req = (
        db.query(ClinicalPaymentRequest)
        .filter((ClinicalPaymentRequest.id == request_id) | (ClinicalPaymentRequest.request_code == request_id))
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Solicitud de pago clínica no encontrada.")

    if req.status == "PAGADA":
        raise HTTPException(status_code=400, detail="Esta solicitud de pago ya fue pagada previamente por Finanzas.")

    today = date.today()
    method = payload.payment_method or "TRANSFER"

    # 1. Garantizar registro en Libro de Cuentas por Pagar (CxP)
    payable = None
    if req.payable_id:
        payable = db.query(FinancePayable).filter(FinancePayable.id == req.payable_id).first()

    if not payable:
        payable = FinancePayable(
            company_id=req.company_id,
            supplier_rut=req.supplier_rut,
            supplier_name=req.supplier_name,
            document_type="FACTURA_PROVEEDOR",
            document_number=req.invoice_number,
            category=req.category,
            cost_center=req.cost_center,
            business_unit=req.business_unit,
            issue_date=req.request_date,
            due_date=req.due_date,
            total_amount=req.amount_clp,
            paid_amount=req.amount_clp,
            balance=Decimal("0"),
            status="PAID",
            payment_method=method,
            paid_at=today,
            notes=f"Factura adjunta ({req.attachment_filename}) ingresada y pagada desde Solicitud {req.request_code} (Dirección Clínica)",
        )
        db.add(payable)
        db.flush()
        req.payable_id = payable.id
    else:
        payable.paid_amount = payable.total_amount
        payable.balance = Decimal("0")
        payable.status = "PAID"
        payable.payment_method = method
        payable.paid_at = today

    # 2. Registrar Egreso en Tesorería de Clínica San Bao SpA
    ref_num = (payload.payment_reference or "").strip() or f"TRF-CLIN-{req.invoice_number}"
    bank_acc = "Banco Santander • Cta. Cte. N° 0-000-7482910-4 (Clínica SpA)"
    mov = FinanceTreasuryMovement(
        company_id=req.company_id,
        bank_account_name=bank_acc,
        movement_date=today,
        movement_type="EGRESO",
        category=req.category,
        cost_center=req.cost_center,
        business_unit=req.business_unit,
        concept=f"Pago Solicitud Dirección Clínica {req.request_code} • Factura #{req.invoice_number} — {req.supplier_name}",
        counterparty_name=req.supplier_name,
        counterparty_rut=req.supplier_rut,
        amount=req.amount_clp,
        payment_method=method,
        reference_number=ref_num,
        bank_statement_code=f"CART-AUTO-{uuid.uuid4().hex[:5].upper()}",
        bank_reconciled=True,
        reconciled_at=datetime.now(timezone.utc),
    )
    db.add(mov)

    # 3. Registrar Asiento Contable en Libro Diario
    seq = db.query(FinanceJournalEntry).count() + 1
    entry_num = f"ASI-2026-{seq:04d}"
    while db.query(FinanceJournalEntry).filter(FinanceJournalEntry.entry_number == entry_num).first():
        seq += 1
        entry_num = f"ASI-2026-{seq:04d}"

    je = FinanceJournalEntry(
        company_id=req.company_id,
        entry_number=entry_num,
        entry_date=today,
        entry_type="EGRESO",
        glosa=f"Pago Solicitud {req.request_code} (Dirección Clínica) Factura #{req.invoice_number} a {req.supplier_name}",
        account_debit_code="2.1.01",
        account_debit_name="Cuentas por Pagar Proveedores Nacionales (CxP)",
        account_credit_code="1.1.01",
        account_credit_name="Caja y Bancos",
        amount=req.amount_clp,
        cost_center=req.cost_center,
        business_unit=req.business_unit,
        reference_doc=req.invoice_number,
        status="POSTED",
    )
    db.add(je)

    # 4. Actualizar estado de la solicitud de Dirección Clínica a PAGADA
    req.status = "PAGADA"
    req.payment_date = today
    req.payment_method = method
    req.payment_reference = ref_num
    req.journal_entry_number = entry_num
    req.finance_notes = (
        payload.finance_notes
        or f"Factura adjunta ingresada y pagada por Finanzas ({method} • Ref: {ref_num} • Asiento: {entry_num})."
    )

    db.commit()
    db.refresh(req)

    return APIResponse(
        message=f"Solicitud {req.request_code} (Factura #{req.invoice_number}) PAGADA exitosamente por Finanzas. El estado en Dirección Clínica ha cambiado a PAGADA.",
        data=_serialize_payment_request(db, req),
    )


# -----------------------------------------------------------------------------
# 9. Toma de Hora Semanal (Acupuntura / Tui Na), Disponibilidad por Tutor y Sobrecupos Manuales
# -----------------------------------------------------------------------------
OFFICIAL_CLINICAL_SHIFT_HOURS = {
    "ACUPUNTURA": {
        "AM": ["10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30", "11:45", "12:00", "12:20", "12:40", "13:00"],
        "PM": ["15:00", "15:15", "15:30", "15:45", "16:00", "16:15", "16:30", "16:45", "17:00", "17:20", "17:40"],
        "VESPERTINO": ["18:00", "18:15", "18:30", "18:45", "19:00", "19:15", "19:30", "19:45", "20:00", "20:20", "20:40"],
    },
    "TUI_NA": {
        "AM": ["10:15", "10:45", "11:15", "11:45", "12:15", "12:45"],
        "PM": ["15:15", "15:45", "16:15", "16:45", "17:15", "17:45"],
    },
}


class ClinicalOverbookingCreatePayload(BaseModel):
    campus_code: Optional[str] = "santiago"
    campus_id: Optional[str] = None
    service_type: str = "ACUPUNTURA"
    shift_period: str = "AM"
    shift_code: Optional[str] = None
    appointment_date: date
    requested_time: str = Field(..., min_length=3)
    tutor_name: str = Field(..., min_length=2)
    room_name: Optional[str] = None
    box_name: Optional[str] = None
    patient_rut: str = Field(..., min_length=3)
    patient_name: str = Field(..., min_length=2)
    patient_phone: Optional[str] = None
    treatment_name: Optional[str] = "Sesión Acupuntura General"
    reason: str = Field(..., min_length=3)
    requested_by: Optional[str] = "Secretaría Clínica"


class ClinicalOverbookingDecidePayload(BaseModel):
    decision: str = Field(..., description="APPROVE o REJECT")
    authorized_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    decision_notes: Optional[str] = None


def ensure_sample_overbookings(db: Session, company_id: str):
    """Garantiza solicitudes de sobrecupo manual de muestra (Acupuntura y Tui Na) para aprobar en Dirección Clínica."""
    existing = db.query(ClinicalOverbookingRequest).filter(ClinicalOverbookingRequest.deleted_at.is_(None)).first()
    if existing:
        return

    clinica = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first() or db.query(Company).first()
    cid = clinica.id if clinica else company_id
    santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()

    today = date.today()
    # Alinear con lunes de la semana actual
    monday = today - timedelta(days=today.weekday())

    samples = [
        ClinicalOverbookingRequest(
            company_id=cid,
            campus_id=santiago.id if santiago else None,
            request_code="SOB-2026-0001",
            service_type="ACUPUNTURA",
            shift_period="AM",
            appointment_date=monday + timedelta(days=1),  # Martes
            requested_time="10:30",
            tutor_name="Dra. Marcela Pérez Morales",
            room_name="Box de Acupuntura Tai Yang (BOX-01)",
            patient_rut="16.412.890-5",
            patient_name="Carolina Méndez Rojas",
            patient_phone="+56 9 9123 4455",
            treatment_name="Sesión Acupuntura General ($35.000 CLP)",
            reason="Crisis aguda de migraña y cervicalgia; requiere sobrecupo urgente con Dra. Marcela Pérez.",
            status="PENDING",
        ),
        ClinicalOverbookingRequest(
            company_id=cid,
            campus_id=santiago.id if santiago else None,
            request_code="SOB-2026-0002",
            service_type="TUI_NA",
            shift_period="PM",
            appointment_date=monday + timedelta(days=2),  # Miércoles
            requested_time="16:15",
            tutor_name="Dra. Marcela Pérez Morales",
            room_name="Sala Tui na & Masajes (Box Prácticas)",
            patient_rut="14.789.321-K",
            patient_name="Jorge Santander Díaz",
            patient_phone="+56 9 8451 2210",
            treatment_name="Pack 4 Sesiones Masaje Terapéutico Tui Na ($110.000 CLP)",
            reason="Sobrecupo manual en Tui Na PM por contractura lumbar severa previo a viaje laboral.",
            status="PENDING",
        ),
        ClinicalOverbookingRequest(
            company_id=cid,
            campus_id=vina.id if vina else None,
            request_code="SOB-2026-0003",
            service_type="ACUPUNTURA",
            shift_period="VESPERTINO",
            appointment_date=monday + timedelta(days=3),  # Jueves
            requested_time="19:15",
            tutor_name="Dr. Roberto Gómez Valdés",
            room_name="Box Acupuntura Shen (BOX-VINA-01)",
            patient_rut="18.210.540-2",
            patient_name="Valentina Pizarro Silva",
            patient_phone="+56 9 7744 8899",
            treatment_name="Tratamiento Integral Moxa + Ventosas ($42.000 CLP)",
            reason="Continuidad de ciclo de acupuntura analgésica en turno vespertino.",
            status="APPROVED",
            authorized_by="Dr. Roberto Valenzuela (Dirección Clínica)",
            authorized_at=datetime.now(),
            resolution_notes="Sobrecupo autorizado por Dirección Clínica; box y camilla adicional habilitada.",
        ),
    ]
    for s in samples:
        db.add(s)
    db.commit()


def _serialize_overbooking(db: Session, item: ClinicalOverbookingRequest) -> Dict[str, Any]:
    campus = db.query(Campus).filter(Campus.id == item.campus_id).first() if item.campus_id else None
    weekday_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    wname = weekday_names[item.appointment_date.weekday()] if item.appointment_date else ""
    campus_key = "vina" if (campus and "VINA" in campus.code) else "santiago"
    svc_prefix = "TUI" if item.service_type == "TUI_NA" else "ACU"
    camp_prefix = "VINA" if campus_key == "vina" else "STGO"
    per_prefix = "VESP" if item.shift_period == "VESPERTINO" else item.shift_period
    shift_code = f"TUR-{svc_prefix}-{camp_prefix}-{per_prefix}"
    return {
        "id": item.id,
        "request_code": item.request_code,
        "service_type": item.service_type,
        "service_label": "Acupuntura" if item.service_type == "ACUPUNTURA" else "Tui Na",
        "shift_period": item.shift_period,
        "shift_code": shift_code,
        "appointment_date": str(item.appointment_date),
        "weekday_name": wname,
        "requested_time": item.requested_time,
        "tutor_name": item.tutor_name,
        "room_name": item.room_name,
        "box_name": item.room_name,
        "campus_name": campus.name if campus else "Clínica San Bao - Sede Central Santiago",
        "campus_key": campus_key,
        "campus_id": campus_key,
        "patient_rut": item.patient_rut,
        "patient_name": item.patient_name,
        "patient_phone": item.patient_phone or "+56 9 1234 5678",
        "treatment_name": item.treatment_name or "Sesión Clínica MTC",
        "reason": item.reason,
        "requested_by": "Secretaría / Recepción Clínica",
        "status": item.status,
        "authorized_by": item.authorized_by,
        "authorized_at": item.authorized_at.strftime("%Y-%m-%d %H:%M") if item.authorized_at else None,
        "resolution_notes": item.resolution_notes,
        "decision_notes": item.resolution_notes,
    }


@router.get("/overbookings", summary="Listar solicitudes de sobrecupo manual (Acupuntura y Tui Na)")
def list_clinical_overbookings(
    status_filter: Optional[str] = Query(None, alias="status", description="ALL | PENDING | APPROVED | REJECTED"),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_overbookings(db, active_company.id)

    all_items = (
        db.query(ClinicalOverbookingRequest)
        .filter(ClinicalOverbookingRequest.deleted_at.is_(None))
        .order_by(ClinicalOverbookingRequest.appointment_date.asc(), ClinicalOverbookingRequest.created_at.desc())
        .all()
    )
    serialized = [_serialize_overbooking(db, x) for x in all_items]

    if status_filter and status_filter.upper() != "ALL":
        filtered = [x for x in serialized if x["status"] == status_filter.upper()]
    else:
        filtered = serialized

    return APIResponse(
        data={
            "kpis": {
                "total_count": len(serialized),
                "pending_count": sum(1 for x in serialized if x["status"] == "PENDING"),
                "approved_count": sum(1 for x in serialized if x["status"] == "APPROVED"),
                "rejected_count": sum(1 for x in serialized if x["status"] == "REJECTED"),
                "acupuntura_count": sum(1 for x in serialized if x["service_type"] == "ACUPUNTURA"),
                "tuina_count": sum(1 for x in serialized if x["service_type"] == "TUI_NA"),
            },
            "official_shift_hours": OFFICIAL_CLINICAL_SHIFT_HOURS,
            "items": filtered,
        }
    )


@router.post("/overbookings", status_code=status.HTTP_201_CREATED, summary="Crear solicitud de sobrecupo manual (Acupuntura o Tui Na) para autorización de Dirección Clínica")
def create_clinical_overbooking_request(
    payload: ClinicalOverbookingCreatePayload,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_overbookings(db, active_company.id)

    clinica = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first() or active_company
    campus = None
    campus_ref = (payload.campus_id or payload.campus_code or "santiago").lower()
    if "vina" in campus_ref or "viña" in campus_ref:
        campus = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
    else:
        campus = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()

    seq = db.query(ClinicalOverbookingRequest).count() + 1
    req_code = f"SOB-2026-{seq:04d}"
    while db.query(ClinicalOverbookingRequest).filter(ClinicalOverbookingRequest.request_code == req_code).first():
        seq += 1
        req_code = f"SOB-2026-{seq:04d}"

    stype = "TUI_NA" if "TUI" in (payload.service_type or "").upper() else "ACUPUNTURA"
    sper = (payload.shift_period or "AM").upper()

    item = ClinicalOverbookingRequest(
        company_id=clinica.id,
        campus_id=campus.id if campus else None,
        request_code=req_code,
        service_type=stype,
        shift_period=sper,
        appointment_date=payload.appointment_date,
        requested_time=payload.requested_time.strip(),
        tutor_name=payload.tutor_name.strip(),
        room_name=(payload.room_name or payload.box_name or "Box Clínico Asignado").strip(),
        patient_rut=payload.patient_rut.strip(),
        patient_name=payload.patient_name.strip(),
        patient_phone=(payload.patient_phone or "+56 9 1234 5678").strip(),
        treatment_name=(payload.treatment_name or "Sesión Clínica MTC").strip(),
        reason=payload.reason.strip(),
        status="PENDING",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return APIResponse(
        message=f"Solicitud de Sobrecupo {req_code} ({'Tui Na' if stype == 'TUI_NA' else 'Acupuntura'} • {sper} {item.requested_time} hrs) enviada al módulo de Dirección Clínica para su aprobación.",
        data=_serialize_overbooking(db, item),
    )


@router.post("/overbookings/{overbooking_id}/decide", summary="Dirección Clínica aprueba o rechaza una solicitud de sobrecupo manual")
def decide_clinical_overbooking_request(
    overbooking_id: str,
    payload: ClinicalOverbookingDecidePayload,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_overbookings(db, active_company.id)

    item = (
        db.query(ClinicalOverbookingRequest)
        .filter(
            (ClinicalOverbookingRequest.id == overbooking_id)
            | (ClinicalOverbookingRequest.request_code == overbooking_id)
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitud de sobrecupo no encontrada.")

    dec = (payload.decision or "").upper().strip()
    if dec in ("APPROVE", "APPROVED", "APROBAR", "APROBADO"):
        item.status = "APPROVED"
        item.authorized_by = "Dr. Roberto Valenzuela (Dirección Clínica)"
        item.authorized_at = datetime.now()
        item.resolution_notes = (
            payload.resolution_notes
            or "Sobrecupo manual autorizado por Dirección Clínica e incorporado a la agenda semanal."
        )
        msg = f"Sobrecupo {item.request_code} para {item.patient_name} ({item.appointment_date} {item.requested_time} hrs con {item.tutor_name}) APROBADO por Dirección Clínica."
    else:
        item.status = "REJECTED"
        item.authorized_by = "Dr. Roberto Valenzuela (Dirección Clínica)"
        item.authorized_at = datetime.now()
        item.resolution_notes = payload.resolution_notes or "Sobrecupo rechazado por capacidad máxima de box."
        msg = f"Solicitud de sobrecupo {item.request_code} RECHAZADA por Dirección Clínica."

    db.commit()
    db.refresh(item)

    return APIResponse(
        message=msg,
        data=_serialize_overbooking(db, item),
    )


# -----------------------------------------------------------------------------
# 11. Cierre de Turnos por Jornada (Día, Semana, Mes o Indefinidamente) y
#     Nómina de Pacientes Afectados enviada a Gestión Clínica con Propuesta
#     de Nueva Hora para Reagendar (WhatsApp Directo o Llamada Telefónica)
# -----------------------------------------------------------------------------
from urllib.parse import quote


class AffectedPatientManagePayload(BaseModel):
    action: str = Field(..., description="SEND_WHATSAPP | LOG_PHONE_CALL | CONFIRM_RESCHEDULE | UPDATE_PROPOSAL")
    proposed_date: Optional[date] = None
    proposed_time: Optional[str] = None
    proposed_tutor_name: Optional[str] = None
    proposed_shift_code: Optional[str] = None
    contact_notes: Optional[str] = None
    handled_by: Optional[str] = "Secretaría / Gestión Clínica"


class AffectedPatientsBulkCreatePayload(BaseModel):
    shift_code: str = "TUR-ACU-STGO-AM"
    service_type: str = "ACUPUNTURA"
    shift_period: str = "AM"
    closure_scope: str = "DAY"  # DAY, WEEK, MONTH, INDEFINITE
    closure_dates_text: str = "03/11/2026"
    closure_reason: str = "Cierre de jornada por Dirección Clínica"
    campus_code: Optional[str] = "santiago"
    tutor_name: str = "Dra. Marcela Pérez Morales"
    box_name: str = "Box de Acupuntura Tai Yang (BOX-01)"
    patients: Optional[List[Dict[str, Any]]] = None


def _build_whatsapp_and_tel_links(item: ClinicalShiftClosureAffectedPatient) -> Dict[str, str]:
    raw_digits = "".join(ch for ch in (item.patient_phone or "") if ch.isdigit())
    if not raw_digits.startswith("56") and len(raw_digits) == 9:
        raw_digits = "56" + raw_digits
    if not raw_digits:
        raw_digits = "56991234567"

    scope_labels = {
        "DAY": "por el día",
        "SINGLE_DATE": "por el día",
        "WEEK": "por la semana",
        "MONTH": "por el mes",
        "INDEFINITE": "de forma indefinida",
        "PERMANENT": "de forma indefinida",
    }
    scope_txt = scope_labels.get((item.closure_scope or "DAY").upper(), "por disposición clínica")
    svc_label = "Acupuntura" if item.service_type == "ACUPUNTURA" else "Tui na"

    wa_message = (
        f"Estimado(a) {item.patient_name}, le escribimos de Clínica San Bao SpA. "
        f"Le informamos que el turno de {svc_label} ({item.shift_period}) con {item.tutor_name} "
        f"donde tenía hora agendada el {item.original_date.strftime('%d/%m/%Y')} a las {item.original_time} hrs "
        f"ha sido cerrado {scope_txt} ({item.closure_dates_text} • Motivo: {item.closure_reason}). "
        f"Le proponemos reagendar su atención para el día {item.proposed_date.strftime('%d/%m/%Y')} "
        f"a las {item.proposed_time} hrs con {item.proposed_tutor_name}. "
        f"¿Nos confirma si le acomoda esta nueva hora?"
    )
    return {
        "whatsapp_message": wa_message,
        "whatsapp_url": f"https://wa.me/{raw_digits}?text={quote(wa_message)}",
        "tel_url": f"tel:+{raw_digits}",
    }


def _serialize_affected_patient(db: Session, item: ClinicalShiftClosureAffectedPatient) -> Dict[str, Any]:
    campus = db.query(Campus).filter(Campus.id == item.campus_id).first() if item.campus_id else None
    campus_key = "vina" if (campus and "VINA" in campus.code) else "santiago"
    links = _build_whatsapp_and_tel_links(item)
    scope_badge_map = {
        "DAY": "Por Día",
        "SINGLE_DATE": "Por Día",
        "WEEK": "Por Semana",
        "MONTH": "Por Mes",
        "INDEFINITE": "Indefinidamente",
        "PERMANENT": "Indefinidamente",
        "DATE_RANGE": "Rango de Fechas",
    }
    return {
        "id": item.id,
        "closure_code": item.closure_code,
        "shift_code": item.shift_code,
        "service_type": item.service_type,
        "service_label": "Acupuntura" if item.service_type == "ACUPUNTURA" else "Tui na",
        "shift_period": item.shift_period,
        "closure_scope": item.closure_scope,
        "closure_scope_label": scope_badge_map.get((item.closure_scope or "DAY").upper(), item.closure_scope),
        "closure_dates_text": item.closure_dates_text,
        "closure_reason": item.closure_reason,
        "campus_id": campus_key,
        "campus_name": campus.name if campus else "Clínica San Bao - Sede Central Santiago",
        "tutor_name": item.tutor_name,
        "box_name": item.box_name,
        "patient_rut": item.patient_rut,
        "patient_name": item.patient_name,
        "patient_phone": item.patient_phone,
        "treatment_name": item.treatment_name or "Sesión Clínica MTC",
        "original_date": str(item.original_date),
        "original_time": item.original_time,
        "proposed_date": str(item.proposed_date),
        "proposed_time": item.proposed_time,
        "proposed_tutor_name": item.proposed_tutor_name,
        "proposed_shift_code": item.proposed_shift_code,
        "contact_channel": item.contact_channel,
        "contact_notes": item.contact_notes or "",
        "status": item.status,
        "notified_at": item.notified_at.strftime("%Y-%m-%d %H:%M") if item.notified_at else None,
        "rescheduled_at": item.rescheduled_at.strftime("%Y-%m-%d %H:%M") if item.rescheduled_at else None,
        "handled_by": item.handled_by or "Pendiente Gestión Clínica",
        "whatsapp_message": links["whatsapp_message"],
        "whatsapp_url": links["whatsapp_url"],
        "tel_url": links["tel_url"],
    }


def ensure_sample_shift_closure_affected_patients(db: Session, company_id: str):
    """Garantiza registros de muestra en el panel de Gestión Clínica de pacientes afectados por cierre de turno."""
    existing = (
        db.query(ClinicalShiftClosureAffectedPatient)
        .filter(ClinicalShiftClosureAffectedPatient.deleted_at.is_(None))
        .first()
    )
    if existing:
        return

    clinica = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first() or db.query(Company).first()
    cid = clinica.id if clinica else company_id
    santiago = db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    vina = db.query(Campus).filter(Campus.code == "SEDE-VINA").first()

    base_date = date(2026, 11, 3)
    samples = [
        ClinicalShiftClosureAffectedPatient(
            company_id=cid,
            campus_id=santiago.id if santiago else None,
            closure_code="CIE-2026-0001",
            shift_code="TUR-ACU-STGO-AM",
            service_type="ACUPUNTURA",
            shift_period="AM",
            closure_scope="DAY",
            closure_dates_text="03/11/2026 (Cierre por Día)",
            closure_reason="Jornada Académica / Capacitación Docente MTC",
            tutor_name="Dra. Marcela Pérez Morales",
            box_name="Box de Acupuntura Tai Yang (BOX-01)",
            patient_rut="17.123.456-5",
            patient_name="Rodrigo Silva",
            patient_phone="+56 9 9123 4567",
            treatment_name="Sesión Acupuntura General ($35.000 CLP)",
            original_date=base_date,
            original_time="10:00",
            proposed_date=base_date + timedelta(days=1),
            proposed_time="10:15",
            proposed_tutor_name="Dra. Marcela Pérez Morales",
            proposed_shift_code="TUR-ACU-STGO-AM",
            contact_channel="NONE",
            status="PENDING_CONTACT",
            contact_notes="Enviado automáticamente desde Dirección Clínica al cerrar jornada AM.",
        ),
        ClinicalShiftClosureAffectedPatient(
            company_id=cid,
            campus_id=santiago.id if santiago else None,
            closure_code="CIE-2026-0002",
            shift_code="TUR-TUI-STGO-PM",
            service_type="TUI_NA",
            shift_period="PM",
            closure_scope="WEEK",
            closure_dates_text="Semana del 02/11/2026 al 07/11/2026 (Cierre por Semana)",
            closure_reason="Mantención / Sanitización y Desinfección de Boxes",
            tutor_name="Dra. Marcela Pérez Morales",
            box_name="Sala Tui na & Masajes (Box Prácticas)",
            patient_rut="15.987.654-3",
            patient_name="Andrea Castro P.",
            patient_phone="+56 9 8765 4321",
            treatment_name="Sesión Tui na Terapéutico ($32.000 CLP)",
            original_date=base_date + timedelta(days=1),
            original_time="15:45",
            proposed_date=base_date + timedelta(days=7),
            proposed_time="15:45",
            proposed_tutor_name="Lic. Patricia Soto Henríquez",
            proposed_shift_code="TUR-TUI-STGO-AM",
            contact_channel="WHATSAPP",
            status="PROPOSAL_SENT_WHATSAPP",
            notified_at=datetime.now(),
            handled_by="Valentina Morales (Secretaría Clínica)",
            contact_notes="Propuesta enviada por WhatsApp directo desde el portal.",
        ),
        ClinicalShiftClosureAffectedPatient(
            company_id=cid,
            campus_id=vina.id if vina else None,
            closure_code="CIE-2026-0003",
            shift_code="TUR-ACU-VINA-VESP",
            service_type="ACUPUNTURA",
            shift_period="VESPERTINO",
            closure_scope="INDEFINITE",
            closure_dates_text="Indefinidamente desde el 04/11/2026",
            closure_reason="Licencia Médica / Permiso Administrativo del Terapeuta",
            tutor_name="Dr. Roberto Gómez Valdés",
            box_name="Box Acupuntura Shen (BOX-VINA-01)",
            patient_rut="16.890.123-4",
            patient_name="Matías Fuenzalida",
            patient_phone="+56 9 7654 3210",
            treatment_name="Sesión Acupuntura General ($35.000 CLP)",
            original_date=base_date + timedelta(days=1),
            original_time="18:30",
            proposed_date=base_date + timedelta(days=2),
            proposed_time="15:30",
            proposed_tutor_name="Lic. Patricia Soto Henríquez",
            proposed_shift_code="TUR-ACU-VINA-PM",
            contact_channel="NONE",
            status="PENDING_CONTACT",
            contact_notes="Turno vespertino cerrado indefinidamente; se propone traspaso a Turno PM.",
        ),
    ]
    for s in samples:
        db.add(s)
    db.commit()


def _register_affected_patients_for_closed_shift(
    db: Session,
    company_id: str,
    shift: ClinicalShiftSchedule,
    closure_scope: str,
    c_start: date,
    c_end: Optional[date],
    custom_patients: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    ensure_sample_shift_closure_affected_patients(db, company_id)

    tutor_name = "Dra. Marcela Pérez Morales"
    if shift.practitioner and shift.practitioner.person:
        tutor_name = f"Dr(a). {shift.practitioner.person.first_name} {shift.practitioner.person.last_name}"

    box_name = shift.room.name if shift.room else "Box de Acupuntura Tai Yang (BOX-01)"
    service_type = shift.service_type or "ACUPUNTURA"
    shift_period = shift.shift_period or "AM"
    slots = OFFICIAL_CLINICAL_SHIFT_HOURS.get(service_type, {}).get(shift_period) or ["10:00", "10:15", "10:30"]

    # Calcular fecha propuesta según el alcance del cierre (Día -> +1 día, Semana -> +7 días, Mes -> mes sig., Indefinido -> otro turno +1 día)
    scope_norm = (closure_scope or "DAY").upper()
    if scope_norm == "WEEK":
        base_proposed_date = (c_end or (c_start + timedelta(days=6))) + timedelta(days=1)
    elif scope_norm == "MONTH":
        base_proposed_date = (c_end or (c_start + timedelta(days=28))) + timedelta(days=1)
    else:
        base_proposed_date = c_start + timedelta(days=1)
    if base_proposed_date.weekday() == 6:  # Evitar domingo
        base_proposed_date += timedelta(days=1)

    seq = db.query(ClinicalShiftClosureAffectedPatient).count() + 1
    closure_code = f"CIE-2026-{seq:04d}"

    patients_to_create = custom_patients
    if not patients_to_create:
        # Generar nómina de pacientes con hora agendada en el turno cerrado
        patients_to_create = [
            {
                "patient_rut": "17.123.456-5",
                "patient_name": "Rodrigo Silva",
                "patient_phone": "+56 9 9123 4567",
                "treatment_name": "Sesión Acupuntura General ($35.000 CLP)" if service_type == "ACUPUNTURA" else "Sesión Tui na Terapéutico ($32.000 CLP)",
                "original_date": str(c_start),
                "original_time": slots[0],
                "proposed_date": str(base_proposed_date),
                "proposed_time": slots[min(1, len(slots) - 1)],
            },
            {
                "patient_rut": "18.765.432-1",
                "patient_name": "Camila Soto M.",
                "patient_phone": "+56 9 8456 7890",
                "treatment_name": "Sesión de Control y Seguimiento ($28.000 CLP)" if service_type == "ACUPUNTURA" else "Sesión Tui na Terapéutico ($32.000 CLP)",
                "original_date": str(c_start),
                "original_time": slots[min(2, len(slots) - 1)],
                "proposed_date": str(base_proposed_date),
                "proposed_time": slots[min(3, len(slots) - 1)],
            },
        ]

    created_records = []
    for idx, p in enumerate(patients_to_create):
        orig_d = p.get("original_date")
        if isinstance(orig_d, str):
            try:
                orig_d = date.fromisoformat(orig_d)
            except Exception:
                orig_d = c_start
        elif not isinstance(orig_d, date):
            orig_d = c_start

        prop_d = p.get("proposed_date")
        if isinstance(prop_d, str):
            try:
                prop_d = date.fromisoformat(prop_d)
            except Exception:
                prop_d = base_proposed_date
        elif not isinstance(prop_d, date):
            prop_d = base_proposed_date

        rec = ClinicalShiftClosureAffectedPatient(
            company_id=company_id,
            campus_id=shift.campus_id,
            shift_id=shift.id,
            closure_code=closure_code,
            shift_code=shift.shift_code,
            service_type=service_type,
            shift_period=shift_period,
            closure_scope=scope_norm,
            closure_dates_text=shift.closure_dates_text or str(c_start),
            closure_reason=shift.closure_reason or "Cierre de jornada por Dirección Clínica",
            tutor_name=p.get("tutor_name") or tutor_name,
            box_name=p.get("box_name") or box_name,
            patient_rut=p.get("patient_rut") or "17.123.456-5",
            patient_name=p.get("patient_name") or "Paciente Citado",
            patient_phone=p.get("patient_phone") or "+56 9 9123 4567",
            treatment_name=p.get("treatment_name") or "Sesión Clínica MTC",
            original_date=orig_d,
            original_time=p.get("original_time") or slots[min(idx, len(slots) - 1)],
            proposed_date=prop_d,
            proposed_time=p.get("proposed_time") or slots[min(idx + 1, len(slots) - 1)],
            proposed_tutor_name=p.get("proposed_tutor_name") or tutor_name,
            proposed_shift_code=p.get("proposed_shift_code") or shift.shift_code,
            contact_channel="NONE",
            status="PENDING_CONTACT",
            contact_notes=f"Turno cerrado ({shift.closure_dates_text}). Enviado por Dirección Clínica a Gestión Clínica.",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        created_records.append(_serialize_affected_patient(db, rec))

    return created_records


@router.get(
    "/shift-closures/affected-patients",
    summary="Listar nómina de pacientes afectados por cierre de turnos enviada a Gestión Clínica con propuesta de nueva hora",
)
def list_shift_closure_affected_patients(
    status_filter: Optional[str] = Query(None, alias="status"),
    campus_filter: Optional[str] = Query(None, alias="campus"),
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_shift_closure_affected_patients(db, active_company.id)

    all_items = (
        db.query(ClinicalShiftClosureAffectedPatient)
        .filter(ClinicalShiftClosureAffectedPatient.deleted_at.is_(None))
        .order_by(ClinicalShiftClosureAffectedPatient.created_at.desc())
        .all()
    )
    serialized = [_serialize_affected_patient(db, x) for x in all_items]

    filtered = serialized
    if status_filter and status_filter.upper() != "ALL":
        filtered = [x for x in filtered if x["status"] == status_filter.upper()]
    if campus_filter and campus_filter.lower() not in ("all", ""):
        filtered = [x for x in filtered if x["campus_id"] == campus_filter.lower()]

    return APIResponse(
        data={
            "kpis": {
                "total_count": len(serialized),
                "pending_count": sum(1 for x in serialized if x["status"] == "PENDING_CONTACT"),
                "whatsapp_sent_count": sum(1 for x in serialized if x["status"] == "PROPOSAL_SENT_WHATSAPP"),
                "phone_called_count": sum(1 for x in serialized if x["status"] == "CONTACTED_PHONE"),
                "rescheduled_count": sum(1 for x in serialized if x["status"] == "RESCHEDULED"),
            },
            "official_shift_hours": OFFICIAL_CLINICAL_SHIFT_HOURS,
            "items": filtered,
        }
    )


@router.post(
    "/shift-closures/affected-patients",
    status_code=status.HTTP_201_CREATED,
    summary="Generar y enviar desde Dirección Clínica la nómina de pacientes afectados por cierre de turno a Gestión Clínica",
)
def create_shift_closure_affected_patients_batch(
    payload: AffectedPatientsBulkCreatePayload,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_shift_closure_affected_patients(db, active_company.id)

    clinica = db.query(Company).filter(Company.trade_name.ilike("%San Bao%")).first() or active_company
    campus = (
        db.query(Campus).filter(Campus.code == "SEDE-VINA").first()
        if payload.campus_code and "vina" in payload.campus_code.lower()
        else db.query(Campus).filter(Campus.code == "SEDE-CENTRAL").first()
    )

    seq = db.query(ClinicalShiftClosureAffectedPatient).count() + 1
    closure_code = f"CIE-2026-{seq:04d}"
    stype = "TUI_NA" if "TUI" in (payload.service_type or "").upper() else "ACUPUNTURA"
    sper = (payload.shift_period or "AM").upper()
    slots = OFFICIAL_CLINICAL_SHIFT_HOURS.get(stype, {}).get(sper) or ["10:00", "10:15", "10:30"]

    patients_input = payload.patients or [
        {
            "patient_rut": "17.123.456-5",
            "patient_name": "Rodrigo Silva",
            "patient_phone": "+56 9 9123 4567",
            "original_date": str(date.today()),
            "original_time": slots[0],
            "proposed_date": str(date.today() + timedelta(days=1)),
            "proposed_time": slots[min(1, len(slots) - 1)],
        }
    ]

    created_items = []
    for idx, p in enumerate(patients_input):
        orig_d_str = p.get("original_date") or str(date.today())
        prop_d_str = p.get("proposed_date") or str(date.today() + timedelta(days=1))
        try:
            orig_d = date.fromisoformat(orig_d_str)
        except Exception:
            orig_d = date.today()
        try:
            prop_d = date.fromisoformat(prop_d_str)
        except Exception:
            prop_d = orig_d + timedelta(days=1)

        rec = ClinicalShiftClosureAffectedPatient(
            company_id=clinica.id,
            campus_id=campus.id if campus else None,
            closure_code=closure_code,
            shift_code=payload.shift_code,
            service_type=stype,
            shift_period=sper,
            closure_scope=(payload.closure_scope or "DAY").upper(),
            closure_dates_text=payload.closure_dates_text,
            closure_reason=payload.closure_reason,
            tutor_name=p.get("tutor_name") or payload.tutor_name,
            box_name=p.get("box_name") or payload.box_name,
            patient_rut=p.get("patient_rut") or "17.123.456-5",
            patient_name=p.get("patient_name") or "Paciente Citado",
            patient_phone=p.get("patient_phone") or "+56 9 9123 4567",
            treatment_name=p.get("treatment_name") or "Sesión Clínica MTC",
            original_date=orig_d,
            original_time=p.get("original_time") or slots[min(idx, len(slots) - 1)],
            proposed_date=prop_d,
            proposed_time=p.get("proposed_time") or slots[min(idx + 1, len(slots) - 1)],
            proposed_tutor_name=p.get("proposed_tutor_name") or payload.tutor_name,
            proposed_shift_code=p.get("proposed_shift_code") or payload.shift_code,
            contact_channel="NONE",
            status="PENDING_CONTACT",
            contact_notes=f"Nómina enviada desde Dirección Clínica por cierre ({payload.closure_dates_text}).",
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        created_items.append(_serialize_affected_patient(db, rec))

    return APIResponse(
        message=f"Se envió a Gestión Clínica la nómina con {len(created_items)} paciente(s) afectado(s) por el cierre del turno {payload.shift_code}.",
        data=created_items,
    )


@router.post(
    "/shift-closures/affected-patients/{item_id}/manage",
    summary="Gestionar paciente afectado en Gestión Clínica: enviar WhatsApp, registrar llamada telefónica o confirmar reagendamiento",
)
def manage_shift_closure_affected_patient(
    item_id: str,
    payload: AffectedPatientManagePayload,
    auth_ctx=Depends(get_active_company_and_user_flexible),
    db: Session = Depends(get_db),
):
    active_company, _ = auth_ctx
    ensure_sample_shift_closure_affected_patients(db, active_company.id)

    item = (
        db.query(ClinicalShiftClosureAffectedPatient)
        .filter(
            (ClinicalShiftClosureAffectedPatient.id == item_id)
            | (ClinicalShiftClosureAffectedPatient.closure_code == item_id)
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Registro de paciente afectado no encontrado.")

    if payload.proposed_date:
        item.proposed_date = payload.proposed_date
    if payload.proposed_time:
        item.proposed_time = payload.proposed_time.strip()
    if payload.proposed_tutor_name:
        item.proposed_tutor_name = payload.proposed_tutor_name.strip()
    if payload.proposed_shift_code:
        item.proposed_shift_code = payload.proposed_shift_code.strip()
    if payload.handled_by:
        item.handled_by = payload.handled_by.strip()

    act = (payload.action or "").upper().strip()
    if act == "SEND_WHATSAPP":
        item.contact_channel = "WHATSAPP"
        item.status = "PROPOSAL_SENT_WHATSAPP"
        item.notified_at = datetime.now()
        item.contact_notes = (
            payload.contact_notes
            or f"Propuesta de nueva hora ({item.proposed_date} • {item.proposed_time} hrs) enviada por WhatsApp directo al {item.patient_phone}."
        )
        msg = f"Propuesta de reagendamiento enviada por WhatsApp a {item.patient_name} ({item.patient_phone})."
    elif act == "LOG_PHONE_CALL":
        item.contact_channel = "PHONE_CALL"
        item.status = "CONTACTED_PHONE"
        item.notified_at = datetime.now()
        item.contact_notes = (
            payload.contact_notes
            or f"Contacto vía llamada telefónica al {item.patient_phone}; se ofreció nueva hora {item.proposed_date} a las {item.proposed_time} hrs."
        )
        msg = f"Gestión vía llamada telefónica registrada para {item.patient_name} ({item.patient_phone})."
    elif act == "CONFIRM_RESCHEDULE":
        if item.contact_channel == "NONE":
            item.contact_channel = "WHATSAPP"
        item.status = "RESCHEDULED"
        item.rescheduled_at = datetime.now()
        item.contact_notes = (
            payload.contact_notes
            or f"Hora reagendada y confirmada para el {item.proposed_date} a las {item.proposed_time} hrs con {item.proposed_tutor_name}."
        )
        msg = (
            f"Hora de {item.patient_name} reagendada exitosamente para el {item.proposed_date} "
            f"a las {item.proposed_time} hrs ({item.proposed_tutor_name})."
        )
    else:
        item.contact_notes = payload.contact_notes or item.contact_notes
        msg = f"Propuesta de reagendamiento actualizada para {item.patient_name}."

    db.commit()
    db.refresh(item)

    return APIResponse(
        message=msg,
        data=_serialize_affected_patient(db, item),
    )




