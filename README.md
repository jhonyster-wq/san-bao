# SISTEMA INTEGRAL SAN BAO
> Plataforma empresarial modular para la integración y gestión de operaciones del **Instituto de Medicina China Clásica SpA** y **Servicios Clínicos San Bao SpA**.

---

## 1. Visión y Principio Rector
Un único ecosistema tecnológico donde la Escuela y la Clínica comparten de forma controlada la información institucional, garantizando:
- **Identidad única para cada persona:** Alumnos, pacientes, docentes y terapeutas se identifican de manera centralizada mediante su **RUT chileno** (validado por algoritmo Módulo 11), sin duplicidad de datos.
- **Separación estricta bi-societaria:** Contabilidad, facturación electrónica (DTE), contratos y aranceles se encuentran estrictamente particionados por persona jurídica (`X-Company-ID`).
- **Aislamiento reforzado de datos clínicos:** Cumplimiento de la **Ley N° 20.584** sobre derechos y deberes en salud y la **Ley N° 19.628** sobre datos sensibles. Fichas de atención médica y diagnósticos de Medicina Tradicional China (MTC) protegidos con trazabilidad inmutable de accesos.

---

## 2. Tecnologías y Stack
- **Backend:** Python 3.10+ / FastAPI (API REST, OpenAPI/Swagger nativo).
- **Validación de Datos:** Pydantic v2 & Pydantic-Settings.
- **ORM & Persistencia:** SQLAlchemy 2.0 con soporte nativo para esquemas PostgreSQL y SQLite en pruebas.
- **Migraciones:** Alembic con autogeneración e inspección multi-esquema.
- **Seguridad:** Autenticación OAuth2 / JWT (HS256/RS256), hashing Bcrypt de contraseñas.
- **Contenedores:** Docker & Docker Compose (FastAPI + PostgreSQL 16).
- **Pruebas:** Pytest con cobertura automatizada.

---

## 3. Estructura del Proyecto

```
SanBao/
├── backend/
│   ├── app/
│   │   ├── core/                  # Configuración, sesión DB, seguridad JWT, auditoría, excepciones
│   │   ├── shared/                # Validador RUT Módulo 11, paginación, respuestas API
│   │   ├── modules/
│   │   │   ├── institutional/     # Núcleo: Sociedades, Sedes, Personas, Usuarios, RBAC
│   │   │   │   ├── models/        # Company, Campus, Room, Person, User, Role, Permission, AuditLog
│   │   │   │   ├── schemas/       # Esquemas Pydantic v2 validados
│   │   │   │   ├── services/      # Lógica de negocio (Auth, Company, Person, RBAC)
│   │   │   │   └── routers/       # Endpoints REST (/auth, /companies, /people, /campuses)
│   │   │   ├── academic/          # Módulo 1: Gestión Académica (Programas, Mallas, Cohortes, Matrículas, Calificaciones)
│   │   │   ├── clinical/          # Módulo 2: Gestión Clínica (Ficha MTC, Pacientes, Agenda, Boxes, Prácticas Supervisadas, Ley 20.584)
│   │   │   ├── finance/           # Módulo 3: Finanzas y Contabilidad (Aranceles, Cuotas, Pagos, Morosidad)
│   │   │   ├── hr/                # Módulo 4: Personas y Remuneraciones
│   │   │   ├── ecommerce/         # Módulo 5: Comercio Electrónico
│   │   │   ├── lms/               # Módulo 6: Aula Virtual
│   │   │   ├── integrations/      # Módulo 7: Integraciones y DTE
│   │   │   └── bi/                # Módulo 8: Business Intelligence
│   │   └── main.py                # Aplicación FastAPI y registro de rutas
│   ├── alembic/                   # Migraciones de base de datos
│   ├── scripts/
│   │   └── init_schemas.sql       # Creación de esquemas PostgreSQL
│   ├── tests/                     # Suite de pruebas automatizadas
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml             # Orquestación de servicios
├── pytest.ini                     # Configuración de pruebas
├── .env.example                   # Variables de entorno modelo
└── README.md
```

---

## 4. Esquemas de Base de Datos (PostgreSQL)

| Esquema | Contenido y Propósito |
|---|---|
| `core` | Entidades maestras: `companies`, `campuses`, `rooms`, `people`, `users`, `roles`, `permissions`, `user_company_roles` |
| `academic` | Carreras, mallas curriculares, asignaturas, cohortes, matrículas, notas, asistencia |
| `clinical` | Pacientes, fichas clínicas MTC (pulso, lengua, síndromes), atenciones supervisadas, agenda médica |
| `finance` | Aranceles, compromisos de pago, documentos tributarios (DTE), tesorería |
| `hr` | Contratos laborales, liquidaciones con gratificación y AFP/Fonasa, boletas de honorarios BHE |
| `ecommerce` | Cursos abiertos, pasarelas de pago Webpay/Flow, órdenes e inscripciones automáticas |
| `lms` | Cursos virtuales, módulos, lecciones, progreso, tareas y entregas |
| `integrations` | Documentos Tributarios Electrónicos (DTE SII: Boletas exentas 41, Facturas 33 con TED), Webhooks y Firma Electrónica |
| `bi` | Inteligencia de Negocios: KPIs financieros consolidados y por sociedad, ocupación clínica y métricas académicas |
| `audit` | Registros inmutables de trazabilidad y accesos clínicos Ley N° 20.584 |

