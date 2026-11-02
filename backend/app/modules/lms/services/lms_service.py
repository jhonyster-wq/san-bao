from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.lms.models.course import LMSCourse, CourseModule, Lesson
from app.modules.lms.models.progress import LMSEnrollment, LessonProgress, Assignment, Submission
from app.modules.lms.schemas.course import LMSCourseCreate, CourseModuleCreate, LessonCreate
from app.modules.lms.schemas.progress import AssignmentCreate, SubmissionCreate, SubmissionGradeRequest
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, SanBaoException


class LMSService:
    def __init__(self, db: Session):
        self.db = db

    def create_course(self, data: LMSCourseCreate) -> LMSCourse:
        existing = self.db.query(LMSCourse).filter(LMSCourse.code == data.code.strip().upper(), LMSCourse.deleted_at.is_(None)).first()
        if existing:
            raise EntityAlreadyExistsException("Curso LMS", "código", data.code)

        course = LMSCourse(
            code=data.code.strip().upper(),
            title=data.title.strip(),
            summary=data.summary,
            cover_image_url=data.cover_image_url,
            instructor_name=data.instructor_name,
            academic_course_id=data.academic_course_id,
            academic_cohort_id=data.academic_cohort_id,
            is_published=data.is_published,
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_course(self, course_id: str) -> LMSCourse:
        course = self.db.query(LMSCourse).filter(LMSCourse.id == course_id, LMSCourse.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException("Curso LMS", course_id)
        return course

    def create_module(self, data: CourseModuleCreate) -> CourseModule:
        course = self.get_course(data.course_id)
        module = CourseModule(
            course_id=course.id,
            title=data.title.strip(),
            description=data.description,
            order_index=data.order_index,
            is_published=data.is_published,
        )
        self.db.add(module)
        self.db.commit()
        self.db.refresh(module)
        return module

    def create_lesson(self, data: LessonCreate) -> Lesson:
        module = self.db.query(CourseModule).filter(CourseModule.id == data.module_id, CourseModule.deleted_at.is_(None)).first()
        if not module:
            raise EntityNotFoundException("Módulo", data.module_id)

        lesson = Lesson(
            module_id=data.module_id,
            title=data.title.strip(),
            content_type=data.content_type,
            content_body=data.content_body,
            video_url=data.video_url,
            attachment_url=data.attachment_url,
            duration_minutes=data.duration_minutes,
            order_index=data.order_index,
            is_published=data.is_published,
        )
        self.db.add(lesson)
        self.db.commit()
        self.db.refresh(lesson)
        return lesson

    def enroll_user(self, course_id: str, user_id: str) -> LMSEnrollment:
        """Matricula o habilita a un usuario en un curso del LMS."""
        existing = (
            self.db.query(LMSEnrollment)
            .filter(
                LMSEnrollment.course_id == course_id,
                LMSEnrollment.user_id == user_id,
                LMSEnrollment.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            existing.status = "ACTIVE"
            self.db.commit()
            return existing

        enrollment = LMSEnrollment(
            course_id=course_id,
            user_id=user_id,
            progress_percentage=Decimal(0),
            status="ACTIVE",
        )
        self.db.add(enrollment)
        self.db.commit()
        self.db.refresh(enrollment)
        return enrollment

    def mark_lesson_progress(self, lesson_id: str, user_id: str, is_completed: bool = True) -> LessonProgress:
        """Marca una lección como completada y recalcula el porcentaje de avance global."""
        lesson = self.db.query(Lesson).filter(Lesson.id == lesson_id, Lesson.deleted_at.is_(None)).first()
        if not lesson:
            raise EntityNotFoundException("Lección", lesson_id)

        progress = (
            self.db.query(LessonProgress)
            .filter(LessonProgress.lesson_id == lesson_id, LessonProgress.user_id == user_id)
            .first()
        )
        if not progress:
            progress = LessonProgress(lesson_id=lesson_id, user_id=user_id, is_completed=is_completed)
            self.db.add(progress)
        else:
            progress.is_completed = is_completed
            progress.completed_at = datetime.now(timezone.utc)

        self.db.commit()

        # Recalcular progreso en el curso
        self._recalculate_course_progress(lesson.module.course_id, user_id)
        return progress

    def _recalculate_course_progress(self, course_id: str, user_id: str):
        total_lessons = (
            self.db.query(Lesson)
            .join(CourseModule)
            .filter(CourseModule.course_id == course_id, Lesson.deleted_at.is_(None), Lesson.is_published == True)
            .count()
        )
        if total_lessons == 0:
            return

        completed_lessons = (
            self.db.query(LessonProgress)
            .join(Lesson)
            .join(CourseModule)
            .filter(
                CourseModule.course_id == course_id,
                LessonProgress.user_id == user_id,
                LessonProgress.is_completed == True,
            )
            .count()
        )

        progress_pct = round((Decimal(completed_lessons) / Decimal(total_lessons)) * Decimal(100), 1)

        enrollment = (
            self.db.query(LMSEnrollment)
            .filter(LMSEnrollment.course_id == course_id, LMSEnrollment.user_id == user_id)
            .first()
        )
        if enrollment:
            enrollment.progress_percentage = progress_pct
            if progress_pct >= Decimal(100):
                enrollment.status = "COMPLETED"
                enrollment.completed_at = datetime.now(timezone.utc)
            self.db.commit()

    def create_assignment(self, data: AssignmentCreate) -> Assignment:
        assignment = Assignment(
            lesson_id=data.lesson_id,
            title=data.title.strip(),
            instructions=data.instructions,
            max_score=data.max_score,
            due_date=data.due_date,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def submit_assignment(self, data: SubmissionCreate, user_id: str) -> Submission:
        submission = Submission(
            assignment_id=data.assignment_id,
            user_id=user_id,
            content_text=data.content_text,
            attachment_url=data.attachment_url,
            status="SUBMITTED",
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def grade_submission(self, submission_id: str, data: SubmissionGradeRequest, graded_by: str) -> Submission:
        submission = self.db.query(Submission).filter(Submission.id == submission_id, Submission.deleted_at.is_(None)).first()
        if not submission:
            raise EntityNotFoundException("Entrega", submission_id)

        submission.score = data.score
        submission.feedback = data.feedback
        submission.graded_by = graded_by
        submission.status = "GRADED"
        self.db.commit()
        self.db.refresh(submission)
        return submission
