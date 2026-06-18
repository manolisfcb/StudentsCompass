# StudentsCompass Capstone - Fase 1

## Replanteamiento academico

**Proyecto:** StudentsCompass  
**Fase:** 1  
**Enfoque:** Skill Gap Analysis and Learning Path Optimization for International Students Using Labor Market Data and OR-Tools  
**Duracion estimada:** 1 semana

## 1. Proposito de la fase

La Fase 1 redefine StudentsCompass como un proyecto academico de analitica de datos y optimizacion, no solamente como una plataforma web para estudiantes. La aplicacion sigue siendo la interfaz de demostracion, pero el centro del capstone pasa a ser el sistema que conecta datos del mercado laboral, habilidades extraidas de CVs, brechas de preparacion y rutas de aprendizaje optimizadas.

El resultado de esta fase es una definicion clara del problema, los objetivos, el alcance, las metricas y el pipeline que guiaran la implementacion tecnica posterior.

## 2. Titulo propuesto

**Skill Gap Analysis and Learning Path Optimization for International Students Using Labor Market Data and OR-Tools**

Titulo alternativo en espanol:

**Analisis de brechas de habilidades y optimizacion de rutas de aprendizaje para estudiantes internacionales usando datos del mercado laboral y OR-Tools**

## 3. Problema

Los estudiantes internacionales que buscan iniciar o mejorar su carrera profesional en Canada enfrentan una brecha entre las habilidades que ya poseen y las habilidades demandadas por roles laborales reales. Aunque existen cursos, recursos y plataformas de aprendizaje, no siempre es claro cual combinacion de recursos ofrece la mejor preparacion bajo restricciones reales de tiempo, costo y dificultad.

StudentsCompass busca resolver este problema mediante un sistema que:

- Extrae habilidades desde ofertas laborales.
- Extrae habilidades desde CVs de estudiantes.
- Normaliza habilidades equivalentes bajo una taxonomia comun.
- Calcula brechas entre el perfil actual y un rol objetivo.
- Recomienda recursos educativos relevantes.
- Prepara la base para optimizar rutas de aprendizaje usando restricciones reales.

## 4. Pregunta de investigacion

**Dado un CV, un rol objetivo y restricciones reales de tiempo, costo y dificultad, cual es la ruta optima de cursos o recursos que maximiza la cobertura de habilidades laborales y mejora la preparacion del estudiante?**

## 5. Objetivo general

Disenar e implementar un sistema analitico que identifique brechas de habilidades entre estudiantes internacionales y roles laborales objetivo, y que recomiende rutas de aprendizaje eficientes usando datos del mercado laboral, informacion del CV y tecnicas de optimizacion.

## 6. Objetivos especificos

1. Construir una base analitica estructurada para representar habilidades, ofertas laborales, CVs, cursos y relaciones entre cursos y habilidades.
2. Extraer y normalizar habilidades desde job postings y CVs usando reglas, taxonomias y soporte semantico.
3. Calcular el skill gap entre un estudiante y un rol objetivo.
4. Recomendar recursos educativos que cubran las habilidades faltantes.
5. Preparar un modelo de optimizacion que seleccione rutas de aprendizaje bajo restricciones de presupuesto, tiempo y dificultad.
6. Evaluar la calidad de las recomendaciones usando metricas cuantitativas y comparacion contra baselines simples.

## 7. Alcance inicial

Para mantener el capstone enfocado y defendible, el alcance inicial se limita a 2 o 3 roles objetivo:

- Data Analyst.
- Business Analyst.
- Junior Data Scientist.

El primer prototipo debe concentrarse en estos roles antes de expandirse a otras industrias o niveles de experiencia.

## 8. Entradas y salidas del sistema

### Entradas

- CV del estudiante.
- Rol objetivo.
- Job postings relacionados con el rol objetivo.
- Catalogo de cursos o recursos.
- Restricciones del estudiante: presupuesto, horas disponibles, nivel de dificultad y numero maximo de cursos.

