from app.modules.academic.routers.programs import router as academic_programs_router
from app.modules.academic.routers.periods import router as academic_periods_router
from app.modules.academic.routers.students import router as academic_students_router
from app.modules.academic.routers.coordinator import router as academic_coordinator_router
from app.modules.academic.routers.teacher_portal import router as academic_teacher_router

__all__ = [
    "academic_programs_router",
    "academic_periods_router",
    "academic_students_router",
    "academic_coordinator_router",
    "academic_teacher_router",
]
