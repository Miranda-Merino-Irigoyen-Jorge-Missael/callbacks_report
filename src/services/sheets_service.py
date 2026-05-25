import logging
import datetime
from src.core.google_client import google_manager
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

class SheetsService:
    """
    Servicio encargado de interactuar con la hoja 'DC'.
    Maneja la lectura de transcripciones completadas y la escritura final de reportes.
    """
    
    # Mapeo estricto de columnas para la hoja DC (1-based index para gspread)
    COL_CLIENT_ID = 1          # Columna A
    COL_CLIENT_NAME = 2        # Columna B
    COL_AUDIO_LINK = 3         # Columna C
    COL_TRANSCRIPTION_LINK = 4 # Columna D
    COL_STATUS = 5             # Columna E
    COL_DELIVERABLE = 6        # Columna F
    COL_VISA_TYPE = 7          # Columna G
    COL_OUTPUT_LINK = 8        # Columna H

    def __init__(self):
        self.client = google_manager.get_sheets_client()
        self.spreadsheet_id = Config.SPREADSHEET_ID
        self.sheet_name = Config.SHEET_NAME
        self._sheet = None

    @property
    def sheet(self):
        """Lazy load para inicializar la conexión con gspread únicamente cuando se use."""
        if not self._sheet:
            try:
                sh = self.client.open_by_key(self.spreadsheet_id)
                self._sheet = sh.worksheet(self.sheet_name)
            except Exception as e:
                logger.error(f"Error conectando a la hoja {self.sheet_name}: {e}")
                raise
        return self._sheet

    def get_pending_rows(self):
        """
        Analiza la hoja 'DC' y extrae las filas que cumplen con los requisitos de procesamiento.
        """
        pending_rows = []
        try:
            all_values = self.sheet.get_all_values()
            
            for i, row in enumerate(all_values):
                row_idx = i + 1  # gspread requiere índices basados en 1
                if row_idx == 1: 
                    continue  # Omitir la fila de encabezados

                # Extraer datos asegurando que la fila tenga suficientes columnas
                status = row[self.COL_STATUS - 1].strip() if len(row) >= self.COL_STATUS else ""
                transcription_link = row[self.COL_TRANSCRIPTION_LINK - 1].strip() if len(row) >= self.COL_TRANSCRIPTION_LINK else ""
                output_link = row[self.COL_OUTPUT_LINK - 1].strip() if len(row) >= self.COL_OUTPUT_LINK else ""
                deliverable = row[self.COL_DELIVERABLE - 1].strip() if len(row) >= self.COL_DELIVERABLE else ""
                visa_type = row[self.COL_VISA_TYPE - 1].strip() if len(row) >= self.COL_VISA_TYPE else ""

                # --- APLICACIÓN ESTRICTA DE REGLAS DE NEGOCIO ---

                # REGLA 1: Solo procesar si el status es exactamente 'TRANSCRIPT COMPLETED'
                if status != 'TRANSCRIPT COMPLETED':
                    continue

                # REGLA 2: NO procesar si ya existe un link generado en la Columna H
                if output_link:
                    continue
                
                # REGLA 3: NO procesar si la Columna D está vacía o el link es muy corto (inválido)
                if not transcription_link or len(transcription_link) < 10:
                    continue

                # REGLA 4: Exclusión estricta de 'Re-Screening' + 'General'
                if deliverable == 'Re-Screening' and visa_type == 'General':
                    logger.warning(f"Fila {row_idx}: Ignorada (Re-Screening con Visa General no permitido).")
                    continue
                    
                # Si sobrevive a todos los filtros, agregamos la fila para procesar
                row_data = {
                    'row_idx': row_idx,
                    'client_id': row[self.COL_CLIENT_ID - 1] if len(row) >= self.COL_CLIENT_ID else "",
                    'client_name': row[self.COL_CLIENT_NAME - 1] if len(row) >= self.COL_CLIENT_NAME else "",
                    'audio_link': row[self.COL_AUDIO_LINK - 1] if len(row) >= self.COL_AUDIO_LINK else "",
                    'transcription_link': transcription_link,
                    'deliverable': deliverable,
                    'visa_type': visa_type
                }
                pending_rows.append(row_data)
            
            return pending_rows

        except Exception as e:
            logger.error(f"Error analizando filas pendientes en gspread: {e}")
            raise

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=Config.RETRY_MIN_WAIT, max=Config.RETRY_MAX_WAIT),
        retry=retry_if_exception_type((GoogleAPIError, TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def update_status(self, row_idx, status_text):
        """Actualiza la columna E (Status) para control de errores o flujos."""
        try:
            self.sheet.update_cell(row_idx, self.COL_STATUS, status_text)
            logger.info(f"Fila {row_idx}: Estado en columna E cambiado a '{status_text}'.")
        except Exception as e:
            logger.error(f"Error actualizando estado en la fila {row_idx}: {e}")
            raise

    @retry(
        stop=stop_after_attempt(Config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=Config.RETRY_MIN_WAIT, max=Config.RETRY_MAX_WAIT),
        retry=retry_if_exception_type((GoogleAPIError, TimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def write_output_doc(self, row_idx, doc_url):
        """
        Escribe el enlace del Google Doc final en la columna H.
        Adicionalmente cambia el estado a 'COMPLETED' para indicar que terminó exitosamente.
        """
        try:
            # Escribir el link en la columna H
            self.sheet.update_cell(row_idx, self.COL_OUTPUT_LINK, doc_url)
            logger.info(f"Fila {row_idx}: Enlace del reporte registrado exitosamente en la columna H.")
            
            # Cambiar el dropdown de la columna E para cerrar el ciclo de la fila
            self.update_status(row_idx, 'COMPLETED')
        except Exception as e:
            logger.error(f"Error escribiendo el enlace final en la fila {row_idx}: {e}")
            raise

# Instancia global disponible para importación
sheets_service = SheetsService()