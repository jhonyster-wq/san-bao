from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Body, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.institutional.models import User
from app.modules.hr.schemas import (
    HREmployeeCreate,
    HREmployeeResponse,
    HRContractCreate,
    HRContractResponse,
    HRLeaveRequestCreate,
    HRLeaveRequestResponse,
    HRFeeReceiptCreate,
    HRFeeReceiptResponse,
    HRPayrollCreate,
    HRPayrollResponse,
)
from app.modules.hr.services import HRService, HRHubService
from app.modules.finance.services.finance_hub_service import FinanceHubService

router = APIRouter(prefix="/hr", tags=["Recursos Humanos y Remuneraciones"])


# =============================================================================
# ENDPOINTS INTEGRALES MÓDULO 4: PERSONAS & RRHH (/api/v1/hr/hub/...)
# =============================================================================

@router.get("/hub/overview")
def get_hr_hub_overview(
    company_filter: Optional[str] = Query("consolidated"),
    search: Optional[str] = Query(None),
    employee_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Obtiene el panorama integral de las 9 áreas de Personas & RRHH del Holding San Bao."""
    data = HRHubService(db).get_hr_hub_overview(
        company_filter=company_filter,
        search=search,
        employee_type=employee_type,
    )
    return {"success": True, "data": data}


@router.post("/hub/employees")
def create_hr_hub_employee(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """1. Registro de nuevo trabajador o colaborador con contrato y carpeta laboral inicial."""
    data = HRHubService(db).create_employee_from_hub(payload)
    return {"success": True, "data": data}


@router.post("/hub/contracts")
def create_or_update_hr_hub_contract(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """2. Administración de contratos: crea contrato o anexo de contrato."""
    data = HRHubService(db).create_or_update_contract_from_hub(payload)
    return {"success": True, "data": data}


@router.post("/hub/documents")
def create_hr_hub_document(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """3. Control de documentación laboral: registra un nuevo documento en expediente digital."""
    data = HRHubService(db).create_labor_document(payload)
    return {"success": True, "data": data}


@router.put("/hub/documents/{document_id}/verify")
def verify_hr_hub_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    """3. Control de documentación laboral: valida y deja VIGENTE un documento laboral."""
    data = HRHubService(db).verify_labor_document(document_id)
    return {"success": True, "data": data}


@router.post("/hub/attendance")
def create_hr_hub_attendance(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """4. Registro de asistencia: ingresa un nuevo marcaje diario, turno o bloque docente/clínico."""
    data = HRHubService(db).create_attendance_record(payload)
    return {"success": True, "data": data}


@router.post("/hub/leaves")
def create_hr_hub_leave(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """4. Registro de permisos, feriado legal (vacaciones) o licencia médica."""
    data = HRHubService(db).create_leave_request(payload)
    return {"success": True, "data": data}


@router.put("/hub/leaves/{leave_id}/status")
def update_hr_hub_leave_status(
    leave_id: UUID,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """4. Aprueba o rechaza una solicitud de permiso, vacaciones o licencia médica."""
    data = HRHubService(db).update_leave_status(leave_id, str(payload.get("status") or "APPROVED"))
    return {"success": True, "data": data}


@router.post("/hub/bhe")
def create_hr_hub_bhe(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """5. Gestión de honorarios: registra Boleta de Honorarios Electrónica SII (13.75%)."""
    data = FinanceHubService(db).issue_bhe_receipt(payload)
    return {"success": True, "data": data}


@router.post("/hub/payrolls")
def create_hr_hub_payroll(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """6. Remuneraciones y liquidaciones: calcula y emite liquidación mensual legal."""
    data = FinanceHubService(db).generate_employee_payroll(payload)
    return {"success": True, "data": data}


@router.post("/hub/remunerations/{item_type}/{item_id}/pay")
def pay_hr_hub_remuneration(
    item_type: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """5 y 6. Registra el pago efectivo de una Liquidación de Sueldo o Boleta de Honorarios."""
    data = FinanceHubService(db).mark_remuneration_paid(item_type, item_id)
    return {"success": True, "data": data}


@router.put("/hub/previsional/{contract_id}")
def update_hr_hub_previsional(
    contract_id: UUID,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """7. Información previsional: actualiza AFP, Fonasa/Isapre y cotización pactada para Previred."""
    data = HRHubService(db).update_previsional_info(contract_id, payload)
    return {"success": True, "data": data}


@router.put("/hub/professionals/{employee_id}")
def update_hr_hub_professional_profile(
    employee_id: UUID,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    """8. Administración de docentes y profesionales: actualiza cátedras, registro SIS Minsal, box y tarifas."""
    data = HRHubService(db).update_professional_profile(employee_id, payload)
    return {"success": True, "data": data}


# =============================================================================
# ENDPOINTS REST ESTÁNDAR (/api/v1/hr/...)
# =============================================================================

@router.post("/employees", response_model=HREmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    data: HREmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra un nuevo colaborador (Docente, Terapeuta, Administrativo)."""
    return HRService.create_employee(db, data)


@router.get("/employees", response_model=List[HREmployeeResponse])
def list_employees(
    x_company_id: Optional[str] = Header(None),
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista colaboradores activos de la sociedad."""
    target_company = company_id or x_company_id
    return HRService.get_employees(db, target_company)


@router.get("/employees/{id}", response_model=HREmployeeResponse)
def get_employee(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene el expediente de un colaborador."""
    return HRService.get_employee_by_id(db, id)


@router.post("/contracts", response_model=HRContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    data: HRContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra o actualiza contrato laboral o de honorarios de un colaborador."""
    return HRService.create_contract(db, data)


@router.post("/leave-requests", response_model=HRLeaveRequestResponse, status_code=status.HTTP_201_CREATED)
def request_leave(
    data: HRLeaveRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra solicitud de permiso, vacaciones o licencia médica."""
    return HRService.request_leave(db, data)


@router.put("/leave-requests/{id}/approve", response_model=HRLeaveRequestResponse)
def approve_leave(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aprueba formalmente una solicitud de permiso."""
    return HRService.approve_leave(db, id, current_user.id)


@router.post("/fee-receipts", response_model=HRFeeReceiptResponse, status_code=status.HTTP_201_CREATED)
def issue_fee_receipt(
    data: HRFeeReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra boleta de honorarios profesional (BHE) con retención legal SII."""
    return HRService.issue_fee_receipt(db, data)


@router.post("/payrolls/generate", response_model=HRPayrollResponse, status_code=status.HTTP_201_CREATED)
def generate_payroll(
    data: HRPayrollCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calcula y emite liquidación de remuneración mensual legal chilena."""
    return HRService.calculate_and_generate_payroll(db, data)
