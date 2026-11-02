from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_company_context
from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.institutional.models.company import Company
from app.modules.academic.services.coordinator_service import AcademicCoordinatorService
from app.modules.academic.schemas.coordinator import (
    FreezeStudentRequest,
    UnfreezeStudentRequest,
    TransferStudentRequest,
    ApproveClinicalRequest,
    CoordinatorGradeEntryRequest,
    IssueDocumentRequest,
    InitiateOnboardingRequest,
    SignOnboardingContractRequest,
    ConfirmOnboardingWebpayRequest,
    StudentPortalLoginRequest,
    StudentLifeRecordUpdateRequest,
    SecretariatSendCourseEmailRequest,
    ClinicalQRAttendanceRequest,
    StudentPayInstallmentRequest,
    TutorApproveAttendanceRequest,
    TutorRecordEvaluationRequest,
)
from app.shared.responses import APIResponse

router = APIRouter(prefix="/academic/coordinator", tags=["Gestión Académica, Portal de Secretaría, QR MINSAL Alumno y Portal de Tutores"])


# =============================================================================
# 1. MATRÍCULAS Y ALUMNOS VIGENTES
# =============================================================================
@router.get("/enrollments", response_model=APIResponse[List[Dict[str, Any]]], summary="Nómina consolidada de alumnos y matrículas vigentes")
def list_enrollments(
    program_id: Optional[str] = Query(None, description="Filtrar por ID de curso o diplomado"),
    status: Optional[str] = Query(None, description="Filtrar por estado (REGULAR, CONGELADO, etc.)"),
    search: Optional[str] = Query(None, description="Búsqueda por RUT, nombre o matrícula"),
    campus: Optional[str] = Query(None, description="Filtrar por sede (SANTIAGO, VINA_DEL_MAR o ALL)"),
    financial_status: Optional[str] = Query(None, description="Filtrar por estado financiero (AL_DIA, PAGADO_TOTAL, MOROSO, PENDIENTE_PAGO o ALL)"),
    program_category: Optional[str] = Query(None, description="Filtrar por tipo de programa (DIPLOMADO, CURSO o ALL)"),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    items = service.list_enrollments(
        program_id=program_id,
        status=status,
        search=search,
        campus=campus,
        financial_status=financial_status,
        program_category=program_category,
    )
    return APIResponse(data=items)


@router.get("/matriculas/report", response_model=APIResponse[Dict[str, Any]], summary="Listado de matriculados con filtros de sede, estado financiero, diplomados o cursos y resumen dinámico según filtros")
def get_matriculas_report(
    campus: Optional[str] = Query(None, description="Sede: SANTIAGO, VINA_DEL_MAR o ALL"),
    financial_status: Optional[str] = Query(None, description="Estado financiero: AL_DIA, PAGADO_TOTAL, MOROSO, PENDIENTE_PAGO o ALL"),
    program_category: Optional[str] = Query(None, description="Categoría: DIPLOMADO, CURSO o ALL"),
    program_id: Optional[str] = Query(None, description="ID del diplomado o curso específico"),
    status: Optional[str] = Query(None, description="Estado académico opcional"),
    search: Optional[str] = Query(None, description="Búsqueda por alumno, RUT o matrícula"),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    report = service.get_matriculas_report(
        campus=campus,
        financial_status=financial_status,
        program_category=program_category,
        program_id=program_id,
        status=status,
        search=search,
    )
    return APIResponse(data=report)


@router.get("/students/{student_id}/life-record", response_model=APIResponse[Dict[str, Any]], summary="Obtener Hoja de Vida integral del alumno (datos de contacto, notas, clínica, finanzas y bitácora)")
def get_student_life_record(
    student_id: str,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        data = service.get_student_life_record(student_id)
        return APIResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/students/{student_id}/life-record", response_model=APIResponse[Dict[str, Any]], summary="Actualizar datos de contacto (teléfono, correo, dirección) o registrar anotación en la Hoja de Vida del alumno")
def update_student_life_record(
    student_id: str,
    payload: StudentLifeRecordUpdateRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        data = service.update_student_life_record(student_id, payload)
        return APIResponse(
            message="Hoja de Vida y datos de contacto del alumno actualizados exitosamente",
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 2. ACTIVACIÓN O CONGELAMIENTO DE ALUMNOS
# =============================================================================
@router.post("/students/{student_id}/freeze", response_model=APIResponse[Dict[str, Any]], summary="Congelar matrícula de un estudiante")
def freeze_student(
    student_id: str,
    payload: FreezeStudentRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        st = service.freeze_student(student_id, payload)
        return APIResponse(
            message=f"Alumno {st.student_number} congelado formalmente por motivo: {payload.reason}",
            data={
                "student_id": st.id,
                "student_number": st.student_number,
                "status": st.status,
                "freeze_reason": st.freeze_reason,
                "freeze_date": st.freeze_date.isoformat() if st.freeze_date else None,
            },
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/students/{student_id}/unfreeze", response_model=APIResponse[Dict[str, Any]], summary="Reactivar alumno a estado regular")
def unfreeze_student(
    student_id: str,
    payload: UnfreezeStudentRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        st = service.unfreeze_student(student_id, payload)
        return APIResponse(
            message=f"Alumno {st.student_number} reactivado exitosamente a estado REGULAR",
            data={
                "student_id": st.id,
                "student_number": st.student_number,
                "status": st.status,
            },
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =============================================================================
# 3. CAMBIOS DE CURSO DE ALUMNOS
# =============================================================================
@router.post("/students/{student_id}/change-course", response_model=APIResponse[Dict[str, Any]], summary="Traspasar o cambiar alumno de curso/diplomado")
def change_student_course(
    student_id: str,
    payload: TransferStudentRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.transfer_student_course(student_id, payload)
        return APIResponse(message="Traspaso de curso realizado y registrado exitosamente", data=res)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/transfers", response_model=APIResponse[List[Dict[str, Any]]], summary="Historial de cambios de curso")
def list_student_transfers(db: Session = Depends(get_db)):
    service = AcademicCoordinatorService(db)
    items = service.list_student_transfers()
    return APIResponse(data=items)


# =============================================================================
# 4. APROBACIÓN DE ALUMNOS PARA PRÁCTICAS CLÍNICAS (VISUALIZADO EN DIRECCIÓN CLÍNICA)
# =============================================================================
@router.post("/students/{student_id}/approve-clinical", response_model=APIResponse[Dict[str, Any]], summary="Aprobar o revocar alumno para prácticas clínicas")
def approve_clinical_practice(
    student_id: str,
    payload: ApproveClinicalRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        st = service.approve_clinical_practice(student_id, payload)
        msg = "Alumno aprobado formalmente para ingresar a prácticas clínicas supervisadas" if payload.approved else "Aprobación clínica revocada"
        return APIResponse(
            message=msg,
            data={
                "student_id": st.id,
                "clinical_practice_approved": st.clinical_practice_approved,
                "clinical_practice_approval_date": st.clinical_practice_approval_date.isoformat() if st.clinical_practice_approval_date else None,
                "clinical_practice_notes": st.clinical_practice_notes,
            },
        )
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.get("/approved-clinical-students", response_model=APIResponse[List[Dict[str, Any]]], summary="Nómina de alumnos aprobados para prácticas clínicas")
def list_approved_clinical_students(db: Session = Depends(get_db)):
    service = AcademicCoordinatorService(db)
    items = service.list_approved_clinical_interns()
    return APIResponse(data=items)


# =============================================================================
# 5. ENTREGA DE NOTAS Y EVALUACIONES
# =============================================================================
@router.get("/grading/cohorts", response_model=APIResponse[List[Dict[str, Any]]], summary="Cohortes activas para entrega de notas")
def list_grading_cohorts(
    program_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    cohorts = service.list_cohorts_for_grading(program_id=program_id)
    return APIResponse(data=cohorts)


@router.get("/grading/cohorts/{cohort_id}", response_model=APIResponse[Dict[str, Any]], summary="Obtener evaluaciones y calificaciones por cohorte")
def get_cohort_grades(cohort_id: str, db: Session = Depends(get_db)):
    service = AcademicCoordinatorService(db)
    try:
        data = service.list_cohort_students_grades(cohort_id)
        return APIResponse(data=data)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.post("/grading/entry", response_model=APIResponse[Dict[str, Any]], summary="Ingresar o actualizar calificación de un alumno")
def record_grade_entry(
    payload: CoordinatorGradeEntryRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.record_grade_entry(payload)
        return APIResponse(message="Calificación registrada y promedio actualizado exitosamente", data=res)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 6. ENTREGA DE DOCUMENTACIÓN OFICIAL Y DIPLOMAS DE EGRESO
# =============================================================================
@router.post("/documents/issue", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Emitir documento oficial o diploma de egreso")
def issue_official_document(
    payload: IssueDocumentRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        doc = service.issue_official_document(payload)
        return APIResponse(message=f"Documento {doc['document_number']} emitido exitosamente", data=doc)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/documents", response_model=APIResponse[List[Dict[str, Any]]], summary="Listado de documentos oficiales emitidos")
def list_official_documents(
    student_id: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    docs = service.list_documents(student_id=student_id, document_type=document_type)
    return APIResponse(data=docs)


@router.get("/documents/{document_id}", response_model=APIResponse[Dict[str, Any]], summary="Obtener documento oficial por ID para impresión o visualización")
def get_official_document(document_id: str, db: Session = Depends(get_db)):
    service = AcademicCoordinatorService(db)
    try:
        doc = service.get_document(document_id)
        return APIResponse(data=doc)
    except EntityNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =============================================================================
# 7. MATRÍCULA DIGITAL EN 5 PASOS: CATÁLOGO, NO DUPLICIDAD, FIRMA, WEBPAY Y SESIÓN ALUMNO
# =============================================================================
@router.get("/catalog-pricing", response_model=APIResponse[List[Dict[str, Any]]], summary="Catálogo de Diplomados, Cursos y Formación Continua con aranceles precargados")
def get_catalog_pricing(db: Session = Depends(get_db)):
    service = AcademicCoordinatorService(db)
    items = service.get_catalog_programs_with_pricing()
    return APIResponse(data=items)


@router.get("/applicants/lookup", response_model=APIResponse[Dict[str, Any]], summary="Paso 1: Verificar si el postulante existe en el registro de alumnos por RUT")
def lookup_applicant_by_rut(
    rut: str = Query(..., description="RUT del postulante a verificar"),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.lookup_applicant_by_rut(rut)
        return APIResponse(message=res["message"], data=res)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/onboarding", response_model=APIResponse[List[Dict[str, Any]]], summary="Listado de procesos de matrícula digital (Contrato, Firma Electrónica, Webpay y Sesión)")
def list_onboarding_processes(db: Session = Depends(get_db)):
    service = AcademicCoordinatorService(db)
    items = service.list_onboarding_processes()
    return APIResponse(data=items)


@router.post("/onboarding/initiate", response_model=APIResponse[Dict[str, Any]], status_code=status.HTTP_201_CREATED, summary="Pasos 1-3: Confirmar matrícula, validar no duplicidad y enviar link de contrato para firma electrónica")
def initiate_enrollment_onboarding(
    payload: InitiateOnboardingRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.initiate_enrollment_onboarding(payload)
        onb = res["onboarding"]
        return APIResponse(
            message=(
                f"Matrícula {onb['student_number']} confirmada en estado PENDIENTE_FIRMA. "
                f"Link de Contrato Educacional ({onb['contract_code']}) enviado para Firma Electrónica a {onb['email']}."
            ),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/onboarding/{onboarding_id}/sign-contract", response_model=APIResponse[Dict[str, Any]], summary="Paso 4: Confirmar Firma Electrónica (DOCUMENTO_FIRMADO) y generar automáticamente Link de Pago Webpay")
def sign_onboarding_contract(
    onboarding_id: str,
    payload: SignOnboardingContractRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.confirm_onboarding_contract_signature(onboarding_id, payload)
        onb = res["onboarding"]
        return APIResponse(
            message=(
                f"Firma Electrónica confirmada (Estado: DOCUMENTO_FIRMADO · Token {onb['signature_token']}). "
                f"Link de pago Webpay Plus generado automáticamente."
            ),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/onboarding/{onboarding_id}/confirm-webpay", response_model=APIResponse[Dict[str, Any]], summary="Paso 5: Confirmar Pago Webpay, activar Alumno Regular y crear sesión con RUT y Password Segura en Portal del Alumno")
def confirm_onboarding_webpay(
    onboarding_id: str,
    payload: ConfirmOnboardingWebpayRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.confirm_onboarding_webpay_payment(onboarding_id, payload)
        creds = res["portal_credentials"]
        return APIResponse(
            message=(
                f"Pago Webpay confirmado. {creds['full_name']} ({creds['student_number']}) actualizado a ALUMNO REGULAR "
                f"y sesión creada en el Portal del Alumno (Usuario RUT: {creds['rut']} · Password Segura: {creds['password']})."
            ),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/student-portal/login", response_model=APIResponse[Dict[str, Any]], summary="Iniciar sesión en el Portal del Alumno con RUT y Password Segura")
def login_student_portal(
    payload: StudentPortalLoginRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.authenticate_student_portal(payload)
        st = res["student"]
        return APIResponse(
            message=f"Sesión iniciada en el Portal del Alumno: {st['full_name']} ({st['student_number']} · Estado: {st['status']})",
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/student-portal/profile", response_model=APIResponse[Dict[str, Any]], summary="Obtener datos de sesión y perfil del Portal del Alumno")
def get_student_portal_profile(
    student_id: Optional[str] = Query(None, description="ID o RUT del alumno"),
    student_id_or_rut: Optional[str] = Query(None, description="ID o RUT del alumno"),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.get_student_portal_data(student_id_or_rut or student_id)
        return APIResponse(data=res)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/portal-firma/{onboarding_id}", response_class=HTMLResponse, summary="Página interactiva de Firma Electrónica de Contrato Educacional (se abre al hacer clic en el href del correo)")
def get_portal_firma_page(
    onboarding_id: str,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        return HTMLResponse(content=service.render_portal_firma_html(onboarding_id))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/webpay-checkout/{onboarding_id}", response_class=HTMLResponse, summary="Pasarela interactiva Webpay Plus Transbank (se abre al hacer clic en el href de pago Webpay)")
def get_webpay_checkout_page(
    onboarding_id: str,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        return HTMLResponse(content=service.render_webpay_checkout_html(onboarding_id))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# =============================================================================
# 8. PORTAL DE SECRETARÍA (GESTIÓN SECRETARÍA), LECTOR QR MINSAL Y PORTAL DE TUTORES
# =============================================================================
@router.get("/secretariat/overview", response_model=APIResponse[Dict[str, Any]], summary="Portal de Secretaría: Actividades de Sede (modo consulta), Catálogo y Desarrollo de Práctica Clínica por Alumno")
def get_secretariat_portal_overview(
    campus: Optional[str] = Query(None, description="Filtrar por código de sede (SEDE-CENTRAL, SEDE-VINA)"),
    area: Optional[str] = Query(None, description="Filtrar por área (CLINICA, ACADEMICA)"),
    student_q: Optional[str] = Query(None, description="Filtro de alumno (nombre, RUT o matrícula)"),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    data = service.get_secretariat_portal_overview(
        campus_filter=campus,
        area_filter=area,
        student_filter=student_q,
    )
    return APIResponse(data=data)


@router.post("/secretariat/send-course-info", response_model=APIResponse[Dict[str, Any]], summary="Portal de Secretaría: Enviar link de inscripción o información de un curso al correo electrónico del interesado")
def send_secretariat_course_email(
    payload: SecretariatSendCourseEmailRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.send_secretariat_course_email(payload)
        return APIResponse(message=res["message"], data=res)
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/clinical-qr-attendance", response_model=APIResponse[Dict[str, Any]], summary="Portal del Alumno: Registrar lectura QR de práctica clínica bajo normativa MINSAL (fecha, hora entrada y hora salida)")
def record_clinical_qr_attendance(
    payload: ClinicalQRAttendanceRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.record_clinical_qr_attendance(payload)
        return APIResponse(
            message=(
                f"Registro QR MINSAL ({res['qr_code']}) guardado exitosamente: "
                f"Fecha {res['activity_date']} • Entrada {res['check_in_time']} • Salida {res['check_out_time']} "
                f"({res['hours_completed']} hrs clínicas)."
            ),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/clinical-qr-page", response_class=HTMLResponse, summary="Página interactiva de Lectura QR de Práctica Clínica MINSAL con reloj en vivo y botón de guardado de hora y fecha actual")
def get_clinical_qr_page(
    student_id: Optional[str] = Query(None),
    rut: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        return HTMLResponse(content=service.render_clinical_qr_scanner_html(student_id or rut))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/student-portal/pay-installment", response_model=APIResponse[Dict[str, Any]], summary="Portal del Alumno (Escuela San Bao SpA): Pagar cuota del Compromiso Arancelario y emitir DTE 41")
def pay_student_installment(
    payload: StudentPayInstallmentRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.pay_student_installment(payload)
        return APIResponse(
            message=(
                f"Cuota #{res['installment_number']} pagada exitosamente en Escuela San Bao SpA "
                f"(${int(res['paid_amount']):,} CLP). Comprobante DTE 41 emitido."
            ).replace(",", "."),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/tutor-portal/overview", response_model=APIResponse[Dict[str, Any]], summary="Portal de Tutores Clínicos (Clínica San Bao SpA): Turnos asignados exclusivamente al tutor, alumnos en práctica, horas QR MINSAL y evaluación")
def get_tutor_portal_overview(
    tutor_id: Optional[str] = Query(None, description="RUT, ID o nombre del tutor clínico"),
    tutor_name: Optional[str] = Query(None, description="Nombre o RUT del tutor clínico"),
    tutor_rut: Optional[str] = Query(None, description="RUT del tutor clínico"),
    student_q: Optional[str] = Query(None, description="Filtro de alumno"),
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    target_tutor = tutor_id or tutor_rut or tutor_name
    data = service.get_tutor_portal_overview(tutor_rut_or_id=target_tutor, student_filter=student_q)
    return APIResponse(data=data)


@router.post("/tutor-portal/approve-attendance", response_model=APIResponse[Dict[str, Any]], summary="Portal de Tutores Clínicos: Aprobar asistencia y horas prácticas por alumno según registro QR MINSAL")
def tutor_approve_clinical_attendance(
    payload: TutorApproveAttendanceRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.tutor_approve_clinical_attendance(payload)
        return APIResponse(
            message=(
                f"Se aprobaron {res['approved_records_count']} registro(s) MINSAL "
                f"({res['total_hours_accredited']} hrs prácticas acreditadas por Tutor de Clínica San Bao SpA)."
            ),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/tutor-portal/record-evaluation", response_model=APIResponse[Dict[str, Any]], summary="Portal de Tutores Clínicos: Registrar nota de práctica clínica y aprobar asistencia de mentoría")
def tutor_record_clinical_evaluation(
    payload: TutorRecordEvaluationRequest,
    db: Session = Depends(get_db),
):
    service = AcademicCoordinatorService(db)
    try:
        res = service.tutor_record_clinical_evaluation(payload)
        return APIResponse(
            message=(
                f"Evaluación clínica registrada (Nota: {res['recorded_score']} • Asistencia Mentoría: "
                f"{res['mentorship_attendance_pct']}%)."
            ),
            data=res,
        )
    except (EntityNotFoundException, SanBaoException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=getattr(e, "message", str(e)))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


