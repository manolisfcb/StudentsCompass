# Tests

## Estructura de Tests

```
tests/
├── __init__.py
├── conftest.py           # Fixtures compartidas y configuración
├── test_auth.py          # Tests de autenticación
├── test_dashboard.py     # Tests del dashboard
├── test_resume.py        # Tests de CV/Resume
└── test_applications.py  # Tests de aplicaciones
```

## Ejecutar Tests

### Todos los tests
```bash
pytest
```

### Con cobertura
```bash
pytest --cov=app --cov-report=html
```

### Tests específicos
```bash
# Solo tests de autenticación
pytest tests/test_auth.py

# Solo un test específico
pytest tests/test_auth.py::TestAuth::test_login_success

# Tests por categoría
pytest -k "dashboard"
```

### Modo verbose
```bash
pytest -v
```

### Ver prints durante tests
```bash
pytest -s
```

## Cobertura

Después de ejecutar tests con `--cov-report=html`, abre:
```bash
open htmlcov/index.html
```

## Fixtures Disponibles

- `client`: Cliente HTTP async para hacer requests
- `db_session`: Sesión de base de datos para tests
- `test_user`: Usuario de prueba pre-creado
- `test_company`: Empresa de prueba pre-creada
- `auth_headers`: Headers de autenticación para test_user
- `mock_s3_service`: Mock del servicio S3 (evita llamadas reales a AWS)
- `mock_genai`: Mock de Google GenAI (evita llamadas reales a la API)

## Convenciones

- Los tests usan SQLite en memoria (rápido y aislado)
- Los servicios externos (S3, GenAI) están mockeados
- Cada test corre con una base de datos limpia
- Los nombres de tests deben ser descriptivos: `test_<acción>_<resultado>`

## CI/CD

Agrega esto a tu GitHub Actions:

```yaml
- name: Run tests
  run: |
    pytest --cov=app --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```
