import os
import logging
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from src.config import Config

logger = logging.getLogger(__name__)

class GoogleClientManager:
    """
    Singleton para manejar las conexiones autenticadas a Google APIs vía OAuth.
    Usa client_secret.json y genera token.json para recordar la sesión.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleClientManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._creds = None
        self._drive_service = None
        self._sheets_client = None
        self._initialized = True

    def _get_oauth_creds(self):
        """Carga las credenciales OAuth del usuario o inicia el flujo en el navegador."""
        if not self._creds:
            try:
                # 1. Intentar cargar sesión guardada
                if os.path.exists(Config.TOKEN_FILE):
                    self._creds = Credentials.from_authorized_user_file(
                        Config.TOKEN_FILE, Config.SCOPES
                    )
                
                # 2. Si no hay credenciales válidas, autenticar
                if not self._creds or not self._creds.valid:
                    if self._creds and self._creds.expired and self._creds.refresh_token:
                        logger.info("Refrescando token de sesión OAuth...")
                        self._creds.refresh(Request())
                    else:
                        logger.info("Iniciando autenticación OAuth en el navegador...")
                        if not os.path.exists(Config.OAUTH_CREDENTIALS_FILE):
                            raise FileNotFoundError(f"🚨 No se encontró el archivo: {Config.OAUTH_CREDENTIALS_FILE}")
                        
                        flow = InstalledAppFlow.from_client_secrets_file(
                            Config.OAUTH_CREDENTIALS_FILE, Config.SCOPES
                        )
                        # Esto abrirá el navegador
                        self._creds = flow.run_local_server(port=0)
                    
                    # 3. Guardar el token para no pedir login cada vez
                    with open(Config.TOKEN_FILE, 'w') as token:
                        token.write(self._creds.to_json())
                        
                logger.info("Credenciales OAuth cargadas y listas.")
            except Exception as e:
                logger.error(f"Error cargando OAuth: {e}")
                raise
        return self._creds

    def get_drive_service(self):
        """Retorna el servicio de Google Drive API v3."""
        if not self._drive_service:
            creds = self._get_oauth_creds()
            self._drive_service = build('drive', 'v3', credentials=creds)
        return self._drive_service

    def get_sheets_client(self):
        """Retorna el cliente de gspread para manipular la hoja de cálculo."""
        if not self._sheets_client:
            creds = self._get_oauth_creds()
            self._sheets_client = gspread.authorize(creds)
        return self._sheets_client

# Instancia global disponible para importación
google_manager = GoogleClientManager()