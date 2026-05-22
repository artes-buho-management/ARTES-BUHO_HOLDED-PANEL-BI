# ARTES BUHO - PANEL + INFORMES AUTOMATIZADOS

Sistema open source y 100% gratuito con dos capas:

1. Panel interactivo (Streamlit) sobre Google Sheets.
2. Subsistema de informes corporativos PDF (semanal, mensual, anual) con subida a Google Drive.

Todo reutiliza la misma logica analitica para evitar duplicidades.

## Arquitectura

- Fuente de datos: Google Sheets.
- Capa analitica compartida: `shared/analysis_service.py`.
- Panel: `app.py`.
- Informes: `reporting/*` + `main.py`.
- PDF corporativo: ReportLab + matplotlib.
- Drive: Google Drive API (con soporte Shared Drives).
- Email: preparado, desactivado por defecto.

## Estructura de carpetas

```text
HOLDED+LOOKER-STUDIO-BI/
  app.py
  main.py
  config.py
  data_loader.py
  data_processing.py
  analytics.py
  insights.py
  shared/
    __init__.py
    analysis_service.py
  reporting/
    __init__.py
    periods.py
    naming.py
    pdf_builder.py
    drive_manager.py
    email_manager.py
    generator.py
  assets/
    logo_artes_buho.png
  tests/
    test_periods.py
    test_naming.py
    test_drive_structure.py
    test_email_manager.py
  requirements.txt
  .env.example
  .streamlit/config.toml
```

## Configuracion

1. Crear entorno e instalar:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Crear `.env`:

```powershell
copy .env.example .env
```

3. Completar como minimo:

- `GOOGLE_SHEET_ID`
- `TIMEZONE` (por defecto `Europe/Madrid`)
- `GOOGLE_SERVICE_ACCOUNT_JSON` o `GOOGLE_APPLICATION_CREDENTIALS` para Drive/API privada

## Dashboard (existente)

```powershell
streamlit run app.py
```

## Informes corporativos por CLI

Todos los comandos aceptan:

- `--run-datetime "YYYY-MM-DD HH:MM"`
- `--dry-run` (no sube a Drive)
- `--overwrite` (si existe archivo en Drive)
- `--sheet-name "NombrePestana"` (opcional)

### Semanal

```powershell
python main.py generate weekly --run-datetime "2026-04-06 08:00"
```

### Mensual

```powershell
python main.py generate monthly --run-datetime "2026-04-01 08:00"
```

### Anual

```powershell
python main.py generate annual --run-datetime "2027-01-01 08:00"
```

## Reglas de periodo y nombre

- Semanal:
  - Cobertura: semana anterior completa (lunes a domingo).
  - Nombre: `YYMMDD_InformeSemanal.pdf` (fecha de generacion).
- Mensual:
  - Cobertura: mes anterior completo.
  - Nombre: `YYMM_InformeMensual.pdf` (anio/mes analizado).
- Anual:
  - Cobertura: anio anterior completo.
  - Nombre: `YYYY_InformeAnual.pdf` (anio analizado).

## Estructura en Google Drive

El sistema localiza la carpeta padre de la hoja fuente y crea/reutiliza:

```text
Informes/
  InformeSemanal/
  InformeMensual/
  InformeAnual/
```

Comando para preparar estructura:

```powershell
python main.py setup-drive
```

Comportamiento de duplicados:

- Por defecto: `skip` (no duplica si ya existe mismo archivo).
- Con `--overwrite`: reemplaza el PDF existente.

## Programacion automatica (gratis)

## Cron (Linux/Mac)

```cron
0 8 * * 1 cd /ruta/proyecto && /ruta/python main.py generate weekly
0 8 1 * * cd /ruta/proyecto && /ruta/python main.py generate monthly
0 8 1 1 * cd /ruta/proyecto && /ruta/python main.py generate annual
```

## Windows Task Scheduler

Crear 3 tareas con accion:

```text
Programa/script: C:\ruta\python.exe
Argumentos:
  C:\ruta\proyecto\main.py generate weekly
  C:\ruta\proyecto\main.py generate monthly
  C:\ruta\proyecto\main.py generate annual
Iniciar en: C:\ruta\proyecto
```

Triggers:

- Semanal: lunes 08:00.
- Mensual: dia 1 de cada mes, 08:00.
- Anual: dia 1 de enero, 08:00.

## Email preparado pero desactivado

- Configuracion incluida en `.env.example`.
- `EMAIL_ENABLED=False` por defecto.
- Se genera preview de envio (destinatarios/asunto/cuerpo/adjunto).
- No hay envio real en esta fase.

## Tests

```powershell
pytest -q
```

Incluye:

- periodos semanales/mensuales/anuales,
- naming exacto,
- creacion/reutilizacion de carpetas Drive en modo simulado,
- dry-run de email.

## Identidad corporativa

- Empresa: `Artes Buho`.
- Desarrollador: `RUBEN COTON`.
- Colores: rojo, amarillo, blanco.
- Logo: `assets/logo_artes_buho.png`.


---

## CIERRE DE ENTORNO LOCAL (MIGRACION)

- Fecha de cierre: 2026-04-08 15:24:45
- Estado: preparado para migrar a nuevo PC/sistema cloud.
- Repositorio: sincronizado con GitHub en la rama activa.
- Nota: este proyecto queda listo para retomar desde otro equipo clonando el repo.

### CHECKLIST RAPIDA

- [x] Codigo versionado en GitHub.
- [x] README actualizado para traspaso.
- [x] Trabajo local preparado para cierre.


<!-- CIERRE_MIGRACION_2026_04_08 -->
## Cierre de migracion (2026-04-08)
- Estado: preparado para mover a nuevo PC/sistema cloud.
- Fecha de cierre: 
2026-04-08 15:25:38 +02:00
- Rama activa: 
main
- Nota: cambios subidos a GitHub para reanudar desde otro entorno.



## CIERRE CLOUD (2026-04-08)

- Estado: repositorio preparado para migracion a nuevo sistema.
- Ultimo cierre tecnico: 2026-04-08 (Europe/Madrid).
- Siguiente uso recomendado: clonar desde GitHub y continuar en la rama actual.


## CIERRE MIGRACION CLOUD

- Fecha: 2026-04-08
- Estado: preparado para retomar desde nuevo sistema


## CIERRE CLOUD 2026-04-08
- Estado: sincronizado para migracion a nuevo PC/sistema.
- Preparado para retomar desde GitHub.
- Ultima revision: 2026-04-08 15:26:05 +02:00

<!-- MIGRACION_CLOUD_START -->
## ESTADO MIGRACION CLOUD
- Revisado: 2026-04-08
- Repo listo para continuar en otro sistema.
- Estado Git al cerrar: sincronizado en GitHub.
<!-- MIGRACION_CLOUD_END -->
