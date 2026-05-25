import re
import logging

logger = logging.getLogger(__name__)

def get_id_from_url(url: str) -> str:
    """
    Extrae el ID de archivo de una URL de Google Drive o Docs.
    Soporta formatos estándar y IDs directos.
    """
    if not url:
        return None
    
    # Patrón común para docs, sheets, drive file links
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # Patrón para carpetas de drive
    match_folder = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    if match_folder:
        return match_folder.group(1)

    # Si parece un ID directo (largo y sin barras), lo devolvemos tal cual
    if len(url) > 20 and '/' not in url:
        return url
        
    return None