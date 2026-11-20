from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FreezeStudentRequest(BaseModel):
    reason: str = Field(..., description="Motivo del congelamiento (Salud, Laboral, Económico, Personal)")
    effective_date: Optional[date] = Field(default_factory=date.today)
    notes: Optional[str] = None


class UnfreezeStudentRequest(BaseModel):
    effective_date: Optional[date] = Field(default_factory=date.today)
    notes: Optional[str] = None


class TransferStudentRequest(BaseModel):
    to_program_id: str = Field(..., description="ID del nuevo diplomado o curso de destino")
    reason: str = Field(..., description="Motivo justificado del traspaso o cambio de curso")
    effective_date: Optional[date] = Field(default_factory=date.today)
    authorized_by: Optional[str] = Field("Coordinación Académica - Escuela San Bao", description="B.2: Autorizador responsable del cambio de curso")
    authorization_code: Optional[str] = Field(None, description="B.2: Folio de autorización opcional")
    notes: Optional[str] = None


class ApproveClinicalRequest(BaseModel):
    approved: bool = Field(True, description="True para aprobar, False para revocar")
    approval_date: Optional[date] = Field(default_factory=date.today)
    notes: Optional[str] = None


class CoordinatorGradeEntryRequest(BaseModel):
    cohort_id: str = Field(..., description="ID de la cohorte o sección")
    student_id: str = Field(..., description="ID del estudiante")
    evaluation_name: str = Field(..., description="Nombre de la evaluación (Certamen 1, Control Acupuntura, Examen Final)")
    score: float = Field(..., ge=1.0, le=7.0, description="Calificación en escala chilena 1.0 a 7.0")
    weight_percentage: float = Field(25.0, ge=1.0, le=100.0, description="Ponderación porcentual")
    feedback: Optional[str] = None


class IssueDocumentRequest(BaseModel):
    student_id: str = Field(..., description="ID del alumno")
    document_type: str = Field(..., description="ALUMNO_REGULAR, CERTIFICADO_CURSO, DOCUMENTACION_EGRESO, DIPLOMA_EGRESO")
    program_id: Optional[str] = None
    course_id: Optional[str] = None
    notes: Optional[str] = None


class AssignInternToShiftRequest(BaseModel):
    student_id: str = Field(..., description="ID del alumno aprobado para práctica clínica")
    notes: Optional[str] = None


class InitiateOnboardingRequest(BaseModel):
    rut: str = Field(..., description="RUT del postulante (ej: 19.876.543-0)")
    first_name: Optional[str] = Field(None, description="Nombres del postulante")
    last_name: Optional[str] = Field(None, description="Apellido paterno")
    second_last_name: Optional[str] = Field(None, description="Apellido materno")
    full_name: Optional[str] = Field(None, description="Nombre completo alternativo")
    email: str = Field(..., description="Correo electrónico donde se enviará el link de firma electrónica")
    phone: Optional[str] = Field("+56 9 8000 0000", description="Teléfono móvil de contacto")
    program_id: str = Field(..., description="ID de la carrera/diplomado/curso del Catálogo")
    campus: Optional[str] = Field("SANTIAGO", description="Sede de matrícula: SANTIAGO o VINA_DEL_MAR")
    enrollment_fee: Optional[float] = Field(None, description="Valor de matrícula precargado desde el catálogo")
    tuition_amount: Optional[float] = Field(None, description="Arancel total precargado desde el catálogo")
    installments_count: Optional[int] = Field(10, ge=1, le=24, description="Número de cuotas del arancel")
    first_due_date: Optional[str] = Field(None, description="Fecha primer vencimiento opcional")
    guarantor_name: Optional[str] = Field(None, description="Nombre del codeudor/avalista opcional")
    guarantor_rut: Optional[str] = Field(None, description="RUT del codeudor/avalista opcional")
    admission_application_id: Optional[str] = Field(None, description="ID de la entrevista/ficha de admisión origen")
    life_record_notes: Optional[str] = Field(None, description="Descripción opcional para la Hoja de Vida del alumno ingresada en la entrevista")
    hoja_de_vida_descripcion: Optional[str] = Field(None, description="Alias de life_record_notes")


