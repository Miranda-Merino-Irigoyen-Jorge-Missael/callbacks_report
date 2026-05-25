import logging
from src.config import Config
from src.core.vertex_wrapper import vertex_client
from google.genai import types
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)

class ChatService:
    """
    Servicio encargado de seleccionar el prompt adecuado según las reglas de negocio,
    inyectar la transcripción y generar el reporte usando Vertex AI.
    """

    def __init__(self):
        self.client = vertex_client.client
        self.model_name = "gemini-2.5-pro" 

    def _get_prompt_filename(self, deliverable, visa_type):
        """Aplica las reglas de negocio para elegir el archivo .txt correcto."""
        
        if deliverable == 'Discovery Call':
            return "discovery_call_prompt.txt"
            
        elif deliverable == 'Re-Screening':
            # Normalizamos el texto de la visa por seguridad
            v_type = str(visa_type).strip()
            
            if v_type in ['Visa T y Visa U', 'Visa T y U']:
                return "re_screening_visat_visau.txt"
            elif v_type == 'Visa T':
                return "re_screening_visat.txt"
            elif v_type == 'Visa U':
                return "re_screening_visau.txt"
            else:
                raise ValueError(f"Tipo de visa '{v_type}' no tiene un prompt definido para Re-Screening.")
                
        else:
            raise ValueError(f"Entregable no reconocido o vacío: '{deliverable}'")

    def _read_prompt(self, filename):
        """Lee el contenido del archivo local de prompt."""
        prompt_path = Config.PROMPTS_DIR / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"🚨 No se encontró el archivo de prompt: {prompt_path}")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def analyze_transcription(self, deliverable, visa_type, transcription_data):
        """
        Ejecuta la llamada a la IA con el prompt dinámico y la transcripción.
        transcription_data es el dict devuelto por drive_service.get_transcription().
        """
        # 1. Determinar y cargar el prompt base
        prompt_file = self._get_prompt_filename(deliverable, visa_type)
        logger.info(f"Cargando prompt '{prompt_file}' para Entregable='{deliverable}', Visa='{visa_type}'")
        system_instruction = self._read_prompt(prompt_file)

        # 2. Preparar el contenido (Texto o PDF)
        parts = [
            types.Part.from_text(text="A continuación te proporciono la transcripción del cliente. Por favor, analízala y genera el documento según tus instrucciones del sistema:\n\n")
        ]
        
        if transcription_data['type'] == 'text':
            parts.append(types.Part.from_text(text=transcription_data['content']))
            logger.info("Transcripción inyectada como texto nativo.")
        elif transcription_data['type'] == 'pdf':
            with open(transcription_data['path'], "rb") as f:
                pdf_data = f.read()
            parts.append(types.Part.from_bytes(data=pdf_data, mime_type="application/pdf"))
            logger.info("Transcripción inyectada como documento PDF directamente en bytes.")

        contents = [types.Content(role="user", parts=parts)]

        # 3. Configuración de seguridad (apagamos los filtros para temas legales)
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

        # 4. Parámetros de generación. Ajusta la temperatura según prefieras.
        gen_config = types.GenerateContentConfig(
            temperature=0.3, 
            max_output_tokens=8192,
            safety_settings=safety_settings,
            system_instruction=system_instruction
        )

        # 5. Enviar a Vertex AI
        logger.info(f"⏳ Enviando datos al modelo {self.model_name} en Vertex AI global...")
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=gen_config
        )

        # 6. Extraer y limpiar el texto generado
        text = response.text if hasattr(response, 'text') else ""
        if not text and response.candidates:
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                pass
                
        if not text:
            raise ValueError("Vertex AI devolvió una respuesta vacía.")

        # Remover bloques de código markdown por si el modelo los añade
        text = text.strip()
        if text.startswith("```markdown"):
            text = text[11:]
        elif text.startswith("```md"):
            text = text[5:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

# Instancia global
chat_service = ChatService()