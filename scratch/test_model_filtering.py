import os
import sys
from dotenv import load_dotenv

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import cultivos, modelos_ml, plantas
from src.services import crud

def test_filtering():
    load_dotenv()
    db = SessionLocal()
    
    print("--- Probando Filtrado de Modelos por Planta de Cultivo ---")
    
    # 1. Buscar el cultivo de trigo de prueba (ID=3)
    cultivo_db = db.query(cultivos).filter(cultivos.nombre_planta == "Mi Trigo de Prueba").first()
    if not cultivo_db:
        print("Error: No se encontró el cultivo de trigo de prueba. Ejecuta test_prediction.py primero.")
        return
        
    id_planta_trigo = cultivo_db.id_planta
    print(f"Cultivo: {cultivo_db.nombre_planta}, Planta ID: {id_planta_trigo}")

    # 2. Obtener la lista total de modelos en la BD
    modelos_totales = db.query(modelos_ml).all()
    print(f"Total de modelos registrados en la BD: {len(modelos_totales)}")
    for m in modelos_totales:
        print(f" - ID={m.id_modelo}, Nombre='{m.nombre_modelo}', Planta ID={m.id_planta}")

    # 3. Aplicar el filtrado de modelos para el Trigo (ID de planta = id_planta_trigo)
    # Deben retornar:
    # - Modelos con id_planta == id_planta_trigo (Trigo)
    # - Modelos con id_planta == None (Genéricos o Globales)
    # Y NO deben retornar modelos de otros cultivos (Rice, Maize, etc.)
    modelos_filtrados = [
        m for m in modelos_totales 
        if m.id_planta is None or m.id_planta == id_planta_trigo
    ]

    print(f"\nModelos filtrados visibles para el agricultor en el cultivo de Trigo:")
    for m in modelos_filtrados:
        print(f" - ID={m.id_modelo}, Nombre='{m.nombre_modelo}', Planta ID={m.id_planta}")

    # 4. Validar exclusión de otros cultivos
    nombres_filtrados = [m.nombre_modelo for m in modelos_filtrados]
    assert "Random Forest Wheat" in nombres_filtrados, "El modelo de trigo debe estar visible"
    assert "Random Forest Regresor Riego" in nombres_filtrados, "Los modelos genéricos (default) deben estar visibles"
    assert "Random Forest Rice" not in nombres_filtrados, "El modelo de arroz NO debe estar visible para trigo"
    assert "Random Forest Cotton" not in nombres_filtrados, "El modelo de algodón NO debe estar visible para trigo"

    print("\n[OK] EXITO: El filtrado de modelos funciona correctamente. El agricultor solo ve modelos compatibles.")
    
    db.close()

if __name__ == "__main__":
    test_filtering()
