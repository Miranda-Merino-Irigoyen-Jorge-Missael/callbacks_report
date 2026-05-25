import logging
import sys
from src.workflows.dc_workflow import dc_workflow

# Configuración de logs limpia y amigable para la terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("main")

def main():
    print("\n" + "="*60)
    print("🚀 SISTEMA DE REPORTES - DISCOVERY CALL & RE-SCREENING 🚀")
    print("="*60 + "\n")

    try:
        # Arrancamos nuestro nuevo flujo
        dc_workflow.run()
        
    except KeyboardInterrupt:
        print("\n[!] Proceso detenido manualmente por el usuario (Ctrl+C).")
    except Exception as e:
        print(f"\n[!!!] ERROR FATAL NO CONTROLADO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "="*60)
        print("PROCESO TERMINADO")
        print("="*60)

if __name__ == "__main__":
    # Forzar buffering de salida en algunas terminales (VSCode/Windows)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    main()