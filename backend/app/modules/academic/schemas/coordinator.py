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