### Salidas

- Lista de habilidades actuales detectadas en el CV.
- Lista de habilidades requeridas por el rol objetivo.
- Skill gap priorizado.
- Recursos recomendados para cerrar la brecha.
- Preparacion para una ruta optimizada en fases posteriores.

## 9. Metricas de exito

| Area | Metrica | Descripcion |
| --- | --- | --- |
| Extraccion de skills | Precision de extraccion | Porcentaje de habilidades extraidas correctamente desde CVs y job postings en una muestra revisada manualmente. |
| Normalizacion | Tasa de alias resueltos | Porcentaje de variantes como "python programming" o "Python 3" que se consolidan correctamente bajo una habilidad normalizada. |
| Gap analysis | Cobertura de habilidades requeridas | Porcentaje de skills del rol objetivo que el sistema puede identificar y comparar contra el CV. |
| Recomendacion | Cobertura ganada | Porcentaje adicional de skills faltantes cubiertas por los cursos recomendados. |
| Optimizacion | Eficiencia de ruta | Cobertura de skills lograda por hora o por dolar invertido. |
| Evaluacion | Mejora contra baseline | Diferencia entre la ruta optimizada y una seleccion naive de cursos por popularidad, rating o costo. |

## 10. Pipeline propuesto

```text
Job postings + CV + course catalog
        |
        v
Ingestion and cleaning
        |
        v
Skill extraction
        |
        v
Skill normalization and aliases
        |
        v
Structured analytical database
        |
        v
Skill gap analysis
        |
        v
Course/resource matching
        |
        v
Learning path optimization
        |
        v
Dashboard and capstone evaluation
```

## 11. Modelo conceptual inicial

La base tecnica que sigue despues de esta fase debe representar:

- `skills`: catalogo normalizado de habilidades.
- `skill_aliases`: variantes y sinonimos de habilidades.
- `job_skills`: habilidades requeridas por job postings.
- `resume_skills`: habilidades detectadas en CVs.
- `courses`: cursos o recursos disponibles.
- `course_skills`: habilidades cubiertas por cada curso.
- `optimization_runs`: ejecuciones futuras del optimizador.

## 12. Supuestos

- Los job postings son una aproximacion razonable de la demanda laboral.
- Las habilidades extraidas desde CVs representan evidencia parcial, no certificacion absoluta.
- La normalizacion de skills requiere reglas, aliases y posible soporte semantico con embeddings.
- Los cursos recomendados no garantizan empleo, pero pueden mejorar la preparacion observable del estudiante.
- La optimizacion debe ser evaluada contra baselines simples para demostrar valor academico.

## 13. Limitaciones

- El sistema puede heredar sesgos de los datos laborales usados.
- La extraccion automatica de skills puede cometer errores.
- Algunas habilidades son ambiguas o dependen del contexto.
- El catalogo inicial de cursos sera limitado durante el prototipo.
- Las restricciones de tiempo, costo y dificultad son aproximaciones del contexto real del estudiante.

## 14. Entregables de Fase 1

- Titulo final del capstone.
- Pregunta de investigacion.
- Objetivo general y objetivos especificos.
- Alcance inicial con roles objetivo.
- Metricas de exito.
- Pipeline conceptual.
- Modelo conceptual que habilita la P1 tecnica.

## 15. Paso siguiente: P1 Base Analitica

Despues de cerrar esta fase, el siguiente commit tecnico debe construir la base analitica minima:

- Crear migracion y modelos para `skills`, `skill_aliases`, `job_skills`, `resume_skills`, `courses`, `course_skills` y `optimization_runs`.
- Crear seed minimo con 20-30 skills, 10-15 cursos y mapeo course-to-skill.
- Preparar el primer gap analysis para un CV y un target role.
- Dejar embeddings preparados para semantic matching, sin introducir todavia OR-Tools complejo.

