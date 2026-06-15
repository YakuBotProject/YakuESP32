import os
import sys
from datetime import datetime
from pathlib import Path
import joblib
import pandas as pd
from dotenv import load_dotenv
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

# Configurar ruta del proyecto (3 niveles hacia arriba desde src/ML/XGBoost/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.database import SessionLocal
from src.models.models import modelos_ml, historial_modelos, plantas

def train_xgb_models():
    # Cargar variables de entorno desde el directorio raíz del proyecto
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    db = SessionLocal()
    xgb_dir = Path(__file__).resolve().parent
    
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

        print(f"Entrenando XGBoost para {crop}...")
        modelo_xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")
        modelo_xgb.fit(X_train, y_train)

        y_pred_xgb = modelo_xgb.predict(X_test)
        acc_xgb = accuracy_score(y_test, y_pred_xgb)
        prec_xgb = precision_score(y_test, y_pred_xgb)
        rec_xgb = recall_score(y_test, y_pred_xgb)
        f1_xgb = f1_score(y_test, y_pred_xgb)

        print(f"XGB {crop}: Acc={acc_xgb:.4f}, Prec={prec_xgb:.4f}, Rec={rec_xgb:.4f}, F1={f1_xgb:.4f}")

        model_filename_xgb = f"modelo_riego_{crop.lower()}_xgb.joblib"
        model_path_xgb = xgb_dir / model_filename_xgb
        joblib.dump(modelo_xgb, model_path_xgb)
        print(f"Modelo guardado en {model_path_xgb}")

        # --- Versionado y registro en BD ---
        model_name = f"XGBoost {crop}"
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
            
            print(f"[XGBoost] Detectada versión anterior: {model_record.version}. Incrementando a: {nueva_version}")
            model_record.id_planta = id_planta
            model_record.precision_modelo = float(acc_xgb * 100)
            model_record.precision_score = float(prec_xgb)
            model_record.recall_score = float(rec_xgb)
            model_record.f1_score = float(f1_xgb)
            model_record.version = nueva_version
            model_record.ruta = f"src/ML/XGBoost/{model_filename_xgb}"
            model_record.fecha_entrenamiento = datetime.now()
            db.add(model_record)
            db.flush()
            
            accion_hist = "reentrenado"
            desc_hist = f"Modelo XGBoost reentrenado. Versión incrementada a {nueva_version}. Precisión: {acc_xgb:.4f}."
        else:
            nueva_version = "1.0.0"
            print(f"[XGBoost] Creando nuevo modelo en la BD con versión inicial: {nueva_version}")
            model_record = modelos_ml(
                id_planta=id_planta,
                nombre_modelo=model_name,
                algoritmo="XGBoost",
                descripcion=f"Modelo predictivo XGBoost para cultivo de {crop}.",
                ruta_archivo=model_filename_xgb,
                ruta=f"src/ML/XGBoost/{model_filename_xgb}",
                precision_modelo=float(acc_xgb * 100),
                precision_score=float(prec_xgb),
                recall_score=float(rec_xgb),
                f1_score=float(f1_xgb),
                version=nueva_version,
                es_default=False,
                estado="activo",
                creado_por=1,
                fecha_entrenamiento=datetime.now()
            )
            db.add(model_record)
            db.flush()
            
            accion_hist = "creado"
            desc_hist = f"Modelo {model_name} (XGBoost) creado con versión inicial 1.0.0. Precisión: {acc_xgb:.4f}."

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
    print("\n--- Entrenamiento XGBoost Finalizado ---")

if __name__ == "__main__":
    train_xgb_models()
