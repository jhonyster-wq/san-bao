# Solicitud Formal de Cotización (RFP) — Servicio de Hosting Cloud VPS en Chile
## Sistema Integral San Bao (Instituto de Medicina China Clásica SpA & Servicios Clínicos San Bao SpA)

- **Documento:** `solicitud_cotizacion_hosting_san_bao`
- **Fecha de Emisión:** Noviembre 2026
- **Modalidad de Facturación Requerida:** Factura Electrónica Afecta SII (DTE 33) en Pesos Chilenos ($CLP + IVA)
- **Ubicación Geográfica Obligatoria:** Datacenter en **Santiago de Chile** (Baja latencia nacional y cumplimiento Ley N° 20.584 de fichas clínicas)

---

## 1. Carta / Correo Tipo Lista para Enviar a Proveedores de Hosting

> **Asunto:** Solicitud de Cotización Formal — Servidor Cloud VPS Linux en Chile (4 vCPU / 8 GB RAM / 150 GB NVMe) — Holding San Bao SpA
>
> **Estimado Equipo Comercial,**
>
> Junto con saludar, en representación de **Instituto de Medicina China Clásica SpA (RUT 77.123.456-9)** y **Servicios Clínicos San Bao SpA (RUT 76.987.654-5)**, solicitamos a ustedes una **cotización formal con Factura Electrónica en pesos chilenos ($CLP + IVA)** para la contratación de un **Servidor Cloud VPS Dedicado (KVM)** alojado físicamente en **Datacenter de Santiago de Chile**, destinado a operar nuestra plataforma institucional clínico-académica (**Sistema Integral San Bao**).
>
> A continuación detallamos las especificaciones técnicas y de nivel de servicio requeridas:

---

## 2. Especificaciones Técnicas Solicitadas al Proveedor

| Ítem | Componente | Requerimiento Mínimo Exigido | Observaciones / Uso Institucional |
| :---: | :--- | :--- | :--- |
| **01** | **Virtualización** | KVM (Kernel-based Virtual Machine) con recursos garantizados (no sobrevendidos). | Aislamiento completo de kernel para contenedores Docker en producción. |
| **02** | **Procesador (CPU)** | **4 vCPU dedicadas** (Arquitectura AMD EPYC o Intel Xeon Gold/Platinum). | Ejecución concurrente de API FastAPI (Uvicorn), Nginx y motor PostgreSQL 16. |
| **03** | **Memoria RAM** | **8 GB RAM DDR4 / DDR5** (cotizar opcionalmente escalabilidad en caliente a 16 GB RAM). | Buffer pool PostgreSQL 16 (10 esquemas, 78 tablas) y procesos de backend. |
| **04** | **Almacenamiento** | **150 GB SSD NVMe Enterprise** en arreglo redundante RAID-10. | Base de datos transaccional, fichas clínicas MTC, DTE SII y respaldos locales. |
| **05** | **Sistema Operativo** | **Ubuntu Server 22.04 LTS o 24.04 LTS (64-bit)** con acceso `root` por SSH. | Despliegue nativo de `Docker Engine` y `Docker Compose v2`. |
| **06** | **Conectividad y Red** | **1 Dirección IPv4 pública estática dedicada** + enlace nacional PIT Chile (< 15 ms). | Configuración de dominio institucional, SSL/TLS, Webpay Plus y conexión SII. |
| **07** | **Transferencia Mensual** | **Mínimo 2 TB / mes** (idealmente tráfico nacional ilimitado). | Operación continua de los 7 portales web y móviles (Sedes Santiago y Viña del Mar). |
| **08** | **Puertos y Firewall** | Puertos `80 (HTTP)`, `443 (HTTPS)` y `22 (SSH)` habilitados, con protección anti-DDoS. | Compatible con proxy perimetral Cloudflare WAF/CDN. |
| **09** | **Disponibilidad (SLA)** | **SLA >= 99.9%** garantizado por contrato (Operación crítica de **Lunes a Sábado de 08:30 a 22:30 hrs**). | Cero interrupciones durante turnos clínicos y registro de asistencia QR MINSAL. |
| **10** | **Respaldos (Snapshots)** | Servicio de **Snapshots / Backup automatizado de máquina completa** (semanal o diario). | Complementario al respaldo diario `pg_dump` interno de las 03:00 AM. |

---

## 3. Información Comercial que Debe Incluir la Propuesta del Proveedor

Solicitamos que la cotización formal detalle explícitamente:

1. **Valores netos y totales con IVA ($CLP)** en modalidad:
   - Pago **Mensual**
   - Pago **Semestral** (indicar % de descuento aplicable)
   - Pago **Anual** (indicar % de descuento aplicable)
2. **Costo de servicio de Backup / Snapshots automáticos** del VPS en caso de cotizarse como adicional.
3. **Costo y procedimiento de escalamiento futuro (Upgrade sin pérdida de datos)** a **8 vCPU / 16 GB RAM / 250 GB NVMe**.
4. **Tiempo de aprovisionamiento y entrega de credenciales SSH `root`** una vez emitida la Orden de Compra / pago.
5. **Canales y tiempos de respuesta de Soporte Técnico en Chile** (teléfono directo, sistema de tickets 24/7 y correo de emergencias de lunes a sábado).

---

## 4. Datos de Facturación Institucional

Para la emisión de la cotización formal y posterior Factura Electrónica SII (DTE 33), considerar:

- **Razón Social Opción 1 (Academia):** Instituto de Medicina China Clásica SpA (`Escuela San Bao SpA`) — **RUT:** `77.123.456-9`
- **Razón Social Opción 2 (Clínica):** Servicios Clínicos San Bao SpA (`Clínica San Bao SpA`) — **RUT:** `76.987.654-5`
- **Dirección Comercial:** Av. Providencia 1234, Providencia, Santiago, Región Metropolitana.
- **Contacto de Administración y TI:** `admin@sanbao.cl` / `finanzas@sanbao.cl`