class SignOnboardingContractRequest(BaseModel):
    signer_ip: Optional[str] = Field("190.161.42.18", description="IP desde donde el alumno firma electrónicamente")
    otp_code: Optional[str] = Field("849201", description="Código de verificación de correo/OTP")


class ConfirmOnboardingWebpayRequest(BaseModel):
    card_type: Optional[str] = Field("REDCOMPRA_DEBITO", description="REDCOMPRA_DEBITO o VISA_CREDITO")
    card_last4: Optional[str] = Field("4821", description="Últimos 4 dígitos de la tarjeta")
    authorization_code: Optional[str] = Field(None, description="Código de autorización Transbank")


class StudentPortalLoginRequest(BaseModel):
    rut: str = Field(..., description="RUT del alumno regular")
    password: str = Field(..., description="Contraseña segura generada al confirmar matrícula")


class StudentLifeRecordUpdateRequest(BaseModel):
    phone: Optional[str] = Field(None, description="Teléfono de contacto actualizado")
    email: Optional[str] = Field(None, description="Correo electrónico actualizado")
    address: Optional[str] = Field(None, description="Dirección particular actualizada")
    observation_type: Optional[str] = Field("ACADEMICA", description="ACADEMICA, CLINICA, MERITO, CONDUCTUAL, FINANCIERA")
    observation_text: Optional[str] = Field(None, description="Nueva anotación u observación en la Hoja de Vida del alumno")
    author: Optional[str] = Field("Coordinación Académica San Bao", description="Responsable del registro")


class SecretariatSendCourseEmailRequest(BaseModel):
    program_id: Optional[str] = Field(None, description="ID o código del curso/seminario/diplomado seleccionado")
    course_id: Optional[str] = Field(None, description="Alias de program_id")
    course_name: Optional[str] = Field(None, description="Nombre opcional del curso")
    recipient_email: Optional[str] = Field(None, description="Correo electrónico del interesado")
    interested_email: Optional[str] = Field(None, description="Alias de recipient_email")
    recipient_name: Optional[str] = Field("Interesado(a)", description="Nombre opcional del interesado")
    interested_name: Optional[str] = Field(None, description="Alias de recipient_name")
    action_type: str = Field("INSCRIPTION_LINK", description="INSCRIPTION_LINK / LINK_INSCRIPCION o COURSE_INFO / INFORMACION_CURSO")
    campus_name: Optional[str] = Field("Sede Central Providencia, Santiago", description="Sede desde donde Secretaría gestiona el envío")
    notes: Optional[str] = Field(None, description="Mensaje o nota adicional de Secretaría")


class ClinicalQRAttendanceRequest(BaseModel):
    student_id: Optional[str] = Field(None, description="ID o RUT del alumno")
    student_id_or_rut: Optional[str] = Field(None, description="Alias de student_id")
    action: str = Field("CHECK_IN_OUT", description="CHECK_IN, CHECK_OUT, CHECK_IN_OUT, ENTRADA o SALIDA")
    activity_date: Optional[str] = Field(None, description="Fecha en formato YYYY-MM-DD (normativa MINSAL)")
    check_in_time: Optional[str] = Field(None, description="Hora exacta de entrada HH:MM:SS (normativa MINSAL)")
    check_out_time: Optional[str] = Field(None, description="Hora exacta de salida HH:MM:SS (normativa MINSAL)")
    clinical_box: Optional[str] = Field("Box Clínico 01 • Acupuntura (Sede Providencia)", description="Box o sala clínica donde se realiza la práctica")
    box_name: Optional[str] = Field(None, description="Alias de clinical_box")
    campus: Optional[str] = Field(None, description="Sede clínica")
    tutor_rut_or_id: Optional[str] = Field(None, description="RUT o ID del Tutor Clínico supervisor (Clínica San Bao SpA)")
    tutor_name: Optional[str] = Field(None, description="Nombre del Tutor Clínico supervisor")
    qr_token: Optional[str] = Field(None, description="Token QR MINSAL")
    log_id: Optional[str] = Field(None, description="ID del registro si se está marcando salida sobre una entrada abierta")
    notes: Optional[str] = Field(None, description="Actividad clínica realizada o comentario del alumno")


