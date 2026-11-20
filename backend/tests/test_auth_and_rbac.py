import pytest
from app.core.security import get_password_hash, verify_password, create_access_token, decode_token
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.user import User


def test_password_hashing():
    raw_password = "PasswordSanBao2026!"
    hashed = get_password_hash(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_cycle():
    data = {"sub": "user-uuid-123", "company_id": "company-uuid-456", "roles": ["ADMIN_ACADEMICO"]}
    token = create_access_token(data)
    assert isinstance(token, str)

    decoded = decode_token(token)
    assert decoded["sub"] == "user-uuid-123"
    assert decoded["company_id"] == "company-uuid-456"
    assert "ADMIN_ACADEMICO" in decoded["roles"]


def test_seed_companies_exist(db_session):
    instituto = db_session.query(Company).filter(Company.rut == "77123456-9").first()
    clinica = db_session.query(Company).filter(Company.rut == "76987654-5").first()

    assert instituto is not None
    assert "Instituto" in instituto.legal_name
    assert clinica is not None
    assert "Clínicos" in clinica.legal_name


def test_seed_admin_user_exists(db_session):
    admin = db_session.query(User).filter(User.username == "admin").first()
    assert admin is not None
    assert admin.is_superuser is True
    assert verify_password("AdminSanBao2026!", admin.password_hash) is True
    assert len(admin.company_roles) == 2  # Superadmin asignado a ambas sociedades


def test_fase2_master_identity_multirole_cost_centers_and_rbac_anamnesis_guard(client, db_session):
    """
    Fase 2:
    1) Fuente Maestra de Identidad (Req. A): RUT normalizado sin puntos y con guion (Módulo 11),
       misma persona puede ser Alumno, Paciente y Proveedor sin duplicar UUID en core.people.
    2) Catálogo Maestro de Centros de Costo por Sociedad (Req. E.6).
    3) Matriz RBAC y prohibición estricta de ADMIN_FINANZAS para acceder a anamnesis clínica (Req. M).
    """
    from app.modules.institutional.models.person import Person
    from app.modules.institutional.models.rbac import Role, UserCompanyRole
    from app.modules.clinical.models.patient import Patient
    from app.modules.clinical.models.practitioner import Practitioner
    from app.modules.clinical.models.encounter import ClinicalEncounter
    from app.modules.clinical.models.access_log import ClinicalAccessLog

    # 1. Crear/enriquecer identidad maestra con RUT con puntos -> debe normalizarse a sin puntos y con guion
    res_upsert = client.post(
        "/api/v1/institutional/people/upsert-identity",
        json={
            "rut": "19.876.543-0",
            "first_name": "Diego",
            "last_name": "Valenzuela Rojas",
            "email": "diego.valenzuela@alumno.sanbao.cl",
            "enable_supplier": True,
            "business_name": "Insumos Acupuntura Diego Valenzuela EIRL",
            "trade_category": "INSUMOS_CLINICOS",
            "default_cost_center_code": "CC-201 Clínica San Bao - Acupuntura Providencia",
        },
    )
    assert res_upsert.status_code == 200
    identity = res_upsert.json()["data"]
    assert identity["canonical_rut"] == "19876543-0"
    assert identity["mod11_valid"] is True
    assert identity["person"]["rut"] == "19876543-0"
    assert "PROVEEDOR" in identity["active_roles"]
    person_uuid = identity["person"]["id"]

    # Verificar que no se duplicó la persona en core.people al consultar con distinto formato de RUT
    res_get = client.get("/api/v1/institutional/people/identity/19.876.543-0")
    assert res_get.status_code == 200
    assert res_get.json()["data"]["person"]["id"] == person_uuid
    assert db_session.query(Person).filter(Person.rut == "19876543-0").count() == 1

    # 2. Catálogo de Centros de Costo por Sociedad
    res_cc = client.get("/api/v1/finance/hub/cost-centers")
    assert res_cc.status_code == 200
    assert res_cc.json()["data"]["total"] >= 4

    # 3. Matriz RBAC oficial
    res_matrix = client.get("/api/v1/institutional/auth/rbac-matrix")
    assert res_matrix.status_code == 200
    matrix_roles = res_matrix.json()["data"]["roles"]
    assert matrix_roles["ADMIN_FINANZAS"]["can_access_clinical_anamnesis"] is False
    assert "academic:students:read" in matrix_roles["ADMIN_FINANZAS"]["permissions"]
    assert matrix_roles["TUTOR_CLINICO"]["can_access_clinical_anamnesis"] is True
    assert "clinical:practice_hours:read" in matrix_roles["COORDINADOR_ACADEMICO"]["permissions"]
    assert "finance:summary:read" in matrix_roles["DIRECCION"]["permissions"]

    # 4. Verificar que un usuario con rol ADMIN_FINANZAS recibe 403 Forbidden al intentar leer una anamnesis clínica
    clinica = db_session.query(Company).filter(Company.rut == "76987654-5").first()
    fin_role = db_session.query(Role).filter(Role.code == "ADMIN_FINANZAS").first()

    fin_person = Person(
        rut="12456789-5",
        first_name="Claudia",
        last_name="Finanzas",
        email="claudia.finanzas.test@sanbao.cl",
        is_active=True,
    )
    db_session.add(fin_person)
    db_session.flush()

    fin_user = User(
        person_id=fin_person.id,
        username="finanzas_strict_test",
        password_hash=get_password_hash("Finanzas2026!"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(fin_user)
    db_session.flush()

    db_session.add(
        UserCompanyRole(
            user_id=fin_user.id,
            company_id=clinica.id,
            role_id=fin_role.id,
            is_active=True,
        )
    )

    # Asegurar que exista al menos una atención clínica (ClinicalEncounter) para probar el bloqueo
    patient = db_session.query(Patient).first()
    if not patient:
        patient = Patient(person_id=person_uuid, record_number="FICH-2026-9901", is_active=True)
        db_session.add(patient)
        db_session.flush()
    practitioner = db_session.query(Practitioner).first()
    if not practitioner:
        practitioner = Practitioner(person_id=person_uuid, license_number="SIS-9901", specialty="Acupuntura", is_tutor=True, is_active=True)
        db_session.add(practitioner)
        db_session.flush()

    encounter = ClinicalEncounter(
        patient_id=patient.id,
        practitioner_id=practitioner.id,
        reason_for_consultation="Cefalea tensional y síndrome de ascenso de Yang de Hígado",
        status="VALIDATED",
    )
    db_session.add(encounter)
    db_session.commit()

    fin_token = create_access_token({"sub": fin_user.id, "company_id": clinica.id, "roles": ["ADMIN_FINANZAS"]})
    res_enc = client.get(
        f"/api/v1/clinical/encounters/{encounter.id}",
        headers={"Authorization": f"Bearer {fin_token}", "X-Company-ID": clinica.id},
    )
    assert res_enc.status_code == 403
    assert "ADMIN_FINANZAS" in res_enc.json()["detail"]

    # Verificar que el intento bloqueado quedó auditado en ClinicalAccessLog
    denied_log = (
        db_session.query(ClinicalAccessLog)
        .filter(
            ClinicalAccessLog.encounter_id == encounter.id,
            ClinicalAccessLog.user_id == fin_user.id,
            ClinicalAccessLog.action == "DENIED_ANAMNESIS_ACCESS_FINANCE",
        )
        .first()
    )
    assert denied_log is not None

