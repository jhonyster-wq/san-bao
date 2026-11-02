from app.modules.institutional.routers.auth import router as auth_router
from app.modules.institutional.routers.companies import router as companies_router
from app.modules.institutional.routers.people import router as people_router
from app.modules.institutional.routers.campuses import router as campuses_router

__all__ = [
    "auth_router",
    "companies_router",
    "people_router",
    "campuses_router",
]
