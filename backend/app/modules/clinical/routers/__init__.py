from app.modules.clinical.routers.patients import router as clinical_patients_router
from app.modules.clinical.routers.practitioners import router as clinical_practitioners_router
from app.modules.clinical.routers.appointments import router as clinical_appointments_router
from app.modules.clinical.routers.encounters import router as clinical_encounters_router
from app.modules.clinical.routers.supplies import router as clinical_supplies_router
from app.modules.clinical.routers.management import router as clinical_management_router

__all__ = [
    "clinical_patients_router",
    "clinical_practitioners_router",
    "clinical_appointments_router",
    "clinical_encounters_router",
    "clinical_supplies_router",
    "clinical_management_router",
]
