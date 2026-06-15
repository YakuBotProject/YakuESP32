import os
import sys
from datetime import datetime
import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from xgboost import XGBClassifier

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.models.database import SessionLocal
from src.models.models import modelos_ml, historial_modelos, plantas

def train_all_crops():
    load_dotenv()
    db = SessionLocal()
    
    dataset_path = "src/ML/dataset/irrigation_prediction.csv"
    if not os.path.exists(dataset_path):
        print(f"Error: No se encontró el dataset en {dataset_path}")
        return

    print("Cargando dataset...")
    df = pd.read_csv(dataset_path)
    df.columns = df.columns.str.strip()

    crops = ["Rice", "Maize", "Sugarcane", "Potato", "Wheat", "Cotton"]
    stage_mapping = {"Sowing": 0, "Vegetative": 1, "Flowering": 2, "Harvest": 3}

    # Crear carpetas para los modelos si no existen
    rf_dir = "src/ML/Ramdom Forest"
    xgb_dir = "src/ML/XGBoost"
    os.makedirs(rf_dir, exist_ok=True)
    os.makedirs(xgb_dir, exist_ok=True)

    # Definir 13 variables de entrada para lograr precisión superior al 90%
    df["etapa_crecimiento"] = df["Crop_Growth_Stage"].map(stage_mapping)
    df["temperatura_suelo"] = (df["Temperature_C"] - 1.5).round(3)
    df["mulch_yes"] = df["Mulching_Used"].apply(lambda x: 1 if str(x).strip().lower() == "yes" else 0)
    
    df = df.rename(columns={
        "Soil_Moisture": "humedad_suelo",
        "Temperature_C": "temperatura_ambiente",
        "Humidity": "humedad_ambiente",
        "Rainfall_mm": "lluvia",
        "Sunlight_Hours": "horas_sol",
        "Wind_Speed_kmh": "velocidad_viento",
        "Soil_pH": "ph_suelo",
        "Organic_Carbon": "carbono_organico",
        "Electrical_Conductivity": "conductividad_electrica",
        "Previous_Irrigation_mm": "riego_previo"
    })
    
    df["Riego"] = df["Irrigation_Need"].apply(
        lambda x: 0 if str(x).strip().lower() == "low" else 1
    )

    features = [
        "humedad_suelo", "humedad_ambiente", "temperatura_ambiente", "temperatura_suelo", "etapa_crecimiento",
        "ph_suelo", "carbono_organico", "conductividad_electrica", "lluvia", "horas_sol", "velocidad_viento",
        "mulch_yes", "riego_previo"
    ]

    for crop in crops:
        print(f"\n--- Procesando Cultivo: {crop} ---")
        df_crop = df[df["Crop_Type"].str.strip().str.lower() == crop.lower()].copy()
        
        if len(df_crop) == 0:
            print(f"Advertencia: No hay registros para {crop}")
            continue

        X = df_crop[features]
        y = df_crop["Riego"]

        # División entrenamiento/prueba
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # -------------------------------------------------------------
        # 1. ENTRENAR RANDOM FOREST
        # -------------------------------------------------------------
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
        model_path_rf = os.path.join(rf_dir, model_filename_rf)
        joblib.dump(modelo_rf, model_path_rf)

        # Registrar/Actualizar RF en base de datos
        register_model_in_db(
            db=db,
            crop=crop,
            model_name=f"Random Forest {crop}",
            algo="RandomForest",
            filename=model_filename_rf,
            acc=acc_rf,
            prec=prec_rf,
            rec=rec_rf,
            f1=f1_rf
        )

        # -------------------------------------------------------------
        # 2. ENTRENAR XGBOOST
        # -------------------------------------------------------------
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
        model_path_xgb = os.path.join(xgb_dir, model_filename_xgb)
        joblib.dump(modelo_xgb, model_path_xgb)

        # Registrar/Actualizar XGBoost en base de datos
        register_model_in_db(
            db=db,
            crop=crop,
            model_name=f"XGBoost {crop}",
            algo="XGBoost",
            filename=model_filename_xgb,
            acc=acc_xgb,
            prec=prec_xgb,
            rec=rec_xgb,
            f1=f1_xgb
        )

    db.close()
    print("\n--- Entrenamiento y Registro Finalizado ---")

def register_model_in_db(db, crop, model_name, algo, filename, acc, prec, rec, f1):
    planta_db = db.query(plantas).filter(plantas.nombre == crop).first()
    id_planta = planta_db.id_planta if planta_db else None

    model_record = db.query(modelos_ml).filter(modelos_ml.nombre_modelo == model_name).first()
    
    if model_record:
        # Verificar versión anterior para guardar la nueva versión
        v_parts = model_record.version.split('.') if model_record.version else ["1", "0", "0"]
        try:
            v_parts[-1] = str(int(v_parts[-1]) + 1)
        except ValueError:
            v_parts[-1] = "1"
        nueva_version = ".".join(v_parts)
        
        print(f"[{algo}] Detectada versión anterior: {model_record.version}. Incrementando a: {nueva_version}")
        model_record.id_planta = id_planta
        model_record.precision_modelo = float(acc * 100)
        model_record.precision_score = float(prec)
        model_record.recall_score = float(rec)
        model_record.f1_score = float(f1)
        model_record.version = nueva_version
        model_record.fecha_entrenamiento = datetime.now()
        db.add(model_record)
        db.flush()
        
        accion_hist = "reentrenado"
        desc_hist = f"Modelo {algo} reentrenado. Versión incrementada a {nueva_version}. Precisión: {acc:.4f}."
    else:
        nueva_version = "1.0.0"
        print(f"[{algo}] Creando nuevo modelo en la BD con versión inicial: {nueva_version}")
        model_record = modelos_ml(
            id_planta=id_planta,
            nombre_modelo=model_name,
            algoritmo=algo,
            descripcion=f"Modelo predictivo {algo} para cultivo de {crop}.",
            ruta_archivo=filename,
            precision_modelo=float(acc * 100),
            precision_score=float(prec),
            recall_score=float(rec),
            f1_score=float(f1),
            version=nueva_version,
            es_default=False,
            estado="activo",
            creado_por=1,
            fecha_entrenamiento=datetime.now()
        )
        db.add(model_record)
        db.flush()
        
        accion_hist = "creado"
        desc_hist = f"Modelo {model_name} ({algo}) creado con versión inicial 1.0.0. Precisión: {acc:.4f}."

    # Registrar en el historial de modelos
    hist = historial_modelos(
        id_usuario=1,
        id_modelo=model_record.id_modelo,
        accion=accion_hist,
        descripcion=desc_hist,
        fecha=datetime.now()
    )
    db.add(hist)
    db.commit()

if __name__ == "__main__":
    train_all_crops()
