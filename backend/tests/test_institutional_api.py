import pytest
from app.modules.institutional.models.company import Company


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_login_success(client):
    response = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "access_token" in data
    assert data["username"] == "admin"
    assert len(data["available_companies"]) == 2


def test_login_invalid_password(client):
    response = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "WrongPassword"},
    )
    assert response.status_code == 401


def test_switch_company(client, db_session):
    # 1. Login inicial
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    target_company_id = companies[1]["id"]

    # 2. Conmutar contexto
    switch_res = client.post(
        "/api/v1/institutional/auth/switch-company",
        headers={"Authorization": f"Bearer {token}"},
        json={"company_id": target_company_id},
    )
    assert switch_res.status_code == 200
    new_data = switch_res.json()["data"]
    assert new_data["active_company"]["id"] == target_company_id


def test_list_companies(client):
    # Obtener token
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]

    response = client.get(
        "/api/v1/institutional/companies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    companies = response.json()["data"]
    assert len(companies) >= 2


def test_create_person_valid_and_invalid_rut(client):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]

    # RUT válido
    valid_payload = {
        "rut": "12.345.678-5",
        "first_name": "Juan",
        "last_name": "Pérez",
        "second_last_name": "Gómez",
        "email": "juan.perez@sanbao.cl",
        "phone": "+56 9 8765 4321",
    }
    res_valid = client.post(
        "/api/v1/institutional/people",
        headers={"Authorization": f"Bearer {token}"},
        json=valid_payload,
    )
    assert res_valid.status_code == 201
    assert res_valid.json()["data"]["rut"] == "12345678-5"

    # RUT inválido (falla Módulo 11)
    invalid_payload = {
        "rut": "12.345.678-9",  # Dígito verificador incorrecto
        "first_name": "Pedro",
        "last_name": "Soto",
        "email": "pedro.soto@sanbao.cl",
    }
    res_invalid = client.post(
        "/api/v1/institutional/people",
        headers={"Authorization": f"Bearer {token}"},
        json=invalid_payload,
    )
    assert res_invalid.status_code == 422
