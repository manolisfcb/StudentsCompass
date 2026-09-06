# Auditoría y plan incremental de StudentsCompass

Fecha: 2026-09-05. Revisión local: `6a2ea29`. Auditoría estática y pruebas aisladas; no se conectó a producción ni se modificó código productivo. Las líneas son referencias al snapshot y pueden desplazarse.

El sistema es un monolito funcional FastAPI/Jinja con separación parcial por dominios. La evolución recomendada es conservar ese stack y corregir primero controles de acceso, almacenamiento, secretos y gasto de IA. Hay infraestructura reutilizable: autenticación FastAPI Users, SQLAlchemy async, contratos Pydantic, adapters de almacenamiento, guard de presupuesto, batching en mensajes y repositorio de roadmaps.

## Riesgos y prioridades principales

1. **F-01:** SECRET DETECTED en configuración versionada de migraciones; retirar/rotar y alinear destinos de DB.
2. **F-02 / F-07:** autorización ausente en borrado de posts y descarga por clave de recursos.
3. **F-03:** nombre de archivo no escapado en HTML del perfil.
4. **F-04 / F-05:** colisiones de claves S3, borrado antes de commit y límites incompletos de uploads.
5. **F-06:** presupuesto global depende de configuración Redis y no contabiliza todos los reintentos.
6. **F-08 / F-20:** migraciones no reproducibles desde vacío, pasos destructivos y schema dependiente de ramas.
7. **F-11 / F-12:** transiciones/historial de candidaturas y reservas de entrevistas no robustas bajo concurrencia.
8. **F-13 / F-14:** cuota y jobs sin ciclo durable/idempotente completo.
9. **F-15 / F-16:** progreso y contadores manuales con múltiples fuentes de verdad.
10. **F-17 / F-18 / F-19:** N+1 concretos, operaciones síncronas en async y concentración de responsabilidades.

## Evidencia de validación

- Suite completa existente: **173 passed, 1 skipped en 23.39 s**. Se ejecutó con `.venv/bin/python`, `pytest -o addopts='' -p no:cacheprovider -q`, dotenv desactivado, credenciales ficticias y conexiones socket bloqueadas. No se modificaron tests ni se generaron reportes de cobertura en el repositorio.
- Selección previa de posts, presupuesto, reservas, reintentos, uploads y privacidad: **12 passed en 1.39 s**.
- La suite usa SQLite y create_all; no valida la cadena Alembic, concurrencia PostgreSQL ni infraestructura real. Tests verdes no refutan los hallazgos estáticos.
- Al iniciar se observó una eliminación preexistente de `output/pdf/studentscompass_capstone_phase_1.pdf`; no se modificó ese archivo como parte de esta auditoría.

## Esfuerzo y estrategia

Esfuerzo global **alto**, concentrado en esquema histórico y transacciones. Correcciones de autorización/HTML: pequeño; storage/IA/estado de candidatura: medio; baseline y convergencia DB: alto y condicionado al estado real. No se asignan fechas sin conocer capacidad del equipo y tamaño de datos. Ejecutar PRs pequeñas con characterization, expansión de schema, cambio de callers, parity y retiro posterior. Las fases son dependencias técnicas, no una invitación a esperar toda la fase para cerrar una vulnerabilidad independiente.

Simplificaciones con mayor retorno: una policy de aprobación, un proyector de progreso, una transición de candidatura, un guard por intento IA y scopes explícitos para storage. Extraer responsabilidades de Capstone después de fijar contratos. No convertir todos los servicios en interfaces/repositorios.

## Qué no tocar todavía

No reescribir el frontend, cambiar framework/ORM, fusionar cursos con recursos, borrar posts legacy/enrollments, eliminar columnas históricas, sustituir heurísticas por ML real, activar cobros/email real ni cambiar umbral 8. No hacer upgrades en producción hasta probar baseline/restauración. No quitar índices por su apariencia ni recalcular resultados académicos históricos sin versión.

## Documentos

- [Arquitectura actual](01_CURRENT_ARCHITECTURE.md)
- [Hallazgos](02_AUDIT_FINDINGS.md)
- [Arquitectura objetivo y ADR](03_TARGET_ARCHITECTURE.md)
- [Fuentes de verdad](04_SOURCE_OF_TRUTH_MATRIX.md)
- [Auditoría de DB](05_DATABASE_AUDIT.md)
- [Seguridad y costes](06_SECURITY_AND_COST.md)
- [Plan por fases](07_REFACTOR_PLAN.md)
- [TASKS: fuente de verdad de ejecución](TASKS.md)
