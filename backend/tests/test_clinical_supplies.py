import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.modules.institutional.models.company import Company
from app.modules.institutional.models.campus import Campus, Room
from app.modules.clinical.models.practitioner import Practitioner
from app.modules.clinical.services.supply_service import SupplyService, OFFICIAL_SANBAO_SUPPLIES
from app.modules.institutional.models.person import Person


def get_auth_token_and_clinica(client):
    login_res = client.post(
        "/api/v1/institutional/auth/login",
        json={"username": "admin", "password": "AdminSanBao2026!"},
    )
    token = login_res.json()["data"]["access_token"]
    companies = login_res.json()["data"]["available_companies"]
    clinica = next(c for c in companies if "Clínicos" in c["legal_name"] or "76987654" in c["rut"])
    return token, clinica["id"]


def test_seed_official_27_supplies(client: TestClient, db_session: Session):
    """Verifica que el catálogo de 27 insumos oficiales se inicialice con todas sus categorías."""
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    response = client.post("/api/v1/clinical/supplies/seed", headers=headers)
    assert response.status_code == 201
    data = response.json()["data"]

    # Deben ser exactamente los 27 insumos solicitados
    assert len(data) == 27
    names = [item["name"] for item in data]

    # 14 tipos de agujas
    assert "Agujas 25 x 25" in names
    assert "Agujas 25 x 30" in names
    assert "Agujas 25 x 40" in names
    assert "Agujas 30 x 30" in names
    assert "Agujas 30 x 40" in names
    assert "Agujas 16 x 13" in names
    assert "Agujas 18 x 13" in names
    assert "Agujas 20 x 13" in names
    assert "Agujas 22 x 40" in names
    assert "Agujas 18 x 25" in names
    assert "Agujas 25 x 75" in names
    assert "Agujas 30 x 75" in names
    assert "Agujas 30 x 100" in names
    assert "Agujas 35 x 125" in names

    # Moxas
    assert "Moxa c/humo" in names
    assert "Moxa s/humo" in names

    # Auriculoterapia
    assert "Semillas" in names
    assert "Chinchetas" in names
    assert "Imanes" in names

    # Descartables
    assert "Agujas hipodérmicas" in names
    assert "Lancetas" in names
    assert "Sabanilla" in names
    assert "Guantes" in names
    assert "Ventosas plásticas" in names

    # Equipos retornables
    assert "Electro" in names
    assert "Encendedor" in names
    assert "Parlante + cable" in names

    # Verificar banderas de retorno para equipos
    returnable_items = [item["name"] for item in data if item["is_returnable"]]
    assert set(returnable_items) == {"Electro", "Encendedor", "Parlante + cable"}


def test_shift_dispatch_and_return_cycle(client: TestClient, db_session: Session):
    """
    Verifica el flujo completo donde la Secretaria Clínica entrega insumos al terapeuta
    al inicio de turno y recibe los equipos y saldos al cierre.
    """
    token, clinica_id = get_auth_token_and_clinica(client)
    headers = {"Authorization": f"Bearer {token}", "X-Company-ID": clinica_id}

    # Asegurar insumos
    service = SupplyService(db_session)
    supplies = service.seed_official_supplies(clinica_id)
    supplies_map = {s.name: s.id for s in supplies}

    # Crear terapeuta
    person = Person(
        rut="13.456.789-K",
        first_name="Rodrigo",
        last_name="Bustamante",
        email="rodrigo.terapeuta@sanbao.cl",
        is_active=True,
    )
    db_session.add(person)
    db_session.commit()

    practitioner = Practitioner(
        person_id=person.id,
        license_number="ACU-2026-99",
        specialty="Acupuntura y Fitoterapia",
        is_active=True,
    )
    db_session.add(practitioner)
    db_session.commit()

    campus = db_session.query(Campus).first()
    room = db_session.query(Room).filter(Room.room_type == "CLINICAL_BOX").first()

    # 1. Secretaria entrega insumos al inicio de turno
    dispatch_payload = {
        "campus_id": campus.id,
        "practitioner_id": practitioner.id,
        "room_id": room.id if room else None,
        "shift_date": str(date.today()),
        "shift_type": "MANANA",
        "notes": "Entrega de turno mañana Box Tai Yang",
        "items": [
            {"supply_id": supplies_map["Agujas 25 x 25"], "quantity_delivered": 20},
            {"supply_id": supplies_map["Agujas 30 x 40"], "quantity_delivered": 15},
            {"supply_id": supplies_map["Moxa c/humo"], "quantity_delivered": 2},
            {"supply_id": supplies_map["Electro"], "quantity_delivered": 1, "condition_notes": "Equipo N° 3 operativo"},
            {"supply_id": supplies_map["Encendedor"], "quantity_delivered": 1},
            {"supply_id": supplies_map["Parlante + cable"], "quantity_delivered": 1, "condition_notes": "Cable USB + Parlante Bluetooth OK"},
        ],
    }

    res_dispatch = client.post("/api/v1/clinical/supplies/dispatches", json=dispatch_payload, headers=headers)
    assert res_dispatch.status_code == 201
    dispatch_data = res_dispatch.json()["data"]
    assert dispatch_data["status"] == "DISPATCHED"
    assert dispatch_data["dispatch_code"].startswith("ENT-")
    assert len(dispatch_data["items"]) == 6

    dispatch_id = dispatch_data["id"]
    item_ids = {it["supply_id"]: it["id"] for it in dispatch_data["items"]}

    # 2. Consultar lista de despachos del turno
    res_list = client.get(f"/api/v1/clinical/supplies/dispatches?campus_id={campus.id}", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()["data"]) >= 1

    # 3. Al cierre de turno, se registra la devolución de equipos y conteo de usados
    return_payload = {
        "notes": "Turno finalizado sin incidentes. Equipos devueltos íntegros.",
        "items": [
            {
                "item_id": item_ids[supplies_map["Agujas 25 x 25"]],
                "quantity_used": 16,
                "quantity_returned": 4,
            },
            {
                "item_id": item_ids[supplies_map["Electro"]],
                "quantity_used": 1,
                "quantity_returned": 1,
                "condition_notes": "Equipo Electro N° 3 devuelto limpio y operativo",
            },
            {
                "item_id": item_ids[supplies_map["Parlante + cable"]],
                "quantity_used": 1,
                "quantity_returned": 1,
                "condition_notes": "Parlante y cable guardados en recepción",
            },
        ],
    }

    res_return = client.post(f"/api/v1/clinical/supplies/dispatches/{dispatch_id}/return", json=return_payload, headers=headers)
    assert res_return.status_code == 200
    return_data = res_return.json()["data"]
    assert return_data["status"] == "RETURNED"
    assert return_data["returned_at"] is not None
