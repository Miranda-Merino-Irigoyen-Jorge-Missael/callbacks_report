import logging
from google import genai
from src.config import Config

logger = logging.getLogger(__name__)

class AIClientWrapper:
    """
    Wrapper ultraligero para inicializar la conexión con Vertex AI
    apuntando al endpoint global/específico definido en Config.LOCATION.
    """
    def __init__(self):
        try:
            # Inicializamos forzosamente en modo Vertex AI
            self.client = genai.Client(
                vertexai=True,
                project=Config.PROJECT_ID,
                location=Config.LOCATION
            )
            logger.info(f"✅ Vertex AI Client inicializado correctamente en el proyecto '{Config.PROJECT_ID}' (Región: {Config.LOCATION}).")
        except Exception as e:
            logger.error(f"❌ Error crítico inicializando Vertex AI: {e}")
            raise

# Instancia global
vertex_client = AIClientWrapper()