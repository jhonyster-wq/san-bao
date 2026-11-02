import os
import pytest
from fastapi.testclient import TestClient

# Configurar entorno de pruebas antes de importar dependencias de base de datos
os.environ["DATABASE_URL"] = "sqlite:///./test_sanbao.db"
os.environ["ENVIRONMENT"] = "testing"
os.environ["SECRET_KEY"] = "test_secret_key_for_san_bao_testing_123456789"

from app.core.database import Base, engine, SessionLocal, get_db
from app.core.init_db import init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Inicializa la base de datos de pruebas una vez para toda la sesión de test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield
    # Cleanup al finalizar tests
    if os.path.exists("./test_sanbao.db"):
        try:
            os.remove("./test_sanbao.db")
        except Exception:
            pass


@pytest.fixture
def db_session():
    """Proporciona una sesión de base de datos para cada test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Cliente de pruebas HTTP para interactuar con la API FastAPI."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
