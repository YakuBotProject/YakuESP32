import os
import sys
from datetime import datetime
from pathlib import Path
import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# Configurar ruta del proyecto (3 niveles hacia arriba desde src/ML/Ramdom Forest/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.database import SessionLocal
from src.models.models import modelos_ml, historial_modelos, plantas

def train_rf_models():
    # Cargar variables de entorno desde el directorio raíz del proyecto
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    db = SessionLocal()
    rf_dir = Path(__file__).resolve().parent
    
    dataset_path = PROJECT_ROOT / "src" / "ML" / "dataset" / "cropdata_updated.csv"
    if not dataset_path.exists():
        print(f"Error: No se encontró el dataset en {dataset_path}")
        return

    print("Cargando dataset...")
    df = pd.read_csv(dataset_path)
    df.columns = df.columns.str.strip()

    crops = ["Tomato", "Chilli", "Potato", "Carrot", "Wheat"]
    
    # Mapear Seedling Stage a etapa_crecimiento (0: semillero, 1: crecimiento, 2: floracion, 3: cosecha)
    stage_mapping = {
        'Germination': 0,
        'Seedling Stage': 0,
        'Vegetative Growth / Root or Tuber Development': 1,
        'Flowering': 2,
        'Pollination': 2,
        'Fruit/Grain/Bulb Formation': 2,
        'Maturation': 3,
        'Harvest': 3
    }
    df["etapa_crecimiento"] = df["Seedling Stage"].map(stage_mapping)
    df = df.dropna(subset=["etapa_crecimiento"])

    df["humedad_suelo"] = df["MOI"]
    df["humedad_ambiente"] = df["humidity"]
    df["temperatura_ambiente"] = df["temp"]
    df["temperatura_suelo"] = (df["temp"] - 1.5).round(3)
    
    # result = 1 es riego necesario, result = 0 y 2 es no riego necesario
    df["Riego"] = df["result"].apply(lambda x: 1 if x == 1 else 0)

    features = [
        "humedad_suelo", "humedad_ambiente", "temperatura_ambiente", "temperatura_suelo", "etapa_crecimiento"
    ]

    for crop in crops:
        print(f"\n--- Procesando Cultivo: {crop} ---")
        df_crop = df[df["crop ID"].str.strip().str.lower() == crop.lower()].copy()
        
        if len(df_crop) == 0:
            print(f"Advertencia: No hay registros para {crop}")
            continue

        X = df_crop[features]
        y = df_crop["Riego"]

        # División entrenamiento/prueba
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"Entrenando RandomForest para {crop}...")
        modelo_rf = RandomForestClassifier(n_estimators=100, random_state=42)
        modelo_rf.fit(X_train, y_train)

        y_pred_rf = modelo_rf.predict(X_test)
        acc_rf = accuracy_score(y_test, y_pred_rf)
        prec_rf = precision_score(y_test, y_pred_rf)
        rec_rf = recall_score(y_test, y_pred_rf)
        f1_rf = f1_score(y_test, y_pred_rf)

        print(f"RF {crop}: Acc={acc_rf:.4f}, Prec={prec_rf:.4f}, Rec={rec_rf:.4f}, F1={f1_rf:.4f}")

        model_filename_rf = f"modelo_riego_{crop.lower()}_rf.joblib"
        model_path_rf = rf_dir / model_filename_rf
        joblib.dump(modelo_rf, model_path_rf)
        print(f"Modelo guardado en {model_path_rf}")

        # --- Versionado y registro en BD ---
        model_name = f"Random Forest {crop}"
        db_crop_name = "Tomates" if crop == "Tomato" else crop
        planta_db = db.query(plantas).filter(plantas.nombre == db_crop_name).first()
        id_planta = planta_db.id_planta if planta_db else None

        model_record = db.query(modelos_ml).filter(modelos_ml.nombre_modelo == model_name).first()
        
        if model_record:
            v_parts = model_record.version.split('.') if model_record.version else ["1", "0", "0"]
            try:
                v_parts[-1] = str(int(v_parts[-1]) + 1)
            except ValueError:
                v_parts[-1] = "1"
            nueva_version = ".".join(v_parts)
            
            print(f"[RandomForest] Detectada versión anterior: {model_record.version}. Incrementando a: {nueva_version}")
            model_record.id_planta = id_planta
            model_record.precision_modelo = float(acc_rf * 100)
            model_record.precision_score = float(prec_rf)
            model_record.recall_score = float(rec_rf)
            model_record.f1_score = float(f1_rf)
            model_record.version = nueva_version
            model_record.ruta = f"src/ML/Ramdom Forest/{model_filename_rf}"
            model_record.fecha_entrenamiento = datetime.now()
            db.add(model_record)
            db.flush()
            
            accion_hist = "reentrenado"
            desc_hist = f"Modelo RandomForest reentrenado. Versión incrementada a {nueva_version}. Precisión: {acc_rf:.4f}."
        else:
            nueva_version = "1.0.0"
            print(f"[RandomForest] Creando nuevo modelo en la BD con versión inicial: {nueva_version}")
            model_record = modelos_ml(
                id_planta=id_planta,
                nombre_modelo=model_name,
                algoritmo="RandomForest",
                descripcion=f"Modelo predictivo RandomForest para cultivo de {crop}.",
                ruta_archivo=model_filename_rf,
                ruta=f"src/ML/Ramdom Forest/{model_filename_rf}",
                precision_modelo=float(acc_rf * 100),
                precision_score=float(prec_rf),
                recall_score=float(rec_rf),
                f1_score=float(f1_rf),
                version=nueva_version,
                es_default=False,
                estado="activo",
                creado_por=1,
                fecha_entrenamiento=datetime.now()
            )
            db.add(model_record)
            db.flush()
            
            accion_hist = "creado"
            desc_hist = f"Modelo {model_name} (RandomForest) creado con versión inicial 1.0.0. Precisión: {acc_rf:.4f}."

        # Registrar en historial
        hist = historial_modelos(
            id_usuario=1,
            id_modelo=model_record.id_modelo,
            accion=accion_hist,
            descripcion=desc_hist,
            fecha=datetime.now()
        )
        db.add(hist)
        db.commit()
        print("Registro en BD exitoso.")

    db.close()
    print("\n--- Entrenamiento RandomForest Finalizado ---")

if __name__ == "__main__":
    train_rf_models()