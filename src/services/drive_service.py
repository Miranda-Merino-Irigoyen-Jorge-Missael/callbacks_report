import io
import logging
import os
import markdown
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
from src.core.google_client import google_manager
from src.utils.drive_tools import get_id_from_url
from src.config import Config
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from google.api_core.exceptions import GoogleAPIError

logger = logging.getLogger(__name__)

class DriveService:
    """
    Servicio encargado de interactuar con Google Drive.
    Descarga transcripciones (como Texto o PDF) y crea el Google Doc final.
    """
    
    def __init__(self):
        self.service = google_manager.get_drive_service()

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=Config.RETRY_MIN_WAIT, max=Config.RETRY_MAX_WAIT),
        retry=retry_if_exception_type((HttpError, GoogleAPIError, TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_file_metadata(self, file_id):
        """Obtiene el nombre y tipo MIME de un archivo."""
        try:
            return self.service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
        except HttpError as e:
            logger.error(f"Error obteniendo metadata para {file_id}: {e}")
            raise

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=Config.RETRY_MIN_WAIT, max=Config.RETRY_MAX_WAIT),
        retry=retry_if_exception_type((HttpError, GoogleAPIError, TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_transcription(self, url, download_dir):
        """
        Lee el enlace de la transcripción.
        - Si es un Google Doc: Extrae y retorna el texto.
        - Si es un PDF: Descarga el archivo y retorna la ruta.
        """
        file_id = get_id_from_url(url)
        if not file_id:
            raise ValueError(f"No se pudo extraer un ID válido de Drive desde el enlace: {url}")

        meta = self.get_file_metadata(file_id)
        mime_type = meta.get('mimeType')
        name = meta.get('name')

        logger.info(f"Procesando transcripción de Drive: {name} ({mime_type})")

        # CASO 1: Es un Google Doc Nativo
        if mime_type == 'application/vnd.google-apps.document':
            request = self.service.files().export_media(fileId=file_id, mimeType='text/plain')
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            
            text_content = fh.getvalue().decode('utf-8-sig', errors='replace')
            return {'type': 'text', 'content': text_content}

        # CASO 2: Es un archivo PDF
        elif mime_type == 'application/pdf':
            request = self.service.files().get_media(fileId=file_id)
            local_path = os.path.join(download_dir, f"{file_id}.pdf")
            with open(local_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            
            return {'type': 'pdf', 'path': local_path}

        else:
            raise ValueError(f"El tipo de archivo ({mime_type}) no está soportado. Debe ser Google Doc o PDF.")

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=Config.RETRY_MIN_WAIT, max=Config.RETRY_MAX_WAIT),
        retry=retry_if_exception_type((HttpError, GoogleAPIError, TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def create_google_doc(self, title, text_content, folder_id):
        """
        Convierte el Markdown generado por la IA a HTML y crea un nuevo 
        Google Doc nativo con formato.
        """
        try:
            logger.info(f"Creando Google Doc final '{title}' en la carpeta: {folder_id}")
            
            # MAGIA AQUÍ: Convertimos el markdown de Vertex a HTML
            # Usamos extensiones para que respete tablas, listas y saltos de línea
            html_content = markdown.markdown(
                text_content, 
                extensions=['extra', 'nl2br', 'tables']
            )
            
            file_metadata = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.document',
                'parents': [folder_id]
            }
            
            # Subimos el contenido usando mimetype='text/html'
            media = MediaIoBaseUpload(
                io.BytesIO(html_content.encode('utf-8')),
                mimetype='text/html',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            doc_link = file.get('webViewLink')
            logger.info(f"Google Doc creado exitosamente: {doc_link}")
            
            return doc_link

        except Exception as e:
            logger.error(f"Error creando el Google Doc final: {e}")
            raise

# Instancia global disponible para importación
drive_service = DriveService()