---

## 5. Puesta en Marcha

### Opción A: Con Docker Compose (Recomendado)

1. Clonar el repositorio y copiar las variables de entorno:
   ```bash
   cp .env.example .env
   ```
2. Levantar la base de datos PostgreSQL 16 y el backend:
   ```bash
   docker-compose up -d --build
   ```
3. El servicio estará disponible en:
   - **API Backend:** `http://localhost:8000`
   - **Documentación Interactiva Swagger:** `http://localhost:8000/docs`
   - **Documentación ReDoc:** `http://localhost:8000/redoc`

### Opción B: Ejecución Local en Entorno Virtual

1. Crear y activar el entorno virtual Python:
   ```bash
   python3 -m venv backend/.venv
   source backend/.venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Iniciar el servidor de desarrollo:
   ```bash
   uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

---

## 6. Credenciales Iniciales de Desarrollo (Seed)

Al iniciar por primera vez, el sistema autoseed crea:
- **Sociedades:**
  - `Instituto de Medicina China Clásica SpA` (RUT: `77.123.456-9`)
  - `Servicios Clínicos San Bao SpA` (RUT: `76.987.654-5`)
- **Sede Central:**
  - Sede Providencia con Salas teóricas (`Aula Magna Lao Tsé`) y Boxes clínicos (`Box Acupuntura Tai Yang`, `Box Prácticas Supervisadas`).
- **Usuario Administrador:**
  - **Usuario:** `admin`
  - **Contraseña:** `AdminSanBao2026!`
  - **Rol:** `SUPERADMIN` con acceso total a ambas sociedades.

---

## 7. Módulos Implementados

### Módulo 1: Gestión Académica (Instituto SpA)
- **Catálogo Curricular:** Carreras (`academic.programs`), mallas versionadas (`academic.curriculums`) y asignaturas (`academic.courses`) con horas teóricas, prácticas y clínicas.
- **Cohortes y Secciones:** Apertura de secciones por período académico (`academic.academic_periods` y `academic.cohorts`) con cupos, horarios, salas y docente/tutor asignado.
- **Admisión y Matrícula:** Admisión de personas como estudiantes (`academic.students`), generación automática de código de matrícula (`MAT-YYYY-XXXX`) y formalización de matrícula con generación automática del arancel financiero.
- **Libro de Clases y Calificaciones:** Evaluaciones parciales ponderadas, notas en escala chilena 1.0 a 7.0 y cálculo de aprobación (nota >= 4.0).
- **Acreditación de Prácticas Clínicas:** Registro y certificación de horas prácticas de atención bajo supervisión docente (`academic.clinical_practice_hours`), requisito de egreso.

### Módulo 2: Gestión Clínica (Servicios Clínicos San Bao SpA)
- **Ficha Clínica Electrónica MTC:** Diagnóstico por Lengua (cuerpo, forma, saburra), Diagnóstico por Pulso (posiciones Cun, Guan, Chi en ambas muñecas), Diferenciación de Síndromes Zang-Fu y prescripción terapéutica (Acupuntura, Moxibustión, Ventosas, Auriculoterapia).
- **Agenda Médica y Boxes:** Reserva de horas por profesional y box clínico (`clinical.appointments`), con detección y prevención de solapamientos de horario en boxes y agendas.
- **Prácticas Supervisadas e Integración Cruzada:** Flujo donde el estudiante registra el borrador de atención (`DRAFT`) y el tutor clínico acreditado revisa, retroalimenta, califica y firma digitalmente (`SIGNED`). La firma legal acredita de forma automática las horas prácticas en el expediente académico del estudiante.
- **Confidencialidad y Ley N° 20.584:** Trazabilidad inmutable de todas las lecturas, consultas y firmas de fichas de pacientes en `clinical.access_logs` con IP, fecha UTC y usuario responsable.

### Módulo 3: Finanzas & Facturación
- **Aranceles y Compromisos de Pago:** Compromisos financieros (`finance.payment_commitments`) particionados en cuotas mensuales (`finance.installments`) asociadas exclusivamente a la sociedad titular (Instituto de Medicina China Clásica SpA).
- **Recaudación y Conciliación:** Registro de pagos (`finance.payments`), imputación automática a las cuotas más antiguas o vencidas (`finance.payment_allocations`) y cálculo de saldos y morosidad.

