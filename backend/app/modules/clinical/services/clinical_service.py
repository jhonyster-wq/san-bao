from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.modules.clinical.models.patient import Patient
from app.modules.clinical.models.practitioner import Practitioner
from app.modules.clinical.models.appointment import Appointment
from app.modules.clinical.models.encounter import ClinicalEncounter
from app.modules.clinical.models.access_log import ClinicalAccessLog
from app.modules.clinical.schemas.patient import PatientCreate, PatientUpdate
from app.modules.clinical.schemas.practitioner import PractitionerCreate
from app.modules.clinical.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.modules.clinical.schemas.encounter import EncounterCreate, EncounterUpdate, EncounterSignRequest
from app.modules.academic.services.academic_service import AcademicService
from app.modules.academic.schemas.evaluation import ClinicalPracticeHourCreate
from app.modules.institutional.models.person import Person
from app.modules.institutional.models.user import User
from app.modules.institutional.models.rbac import UserCompanyRole, Role, Permission
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, PermissionDeniedException, SanBaoException


class ClinicalService:
    def __init__(self, db: Session):
        self.db = db

    def _assert_can_access_clinical_anamnesis(
        self,
        user_id: Optional[str],
        patient_id: str,
        encounter_id: Optional[str] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> None:
        """
        Verifica cumplimiento de la Matriz de Seguridad y Ley 20.584 (Requerimiento M):
        El perfil ADMIN_FINANZAS tiene explícitamente prohibido el acceso a la anamnesis y ficha clínica.
        """
        if not user_id:
            return
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or user.is_superuser:
            return

        user_roles = (
            self.db.query(Role)
            .join(UserCompanyRole, UserCompanyRole.role_id == Role.id)
            .filter(
                UserCompanyRole.user_id == user_id,
                UserCompanyRole.is_active == True,
                UserCompanyRole.deleted_at.is_(None),
            )
            .all()
        )
        role_codes = {r.code for r in user_roles}
        has_clinical_read = any(
            any(p.code == "clinical:records:read" for p in (r.permissions or []))
            for r in user_roles
        )
        clinical_allowed_roles = {"TUTOR_CLINICO", "TERAPEUTA", "DIRECCION_CLINICA", "ALUMNO_PRACTICA", "SUPERADMIN"}

        if ("ADMIN_FINANZAS" in role_codes or "FINANZAS" in role_codes) and not (
            has_clinical_read or (role_codes & clinical_allowed_roles)
        ):
            self._log_access(
                patient_id=patient_id,
                encounter_id=encounter_id,
                user_id=user_id,
                action="DENIED_ANAMNESIS_ACCESS_FINANCE",
                ip=ip,
                ua=ua,
            )
            raise PermissionDeniedException(
                "Acceso denegado (Ley 20.584 / Matriz RBAC): El rol ADMIN_FINANZAS no tiene acceso a la anamnesis ni ficha clínica."
            )

    # --------------------------------------------------------------------------
    # Registro y Ficha de Pacientes
    # --------------------------------------------------------------------------
    def create_patient(self, data: PatientCreate) -> Patient:
        person = self.db.query(Person).filter(Person.id == data.person_id, Person.deleted_at.is_(None)).first()
        if not person:
            raise EntityNotFoundException("Persona", data.person_id)

        existing = self.db.query(Patient).filter(Patient.person_id == data.person_id, Patient.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Paciente", "persona", data.person_id)

        if not data.record_number:
            year = date.today().year
            count = self.db.query(Patient).filter(Patient.record_number.like(f"FICH-{year}-%")).count()
            record_number = f"FICH-{year}-{count + 1:04d}"
        else:
            record_number = data.record_number.strip().upper()

        patient = Patient(
            person_id=data.person_id,
            record_number=record_number,
            emergency_contact_name=data.emergency_contact_name,
            emergency_contact_phone=data.emergency_contact_phone,
            emergency_contact_relationship=data.emergency_contact_relationship,
            blood_type=data.blood_type,
            allergies=data.allergies,
            chronic_conditions=data.chronic_conditions,
            general_notes=data.general_notes,
            is_active=data.is_active,
        )
        self.db.add(patient)
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def get_patient(self, patient_id: str, user_id: str, ip: str = None, ua: str = None) -> Patient:
        """Obtiene la ficha del paciente registrando inmutablemente el acceso (Ley 20.584)."""
        patient = self.db.query(Patient).filter(Patient.id == patient_id, Patient.deleted_at.is_(None)).first()
        if not patient:
            raise EntityNotFoundException("Paciente", patient_id)

        self._log_access(patient_id=patient.id, user_id=user_id, action="VIEW_RECORD", ip=ip, ua=ua)
        return patient

    def list_patients(self, search: Optional[str] = None, skip: int = 0, limit: int = 50) -> Tuple[List[Patient], int]:
        q = self.db.query(Patient).join(Person).filter(Patient.deleted_at.is_(None))
        if search:
            s = f"%{search.strip()}%"
            q = q.filter((Person.first_name.ilike(s)) | (Person.last_name.ilike(s)) | (Person.rut.ilike(s)) | (Patient.record_number.ilike(s)))
        total = q.count()
        patients = q.offset(skip).limit(limit).all()
        return patients, total

    # --------------------------------------------------------------------------
    # Profesionales y Terapeutas
    # --------------------------------------------------------------------------
    def create_practitioner(self, data: PractitionerCreate) -> Practitioner:
        person = self.db.query(Person).filter(Person.id == data.person_id, Person.deleted_at.is_(None)).first()
        if not person:
            raise EntityNotFoundException("Persona", data.person_id)

        practitioner = Practitioner(
            person_id=data.person_id,
            license_number=data.license_number,
            specialty=data.specialty,
            is_tutor=data.is_tutor,
            is_active=data.is_active,
        )
        self.db.add(practitioner)
        self.db.commit()
        self.db.refresh(practitioner)
        return practitioner

    def list_practitioners(self, only_active: bool = True, only_tutors: bool = False) -> List[Practitioner]:
        q = self.db.query(Practitioner).filter(Practitioner.deleted_at.is_(None))
        if only_active:
            q = q.filter(Practitioner.is_active == True)
        if only_tutors:
            q = q.filter(Practitioner.is_tutor == True)
        return q.all()

    # --------------------------------------------------------------------------
    # Agenda Médica y Boxes
    # --------------------------------------------------------------------------
    def create_appointment(self, data: AppointmentCreate, company_id: str) -> Appointment:
        patient = self.db.query(Patient).filter(Patient.id == data.patient_id, Patient.deleted_at.is_(None)).first()
        if not patient:
            raise EntityNotFoundException("Paciente", data.patient_id)

        practitioner = self.db.query(Practitioner).filter(Practitioner.id == data.practitioner_id, Practitioner.deleted_at.is_(None)).first()
        if not practitioner:
            raise EntityNotFoundException("Terapeuta", data.practitioner_id)

        # Validación institucional de Dirección Clínica: Terapeuta debe estar activo/habilitado
        if not practitioner.is_active:
            raise SanBaoException("El terapeuta se encuentra bloqueado o inactivo por Dirección Clínica")

        # Validación institucional de Dirección Clínica: Horario y Turno asignado (titular o suplente activo)
        from app.modules.clinical.models.management import ClinicalShiftSchedule
        practitioner_shifts = (
            self.db.query(ClinicalShiftSchedule)
            .filter(
                (
                    (ClinicalShiftSchedule.practitioner_id == data.practitioner_id)
                    | (
                        (ClinicalShiftSchedule.substitute_active == True)
                        & (ClinicalShiftSchedule.substitute_practitioner_id == data.practitioner_id)
                    )
                ),
                ClinicalShiftSchedule.shift_date == data.appointment_date,
                ClinicalShiftSchedule.deleted_at.is_(None),
            )
            .all()
        )
        if practitioner_shifts:
            open_shifts = []
            for s in practitioner_shifts:
                if s.status == "CLOSED":
                    # Si el turno fue cerrado indicando fecha única o rango de fechas
                    is_date_closed = False
                    if s.closure_start_date and s.closure_end_date:
                        if s.closure_start_date <= data.appointment_date <= s.closure_end_date:
                            is_date_closed = True
                    elif s.closure_start_date:
                        if s.closure_start_date == data.appointment_date:
                            is_date_closed = True
                    else:
                        is_date_closed = True

                    if not is_date_closed:
                        open_shifts.append(s)
                else:
                    open_shifts.append(s)

            if not open_shifts:
                closure_info = ""
                closed_with_dates = [s for s in practitioner_shifts if s.closure_dates_text]
                if closed_with_dates:
                    closure_info = f" (Fechas de Cierre: {closed_with_dates[0].closure_dates_text} - Motivo: {closed_with_dates[0].closure_reason or 'Dirección Clínica'})"
                raise SanBaoException(f"Todos los turnos asignados por Dirección Clínica para este terapeuta se encuentran CERRADOS{closure_info}")
            matching_shift = next(
                (s for s in open_shifts if s.start_time <= data.start_time and data.end_time <= s.end_time),
                None
            )
            if not matching_shift:
                shift_descriptions = ", ".join(f"{s.shift_name} ({s.start_time}-{s.end_time})" for s in open_shifts)
                raise SanBaoException(
                    f"El horario {data.start_time}-{data.end_time} está fuera de los turnos designados por Dirección Clínica ({shift_descriptions})"
                )

        # Verificar solapamiento de horario en el mismo Box
        box_overlap = (
            self.db.query(Appointment)
            .filter(
                Appointment.room_id == data.room_id,
                Appointment.appointment_date == data.appointment_date,
                Appointment.status.notin_(["CANCELLED", "NO_SHOW"]),
                Appointment.start_time < data.end_time,
                Appointment.end_time > data.start_time,
                Appointment.deleted_at.is_(None),
            )
            .first()
        )
        if box_overlap:
            raise SanBaoException(f"El Box ya se encuentra ocupado en el bloque horario {data.start_time}-{data.end_time}")

        # Verificar solapamiento de agenda del terapeuta
        practitioner_overlap = (
            self.db.query(Appointment)
            .filter(
                Appointment.practitioner_id == data.practitioner_id,
                Appointment.appointment_date == data.appointment_date,
                Appointment.status.notin_(["CANCELLED", "NO_SHOW"]),
                Appointment.start_time < data.end_time,
                Appointment.end_time > data.start_time,
                Appointment.deleted_at.is_(None),
            )
            .first()
        )
        if practitioner_overlap:
            raise SanBaoException("El profesional ya posee una atención agendada en ese horario")

        appointment = Appointment(
            company_id=company_id,
            patient_id=data.patient_id,
            practitioner_id=data.practitioner_id,
            student_id=data.student_id,
            campus_id=data.campus_id,
            room_id=data.room_id,
            appointment_date=data.appointment_date,
            start_time=data.start_time,
            end_time=data.end_time,
            reason=data.reason,
            notes=data.notes,
            status=data.status,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        # Descuento y seguimiento de packs de tratamiento del paciente (Dirección Clínica)
        try:
            from app.modules.clinical.models.management import PatientTreatmentPack, ClinicalSessionPrice
            if getattr(data, "discount_pack_session", True):
                pack_q = self.db.query(PatientTreatmentPack).filter(
                    PatientTreatmentPack.patient_id == data.patient_id,
                    PatientTreatmentPack.status == "ACTIVE",
                    PatientTreatmentPack.remaining_sessions > 0,
                    PatientTreatmentPack.deleted_at.is_(None),
                )
                target_pack_id = getattr(data, "patient_pack_id", None)
                if target_pack_id:
                    pack = pack_q.filter(PatientTreatmentPack.id == target_pack_id).first()
                else:
                    pack = pack_q.order_by(PatientTreatmentPack.created_at.asc()).first()

                if pack:
                    pack.used_sessions += 1
                    pack.remaining_sessions = max(0, pack.total_sessions - pack.used_sessions)
                    if pack.remaining_sessions == 0:
                        pack.status = "EXHAUSTED"
                    self.db.commit()

            # Renovación de pack al tomar hora (mismo tipo u otro arancel) si fue seleccionada
            renew_price_id = getattr(data, "renew_session_price_id", None)
            if renew_price_id:
                price_item = self.db.query(ClinicalSessionPrice).filter(
                    ClinicalSessionPrice.id == renew_price_id,
                    ClinicalSessionPrice.deleted_at.is_(None),
                ).first()
                if price_item:
                    new_pack = PatientTreatmentPack(
                        company_id=company_id,
                        patient_id=data.patient_id,
                        session_price_id=price_item.id,
                        pack_name=price_item.name,
                        service_type=price_item.service_type or "ACUPUNTURA",
                        total_sessions=price_item.session_count or 1,
                        used_sessions=0,
                        remaining_sessions=price_item.session_count or 1,
                        price_paid_clp=price_item.price_clp,
                        status="ACTIVE",
                        purchase_date=date.today(),
                        notes=f"Renovación de pack gestionada al agendar cita {appointment.id}",
                    )
                    self.db.add(new_pack)
                    self.db.commit()
        except Exception:
            pass

        return appointment

    def list_appointments(self, appointment_date: Optional[date] = None, practitioner_id: Optional[str] = None, patient_id: Optional[str] = None) -> List[Appointment]:
        q = self.db.query(Appointment).filter(Appointment.deleted_at.is_(None))
        if appointment_date:
            q = q.filter(Appointment.appointment_date == appointment_date)
        if practitioner_id:
            q = q.filter(Appointment.practitioner_id == practitioner_id)
        if patient_id:
            q = q.filter(Appointment.patient_id == patient_id)
        return q.order_by(Appointment.appointment_date.asc(), Appointment.start_time.asc()).all()

    # --------------------------------------------------------------------------
    # Ficha de Atención Clínica MTC y Supervisión Pedagógica
    # --------------------------------------------------------------------------
    def create_encounter(self, data: EncounterCreate, user_id: str, ip: str = None, ua: str = None) -> ClinicalEncounter:
        patient = self.db.query(Patient).filter(Patient.id == data.patient_id, Patient.deleted_at.is_(None)).first()
        if not patient:
            raise EntityNotFoundException("Paciente", data.patient_id)

        practitioner = self.db.query(Practitioner).filter(Practitioner.id == data.practitioner_id, Practitioner.deleted_at.is_(None)).first()
        if not practitioner:
            raise EntityNotFoundException("Terapeuta", data.practitioner_id)

        # Validación institucional de Dirección Clínica: Terapeuta debe estar activo/habilitado
        if not practitioner.is_active:
            raise SanBaoException("El terapeuta se encuentra bloqueado o inactivo por Dirección Clínica")

        # Si interviene un alumno en práctica, inicia como borrador (DRAFT)
        initial_status = "DRAFT" if data.student_id else "VALIDATED"

        import json as _json
        from datetime import timedelta
        from app.core.security import AES256FieldCipher

        sensitive_snapshot = _json.dumps(
            {
                "reason_for_consultation": data.reason_for_consultation,
                "current_illness_history": data.current_illness_history,
                "zang_fu_syndrome": data.zang_fu_syndrome,
            },
            ensure_ascii=False,
        )
        encrypted_payload = AES256FieldCipher.encrypt(sensitive_snapshot)
        retention_until = date.today().replace(year=date.today().year + 15)

        encounter = ClinicalEncounter(
            patient_id=data.patient_id,
            appointment_id=data.appointment_id,
            practitioner_id=data.practitioner_id,
            student_id=data.student_id,
            reason_for_consultation=data.reason_for_consultation,
            current_illness_history=data.current_illness_history,
            traditional_anamnesis=data.traditional_anamnesis.model_dump() if data.traditional_anamnesis else {},
            tongue_diagnosis=data.tongue_diagnosis.model_dump() if data.tongue_diagnosis else {},
            pulse_diagnosis=data.pulse_diagnosis.model_dump() if data.pulse_diagnosis else {},
            zang_fu_syndrome=data.zang_fu_syndrome,
            eight_principles=data.eight_principles or {},
            therapeutic_principle=data.therapeutic_principle,
            treatment_plan=data.treatment_plan.model_dump() if data.treatment_plan else {},
            recommendations=data.recommendations,
            status=initial_status,
            encrypted_sensitive_payload=encrypted_payload,
            retention_until_date=retention_until,
        )
        self.db.add(encounter)
        self.db.commit()
        self.db.refresh(encounter)

        # Si había cita agendada, marcarla como completada
        if data.appointment_id:
            appt = self.db.query(Appointment).filter(Appointment.id == data.appointment_id).first()
            if appt:
                appt.status = "COMPLETED"
                self.db.commit()

        self._log_access(patient_id=data.patient_id, encounter_id=encounter.id, user_id=user_id, action="CREATE_ENCOUNTER", ip=ip, ua=ua)
        return encounter

    def get_encounter(self, encounter_id: str, user_id: str, ip: str = None, ua: str = None) -> ClinicalEncounter:
        encounter = self.db.query(ClinicalEncounter).filter(ClinicalEncounter.id == encounter_id, ClinicalEncounter.deleted_at.is_(None)).first()
        if not encounter:
            raise EntityNotFoundException("Atención Clínica", encounter_id)

        self._assert_can_access_clinical_anamnesis(
            user_id=user_id,
            patient_id=encounter.patient_id,
            encounter_id=encounter.id,
            ip=ip,
            ua=ua,
        )
        self._log_access(patient_id=encounter.patient_id, encounter_id=encounter.id, user_id=user_id, action="VIEW_ENCOUNTER", ip=ip, ua=ua)
        return encounter

    def update_encounter(self, encounter_id: str, data: EncounterUpdate) -> ClinicalEncounter:
        encounter = self.db.query(ClinicalEncounter).filter(ClinicalEncounter.id == encounter_id, ClinicalEncounter.deleted_at.is_(None)).first()
        if not encounter:
            raise EntityNotFoundException("Atención Clínica", encounter_id)

        if encounter.status == "SIGNED":
            raise SanBaoException("No es posible modificar una atención clínica que ya ha sido sellada y firmada digitalmente.")

        update_dict = data.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            if val is not None and hasattr(val, "model_dump"):
                setattr(encounter, key, val.model_dump())
            elif val is not None:
                setattr(encounter, key, val)

        self.db.commit()
        self.db.refresh(encounter)
        return encounter

    def sign_encounter(
        self,
        encounter_id: str,
        sign_data: EncounterSignRequest,
        signing_user_id: str,
        ip: str = None,
        ua: str = None,
    ) -> ClinicalEncounter:
        """
        Sella y firma electrónicamente la atención médica.
        Si la atención fue realizada por un estudiante bajo supervisión:
        1. Almacena la retroalimentación y nota pedagógica del tutor.
        2. Sella legalmente la ficha con status = 'SIGNED'.
        3. Invoca a AcademicService para acreditar automáticamente las horas prácticas en el expediente del alumno.
        """
        encounter = self.db.query(ClinicalEncounter).filter(ClinicalEncounter.id == encounter_id, ClinicalEncounter.deleted_at.is_(None)).first()
        if not encounter:
            raise EntityNotFoundException("Atención Clínica", encounter_id)

        if encounter.status == "SIGNED":
            raise SanBaoException("La atención clínica ya se encuentra firmada.")

        now = datetime.now(timezone.utc)
        encounter.status = "SIGNED"
        encounter.signed_at = now
        encounter.signed_by = signing_user_id

        if sign_data.tutor_feedback:
            encounter.tutor_feedback = sign_data.tutor_feedback
        if sign_data.tutor_grade:
            encounter.tutor_grade = sign_data.tutor_grade

        # Vínculo e integración con Gestión Académica si hubo estudiante involucrado
        if encounter.student_id:
            practitioner = encounter.practitioner
            academic_service = AcademicService(self.db)
            practice_payload = ClinicalPracticeHourCreate(
                student_id=encounter.student_id,
                tutor_id=practitioner.person_id,
                activity_date=encounter.encounter_date.date() if isinstance(encounter.encounter_date, datetime) else date.today(),
                hours_completed=sign_data.hours_to_credit,
                patient_encounter_id=encounter.id,
                comments=f"Atención clínica acreditada ({encounter.zang_fu_syndrome or 'Atención General MTC'})",
            )
            academic_service.log_clinical_practice_hours(practice_payload)

        self.db.commit()
        self.db.refresh(encounter)

        self._log_access(patient_id=encounter.patient_id, encounter_id=encounter.id, user_id=signing_user_id, action="SIGN_ENCOUNTER", ip=ip, ua=ua)
        return encounter

    # --------------------------------------------------------------------------
    # Auditoría Médica Inmutable (Ley 20.584)
    # --------------------------------------------------------------------------
    def _log_access(self, patient_id: str, user_id: str, action: str, encounter_id: str = None, ip: str = None, ua: str = None):
        log = ClinicalAccessLog(
            patient_id=patient_id,
            encounter_id=encounter_id,
            user_id=user_id,
            action=action,
            ip_address=ip,
            user_agent=ua,
        )
        self.db.add(log)
        self.db.commit()

    def get_patient_access_logs(self, patient_id: str) -> List[ClinicalAccessLog]:
        return (
            self.db.query(ClinicalAccessLog)
            .filter(ClinicalAccessLog.patient_id == patient_id)
            .order_by(ClinicalAccessLog.created_at.desc())
            .all()
        )

    def delete_encounter_respecting_15_year_retention(self, encounter_id: str, user_id: str) -> None:
        """
        Requerimiento M (Ley 20.584):
        Para fichas clínicas, contempla conservación obligatoria por al menos 15 años.
        Bloquea cualquier intento de eliminación antes de cumplirse los 15 años.
        """
        encounter = (
            self.db.query(ClinicalEncounter)
            .filter(ClinicalEncounter.id == encounter_id, ClinicalEncounter.deleted_at.is_(None))
            .first()
        )
        if not encounter:
            raise EntityNotFoundException("Atención Clínica", encounter_id)

        enc_date = encounter.encounter_date.date() if isinstance(encounter.encounter_date, datetime) else date.today()
        min_retention_until = encounter.retention_until_date or enc_date.replace(year=enc_date.year + 15)

        if date.today() < min_retention_until:
            self._log_access(
                patient_id=encounter.patient_id,
                encounter_id=encounter.id,
                user_id=user_id,
                action="BLOCKED_DELETE_15Y_RETENTION_LAW_20584",
            )
            raise PermissionDeniedException(
                f"Conservación Legal Obligatoria (Ley 20.584 / Requerimiento M): Las fichas clínicas deben conservarse por al menos 15 años (protegida hasta {min_retention_until.isoformat()}). Eliminación prohibida."
            )

    def export_patient_clinical_record_portability(
        self,
        patient_id: str,
        user_id: str,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> dict:
        """
        Requerimiento M (Ley 20.584, Ley 19.628 y Ley 21.719):
        Mecanismo de entrega y portabilidad de la ficha clínica para el paciente,
        descifrando el respaldo AES-256 para usuario autorizado y registrando el evento en auditoría.
        """
        import hashlib
        import json as _json
        from app.core.security import AES256FieldCipher

        patient = self.get_patient(patient_id=patient_id, user_id=user_id, ip=ip, ua=ua)
        self._assert_can_access_clinical_anamnesis(user_id=user_id, patient_id=patient.id, ip=ip, ua=ua)

        encounters = (
            self.db.query(ClinicalEncounter)
            .filter(ClinicalEncounter.patient_id == patient.id, ClinicalEncounter.deleted_at.is_(None))
            .order_by(ClinicalEncounter.encounter_date.asc())
            .all()
        )
        encounters_list = []
        for enc in encounters:
            enc_dt = enc.encounter_date.date() if isinstance(enc.encounter_date, datetime) else date.today()
            ret_until = enc.retention_until_date or enc_dt.replace(year=enc_dt.year + 15)
            decrypted_verified = False
            if enc.encrypted_sensitive_payload:
                try:
                    dec_str = AES256FieldCipher.decrypt(enc.encrypted_sensitive_payload)
                    decrypted_verified = len(dec_str) > 0
                except Exception:
                    decrypted_verified = False
            encounters_list.append({
                "encounter_id": enc.id,
                "encounter_date": enc.encounter_date.isoformat() if enc.encounter_date else None,
                "reason_for_consultation": enc.reason_for_consultation,
                "zang_fu_syndrome": enc.zang_fu_syndrome,
                "therapeutic_principle": enc.therapeutic_principle,
                "recommendations": enc.recommendations,
                "status": enc.status,
                "aes256_encrypted_at_rest": bool(enc.encrypted_sensitive_payload),
                "aes256_integrity_verified": decrypted_verified,
                "minimum_retention_until": ret_until.isoformat(),
                "retention_years_mandate": 15,
            })

        self._log_access(
            patient_id=patient.id,
            user_id=user_id,
            action="EXPORT_PORTABILITY_LAW_20584",
            ip=ip,
            ua=ua,
        )
        payload_hash = hashlib.sha256(_json.dumps(encounters_list, sort_keys=True).encode("utf-8")).hexdigest()
        return {
            "portability_standard": "CL-MINSAL-LEY-20584-21719-PORTABLE-JSON-V1",
            "patient_id": patient.id,
            "record_number": patient.record_number,
            "patient_rut": patient.person.rut if patient.person else "",
            "patient_name": patient.person.full_name if patient.person else "Paciente",
            "minimum_retention_years": 15,
            "encryption_standard": "AES-256-GCM (Separate Key Management)",
            "encounters_count": len(encounters_list),
            "encounters": encounters_list,
            "portability_package_sha256": payload_hash,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

