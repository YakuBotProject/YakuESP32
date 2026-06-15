import os
import sys
from sqlalchemy import text
from dotenv import load_dotenv

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal, engine
from src.models.models import cultivos, modelos_ml, cultivo_modelo, predicciones_ml, plantas
from src.routers.ml import obtener_prediccion_riego
from src.schemas.schemas import PrediccionRiegoModel

def test_multicultural_prediction():
    load_dotenv()
    db = SessionLocal()
    
    print("--- Probando Inferencia de ML por Cultivo y Etapa ---")
    
    # 1. Crear o buscar un cultivo de Trigo (id_planta = 7, Wheat)
    # y asignarle la etapa 'floracion'
    planta_trigo = db.query(plantas).filter(plantas.nombre == "Wheat").first()
    if not planta_trigo:
        print("Error: No se encontró la planta 'Wheat' en la BD. Ejecuta la siembra primero.")
        return

    # Limpiar predicciones de prueba previas
    db.execute(text("TRUNCATE TABLE predicciones_ml, cultivo_modelo CASCADE;"))
    db.commit()

    # Buscar cultivo existente o crear uno
    cultivo_test = db.query(cultivos).filter(cultivos.id_planta == planta_trigo.id_planta).first()
    if not cultivo_test:
        print("Insertando cultivo de trigo de prueba...")
        cultivo_test = cultivos(
            id_usuario=2,
            id_planta=planta_trigo.id_planta,
            id_fuente_agua=2,
            id_distrito=1,
            lugar="Invernadero Pruebas ML",
            nombre_planta="Mi Trigo de Prueba",
            etapa_crecimiento="floracion",  # Debería mapearse a 2 (Flowering)
            estado="activo"
        )
        db.add(cultivo_test)
        db.flush()
        db.commit()
    else:
        # Asegurar etapa 'floracion'
        cultivo_test.etapa_crecimiento = "floracion"
        db.add(cultivo_test)
        db.commit()

    print(f"Cultivo de trigo: ID={cultivo_test.id_cultivo}, Planta={planta_trigo.nombre}, Etapa={cultivo_test.etapa_crecimiento}")

    # Datos del sensor:
    # humedad_suelo = 200 (muy seco), humedad_ambiente = 45, temperatura_ambiente = 28, temperatura_suelo = 26.5
    data_input = PrediccionRiegoModel(
        humedad_suelo=200.0,
        humedad_ambiente=45.0,
        temperatura_ambiente=28.0,
        temperatura_suelo=26.5
    )

    algos = ["Random Forest", "XGBoost"]
    for algo in algos:
        model_name = f"{algo} Wheat"
        print(f"\n=== PROBANDO ALGORITMO: {model_name} ===")
        
        # Buscar el modelo en la BD
        modelo_db = db.query(modelos_ml).filter(modelos_ml.nombre_modelo == model_name).first()
        if not modelo_db:
            print(f"Error: No se encontró el modelo '{model_name}'.")
            continue
        
        print(f"Modelo encontrado: ID={modelo_db.id_modelo}, Nombre={modelo_db.nombre_modelo}, Versión={modelo_db.version}, Precisión Registrada={modelo_db.precision_modelo}%")

        # Asignar este modelo al cultivo de trigo
        db.execute(text("TRUNCATE TABLE cultivo_modelo CASCADE;"))
        db.commit()
        
        asig_modelo = cultivo_modelo(
            id_usuario=2,
            id_cultivo=cultivo_test.id_cultivo,
            id_modelo=modelo_db.id_modelo,
            activo=True
        )
        db.add(asig_modelo)
        db.commit()
        print(f"Modelo {model_name} asociado al cultivo.")

        print("Ejecutando predicción mediante obtener_prediccion_riego...")
        resultado = obtener_prediccion_riego(
            data=data_input,
            db=db,
            id_usuario=2,
            id_cultivo=cultivo_test.id_cultivo,
            persistir=True
        )

        print("--- Respuesta de la API ---")
        print(f"Decisión de Riego (0/1): {resultado.get('riego')}")
        print(f"Mensaje: {resultado.get('mensaje')}")
        print(f"Modelo Activo Usado: {resultado.get('modelo_activo')}")
        print(f"Ruta del Archivo: {resultado.get('ruta_modelo')}")
        print(f"Probabilidad de Riego: {resultado.get('probabilidad_riego')}")

        # Verificar si se guardó en la base de datos
        db.expire_all()
        pred_guardada = db.query(predicciones_ml).filter(
            predicciones_ml.id_cultivo == cultivo_test.id_cultivo,
            predicciones_ml.id_modelo == modelo_db.id_modelo
        ).order_by(predicciones_ml.id_prediccion.desc()).first()

        if pred_guardada:
            print("--- Predicción Guardada en la Base de Datos ---")
            print(f"ID Predicción: {pred_guardada.id_prediccion}")
            print(f"Variables Entrada (JSONB): {pred_guardada.variables_entrada}")
            print(f"Recomendación: {pred_guardada.recomendacion}")
            print(f"Probabilidad: {pred_guardada.probabilidad}")
            print(f"Acción Ejecutada: {pred_guardada.accion_ejecutada}")
            
            # Verificar que la etapa_crecimiento esté en el JSONB
            stage_saved = pred_guardada.variables_entrada.get("etapa_crecimiento")
            if stage_saved == 2:
                print(f"[OK] EXITO: La etapa de crecimiento 'floracion' fue correctamente mapeada a '2' y guardada en JSONB para {algo}.")
            else:
                print(f"[FAIL] ERROR: La etapa guardada es {stage_saved}, se esperaba 2.")
        else:
            print(f"[FAIL] ERROR: No se guardó la predicción en la base de datos para {algo}.")

    db.close()

if __name__ == "__main__":
    test_multicultural_prediction()