class StudentPayInstallmentRequest(BaseModel):
    student_id: Optional[str] = Field(None, description="ID o RUT del alumno")
    student_id_or_rut: Optional[str] = Field(None, description="Alias de student_id")
    installment_id: str = Field(..., description="ID de la cuota a pagar en Escuela San Bao SpA")
    concept: Optional[str] = Field(None, description="Concepto de la cuota")
    amount: Optional[float] = Field(None, description="Monto de la cuota")
    payment_method: str = Field("WEBPAY", description="WEBPAY, TRANSFERENCIA, TARJETA")
    card_last4: Optional[str] = Field("4821", description="Últimos 4 dígitos de tarjeta")


class TutorApproveAttendanceRequest(BaseModel):
    log_ids: Optional[List[str]] = Field(None, description="Lista de IDs de registros de horas prácticas a aprobar")
    log_id: Optional[str] = Field(None, description="ID individual de registro de hora práctica")
    student_id: Optional[str] = Field(None, description="ID del alumno para aprobar todos sus registros pendientes")
    status: str = Field("APPROVED", description="APPROVED o REJECTED")
    approved: Optional[bool] = Field(True, description="True para aprobar")
    tutor_name: Optional[str] = Field(None, description="Nombre del tutor")
    tutor_comments: Optional[str] = Field("Asistencia y horas clínicas MINSAL verificadas y aprobadas por Tutor Clínico.", description="Observación del tutor")
    mentorship_attended: bool = Field(True, description="Indica si asistió a la mentoría clínica del turno")


class TutorRecordEvaluationRequest(BaseModel):
    student_id: Optional[str] = Field(None, description="ID o RUT del alumno asignado")
    student_id_or_rut: Optional[str] = Field(None, description="Alias de student_id")
    tutor_id: Optional[str] = Field(None, description="ID o RUT del tutor clínico (Clínica San Bao SpA)")
    tutor_name: Optional[str] = Field(None, description="Nombre del tutor clínico")
    evaluation_name: str = Field("Evaluación de Desempeño en Práctica Clínica & Mentoría", description="Nombre de la evaluación práctica")
    score: Optional[float] = Field(None, ge=1.0, le=7.0, description="Nota escala 1.0 a 7.0")
    practice_grade: Optional[float] = Field(None, ge=1.0, le=7.0, description="Alias de score")
    mentorship_attendance_pct: Optional[float] = Field(100.0, ge=0.0, le=100.0, description="% de asistencia a mentoría clínica")
    approve_pending_hours: bool = Field(True, description="Aprobar simultáneamente las horas clínicas pendientes del alumno")
    feedback: Optional[str] = Field(None, description="Retroalimentación clínica del tutor")
    observation: Optional[str] = Field(None, description="Alias de feedback")


class AdmissionApplicationCreateRequest(BaseModel):
    email: Optional[str] = Field(None, description="Correo electrónico del postulante")
    correo: Optional[str] = Field(None, description="Alias de email (Correo)")
    first_name: Optional[str] = Field(None, description="Nombre del postulante")
    nombre: Optional[str] = Field(None, description="Alias de first_name (Nombre)")
    last_name: Optional[str] = Field(None, description="Apellidos del postulante")
    apellidos: Optional[str] = Field(None, description="Alias de last_name (Apellidos)")
    phone: Optional[str] = Field(None, description="Teléfono de contacto (WhatsApp)")
    telefono: Optional[str] = Field(None, description="Alias de phone (Teléfono de contacto)")
    study_format: Optional[str] = Field("PRESENCIAL", description="Formato de estudio: Presencial o Semipresencial")
    formato_estudio: Optional[str] = Field(None, description="Alias de study_format (Presencial o Semipresencial)")
    campus: Optional[str] = Field("SANTIAGO", description="Sede a la que desea postular: Santiago o Viña del Mar")
    sede: Optional[str] = Field(None, description="Alias de campus (Santiago o Viña del Mar)")
    rut: Optional[str] = Field(None, description="RUT opcional del postulante")
    program_interest: Optional[str] = Field("Diplomado Superior en Medicina China Clásica y Acupuntura", description="Programa de interés")
    source: Optional[str] = Field("PORTAL_WEB", description="Origen: PORTAL_WEB o PRESENCIAL_CLINICA")
    interview_date: Optional[str] = Field(None, description="Fecha de entrevista YYYY-MM-DD (si se agenda de inmediato)")
    interview_time: Optional[str] = Field(None, description="Hora de entrevista HH:MM")
    interviewer_name: Optional[str] = Field(None, description="Nombre del entrevistador")
    interviewer_notes: Optional[str] = Field(None, description="Ficha técnica / observaciones manuales")


