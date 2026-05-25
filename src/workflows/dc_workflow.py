import logging
from src.services.sheets_service import sheets_service
from src.services.drive_service import drive_service
from src.services.chat_service import chat_service
from src.config import Config

logger = logging.getLogger(__name__)

class DCProcessor:
    """
    Orquestador principal para procesar transcripciones de Discovery Calls y Re-Screening.
    """
    def __init__(self):
        pass
    
    def run(self):
        logger.info(">>> INICIANDO PROCESADOR DE DISCOVERY CALLS Y RE-SCREENING <<<")
        
        pending_rows = sheets_service.get_pending_rows()
        if not pending_rows:
            logger.info("No se encontraron casos pendientes listos para procesar.")
            return

        logger.info(f"Se encontraron {len(pending_rows)} casos para procesar.")

        for row in pending_rows:
            self.process_single_case(row)

        logger.info(">>> PROCESO FINALIZADO <<<")

    def process_single_case(self, row_data):
        row_idx = row_data['row_idx']
        client_name = row_data.get('client_name', 'Cliente_Desconocido')
        deliverable = row_data.get('deliverable', '')
        visa_type = row_data.get('visa_type', '') 
        transcription_link = row_data.get('transcription_link', '')
        
        logger.info(f"--- Procesando Fila {row_idx}: {client_name} | Entregable: {deliverable} ---")
        
        if not transcription_link or len(str(transcription_link)) < 10:
            logger.error(f"Fila {row_idx}: No hay enlace de transcripción válido en la columna D.")
            sheets_service.update_status(row_idx, "ERROR: SIN TRANSCRIPCIÓN")
            return

        try:
            # 1. Marcar estado como PROCESSING en el Sheet para que el usuario sepa que inició
            sheets_service.update_status(row_idx, "PROCESSING")

            # 2. Determinar la carpeta destino en Drive según el Entregable
            if deliverable == 'Discovery Call':
                folder_id = Config.DRIVE_FOLDER_DISCOVERY_CALL
            elif deliverable == 'Re-Screening':
                folder_id = Config.DRIVE_FOLDER_RE_SCREENING
            else:
                raise ValueError(f"Entregable '{deliverable}' no cuenta con una carpeta de destino configurada.")

            # 3. Extraer la transcripción desde Drive (Texto nativo o PDF)
            logger.info("Extrayendo transcripción...")
            transcription_data = drive_service.get_transcription(transcription_link, Config.LOCAL_OUTPUT_DIR)

            # 4. Mandar todo a la IA (Vertex AI) con los prompts dinámicos
            logger.info("Generando reporte con IA...")
            generated_text = chat_service.analyze_transcription(deliverable, visa_type, transcription_data)

            # 5. Crear el documento nativo en Google Docs y colocarlo en la carpeta correcta
            doc_title = f"{client_name} - {deliverable} Report"
            doc_link = drive_service.create_google_doc(doc_title, generated_text, folder_id)

            # 6. Escribir el enlace en la columna H y cambiar estado a COMPLETED
            sheets_service.write_output_doc(row_idx, doc_link)
            logger.info(f"✅ Caso {client_name} terminado exitosamente.")

        except Exception as e:
            logger.error(f"❌ Error procesando el caso {client_name} (Fila {row_idx}): {e}")
            try:
                # Escribir el error en el status (columna E) para visibilidad en el Sheet
                error_msg = f"ERROR: {str(e)[:45]}"
                sheets_service.update_status(row_idx, error_msg)
            except Exception as sheet_err:
                logger.error(f"No se pudo actualizar el status de error en el Sheet: {sheet_err}")

# Instancia global
dc_workflow = DCProcessor()