from app.modules.academic.models.program import Program, Curriculum, Course, CurriculumCourse
from app.modules.academic.models.period import AcademicPeriod, Cohort
from app.modules.academic.models.student import (
    Student,
    Enrollment,
    CohortEnrollment,
    StudentCourseTransfer,
    AcademicDocument,
    StudentOnboarding,
)
from app.modules.academic.models.evaluation import Evaluation, Grade, Attendance, ClinicalPracticeHour
from app.modules.academic.models.content import CourseClassContent

__all__ = [
    "Program",
    "Curriculum",
    "Course",
    "CurriculumCourse",
    "AcademicPeriod",
    "Cohort",
    "Student",
    "Enrollment",
    "CohortEnrollment",
    "StudentCourseTransfer",
    "AcademicDocument",
    "StudentOnboarding",
    "Evaluation",
    "Grade",
    "Attendance",
    "ClinicalPracticeHour",
    "CourseClassContent",
]
