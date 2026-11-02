# Informe de Recomendación de Hosting en Chile y Directorio de Contactos Comerciales
## Sistema Integral San Bao — Instituto de Medicina China Clásica SpA & Servicios Clínicos San Bao SpA

- **Documento:** `informe_recomendacion_hosting_chile_san_bao`
- **Fecha de Emisión:** Noviembre 2026
- **Destinatario:** Dirección Ejecutiva, Dirección Académica y Dirección Clínica — Holding San Bao SpA
- **Arquitectura Objetivo:** Servidor Cloud VPS Linux KVM (**4 vCPU • 8 GB RAM • 150 GB SSD NVMe • Ubuntu 24.04 LTS**) en **Datacenter Santiago de Chile** (`Docker Compose`: `FastAPI` + `PostgreSQL 16` + `Nginx`).

---

## 1. Resumen Ejecutivo y Recomendación Principal

Para operar el **Sistema Integral San Bao** (que unifica la plataforma de **Academia** y la plataforma de **Clínica MTC** en las sedes de **Providencia, Santiago** y **Viña del Mar**), se requiere un proveedor con **Datacenter físico en Santiago de Chile**, **conexión directa a PIT Chile (latencia < 15 ms)**, **soberanía nacional de datos clínicos (Ley N° 20.584 y Ley N° 19.628 / 21.719)** y **emisión de Factura Electrónica Afecta SII (DTE 33) en Pesos Chilenos (`$CLP + IVA`)**.

**Recomendación N° 1 (Mejor Relación Calidad / Rendimiento / Soporte Local):**
Se recomienda contratar en primera opción **HN Datacenter (`hn.cl`) — Plan VPS Premium Linux** o **EcoHosting.cl — Plan VPS Cloud XL / VPS 4**, y como alternativa administrada **Netlinux Chile**. Estos proveedores cuentan con infraestructura propia en Santiago, almacenamiento NVMe de baja latencia para PostgreSQL 16, tarifa plana mensual en pesos chilenos sin cobros variables por tráfico y soporte técnico directo en Chile.

---

## 2. Matriz Comparativa de Proveedores Recomendados en Chile

| Ranking | Proveedor en Chile | Plan Recomendado | Recursos Técnicos | Valor Mensual Estimado (+ IVA) | Nivel de Recomendación y Ventaja Clave |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **1°** | **HN Datacenter (`hn.cl`)** | **VPS Premium Linux (KVM)** | 4 vCPU • 8 GB RAM • 150 GB SSD RAID-10 • 1 IPv4 Fija | **$85.000 – $90.900 CLP** | **Recomendado Principal (Infraestructura Propia):** Datacenter propio en Santiago (Ñuñoa), especialistas en Linux/KVM, baja latencia nacional y atención telefónica/ingeniería directa. |
| **2°** | **EcoHosting (`ecohosting.cl`)** | **VPS Cloud XL (NVMe)** | 4 vCPU • 8 GB RAM • 120–150 GB SSD NVMe • 1 IPv4 Fija | **$55.000 – $85.900 CLP** | **Mejor Relación Precio / Velocidad NVMe:** Discos NVMe empresariales ideales para los 10 esquemas PostgreSQL 16, activación rápida y facturación automática SII. |
| **3°** | **HostingPlus (`hostingplus.cl`)** | **VPS Medio Plus (VPS 2)** | 4 vCore • 8 GB RAM • 150 GB SSD NVMe • 1 IPv4 Fija | **$89.900 – $99.900 CLP** | **Excelente Soporte 24/7 en Chile:** Servidores en Datacenter Tier III en Santiago, snapshots programados y soporte permanente por teléfono y ticket. |
| **4°** | **Netlinux (`netlinux.cl`)** | **Cloud VPS Empresarial Administrado** | 4 vCPU • 8 GB RAM • 160 GB NVMe • Monitoreo 24/7 | **$75.000 – $120.000 CLP** | **Ideal si se busca Administración Delegada:** Especialistas en código abierto (Ubuntu, Docker, PostgreSQL, Nginx) con acompañamiento de ingenieros locales. |
| **5°** | **Hosting.cl (`hosting.cl`)** | **Plan VPS 3 / VPS 4 NVMe** | 4 vCPU • 8 GB RAM • 160 GB NVMe • 1 IPv4 Fija | **$49.900 – $69.900 CLP** | **Alternativa Económica Confiable:** Amplia trayectoria en Chile, facturación mensual/anual DTE 33 SII y panel de autogestión KVM. |
| **6°** | **Gtd Teleductos / Entel Cloud** | **IaaS Cloud Server Salud Tier III** | 4 vCPU • 8 GB RAM • 200 GB SAN • Firewall Perimetral | **$180.000 – $260.000 CLP** | **Opción Corporativa Hospitalaria:** Datacenter Tier III Certificado (ISO 27001), SLA 99.95% contractual y ejecutivo de cuenta dedicado. |
| **7°** | **Google Cloud (`southamerica-west1`)** | **Compute Engine `e2-standard-2` + Cloud SQL** | 2–4 vCPU • 8 GB RAM + PostgreSQL 16 Administrado | **$85.000 – $125.000 CLP** | **Opción Hiperescalar en Quilicura (Santiago):** Base de datos PostgreSQL gestionada con alta disponibilidad y backups punto-en-el-tiempo automáticos. |

