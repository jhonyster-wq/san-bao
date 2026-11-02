from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.core.exceptions import EntityNotFoundException, SanBaoException
from app.modules.academic.models.program import Course, Program, CurriculumCourse, Curriculum
from app.modules.academic.models.period import Cohort, AcademicPeriod
from app.modules.academic.models.student import Student, Enrollment, CohortEnrollment
from app.modules.academic.models.evaluation import Evaluation, Grade, Attendance
from app.modules.academic.models.content import CourseClassContent
from app.modules.academic.schemas.teacher_portal import (
    TeacherCourseResponse,
    EvaluationCreateRequest,
    TeacherGradeEntryRequest,
    BatchAttendanceSaveRequest,
    ContentUploadRequest,
)
from app.modules.institutional.models.person import Person
from app.modules.institutional.models.user import User

logger = logging.getLogger("sanbao.academic.teacher")


class TeacherPortalService:
    def __init__(self, db: Session):
        self.db = db

    def _get_default_teacher_person(self) -> Optional[Person]:
        """Obtiene la persona asociada al docente titular de muestra (Prof. Zhiwei Chen)."""
        docente_user = self.db.query(User).filter(User.username == "docente").first()
        if docente_user and docente_user.person:
            return docente_user.person
        # Fallback a búsqueda por RUT
        person = self.db.query(Person).filter(Person.rut == "148901234").first()
        return person

    def ensure_sample_teacher_data(self, teacher_person_id: Optional[str] = None) -> Person:
        """Asegura que existan cursos asignados, evaluaciones, asistencias y contenidos pedagógicos de muestra."""
        if not teacher_person_id:
            teacher_person = self._get_default_teacher_person()
            if not teacher_person:
                # Crear persona si no existe
                teacher_person = Person(
                    rut="148901234",
                    first_name="Zhiwei",
                    last_name="Chen",
                    second_last_name="Wang",
                    email="zhiwei.chen@sanbao.cl",
                    phone="+56 9 6123 7890",
                    gender="MALE",
                    is_active=True,
                )
                self.db.add(teacher_person)
                self.db.commit()
                self.db.refresh(teacher_person)
            teacher_person_id = teacher_person.id
        else:
            teacher_person = self.db.query(Person).filter(Person.id == teacher_person_id).first()

        # 1. Asegurar programas y cursos
        prog_mtc = self.db.query(Program).filter(Program.code == "DIP-MTC").first()
        if not prog_mtc:
            prog_mtc = Program(
                code="DIP-MTC",
                name="Diplomado en Medicina China Clásica",
                program_type="DIPLOMADO",
                degree_title="Acupunturista y Terapeuta MTC",
                total_semesters=4,
                total_theoretical_hours=480,
                total_practical_hours=320,
                min_clinical_hours=240,
                is_active=True,
            )
            self.db.add(prog_mtc)
            self.db.commit()
            self.db.refresh(prog_mtc)

        prog_tuina = self.db.query(Program).filter(Program.code == "DIP-TUINA").first()
        if not prog_tuina:
            prog_tuina = Program(
                code="DIP-TUINA",
                name="Diplomado en Masaje Terapéutico Tui Na",
                program_type="DIPLOMADO",
                degree_title="Terapeuta en Tui Na y Ventosas",
                total_semesters=2,
                total_theoretical_hours=240,
                total_practical_hours=180,
                min_clinical_hours=120,
                is_active=True,
            )
            self.db.add(prog_tuina)
            self.db.commit()
            self.db.refresh(prog_tuina)

        # 2. Cursos asignados a este docente
        courses_def = [
            ("MTC-101", "Fundamentos de Medicina Tradicional China", prog_mtc.id, 60, 40, 20, 6),
            ("MTC-201", "Puntos y Meridianos Acupunturales I", prog_mtc.id, 50, 50, 40, 8),
            ("TUI-101", "Técnicas Básicas de Tuina y Masaje Terapéutico", prog_tuina.id, 40, 60, 30, 6),
        ]

        assigned_courses = []
        for code, name, pid, th, ph, ch, cr in courses_def:
            c = self.db.query(Course).filter(Course.code == code).first()
            if not c:
                c = Course(
                    code=code,
                    name=name,
                    description=f"Cátedra oficial de {name} impartida en Escuela San Bao.",
                    program_id=pid,
                    teacher_id=teacher_person_id,
                    theoretical_hours=th,
                    practical_hours=ph,
                    clinical_hours=ch,
                    credits=cr,
                    is_active=True,
                )
                self.db.add(c)
                self.db.commit()
                self.db.refresh(c)
            else:
                c.teacher_id = teacher_person_id
                if pid and not c.program_id:
                    c.program_id = pid
                self.db.commit()
            assigned_courses.append(c)

        # Incluir otros cursos que pudieran haber sido asignados dinámicamente a este docente
        extra_courses = self.db.query(Course).filter(Course.teacher_id == teacher_person_id, Course.deleted_at.is_(None)).all()
        for ec in extra_courses:
            if ec.id not in [x.id for x in assigned_courses]:
                assigned_courses.append(ec)

        # 3. Cohorte activa
        period = self.db.query(AcademicPeriod).first()
        if not period:
            period = AcademicPeriod(
                code="2026-S1",
                name="Primer Semestre 2026",
                year=2026,
                semester_number=1,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 7, 31),
                is_active=True,
            )
            self.db.add(period)
            self.db.commit()
            self.db.refresh(period)

        # Asegurar cohorte para cada curso asignado
        course_cohort_map = {}
        for c in assigned_courses:
            ch = self.db.query(Cohort).filter(Cohort.course_id == c.id).first()
            if not ch:
                ch = Cohort(
                    academic_period_id=period.id,
                    course_id=c.id,
                    teacher_id=teacher_person_id,
                    code=f"COH-2026-{c.code}",
                    quota=30,
                    status="IN_PROGRESS",
                )
                self.db.add(ch)
                self.db.commit()
                self.db.refresh(ch)
            course_cohort_map[c.id] = ch

        main_course = assigned_courses[0]
        cohort = course_cohort_map[main_course.id]

        # 4. Estudiantes de muestra matriculados
        students_data = [
            ("198765430", "Diego", "Valenzuela", "MAT-2026-0001"),
            ("187654321", "Camila", "Soto", "MAT-2026-0002"),
            ("176543210", "Ignacio", "Morales", "MAT-2026-0003"),
            ("165432109", "Valentina", "Araya", "MAT-2026-0004"),
        ]
        sample_students = []
        for rut_clean, fname, lname, mat in students_data:
            p = self.db.query(Person).filter(Person.rut == rut_clean).first()
            if not p:
                p = Person(rut=rut_clean, first_name=fname, last_name=lname, email=f"{fname.lower()}@sanbao.cl", is_active=True)
                self.db.add(p)
                self.db.commit()
                self.db.refresh(p)
            st = self.db.query(Student).filter(Student.person_id == p.id).first()
            if not st:
                cur_num = mat
                counter = 1
                while self.db.query(Student).filter(Student.student_number == cur_num).first():
                    cur_num = f"MAT-2026-{counter:04d}"
                    counter += 1
                st = Student(person_id=p.id, student_number=cur_num, admission_date=date(2026, 3, 1), status="REGULAR")
                self.db.add(st)
                self.db.commit()
                self.db.refresh(st)
            # Asegurar matrícula del estudiante en el programa
            enr = self.db.query(Enrollment).filter(Enrollment.student_id == st.id, Enrollment.program_id == prog_mtc.id).first()
            if not enr:
                enr = Enrollment(
                    student_id=st.id,
                    program_id=prog_mtc.id,
                    academic_period_id=period.id,
                    enrollment_date=date(2026, 3, 1),
                    status="CONFIRMED",
                )
                self.db.add(enr)
                self.db.commit()
                self.db.refresh(enr)
            # Matricular en la cohorte de cada curso asignado
            for c in assigned_courses:
                c_ch = course_cohort_map[c.id]
                cenr = self.db.query(CohortEnrollment).filter(CohortEnrollment.cohort_id == c_ch.id, CohortEnrollment.student_id == st.id).first()
                if not cenr:
                    cenr = CohortEnrollment(cohort_id=c_ch.id, student_id=st.id, enrollment_id=enr.id, status="ENROLLED")
                    self.db.add(cenr)
                    self.db.commit()
            sample_students.append(st)

        # 5. Evaluaciones, calificaciones, asistencias y contenidos para cada curso asignado
        for crs in assigned_courses:
            crs_cohort = course_cohort_map[crs.id]
            evals_def = [
                (f"Certamen 1: Fundamentos Teóricos {crs.code}", 30.0, date(2026, 4, 15)),
                (f"Taller Práctico y Casos Clínicos {crs.code}", 30.0, date(2026, 5, 20)),
                (f"Examen Semestral Integrador {crs.code}", 40.0, date(2026, 7, 5)),
            ]
            eval_objs = []
            for ename, weight, edate in evals_def:
                ev = (
                    self.db.query(Evaluation)
                    .filter(Evaluation.cohort_id == crs_cohort.id, Evaluation.name == ename)
                    .first()
                )
                if not ev:
                    ev = Evaluation(
                        cohort_id=crs_cohort.id,
                        course_id=crs.id,
                        name=ename,
                        weight_percentage=weight,
                        evaluation_date=edate,
                        description=f"Evaluación oficial para {crs.name}",
                    )
                    self.db.add(ev)
                    self.db.commit()
                    self.db.refresh(ev)
                elif not ev.course_id:
                    ev.course_id = crs.id
                    self.db.commit()
                eval_objs.append(ev)

            # 6. Calificaciones de muestra
            sample_scores = {
                sample_students[0].id: [6.8, 6.5, 7.0],
                sample_students[1].id: [6.2, 5.8, 6.4],
                sample_students[2].id: [5.0, 4.5, 5.2],
                sample_students[3].id: [6.5, 6.9, 6.7],
            }
            for st_id, scores in sample_scores.items():
                for ev, sc in zip(eval_objs, scores):
                    g = self.db.query(Grade).filter(Grade.evaluation_id == ev.id, Grade.student_id == st_id).first()
                    if not g:
                        g = Grade(evaluation_id=ev.id, student_id=st_id, score=sc, feedback="Buen desempeño en actividades pedagógicas.")
                        self.db.add(g)
            self.db.commit()

            # 7. Asistencia de muestra
            past_dates = [date(2026, 3, 10), date(2026, 3, 17), date(2026, 3, 24), date(2026, 3, 31)]
            topics = [
                f"Clase 1: Introducción y Marco Teórico de {crs.name}",
                f"Clase 2: Fundamentos Metodológicos y Práctica I",
                f"Clase 3: Desarrollo de Casos Clínicos y Taller",
                f"Clase 4: Integración Práctica y Revisión",
            ]
            for idx, (dt, top) in enumerate(zip(past_dates, topics), 1):
                for st in sample_students:
                    att = (
                        self.db.query(Attendance)
                        .filter(
                            Attendance.course_id == crs.id,
                            Attendance.student_id == st.id,
                            Attendance.class_date == dt,
                        )
                        .first()
                    )
                    if not att:
                        is_pres = not (st.id == sample_students[2].id and idx == 2)
                        att = Attendance(
                            cohort_id=crs_cohort.id,
                            course_id=crs.id,
                            student_id=st.id,
                            class_date=dt,
                            class_number=idx,
                            session_topic=top,
                            status="PRESENTE" if is_pres else "JUSTIFICADO",
                            is_present=is_pres,
                            is_excused=not is_pres,
                            notes="Asistencia registrada" if is_pres else "Licencia médica acreditada",
                        )
                        self.db.add(att)
            self.db.commit()

            # 8. Contenidos de muestra
            contents_def = [
                (1, f"Clase 1: Introducción a {crs.name}", f"Diapositivas Cátedra Clase 1 - {crs.code}", "PRESENTACION_PPT", "PPT 8.5 MB", f"/static/academic/{crs.code.lower()}_clase1.pdf", "Presentación base con fundamentos teóricos."),
                (1, f"Clase 1: Introducción a {crs.name}", f"Guía de Lectura N° 1 - {crs.code}", "DOCUMENTO_PDF", "PDF 1.8 MB", f"/static/academic/{crs.code.lower()}_guia1.pdf", "Texto de lectura obligatoria para cátedra."),
                (2, f"Clase 2: Métodos y Práctica de {crs.name}", f"Manual Práctico de Casos {crs.code}", "DOCUMENTO_PDF", "PDF 3.2 MB", f"/static/academic/{crs.code.lower()}_manual.pdf", "Material de estudio complementario y esquemas."),
                (3, f"Clase 3: Integración de {crs.name}", f"Grabación Sesión Sincrónica - Clase 3", "VIDEO_CLASE", "Video 65 min", f"https://sanbao.cl/clases/{crs.code.lower()}-clase3", "Video de cátedra con demostración en vivo."),
                (4, f"Clase 4: Evaluación y Cierre de Módulo", f"Pauta de Evaluación y Rúbrica {crs.code}", "DOCUMENTO_PDF", "PDF 1.2 MB", f"/static/academic/{crs.code.lower()}_rubrica.pdf", "Rúbrica de evaluación clínica y teórica."),
            ]
            for cnum, ctitle, rtitle, rtype, fsize, aurl, desc in contents_def:
                cnt = (
                    self.db.query(CourseClassContent)
                    .filter(
                        CourseClassContent.course_id == crs.id,
                        CourseClassContent.class_number == cnum,
                        CourseClassContent.resource_title == rtitle,
                    )
                    .first()
                )
                if not cnt:
                    cnt = CourseClassContent(
                        course_id=crs.id,
                        cohort_id=crs_cohort.id,
                        class_number=cnum,
                        class_title=ctitle,
                        resource_title=rtitle,
                        resource_type=rtype,
                        attachment_url=aurl,
                        file_size_text=fsize,
                        description=desc,
                        uploaded_by_id=None,
                        uploaded_by_name="Prof. Zhiwei Chen",
                        is_published=True,
                    )
                    self.db.add(cnt)
            self.db.commit()
        return teacher_person

    # =========================================================================
    # 1. VER LOS CURSOS ASIGNADOS
    # =========================================================================
    def list_teacher_assigned_courses(self, teacher_person_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista las asignaturas y cursos asignados al docente con métricas de alumnos, notas y asistencia."""
        teacher_person = self.ensure_sample_teacher_data(teacher_person_id)
        target_teacher_id = teacher_person.id

        # Buscar cursos donde el docente es titular o cursos transversales
        courses = (
            self.db.query(Course)
            .filter(Course.deleted_at.is_(None))
            .filter((Course.teacher_id == target_teacher_id) | (Course.teacher_id.is_(None)))
            .order_by(Course.code.asc())
            .all()
        )

        result = []
        for c in courses:
            # Buscar cohorte asociada
            cohort = self.db.query(Cohort).filter(Cohort.course_id == c.id).first()
            if not cohort and c.program_id:
                cohort = self.db.query(Cohort).join(Course, Course.id == Cohort.course_id).filter(Course.program_id == c.program_id).first()
            if not cohort:
                cohort = self.db.query(Cohort).first()

            # Contar alumnos
            enrolled_count = 0
            student_ids = []
            if cohort:
                enrollments = (
                    self.db.query(CohortEnrollment)
                    .filter(CohortEnrollment.cohort_id == cohort.id, CohortEnrollment.deleted_at.is_(None))
                    .all()
                )
                enrolled_count = len(enrollments)
                student_ids = [e.student_id for e in enrollments]

            # Contar evaluaciones
            evals_query = self.db.query(Evaluation).filter(Evaluation.deleted_at.is_(None))
            if cohort:
                evals_query = evals_query.filter(
                    (Evaluation.course_id == c.id) | ((Evaluation.cohort_id == cohort.id) & (Evaluation.course_id.is_(None)))
                )
            else:
                evals_query = evals_query.filter(Evaluation.course_id == c.id)
            evals = evals_query.all()
            evals_count = len(evals)

            # Promedio general del curso
            avg_grade = None
            if evals and student_ids:
                eval_ids = [e.id for e in evals]
                grades = (
                    self.db.query(Grade)
                    .filter(Grade.evaluation_id.in_(eval_ids), Grade.student_id.in_(student_ids), Grade.deleted_at.is_(None))
                    .all()
                )
                if grades:
                    avg_grade = round(sum(float(g.score) for g in grades) / len(grades), 1)

            # Asistencia acumulada
            att_records = (
                self.db.query(Attendance)
                .filter(Attendance.course_id == c.id, Attendance.deleted_at.is_(None))
                .all()
            )
            avg_att_pct = 100.0
            if att_records:
                present_count = sum(1 for a in att_records if a.is_present or a.status == "PRESENTE")
                avg_att_pct = round((present_count / len(att_records)) * 100.0, 1)

            # Contar contenidos subidos
            contents_count = (
                self.db.query(CourseClassContent)
                .filter(CourseClassContent.course_id == c.id, CourseClassContent.deleted_at.is_(None))
                .count()
            )

            result.append({
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "description": c.description,
                "program_id": c.program_id,
                "program_name": c.program.name if c.program else "Transversal / Formación Continua",
                "program_type": c.program.program_type if c.program else "CURSO",
                "cohort_id": cohort.id if cohort else None,
                "cohort_name": getattr(cohort, "name", None) or (f"Sección {cohort.code}" if cohort else "General"),
                "theoretical_hours": c.theoretical_hours,
                "practical_hours": c.practical_hours,
                "clinical_hours": c.clinical_hours,
                "credits": c.credits,
                "enrolled_students_count": enrolled_count,
                "evaluations_count": evals_count,
                "contents_count": contents_count,
                "average_attendance_pct": avg_att_pct,
                "attendance_average": avg_att_pct,
                "average_grade": avg_grade,
                "grade_average": avg_grade,
                "cohort_code": cohort.code if cohort else "COH-2026",
                "is_active": c.is_active,
            })

        return result

    # =========================================================================
    # 2. REGISTRAR NOTA POR ALUMNO
    # =========================================================================
    def get_course_students_and_grades(self, course_id: str, cohort_id: Optional[str] = None) -> Dict[str, Any]:
        """Obtiene la planilla de calificaciones del curso, listando evaluaciones y notas de cada estudiante."""
        course = self.db.query(Course).filter(Course.id == course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException(f"Asignatura con ID {course_id} no encontrada.")

        # Obtener o inferir cohorte
        if not cohort_id:
            ch = self.db.query(Cohort).filter(Cohort.course_id == course.id).first()
            if not ch and course.program_id:
                ch = self.db.query(Cohort).join(Course, Course.id == Cohort.course_id).filter(Course.program_id == course.program_id).first()
            if ch:
                cohort_id = ch.id

        # Evaluaciones del curso
        eval_query = self.db.query(Evaluation).filter(Evaluation.deleted_at.is_(None))
        if cohort_id:
            eval_query = eval_query.filter(
                (Evaluation.course_id == course.id) | ((Evaluation.cohort_id == cohort_id) & (Evaluation.course_id.is_(None)))
            )
        else:
            eval_query = eval_query.filter(Evaluation.course_id == course.id)
        evaluations = eval_query.order_by(Evaluation.evaluation_date.asc()).all()

        # Estudiantes
        students_query = self.db.query(Student).filter(Student.deleted_at.is_(None))
        if cohort_id:
            students_query = (
                students_query.join(CohortEnrollment, CohortEnrollment.student_id == Student.id)
                .filter(CohortEnrollment.cohort_id == cohort_id, CohortEnrollment.deleted_at.is_(None))
            )
        students = students_query.order_by(Student.student_number.asc()).all()

        students_list = []
        all_student_averages = []

        for st in students:
            person = st.person
            full_name = f"{person.first_name} {person.last_name}" if person else f"Alumno {st.student_number}"
            rut_formatted = person.rut_formatted if person and hasattr(person, "rut_formatted") else (person.rut if person else "--")

            # Mapear notas del alumno
            grades_map = {}
            weighted_sum = 0.0
            weights_total = 0.0
            simple_sum = 0.0
            count = 0

            for ev in evaluations:
                g = self.db.query(Grade).filter(Grade.evaluation_id == ev.id, Grade.student_id == st.id, Grade.deleted_at.is_(None)).first()
                if g:
                    sc = float(g.score)
                    grades_map[ev.id] = {
                        "grade_id": g.id,
                        "evaluation_name": ev.name,
                        "score": sc,
                        "feedback": g.feedback,
                    }
                    w = float(ev.weight_percentage)
                    weighted_sum += sc * (w / 100.0)
                    weights_total += w
                    simple_sum += sc
                    count += 1
                else:
                    grades_map[ev.id] = {
                        "grade_id": None,
                        "evaluation_name": ev.name,
                        "score": None,
                        "feedback": None,
                    }

            final_avg = None
            if weights_total >= 99.0:
                final_avg = round(weighted_sum, 1)
            elif count > 0:
                final_avg = round(simple_sum / count, 1)

            if final_avg is not None:
                all_student_averages.append(final_avg)

            students_list.append({
                "student_id": st.id,
                "student_number": st.student_number,
                "student_name": full_name,
                "rut": rut_formatted,
                "status": st.status,
                "grades": grades_map,
                "weighted_average": final_avg,
                "is_approved": (final_avg is not None and final_avg >= 4.0),
            })

        course_average = round(sum(all_student_averages) / len(all_student_averages), 1) if all_student_averages else None
        approval_rate = (
            round((sum(1 for a in all_student_averages if a >= 4.0) / len(all_student_averages)) * 100.0, 1)
            if all_student_averages
            else 0.0
        )

        return {
            "course": {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "program_name": course.program.name if course.program else "General",
                "cohort_id": cohort_id,
            },
            "evaluations": [
                {
                    "id": ev.id,
                    "name": ev.name,
                    "weight_percentage": float(ev.weight_percentage),
                    "evaluation_date": ev.evaluation_date.isoformat(),
                    "description": ev.description,
                }
                for ev in evaluations
            ],
            "students": students_list,
            "metrics": {
                "total_students": len(students_list),
                "course_average": course_average,
                "approval_rate": approval_rate,
            },
        }

    def create_course_evaluation(self, course_id: str, payload: EvaluationCreateRequest) -> Dict[str, Any]:
        """Crea una nueva evaluación programada para el curso cátedra."""
        course = self.db.query(Course).filter(Course.id == course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException(f"Asignatura {course_id} no encontrada.")

        cohort_id = payload.cohort_id
        if not cohort_id:
            ch = self.db.query(Cohort).filter(Cohort.course_id == course.id).first()
            if not ch and course.program_id:
                ch = self.db.query(Cohort).join(Course, Course.id == Cohort.course_id).filter(Course.program_id == course.program_id).first()
            if ch:
                cohort_id = ch.id
        if not cohort_id:
            first_cohort = self.db.query(Cohort).first()
            cohort_id = first_cohort.id if first_cohort else None

        if not cohort_id:
            raise SanBaoException("No se encontró una cohorte académica para asociar la evaluación.")

        ev = Evaluation(
            cohort_id=cohort_id,
            course_id=course.id,
            name=payload.name,
            weight_percentage=payload.weight_percentage,
            evaluation_date=payload.evaluation_date,
            description=payload.description or f"Evaluación de cátedra para {course.name}",
        )
        self.db.add(ev)
        self.db.commit()
        self.db.refresh(ev)

        return {
            "id": ev.id,
            "course_id": ev.course_id,
            "cohort_id": ev.cohort_id,
            "name": ev.name,
            "weight_percentage": float(ev.weight_percentage),
            "evaluation_date": ev.evaluation_date.isoformat(),
        }

    def record_student_grade(self, course_id: str, payload: TeacherGradeEntryRequest, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Registra o actualiza la calificación (escala 1.0 a 7.0) de un alumno en una evaluación."""
        if payload.score < 1.0 or payload.score > 7.0:
            raise SanBaoException("La calificación debe estar dentro de la escala oficial chilena de 1.0 a 7.0")

        evaluation = self.db.query(Evaluation).filter(Evaluation.id == payload.evaluation_id).first()
        if not evaluation:
            raise EntityNotFoundException("Evaluación no encontrada.")

        student = self.db.query(Student).filter(Student.id == payload.student_id).first()
        if not student:
            raise EntityNotFoundException("Estudiante no encontrado.")

        grade = (
            self.db.query(Grade)
            .filter(Grade.evaluation_id == payload.evaluation_id, Grade.student_id == payload.student_id)
            .first()
        )
        if not grade:
            grade = Grade(
                evaluation_id=payload.evaluation_id,
                student_id=payload.student_id,
                score=payload.score,
                feedback=payload.feedback,
                graded_by=user_id,
            )
            self.db.add(grade)
        else:
            grade.score = payload.score
            if payload.feedback is not None:
                grade.feedback = payload.feedback
            if user_id:
                grade.graded_by = user_id

        self.db.commit()
        self.db.refresh(grade)

        return {
            "grade_id": grade.id,
            "evaluation_id": grade.evaluation_id,
            "evaluation_name": evaluation.name,
            "student_id": grade.student_id,
            "score": float(grade.score),
            "feedback": grade.feedback,
            "is_approved": float(grade.score) >= 4.0,
        }

    # =========================================================================
    # 3. REGISTRAR ASISTENCIA POR ALUMNO
    # =========================================================================
    def get_course_attendance(
        self,
        course_id: str,
        cohort_id: Optional[str] = None,
        class_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Obtiene la planilla de asistencia del curso para una fecha y el resumen histórico de sesiones."""
        course = self.db.query(Course).filter(Course.id == course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException(f"Asignatura {course_id} no encontrada.")

        if not cohort_id:
            ch = self.db.query(Cohort).filter(Cohort.course_id == course.id).first()
            if not ch and course.program_id:
                ch = self.db.query(Cohort).join(Course, Course.id == Cohort.course_id).filter(Course.program_id == course.program_id).first()
            if ch:
                cohort_id = ch.id

        if not class_date:
            class_date = date.today()

        # Buscar sesiones pasadas registradas de este curso
        past_dates = (
            self.db.query(
                Attendance.class_date,
                Attendance.class_number,
                Attendance.session_topic,
                func.count(Attendance.id).label("total_records"),
                func.sum(case((Attendance.is_present == True, 1), else_=0)).label("present_count"),
            )
            .filter(Attendance.course_id == course.id, Attendance.deleted_at.is_(None))
            .group_by(Attendance.class_date, Attendance.class_number, Attendance.session_topic)
            .order_by(Attendance.class_date.desc())
            .all()
        )

        past_sessions = [
            {
                "class_date": row[0].isoformat(),
                "class_number": row[1] or 1,
                "session_topic": row[2] or f"Clase del {row[0].isoformat()}",
                "total_records": row[3],
                "present_count": row[4] or 0,
                "attendance_rate": round(((row[4] or 0) / max(row[3], 1)) * 100.0, 1),
            }
            for row in past_dates
        ]

        total_classes_recorded = len(past_dates)

        # Detectar número de clase sugerido y tema si ya existe registro para la fecha consultada
        current_session_info = next((s for s in past_sessions if s["class_date"] == class_date.isoformat()), None)
        suggested_class_number = current_session_info["class_number"] if current_session_info else total_classes_recorded + 1
        suggested_topic = current_session_info["session_topic"] if current_session_info else f"Clase {suggested_class_number}: Materia de cátedra"

        # Obtener nómina de alumnos
        students_query = self.db.query(Student).filter(Student.deleted_at.is_(None))
        if cohort_id:
            students_query = (
                students_query.join(CohortEnrollment, CohortEnrollment.student_id == Student.id)
                .filter(CohortEnrollment.cohort_id == cohort_id, CohortEnrollment.deleted_at.is_(None))
            )
        students = students_query.order_by(Student.student_number.asc()).all()

        students_attendance = []
        for st in students:
            person = st.person
            full_name = f"{person.first_name} {person.last_name}" if person else f"Alumno {st.student_number}"
            rut_formatted = person.rut_formatted if person and hasattr(person, "rut_formatted") else (person.rut if person else "--")

            # Asistencia del día consultado
            day_att = (
                self.db.query(Attendance)
                .filter(
                    Attendance.course_id == course.id,
                    Attendance.student_id == st.id,
                    Attendance.class_date == class_date,
                    Attendance.deleted_at.is_(None),
                )
                .first()
            )

            # Historial acumulado del estudiante en este curso
            st_history = (
                self.db.query(Attendance)
                .filter(
                    Attendance.course_id == course.id,
                    Attendance.student_id == st.id,
                    Attendance.deleted_at.is_(None),
                )
                .all()
            )
            attended_count = sum(1 for a in st_history if a.is_present or a.status == "PRESENTE")
            total_st_classes = len(st_history)
            att_percentage = round((attended_count / total_st_classes) * 100.0, 1) if total_st_classes > 0 else 100.0

            students_attendance.append({
                "student_id": st.id,
                "student_number": st.student_number,
                "student_name": full_name,
                "rut": rut_formatted,
                "status": day_att.status if day_att else "PRESENTE",
                "notes": day_att.notes if day_att else "",
                "attended_classes_count": attended_count,
                "total_student_classes": total_st_classes,
                "attendance_percentage": att_percentage,
                "is_at_risk": att_percentage < 75.0,  # Exigencia mínima 75% reglamentaria
            })

        return {
            "course": {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "cohort_id": cohort_id,
            },
            "class_date": class_date.isoformat(),
            "class_number": suggested_class_number,
            "session_topic": suggested_topic,
            "total_classes_recorded": total_classes_recorded,
            "past_sessions": past_sessions,
            "students": students_attendance,
        }

    def record_session_attendance(self, course_id: str, payload: BatchAttendanceSaveRequest) -> Dict[str, Any]:
        """Guarda en lote la asistencia de todos los alumnos para una fecha y sesión de clase."""
        course = self.db.query(Course).filter(Course.id == course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException(f"Asignatura {course_id} no encontrada.")

        cohort_id = payload.cohort_id
        if not cohort_id:
            ch = self.db.query(Cohort).filter(Cohort.course_id == course.id).first()
            if not ch and course.program_id:
                ch = self.db.query(Cohort).join(Course, Course.id == Cohort.course_id).filter(Course.program_id == course.program_id).first()
            if ch:
                cohort_id = ch.id
        if not cohort_id:
            first_cohort = self.db.query(Cohort).first()
            cohort_id = first_cohort.id if first_cohort else None

        counts = {"PRESENTE": 0, "AUSENTE": 0, "JUSTIFICADO": 0, "ATRASO": 0}

        for item in payload.records:
            st_status = item.status.upper()
            if st_status not in counts:
                st_status = "PRESENTE"
            counts[st_status] += 1

            is_pres = st_status in ("PRESENTE", "ATRASO")
            is_exc = st_status == "JUSTIFICADO"

            att = (
                self.db.query(Attendance)
                .filter(
                    Attendance.course_id == course.id,
                    Attendance.student_id == item.student_id,
                    Attendance.class_date == payload.class_date,
                )
                .first()
            )
            if not att:
                att = Attendance(
                    cohort_id=cohort_id,
                    course_id=course.id,
                    student_id=item.student_id,
                    class_date=payload.class_date,
                    class_number=payload.class_number,
                    session_topic=payload.session_topic,
                    status=st_status,
                    is_present=is_pres,
                    is_excused=is_exc,
                    notes=item.notes,
                )
                self.db.add(att)
            else:
                att.cohort_id = cohort_id
                att.class_number = payload.class_number
                att.session_topic = payload.session_topic
                att.status = st_status
                att.is_present = is_pres
                att.is_excused = is_exc
                att.notes = item.notes

        self.db.commit()

        return {
            "course_id": course.id,
            "class_date": payload.class_date.isoformat(),
            "class_number": payload.class_number,
            "session_topic": payload.session_topic,
            "records_saved": len(payload.records),
            "summary": counts,
        }

    # =========================================================================
    # 4. SUBE CONTENIDO POR CURSO Y CLASE
    # =========================================================================
    def list_course_class_contents(self, course_id: str) -> Dict[str, Any]:
        """Obtiene la biblioteca de materiales didácticos, grabaciones y lecturas agrupados por clase."""
        course = self.db.query(Course).filter(Course.id == course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException(f"Asignatura {course_id} no encontrada.")

        contents = (
            self.db.query(CourseClassContent)
            .filter(CourseClassContent.course_id == course.id, CourseClassContent.deleted_at.is_(None))
            .order_by(CourseClassContent.class_number.asc(), CourseClassContent.created_at.desc())
            .all()
        )

        # Agrupar por clase
        classes_map: Dict[int, Dict[str, Any]] = {}
        type_counts = {"DOCUMENTO_PDF": 0, "PRESENTACION_PPT": 0, "VIDEO_CLASE": 0, "LECTURA_COMPLEMENTARIA": 0, "ENLACE_WEB": 0}

        for item in contents:
            cnum = item.class_number
            if cnum not in classes_map:
                classes_map[cnum] = {
                    "class_number": cnum,
                    "class_title": item.class_title,
                    "items": [],
                }
            classes_map[cnum]["items"].append({
                "id": item.id,
                "resource_title": item.resource_title,
                "resource_type": item.resource_type,
                "attachment_url": item.attachment_url,
                "file_size_text": item.file_size_text,
                "description": item.description,
                "uploaded_by_name": item.uploaded_by_name or "Docente Titular",
                "is_published": item.is_published,
                "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            })

            if item.resource_type in type_counts:
                type_counts[item.resource_type] += 1

        grouped_classes = list(classes_map.values())
        grouped_classes.sort(key=lambda x: x["class_number"])

        return {
            "course": {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "program_name": course.program.name if course.program else "General",
            },
            "total_contents": len(contents),
            "total_classes": len(grouped_classes),
            "type_counts": type_counts,
            "classes": grouped_classes,
        }

    def upload_course_class_content(self, course_id: str, payload: ContentUploadRequest, user: Optional[Any] = None) -> Dict[str, Any]:
        """Registra un nuevo contenido didáctico (guía, ppt, video) para una clase del curso."""
        course = self.db.query(Course).filter(Course.id == course_id, Course.deleted_at.is_(None)).first()
        if not course:
            raise EntityNotFoundException(f"Asignatura {course_id} no encontrada.")

        uploader_name = "Prof. Zhiwei Chen"
        uploader_id = None
        if user:
            uploader_id = getattr(user, "id", None)
            if hasattr(user, "person") and user.person:
                uploader_name = f"Prof. {user.person.first_name} {user.person.last_name}"

        # URL por defecto si no viene provista
        attachment_url = payload.attachment_url
        if not attachment_url:
            clean_title = payload.resource_title.lower().replace(" ", "_").replace("/", "-")
            attachment_url = f"/static/academic/materials/{course.code.lower()}_clase{payload.class_number}_{clean_title}.pdf"

        content = CourseClassContent(
            course_id=course.id,
            cohort_id=payload.cohort_id,
            class_number=payload.class_number,
            class_title=payload.class_title,
            resource_title=payload.resource_title,
            resource_type=payload.resource_type,
            attachment_url=attachment_url,
            file_size_text=payload.file_size_text or "2.4 MB",
            description=payload.description,
            uploaded_by_id=uploader_id,
            uploaded_by_name=uploader_name,
            is_published=payload.is_published,
        )
        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)

        return {
            "id": content.id,
            "course_id": content.course_id,
            "class_number": content.class_number,
            "class_title": content.class_title,
            "resource_title": content.resource_title,
            "resource_type": content.resource_type,
            "attachment_url": content.attachment_url,
            "file_size_text": content.file_size_text,
            "uploaded_by_name": content.uploaded_by_name,
            "is_published": content.is_published,
        }

    def delete_course_class_content(self, content_id: str) -> None:
        """Elimina un contenido didáctico subido."""
        content = self.db.query(CourseClassContent).filter(CourseClassContent.id == content_id).first()
        if not content:
            raise EntityNotFoundException("Contenido no encontrado.")
        self.db.delete(content)
        self.db.commit()
