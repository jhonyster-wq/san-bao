from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.clinical.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.modules.clinical.services.clinical_service import ClinicalService
from app.shared.responses import APIResponse

router = APIRouter(prefix="/clinical/appointments", tags=["Clínica: Agenda Médica y Boxes"])


@router.post("", response_model=APIResponse[AppointmentResponse], status_code=status.HTTP_201_CREATED, summary="Agendar hora de atención en Box")
def create_appointment(
    payload: AppointmentCreate,
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Agenda una atención en un box clínico específico, validando que no existan
    solapamientos ni del terapeuta ni de la disponibilidad física del box.
    """
    service = ClinicalService(db)
    try:
        appointment = service.create_appointment(payload, company_id=active_company.id)
        return APIResponse(message="Atención agendada exitosamente", data=appointment)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=APIResponse[List[AppointmentResponse]], summary="Consultar agenda clínica")
def list_appointments(
    appointment_date: Optional[date] = Query(None, description="Fecha de atención"),
    practitioner_id: Optional[str] = Query(None, description="Filtrar por profesional"),
    patient_id: Optional[str] = Query(None, description="Filtrar por paciente"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ClinicalService(db)
    appointments = service.list_appointments(
        appointment_date=appointment_date,
        practitioner_id=practitioner_id,
        patient_id=patient_id,
    )
    return APIResponse(data=appointments)


@router.get("/available-slots", summary="Consultar horas disponibles según turnos designados por Dirección Clínica")
def get_available_slots_by_shift(
    campus_id: Optional[str] = Query(None, description="ID o código de Sede (santiago / vina)"),
    appointment_date: Optional[date] = Query(None, description="Fecha de consulta"),
    practitioner_id: Optional[str] = Query(None, description="Filtrar por terapeuta"),
    service_type: Optional[str] = Query(None, description="Tipo de turno: ACUPUNTURA o TUI_NA"),
    active_company: Company = Depends(require_company_context),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retorna la grilla de terapeutas, turnos oficiales, boxes y bloques horarios
    autorizados por Dirección Clínica para agendamiento de pacientes.
    """
    from app.modules.clinical.models.management import ClinicalShiftSchedule
    from app.modules.clinical.models.practitioner import Practitioner
    from app.modules.institutional.models.person import Person
    from app.modules.institutional.models.campus import Campus, Room
    from app.modules.clinical.models.appointment import Appointment
    from app.modules.clinical.routers.management import ensure_sample_shifts

    ensure_sample_shifts(db, active_company.id)
    query_date = appointment_date or date.today()

    q = db.query(ClinicalShiftSchedule).filter(
        ClinicalShiftSchedule.company_id == active_company.id,
        ClinicalShiftSchedule.deleted_at.is_(None),
        ClinicalShiftSchedule.status != "CLOSED",
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

    if practitioner_id:
        q = q.filter(ClinicalShiftSchedule.practitioner_id == practitioner_id)

    if service_type:
        st_norm = service_type.upper().replace("-", "_").replace(" ", "_")
        q = q.filter(ClinicalShiftSchedule.service_type == st_norm)

    shifts = q.all()

    results = []
    for s in shifts:
        practitioner = db.query(Practitioner).filter(Practitioner.id == s.practitioner_id).first()
        if not practitioner or not practitioner.is_active:
            continue

        person = db.query(Person).filter(Person.id == practitioner.person_id).first()
        campus = db.query(Campus).filter(Campus.id == s.campus_id).first()
        room = db.query(Room).filter(Room.id == s.room_id).first()

        # Bloques horarios oficiales por especialidad y turno (Acupuntura y Tui Na)
        OFFICIAL_SHIFT_SLOTS = {
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
        stype_key = (s.service_type or "ACUPUNTURA").upper()
        sper_key = (s.shift_period or "AM").upper()
        slot_times = OFFICIAL_SHIFT_SLOTS.get(stype_key, OFFICIAL_SHIFT_SLOTS["ACUPUNTURA"]).get(sper_key, [])

        slots = []
        for idx, t_str in enumerate(slot_times):
            curr_h, curr_m = map(int, t_str.split(":"))
            dur = 30 if stype_key == "TUI_NA" else (20 if idx >= 8 else 15)
            end_total = curr_h * 60 + curr_m + dur
            next_h, next_m = end_total // 60, end_total % 60
            end_str = f"{next_h:02d}:{next_m:02d}"

            is_booked = (
                db.query(Appointment)
                .filter(
                    Appointment.practitioner_id == practitioner.id,
                    Appointment.appointment_date == query_date,
                    Appointment.status.notin_(["CANCELLED", "NO_SHOW"]),
                    Appointment.start_time == t_str,
                    Appointment.deleted_at.is_(None),
                )
                .first()
                is not None
            )

            slots.append({
                "time_slot": t_str,
                "start_time": t_str,
                "end_time": end_str,
                "is_available": not is_booked,
            })

        results.append({
            "shift_id": s.id,
            "shift_code": s.shift_code,
            "shift_name": s.shift_name,
            "service_type": s.service_type,
            "shift_period": s.shift_period,
            "day_schedule": s.day_schedule,
            "shift_window": f"{s.start_time} - {s.end_time}",
            "status": s.status,
            "campus_id": s.campus_id,
            "campus_name": campus.name if campus else "Sede San Bao",
            "room_id": s.room_id,
            "room_name": room.name if room else "Box Asignado",
            "practitioner_id": practitioner.id,
            "practitioner_name": f"{person.first_name} {person.last_name}" if person else "Terapeuta",
            "practitioner_specialty": practitioner.specialty,
            "practitioner_license": practitioner.license_number,
            "accredited_by": "Dirección Clínica San Bao (Dr. Roberto Valenzuela)",
            "slots": slots,
        })

    return APIResponse(data=results)