class ScheduleAdmissionInterviewRequest(BaseModel):
    interview_date: str = Field(..., description="Fecha de entrevista YYYY-MM-DD")
    interview_time: Optional[str] = Field("11:00", description="Hora de entrevista HH:MM")
    interviewer_name: Optional[str] = Field("Coordinación Académica San Bao", description="Entrevistador asignado")
    interview_modality: Optional[str] = Field("PRESENCIAL", description="PRESENCIAL o VIDEOCONFERENCIA")
    interviewer_notes: Optional[str] = Field(None, description="Observaciones o notas previas de coordinación")


class EvaluateAdmissionInterviewRequest(BaseModel):
    decision: str = Field("ACEPTADO", description="Criterio del entrevistador: ACEPTADO o RECHAZADO")
    interviewer_name: Optional[str] = Field(None, description="Nombre del entrevistador que evalúa")
    interviewer_notes: Optional[str] = Field(None, description="Descripción para la Hoja de Vida y comentarios de la entrevista")
    life_record_notes: Optional[str] = Field(None, description="Descripción opcional para la Hoja de Vida del alumno")
    hoja_de_vida_descripcion: Optional[str] = Field(None, description="Alias de life_record_notes")
    rut: Optional[str] = Field(None, description="RUT confirmado en la entrevista para iniciar matrícula")


# =============================================================================
# FASE 3: ESQUEMAS DE GESTIÓN ACADÉMICA AVANZADA Y PUENTE CLÍNICO-ACADÉMICO
# =============================================================================
class MultiCohortEnrollmentRequest(BaseModel):
    cohort_id: str = Field(..., description="ID de la cohorte/sección a inscribir simultáneamente")
    enrollment_type: str = Field("TRANSITORIA", description="B.1: REGULAR, TRANSITORIA, RECUPERACION")
    valid_from: Optional[date] = Field(default_factory=date.today, description="Inicio de vigencia")
    valid_until: Optional[date] = Field(None, description="Término de vigencia")
    origin_cohort_id: Optional[str] = Field(None, description="Cohorte de origen si aplica")
    notes: Optional[str] = Field(None, description="Motivo o detalle de la inscripción simultánea")


class AcademicIncidentCreateRequest(BaseModel):
    student_id: str = Field(..., description="ID del alumno")
    cohort_id: Optional[str] = None
    course_id: Optional[str] = None
    reported_by_id: Optional[str] = None
    reported_by_name: str = Field("Docente Titular San Bao", description="Nombre del docente que registra la incidencia")
    incident_date: Optional[date] = Field(default_factory=date.today)
    title: str = Field(..., description="Título breve de la incidencia")
    description: str = Field(..., description="Descripción detallada reportada por el docente")
    category: Optional[str] = Field("ACADEMICA", description="ACADEMICA, CONDUCTUAL, ASISTENCIA, CLINICA, RECONOCIMIENTO")
    severity: Optional[str] = Field("MEDIA", description="BAJA, MEDIA, ALTA")


class AcademicIncidentUpdateByTeacherRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reported_by_id: Optional[str] = None


class AcademicIncidentModerateRequest(BaseModel):
    decision: str = Field("VALIDADA_PUBLICADA", description="VALIDADA_PUBLICADA o RECHAZADA")
    category: Optional[str] = Field(None, description="Tipificación validada: ACADEMICA, CONDUCTUAL, ASISTENCIA, CLINICA, RECONOCIMIENTO")
    severity: Optional[str] = Field(None, description="Severidad validada: BAJA, MEDIA, ALTA")
    reviewed_by_name: str = Field("Coordinación Académica San Bao", description="Responsable de Coordinación o Dirección que modera")
    moderation_notes: Optional[str] = Field(None, description="Resolución o comentario de validación")


