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
