# Informe Técnico de Hosting, Base de Datos PostgreSQL (3NF/BCNF) y Alta Disponibilidad
## Sistema Integral San Bao — Escuela San Bao SpA & Clínica San Bao SpA

- **Documento:** `informe_tecnico_hosting_san_bao`
- **Versión:** 2.0 (Producción — Arquitectura Normalizada 3NF/BCNF y 7 Portales Especializados)
- **Entidades Jurídicas Cubiertas:**
  1. **Instituto de Medicina China Clásica SpA (`Escuela San Bao SpA`)** — RUT `77.123.456-9`
  2. **Servicios Clínicos San Bao SpA (`Clínica San Bao SpA`)** — RUT `76.987.654-5`

---

## 1. Alcance Funcional y Portales Operativos en Producción

La infraestructura aloja los **7 portales especializados con control de acceso basado en roles (RBAC)** y aislamiento contable/RRHH bi-societario:

| Portal | Perfil / Rol | Sociedad SpA | Módulos y Operaciones Críticas |
| :--- | :--- | :--- | :--- |
| **1. Portal Administrativo** | Superadmin ERP / Finanzas / RRHH | Holding Consolidado (Ambas SpA) | Dashboard Ejecutivo BI, Finanzas & DTE SII (13 sub-áreas), Personas & RRHH (separación Docentes Escuela SpA vs Tutores Clínica SpA), LMS/E-Commerce e Integraciones. |
| **2. Portal Académico** | Dirección Académica y Gestión Académica | Escuela San Bao SpA | Diseño de Malla Curricular por semestres, suma de asignaturas con 1 o 2 docentes activos en RRHH, expedientes y hoja de vida, notas, congelamientos, traspasos y diplomas. |
| **3. Portal Clínico MTC** | Dirección Clínica y Recepción Sedes | Clínica San Bao SpA | Programación de turnos asistenciales (Santiago y Viña del Mar), asignación de tutores y practicantes, agenda de boxes, fichas clínicas MTC (Ley N° 20.584) y control de insumos. |
| **4. Portal de Alumnos** | Alumno Regular | Escuela San Bao SpA | Registro de asistencia a práctica clínica mediante **Lectura de Código QR Normativa MINSAL** (fecha/hora exacta de entrada y salida), resumen de horas clínicas, notas/ramos y pago de cuotas de arancel en línea. |
| **5. Portal de Docentes** | Docente de Cátedra (`TEACHER`) | Escuela San Bao SpA | Cursos asignados, libro de calificaciones ponderadas, control de asistencia por sesión y material pedagógico. |
| **6. Portal de Tutores** | Tutor Clínico (`PRACTITIONER`) | Clínica San Bao SpA | Visualización exclusiva de los turnos clínicos asignados al tutor, registro de notas de práctica y visación en 1 clic de asistencia QR MINSAL por alumno. |
| **7. Portal de Secretaría** | Gestión Secretaría de Sede | Escuela San Bao SpA / Consulta Clínica | Consulta de actividades clínicas y académicas de la sede, catálogo de cursos/seminarios (Presencial, Semipresencial, Virtual, Híbrido) con envío de link de inscripción/información por correo, seguimiento de práctica clínica por alumno y matrícula. |

---

## 2. Perfil Operativo y Nivel de Servicio Requerido (SLA 99.9%)

| Parámetro Operativo | Especificación Institucional San Bao |
| :--- | :--- |
| **Días Operativos** | **Lunes a Sábado** (6 días continuos por semana). |
| **Horario Crítico Continuo** | **08:30 a 22:30 hrs** (Turnos AM `10:00–14:00`, PM `15:00–19:00` y Vespertino `18:00–22:00`). |
| **Disponibilidad Garantizada (SLA)** | **99.9% mensual** en horario hábil (tolerancia cero a caídas en atención de boxes y marcaje QR MINSAL). |
| **Ventana de Mantenimiento** | **Domingos de 00:00 a 06:00 hrs** exclusivamente. |
| **RTO / RPO** | **RTO < 30 minutos** (recuperación ante desastre) • **RPO < 1 hora** (pérdida máxima admisible). |
| **Respaldos Automatizados** | Backup diario `pg_dump` comprimido y cifrado a las **03:00 AM** con retención local (7 días) y copia externa off-site (S3 / R2). |

---

## 3. Arquitectura de Software, Normalización PostgreSQL y Rendimiento

