-- ==============================================================================
-- SISTEMA INTEGRAL SAN BAO: INICIALIZACIÓN Y NORMALIZACIÓN 3NF/BCNF POSTGRESQL
-- ==============================================================================

-- 1. Extensiones para generación de UUID v4 e índices B-Tree / GIN de alto rendimiento
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 2. Creación de los 10 esquemas lógicos aislados por dominio
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS academic;
CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS finance;
CREATE SCHEMA IF NOT EXISTS hr;
CREATE SCHEMA IF NOT EXISTS ecommerce;
CREATE SCHEMA IF NOT EXISTS lms;
CREATE SCHEMA IF NOT EXISTS integrations;
CREATE SCHEMA IF NOT EXISTS bi;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA core IS 'Entidades maestras transversales (3NF): personas (RUT único), usuarios, roles RBAC, sociedades SpA y sedes';
COMMENT ON SCHEMA academic IS 'Módulo 1: Gestión Académica, mallas curriculares, asignaturas (hasta 2 docentes RRHH activos), alumnos y matrículas';
COMMENT ON SCHEMA clinical IS 'Módulo 2: Gestión Clínica, fichas electrónicas MTC (Ley 20.584), agendas, turnero por tutor y prácticas supervisadas';
COMMENT ON SCHEMA finance IS 'Módulo 3: Finanzas bi-societarias, centros de costo (3NF), unidades de negocio (3NF), aranceles, CxC, CxP y contabilidad';
COMMENT ON SCHEMA hr IS 'Módulo 4: Personas y RRHH (Docentes Escuela SpA vs Tutores Clínica SpA), contratos, liquidaciones, Previred y BHE SII';
COMMENT ON SCHEMA ecommerce IS 'Módulo 5: Venta online de cursos, seminarios y formación continua';
COMMENT ON SCHEMA lms IS 'Módulo 6: Aula virtual, materiales pedagógicos y progreso curricular';
COMMENT ON SCHEMA integrations IS 'Módulo 7: DTE SII, firma electrónica SHA-256, webhooks, flujos de visación y trazabilidad';
COMMENT ON SCHEMA bi IS 'Módulo 8: Inteligencia de Negocios y vistas analíticas consolidadas';
COMMENT ON SCHEMA audit IS ' Trazabilidad e historial inmutable de operaciones';

-- ==============================================================================
-- 3. TABLAS MAESTRAS NORMALIZADAS (3NF) DE CENTROS DE COSTOS Y UNIDADES DE NEGOCIO
-- ==============================================================================
CREATE TABLE IF NOT EXISTS finance.cost_centers (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES core.companies(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL,
    area_type VARCHAR(50) NOT NULL DEFAULT 'ACADEMICO',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_finance_cost_center_company_code UNIQUE (company_id, code)
);

CREATE TABLE IF NOT EXISTS finance.business_units (
    id VARCHAR(36) PRIMARY KEY,
    company_id VARCHAR(36) NOT NULL REFERENCES core.companies(id) ON DELETE RESTRICT,
    campus_id VARCHAR(36) REFERENCES core.campuses(id) ON DELETE SET NULL,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(160) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_finance_business_unit_company_code UNIQUE (company_id, code)
);

-- ==============================================================================
-- 4. RESTRICCIONES DE UNICIDAD COMPUESTA (BCNF) E ÍNDICES B-TREE COMPUESTOS
-- ==============================================================================
-- Académico: Malla Curricular, Matrículas, Notas, Asistencia y Horas Clínicas QR MINSAL
CREATE INDEX IF NOT EXISTS ix_curriculum_courses_curr_sem ON academic.curriculum_courses (curriculum_id, semester);
CREATE INDEX IF NOT EXISTS ix_enrollments_student_status ON academic.enrollments (student_id, status);
CREATE INDEX IF NOT EXISTS ix_cohort_enrollments_cohort_status ON academic.cohort_enrollments (cohort_id, status);
CREATE INDEX IF NOT EXISTS ix_grades_student_eval ON academic.grades (student_id, evaluation_id);
CREATE INDEX IF NOT EXISTS ix_attendances_student_course_date ON academic.attendances (student_id, course_id, class_date);
CREATE INDEX IF NOT EXISTS ix_clinical_practice_student_status ON academic.clinical_practice_hours (student_id, status);
CREATE INDEX IF NOT EXISTS ix_clinical_practice_tutor_date ON academic.clinical_practice_hours (tutor_id, activity_date);

-- Clínico: Agenda de Boxes y Turnero Asistencial por Tutor
CREATE INDEX IF NOT EXISTS ix_appointments_campus_date_status ON clinical.appointments (campus_id, appointment_date, status);
CREATE INDEX IF NOT EXISTS ix_appointments_practitioner_date ON clinical.appointments (practitioner_id, appointment_date);
CREATE INDEX IF NOT EXISTS ix_shifts_practitioner_date ON clinical.clinical_shift_schedules (practitioner_id, shift_date);
CREATE INDEX IF NOT EXISTS ix_shifts_campus_date_period ON clinical.clinical_shift_schedules (campus_id, shift_date, shift_period);

-- Finanzas, RRHH e Integraciones DTE SII
CREATE INDEX IF NOT EXISTS ix_installments_status_duedate ON finance.installments (status, due_date);
CREATE INDEX IF NOT EXISTS ix_hr_employees_comp_type_active ON hr.hr_employees (company_id, employee_type, is_active);
CREATE INDEX IF NOT EXISTS ix_hr_payrolls_comp_period ON hr.hr_payrolls (company_id, period_year, period_month);
CREATE INDEX IF NOT EXISTS ix_dte_company_date ON integrations.dte_documents (company_id, issue_date);
