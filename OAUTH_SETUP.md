# Configuración de OAuth 2.0 para Google Drive

## Pasos para obtener credenciales OAuth:

### 1. Ve a Google Cloud Console
https://console.cloud.google.com/apis/credentials

### 2. Crea un proyecto (si no tienes uno)
- Click en el dropdown del proyecto arriba
- "New Project"
- Dale un nombre (ej: "StudentsCompass")

### 3. Habilita la API de Google Drive
- Ve a: https://console.cloud.google.com/apis/library
- Busca "Google Drive API"
- Click en "Enable"

### 4. Configura la pantalla de consentimiento OAuth
- Ve a: https://console.cloud.google.com/apis/credentials/consent
- Selecciona "External" (para cuentas personales)
- Rellena:
  - App name: StudentsCompass
  - User support email: tu email
  - Developer contact: tu email
- Click "Save and Continue"
- En "Scopes": click "Save and Continue" (no necesitas añadir nada)
- En "Test users": añade tu email de Google
- Click "Save and Continue"

### 5. Crea las credenciales OAuth 2.0
- Ve a: https://console.cloud.google.com/apis/credentials
- Click "Create Credentials" → "OAuth client ID"
- Application type: "Desktop app"
- Name: "StudentsCompass Desktop"
- Click "Create"
- Click "Download JSON"

### 6. Guarda el archivo JSON
Renombra el archivo descargado a `google_oauth_client.json` y ponlo en:
```
app/credentials/google_oauth_client.json
```

### 7. Primera ejecución
La primera vez que ejecutes la app y hagas una subida de CV:
```bash
uv run main.py
```

Se abrirá un navegador para que autorices la aplicación. Después de autorizar:
- Se guardará `app/credentials/token.pickle`
- Ya no pedirá autorización en siguientes ejecuciones
- El token se renueva automáticamente cuando expira

### 8. Crea una carpeta en Google Drive
- Ve a tu Google Drive personal
- Crea una carpeta para los CVs (ej: "StudentsCompass_CVs")
- Copia el ID de la carpeta desde la URL:
  ```
  https://drive.google.com/drive/folders/[ESTE_ES_EL_ID]
  ```
- Actualiza `.env`:
  ```
  GOOGLE_DRIVE_FOLDER_ID=tu_folder_id_aqui
  ```

## Notas importantes:
- ✅ Funciona con cuentas personales de Google (sin Workspace)
- ✅ Usa tu cuota de Drive personal (15GB gratis)
- ✅ Los archivos se guardan en TU Drive
- ✅ El token se renueva automáticamente
- ⚠️ No subas `google_oauth_client.json` ni `token.pickle` a Git (ya están en .gitignore)
