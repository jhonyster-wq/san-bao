# PROPUESTA OFICIAL RFQ — PRISMA DIGITAL SYSTEMS SpA
## ECOSISTEMA SAN BAO (ERP Corporativo Multisociedad, Gestor de Campo Clínico y Capa de Integración Transaccional)

- **Empresa Oferente:** PRISMA Digital Systems SpA
- **Representante Legal:** Jhony Sánchez Cáceres
- **Entorno Demo en Vivo (7 Portales Operativos):** https://san-bao.onrender.com/app
- **Criterios de Evaluación RFQ:** Técnico (`40%`) • Ciberseguridad (`30%`) • Comercial (`30%`)
- **Valor UF Oficial Utilizado:** `$41.357,30 CLP` (18 de noviembre de 2026)

---

## Estructura Clara de la Carpeta según los 4 Puntos Exigidos en el RFQ

| Punto del RFQ | Archivo Entregable | Formato | Contenido Exacto |
| :---: | :--- | :---: | :--- |
| **Resumen Directorio** | `00_Carta_Ejecutiva_y_Resumen_Directorio_RFQ.pdf` | `.pdf` | Carta ejecutiva suscrita por **Jhony Sánchez Cáceres**, síntesis de los 4 pilares del RFQ, enlace a la demo en vivo, cuadro económico separado y aceptación de reserva del Directorio. |
| **Punto 1 RFQ** *(Técnico 40%)* | `01_Arquitectura_Soluciones_y_Matriz_Cumplimiento_RFQ.docx` | `.docx` | Arquitectura general, soluciones propuestas (ERP Multisociedad, Gestor Clínico MTC y Capa de Integración), resumen de cumplimiento de las Secciones 1 a 6 y 8 con evidencia, modalidad, brechas, supuestos, dependencias y exclusiones. |
| **Punto 1 RFQ (Anexo)** *(Técnico 40%)* | `01_Anexo_Matriz_Cumplimiento_Detallada_RFQ.xlsx` | `.xlsx` | Matriz granular de los **32 requisitos** (Secciones 1 a 6 y 8) con las 14 columnas obligatorias, autofiltros y hoja `Resumen_Ejecutivo` con porcentajes automáticos (`96,9%` implementado y verificado en código y Pytest). |
| **Punto 2 RFQ** *(Técnico 40%)* | `02_Plan_Implementacion_ERP_Clinico_e_Integracion_RFQ.docx` | `.docx` | Plan de implementación en **12 semanas (6 etapas)** con diagrama Gantt semanal, separación de ERP, Gestor Clínico e Integración, 4 hitos de interoperabilidad, responsables, dimensionamiento, limpieza y migración de datos (RUT Módulo 11), capacitación y las 7 pruebas de aceptación (UAT). |
| **Punto 3 RFQ** *(Comercial 30%)* | `03_Oferta_Economica_Separada_y_TCO_3_Anos_RFQ.docx` | `.docx` | Oferta económica separada para **ERP Corporativo (`180 UF`)**, **Gestor Clínico (`155 UF`)** e **Integración (`115 UF`)**, desglose de las 11 partidas de implementación y 13 recurrentes, TCO a 3 años en 3 escenarios, moneda (UF/CLP), impuestos (Neto + IVA 19%), pago en 4 hitos y vigencia de 60 días (sin tarifarios internos por perfil). |
| **Punto 3 RFQ (Anexo)** *(Comercial 30%)* | `03_Anexo_Modelo_Economico_y_TCO_RFQ.xlsx` | `.xlsx` | Modelo financiero editable con 4 pestañas (`Parametros_y_Condiciones`, `Oferta_Separada_3_Sistemas`, `Desglose_Implementacion` y `Costos_Recurrentes` + `TCO_36_Meses_y_Escenarios`) con fórmulas dinámicas y sin costos internos. |
| **Punto 4 RFQ** *(Ciberseguridad 30% / Comercial 30%)* | `04_Ciberseguridad_SLA_Soporte_y_Referencias_RFQ.docx` | `.docx` | Controles de ciberseguridad verificados (TLS 1.3, `AES-256-GCM` con llave separada, bloqueo HTTP 403 de Finanzas a Anamnesis, retención 15 años, respaldos 4h/24h por 90 días), declaración transparente de certificaciones con Plan de Cierre (Pentest), SLA `99,9%` Lun–Sáb `08:30–22:30` y referencias/activos verificables en vivo. |