### Módulo 4: Personas y Remuneraciones (RRHH)
- **Expedientes de Colaboradores:** Registro unificado de docentes, terapeutas clínicos y personal administrativo (`hr.hr_employees`), vinculado 1:1 a la persona natural en `core.people`.
- **Contratos Laborales Chilenos:** Contratos indefinidos, plazo fijo y de prestación de servicios a honorarios (`hr.hr_contracts`), con asignación de jornada, sueldo base, valor hora y porcentaje de comisión clínica.
- **Liquidaciones de Sueldo Formales:** Emisión mensual conforme al Código del Trabajo de Chile (`hr.hr_payrolls`): cálculo de gratificación legal (25% con tope de 4.75 IMM / 12), descuentos previsionales (AFP 11.45%, Fonasa 7%, AFC 0.6%) e Impuesto Único de Segunda Categoría.
- **Boletas de Honorarios (BHE):** Registro de boletas de profesionales independientes (`hr.hr_fee_receipts`) con aplicación de la tasa legal de retención del SII (13.75%).
- **Permisos y Licencias:** Solicitud y flujo de aprobación formal de vacaciones y permisos administrativos (`hr.hr_leave_requests`).

### Módulo 5: Comercio Electrónico
- **Tienda Online:** Catálogo de cursos, seminarios y productos (`ecommerce.products`).
- **Órdenes y Pasarelas de Pago:** Órdenes de compra (`ecommerce.orders`) con Webpay Plus y Flow.
- **Integración Transversal Inmediata:** Al confirmarse el pago de un curso virtual, el sistema provisiona automáticamente la persona y usuario si es un alumno nuevo, lo matricula de inmediato en el aula virtual LMS y registra el ingreso en finanzas.

### Módulo 6: LMS (Aula Virtual)
- **Aulas Virtuales:** Cursos online (`lms.courses`) organizados en módulos (`lms.course_modules`) y lecciones (`lms.lessons`).
- **Seguimiento del Aprendizaje:** Marcado de avance y porcentaje de progreso por lección (`lms.lesson_progress`).
- **Tareas y Evaluaciones:** Creación de asignaciones (`lms.assignments`), entregas de alumnos (`lms.submissions`) y retroalimentación con calificación docente.

### Módulo 7: Integraciones y Automatización
- **DTE Facturación Electrónica SII:** Emisión de Boletas Electrónicas Exentas (tipo 41 - exentas de IVA para salud y educación), Boletas Afectas (39) y Facturas (33/34), con control correlativo de folios por sociedad y generación de Timbre Electrónico DTE (TED) estándar SII.
- **Webhooks Salientes:** Despacho automatizado de eventos de negocio (`dte.issued`, `payment.confirmed`, `clinical.encounter_signed`) hacia sistemas externos con registro inmutable de entregas (`integrations.webhook_deliveries`).
- **Firma Electrónica:** Generación y verificación de integridad criptográfica (SHA-256) en documentos institucionales y consentimientos informados (`integrations.digital_signatures`).

### Módulo 8: Inteligencia de Negocios (BI & Dashboards)
- **Panel Ejecutivo Consolidado y por Sociedad:** Indicadores en tiempo real vía `/api/v1/bi/dashboard/executive`.
- **KPIs Financieros:** Recaudación acumulada, cuentas por cobrar (morosidad), egresos de remuneraciones y nómina, y resultado operativo neto en moneda chilena (CLP).
- **KPIs Académicos y Clínicos:** Alumnos regulares, secciones activas, horas clínicas acreditadas, pacientes atendidos y tasa de fichas auditadas bajo Ley N° 20.584.

---

## 8. Frontend Web & Interfaz de Usuario

- **Arquitectura React 18 + TypeScript + Vite + Tailwind CSS:** Interfaz moderna, modular y adaptativa en `frontend/`.
- **Conmutador de Sociedad Activa:** Permite alternar la sesión y las consultas en tiempo real entre el **Instituto de Medicina China Clásica SpA** y **Servicios Clínicos San Bao SpA** mediante el encabezado `X-Company-ID`.
- **Acceso Directo Web:** Disponible en `/app` sirviendo el dashboard interactivo de alta fidelidad.

---

## 9. Ejecución de Pruebas Automatizadas

Para ejecutar la suite completa de 30 pruebas unitarias y de integración:
```bash
backend/.venv/bin/pytest backend/tests -v
```
*(Cobertura 100%: Algoritmo Módulo 11 en RUT, hashing seguro, tokens JWT, aislamiento societario, flujos académicos, ficha clínica MTC Ley 20.584, LMS, E-Commerce, RRHH/nómina, DTE SII y Dashboards BI)*.

---

## 10. Migraciones de Base de Datos (Alembic)

- **Generar nueva revisión automática:**
  ```bash
  backend/.venv/bin/alembic revision --autogenerate -m "descripcion_del_cambio"
  ```
- **Aplicar migraciones:**
  ```bash
  backend/.venv/bin/alembic upgrade head
  ```
