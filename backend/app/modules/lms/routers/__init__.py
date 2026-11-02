from app.modules.lms.routers.courses import router as lms_courses_router
from app.modules.lms.routers.progress import router as lms_progress_router

__all__ = [
    "lms_courses_router",
    "lms_progress_router",
]