---

## 3. Directorio Completo de Contactos Comerciales y Técnicos en Chile

### 3.1. HN Datacenter (HostName Chile — Recomendado N° 1)
- **Razón Social:** Hostname S.A. / HN Datacenter
- **Sitio Web / Cotización VPS:** https://www.hn.cl/vps-chile/
- **Correo Comercial / Cotizaciones:** `ventas@hn.cl` / `comercial@hn.cl`
- **Correo Soporte Técnico:** `soporte@hn.cl`
- **Teléfono Central (Santiago):** `+56 2 2840 1900`
- **Dirección Comercial / Datacenter:** Av. Pedro de Valdivia 3474, Ñuñoa, Santiago, Chile.
- **Horario de Atención Comercial:** Lunes a Viernes de 09:00 a 18:30 hrs (Soporte Técnico 24/7/365).

### 3.2. EcoHosting Chile (Recomendado N° 2 — Alto Rendimiento NVMe)
- **Razón Social:** Ecohosting SpA
- **Sitio Web / Cotización VPS:** https://www.ecohosting.cl/servidores-vps/
- **Correo Comercial / Ventas:** `ventas@ecohosting.cl`
- **Correo Soporte Técnico:** `soporte@ecohosting.cl`
- **Teléfono Central (Santiago):** `+56 2 2583 2020`
- **Dirección Comercial:** Av. Nueva Providencia 1881, Of. 1620, Providencia, Santiago, Chile.

### 3.3. HostingPlus Chile (Recomendado N° 3 — Soporte 24/7 Tier III)
- **Razón Social:** HostingPlus Chile SpA
- **Sitio Web / Cotización VPS:** https://www.hostingplus.cl/vps/
- **Correo Comercial / Ventas:** `ventas@hostingplus.cl`
- **Correo Soporte Técnico:** `soporte@hostingplus.cl`
- **Teléfono Central (Santiago):** `+56 2 2582 1110`
- **Dirección Comercial:** Av. Apoquindo 4700, Piso 11, Las Condes, Santiago, Chile.

### 3.4. Netlinux Chile (Especialistas Linux, Docker y PostgreSQL Administrado)
- **Razón Social:** Netlinux Ingeniería Limitada
- **Sitio Web Oficial:** https://www.netlinux.cl/
- **Correo Comercial / Proyectos:** `contacto@netlinux.cl` / `ventas@netlinux.cl`
- **Teléfono Central (Santiago):** `+56 2 2232 6800`
- **Dirección Comercial:** Av. Providencia 1650, Providencia, Santiago, Chile.

### 3.5. Hosting.cl (Alternativa VPS Nacional Costo-Eficiente)
- **Razón Social:** Hosting.cl SpA
- **Sitio Web / Cotización VPS:** https://www.hosting.cl/vps/
- **Correo Comercial / Ventas:** `ventas@hosting.cl` / `contacto@hosting.cl`
- **Correo Soporte Técnico:** `soporte@hosting.cl`
- **Teléfono Central (Santiago):** `+56 2 2411 5900`
- **Dirección Comercial:** Av. Kennedy 5454, Vitacura, Santiago, Chile.

### 3.6. Gtd Teleductos (Opción Corporativa Tier III Certificado Salud)
- **Razón Social:** Gtd Teleductos S.A. (Grupo Gtd)
- **Sitio Web Corporativo:** https://www.gtd.cl/empresas/data-center-y-cloud
- **Contacto Comercial Empresas:** `empresas@grupogtd.com`
- **Teléfono Mesa Central Empresas:** `600 950 5000` / `+56 2 2380 9000`
- **Dirección Casa Matriz:** Moneda 920, Piso 11, Santiago Centro (Datacenter Panamericana Norte / Liray, Santiago).

### 3.7. Google Cloud Chile — Región `southamerica-west1` (Santiago de Chile)
- **Entidad Local Facturadora:** Google Cloud Chile Limitada (Factura Electrónica SII en CLP)
- **Sitio Web / Contacto Ventas Chile:** https://cloud.google.com/contact
- **Partners Locales Certificados en Santiago:**
  - **Tigabytes Chile (Partner Premier Google Cloud):** `contacto@tigabytes.com` • Tel: `+56 2 2712 1900` (Las Condes, Santiago).
  - **Xertica Chile:** `chile@xertica.com` • Tel: `+56 2 2594 0600` (Providencia, Santiago).