### 3.1. Pila Tecnológica Contenerizada (`Docker Compose`)
- **Proxy Inverso & TLS:** `Nginx Alpine` con HTTP/2, TLS 1.3 (Let's Encrypt / Cloudflare SSL) y caché de activos estáticos.
- **Frontend Web:** Aplicación Web Responsiva (PC, Tablet en Box/Aula y Smartphone para lectura QR MINSAL) con **coalescing de iconos por `requestAnimationFrame`**, **deduplicación de peticiones GET en vuelo con caché de corta duración**, **lazy-loading por portal activo** y contención de renderizado CSS (`content-visibility` / `contain: layout style`).
- **Backend API:** `FastAPI` (Python 3.10+ ASGI con `Uvicorn`), compresión **`GZipMiddleware`** (reducción >85% en transferencia de red), telemetría `X-Process-Time-Ms` y pool de conexiones persistentes (`pool_size=20`, `max_overflow=40`, `pool_pre_ping=True`, `pool_recycle=1800`).
- **Base de Datos Relacional Normalizada (3NF / BCNF):** `PostgreSQL 16` estructurada en **10 esquemas lógicos aislados** (`core`, `academic`, `clinical`, `finance`, `hr`, `ecommerce`, `lms`, `integrations`, `bi`, `audit`), con **78 tablas**, **157 claves foráneas**, **12 restricciones únicas compuestas (BCNF)** y **292 índices B-Tree simples y compuestos**, incluyendo catálogos maestros normalizados para Centros de Costo (`finance.cost_centers`) y Unidades de Negocio (`finance.business_units`).

---

## 4. Dimensionamiento del Servidor (Sizing Cloud VPS en Chile)

| Recurso | Mínimo Producción (Fase 1: 1–2 Sedes) | Recomendado Óptimo (Fase 2: Crecimiento) | Justificación Técnica |
| :--- | :--- | :--- | :--- |
| **Procesador (vCPU)** | **4 vCPU dedicadas (KVM)** | **6 a 8 vCPU dedicadas** | Concurrencia de workers ASGI FastAPI + motor PostgreSQL 16 + generación de DTE/PDF. |
| **Memoria RAM** | **8 GB RAM DDR4 / DDR5** | **16 GB RAM DDR4 / DDR5** | `shared_buffers` PostgreSQL (2 GB) + workers Uvicorn + Nginx + sistema operativo. |
| **Almacenamiento** | **150 GB SSD NVMe** | **250 GB SSD NVMe** | Base de datos, fichas clínicas MTC, certificados/diplomas, XML/PDF DTE SII y backups locales. |
| **Red y Conectividad** | **1 IPv4 pública fija dedicada** | **1 IPv4 fija + Red 1 Gbps** | Requerido para DNS institucional (`sanbao.cl`), webhooks Webpay/Flow y timbre electrónico SII. |
| **Tráfico Mensual** | **2 TB / mes mínimo** | **4 TB / mes o ilimitado** | Tráfico optimizado mediante compresión GZip y caché perimetral Cloudflare Santiago. |
| **Sistema Operativo** | **Ubuntu Server 22.04 / 24.04 LTS (64-bit)** | **Ubuntu Server 24.04 LTS** | Soporte nativo para Docker Engine, Docker Compose v2 y parches de seguridad LTS. |

---

## 5. Comparativa de Proveedores de Hosting Nacional (Facturación en CLP + IVA)

Alojar en un Datacenter en **Santiago de Chile** garantiza latencia inferior a **15 ms** para las sedes de **Providencia** y **Viña del Mar**, soberanía de datos clínicos bajo la **Ley N° 20.584**, y emisión de **Factura Electrónica SII (DTE 33)** para uso de crédito fiscal IVA.

| Proveedor Nacional | Plan Recomendado | Recursos Técnicos | Valor Mensual Ref. | Ventajas Competitivas |
| :--- | :--- | :--- | :--- | :--- |
| **1. HostingPlus.cl** | **VPS Medio Plus (VPS 2)** | 4 vCore • 8 GB RAM • 150 GB SSD NVMe | **$99.900 CLP + IVA** | Datacenter Tier III en Santiago, virtualización KVM dedicada, soporte técnico 24/7 en Chile. |
| **2. HN Datacenter (`hn.cl`)** | **VPS Premium Linux** | 4 vCPU • 8 GB RAM • 150 GB SSD | **$90.900 CLP + IVA** | Datacenter propio en Santiago (Ñuñoa), conexión directa a PIT Chile, soporte especializado Linux. |
| **3. EcoHosting.cl** | **VPS Cloud XL** | 4 vCPU • 8 GB RAM • 120 GB SSD NVMe | **$85.900 CLP + IVA** | Discos NVMe de alta velocidad, red propia en Santiago, excelente relación precio/rendimiento. |
| **4. Entel Cloud / Gtd** | **Cloud Server IaaS Salud** | 4 vCPU • 8 GB RAM • 200 GB SAN | **$180.000+ CLP + IVA** | SLA 99.95% contractual, ejecutivo corporativo asignado y cumplimiento normativo empresarial. |