class CourseApprovalRulesUpdateRequest(BaseModel):
    requires_interview: Optional[bool] = Field(None, description="B.4: True si requiere entrevista de postulación, False para inscripción directa")
    min_attendance_pct: Optional[float] = Field(None, ge=0.0, le=100.0, description="B.5: % de asistencia mínima parametrizable")
    min_passing_grade: Optional[float] = Field(None, ge=1.0, le=7.0, description="B.5: Nota mínima de aprobación")
    requires_grade_for_approval: Optional[bool] = Field(None, description="B.5: False para seminarios que aprueban solo por asistencia")
    auto_issue_diploma: Optional[bool] = Field(None, description="B.5: Generación automática de diploma al aprobar")
    practice_max_months: Optional[int] = Field(None, ge=1, le=36, description="B.8: Plazo máximo estimado de práctica en meses")


class DirectShortCourseEnrollmentRequest(BaseModel):
    rut: str = Field(..., description="RUT del participante")
    first_name: str = Field(..., description="Nombres")
    last_name: str = Field(..., description="Apellidos")
    email: str = Field(..., description="Correo electrónico")
    phone: Optional[str] = Field("+56 9 8000 0000")
    program_id: str = Field(..., description="ID del curso corto o seminario (debe tener requires_interview = False)")
    campus: Optional[str] = Field("SANTIAGO")


class TutorSemesterEvaluationCreateRequest(BaseModel):
    student_id: str = Field(..., description="ID del alumno en práctica")
    tutor_id: Optional[str] = Field(None, description="ID o RUT del tutor clínico")
    period_code: str = Field("2026-2", description="Período semestral ej: 2026-1, 2026-2")
    specialty: str = Field("ACUPUNTURA", description="Especialidad clínica")
    clinical_competency_score: float = Field(..., ge=1.0, le=7.0)
    anamnesis_quality_score: float = Field(..., ge=1.0, le=7.0)
    punctuality_ethics_score: float = Field(..., ge=1.0, le=7.0)
    clinical_reports_required: int = Field(5, ge=0)
    clinical_reports_delivered: int = Field(5, ge=0)
    report_delivery_notes: Optional[str] = None
    feedback: Optional[str] = None


class StudentTutorEvaluationCreateRequest(BaseModel):
    student_id: str = Field(..., description="ID del alumno que evalúa")
    tutor_id: str = Field(..., description="ID o RUT del tutor evaluado")
    period_code: str = Field("2026-2")
    pedagogical_clarity_score: float = Field(..., ge=1.0, le=7.0)
    supervision_support_score: float = Field(..., ge=1.0, le=7.0)
    clinical_feedback_score: float = Field(..., ge=1.0, le=7.0)
    confidential_comments: Optional[str] = None


class ClinicalShiftBridgeClosureRequest(BaseModel):
    idempotency_key: str = Field(..., description="C: Clave única de idempotencia del evento de cierre de sesión/turno")
    student_id: str = Field(..., description="ID del alumno en práctica")
    tutor_id: Optional[str] = Field(None, description="ID o RUT del tutor clínico que cierra y valida la sesión")
    shift_id: Optional[str] = Field(None, description="ID del turno clínico cerrado")
    session_id: Optional[str] = Field(None, description="ID de la atención clínica (ClinicalEncounter) cerrada")
    specialty: str = Field("ACUPUNTURA", description="Especialidad: ACUPUNTURA, TUI_NA, FITOTERAPIA")
    activity_date: Optional[date] = Field(default_factory=date.today)
    hours_completed: int = Field(..., ge=1, le=24, description="Horas clínicas validadas a acumular")
    tutor_evaluation_score: Optional[float] = Field(None, ge=1.0, le=7.0, description="Nota de evaluación de la sesión")
    tutor_feedback: Optional[str] = Field(None, description="Retroalimentación clínica del tutor")
    tutor_hourly_rate_clp: Optional[float] = Field(25000.0, ge=0.0, description="Valor hora del tutor para devengo de remuneraciones/honorarios")


class ClinicalPracticeHourAdjustmentRequest(BaseModel):
    delta_hours: int = Field(..., description="C: Ajuste auditable de horas (+N o -N) sin sobrescribir el registro original")
    reason: str = Field(..., description="Motivo obligatorio del ajuste auditable")
    adjusted_by_user_id: Optional[str] = Field("coordinacion@sanbao.cl", description="Responsable del ajuste")





