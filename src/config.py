import os
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """
    Configuración centralizada para el procesador de Discovery Calls y Re-Screening.
    Conexión configurada para Vertex AI usando el endpoint global.
    """
    APP_VERSION = "v2.0" 

    # 1. Definición de Rutas Base
    BASE_DIR = Path(__file__).resolve().parent.parent
    PROMPTS_DIR = BASE_DIR / "prompts"
    OUTPUT_DIR = BASE_DIR / "output"
    LOCAL_OUTPUT_DIR = OUTPUT_DIR / "results"  
    
    CREDENTIALS_FILE = BASE_DIR / "credentials.json"  
    OAUTH_CREDENTIALS_FILE = BASE_DIR / "client_secret.json"
    TOKEN_FILE = BASE_DIR / "token.json"

    # 2. Carga de variables de entorno
    load_dotenv(BASE_DIR / ".env")

    # 3. Configuración de IA (Vertex AI)
    PROJECT_ID = os.getenv("PROJECT_ID")
    LOCATION = os.getenv("LOCATION", "global") # Configurado para endpoint global/central
    USE_VERTEX_AI = True # Forzamos Vertex AI para este proyecto
    
    # 4. Configuración de Drive y Sheets
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "1jjwFW_0CZnp72njceR5CwvS9baDiNixpqGM3-f7I8rY")
    SHEET_NAME = os.getenv("SHEET_NAME", "DC")
    
    # Nuevos IDs de Carpetas de Destino
    DRIVE_FOLDER_DISCOVERY_CALL = "1_UFNavIGyT2kBxlz2vyqwJTrwF8y2XH-"
    DRIVE_FOLDER_RE_SCREENING = "1auCw5Krc3g_xKKXu2K1hBlirR3dJmJ9d"
    
    # 5. Scopes (Permisos) - Añadimos auth/documents por si usamos la API de Docs nativa
    SCOPES = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/cloud-platform',
        'https://www.googleapis.com/auth/documents'
    ]

    # 6. Configuración de Timeouts y Reintentos
    API_TIMEOUT_SECONDS = 300
    MAX_RETRIES = 2           
    RETRY_MIN_WAIT = 5        
    RETRY_MAX_WAIT = 60    

    @classmethod
    def validate(cls):
        """Asegura que las variables y carpetas críticas existan antes de arrancar."""
        missing = []
        if not cls.PROJECT_ID: missing.append("PROJECT_ID")
        
        if missing:
            raise ValueError(f"Faltan variables en el .env: {', '.join(missing)}")
        
        # Crear carpetas si no existen
        for directory in [cls.PROMPTS_DIR, cls.LOCAL_OUTPUT_DIR]:
            if not directory.exists():
                try:
                    os.makedirs(directory, exist_ok=True)
                except Exception:
                    pass

# Validar al importar
Config.validate()