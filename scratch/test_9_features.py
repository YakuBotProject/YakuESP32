import os
import sys
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score
from xgboost import XGBClassifier

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_9_features():
    dataset_path = "src/ML/dataset/irrigation_prediction.csv"
    df = pd.read_csv(dataset_path)
    df.columns = df.columns.str.strip()

    crop = "Wheat"
    df_crop = df[df["Crop_Type"].str.strip().str.lower() == crop.lower()].copy()

    stage_mapping = {"Sowing": 0, "Vegetative": 1, "Flowering": 2, "Harvest": 3}
    df_crop["etapa_crecimiento"] = df_crop["Crop_Growth_Stage"].map(stage_mapping)
    df_crop["temperatura_suelo"] = (df_crop["Temperature_C"] - 1.5).round(3)
    df_crop = df_crop.rename(columns={
        "Soil_Moisture": "humedad_suelo",
        "Temperature_C": "temperatura_ambiente",
        "Humidity": "humedad_ambiente",
        "Rainfall_mm": "lluvia",
        "Sunlight_Hours": "horas_sol",
        "Wind_Speed_kmh": "velocidad_viento",
        "Soil_pH": "ph_suelo",
        "Organic_Carbon": "carbono_organico",
        "Electrical_Conductivity": "conductividad_electrica"
    })
    
    df_crop["Riego"] = df_crop["Irrigation_Need"].apply(
        lambda x: 0 if str(x).strip().lower() == "low" else 1
    )

    # 9 features
    features = [
        "humedad_suelo", "humedad_ambiente", "temperatura_ambiente", "temperatura_suelo", "etapa_crecimiento",
        "ph_suelo", "carbono_organico", "conductividad_electrica", "lluvia"
    ]
    X = df_crop[features]
    y = df_crop["Riego"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    print(f"9 Features RF - Accuracy: {accuracy_score(y_test, y_pred_rf):.4f}, Precision: {precision_score(y_test, y_pred_rf):.4f}")

    xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")
    xgb.fit(X_train, y_train)
    y_pred_xgb = xgb.predict(X_test)
    print(f"9 Features XGBoost - Accuracy: {accuracy_score(y_test, y_pred_xgb):.4f}, Precision: {precision_score(y_test, y_pred_xgb):.4f}")

if __name__ == "__main__":
    test_9_features()
