import os
import sys
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from xgboost import XGBClassifier

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def tune():
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
    })
    
    # Riego (Low -> 0, Medium/High -> 1)
    df_crop["Riego"] = df_crop["Irrigation_Need"].apply(
        lambda x: 0 if str(x).strip().lower() == "low" else 1
    )

    features = ["humedad_suelo", "humedad_ambiente", "temperatura_ambiente", "temperatura_suelo", "etapa_crecimiento"]
    X = df_crop[features]
    y = df_crop["Riego"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 1. Probar RF base
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    print(f"RF Base - Accuracy: {accuracy_score(y_test, y_pred_rf):.4f}, Precision: {precision_score(y_test, y_pred_rf):.4f}")

    # 2. Probar XGBoost base
    xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")
    xgb.fit(X_train, y_train)
    y_pred_xgb = xgb.predict(X_test)
    print(f"XGBoost Base - Accuracy: {accuracy_score(y_test, y_pred_xgb):.4f}, Precision: {precision_score(y_test, y_pred_xgb):.4f}")

    # 3. ¿Qué pasa si agregamos más variables del dataset original?
    # P. ej. Rainfall_mm, Sunlight_Hours, Wind_Speed_kmh
    # Si las incluimos en el entrenamiento para ver si la precisión sube de 90%
    print("\n--- Entrenando con variables climáticas adicionales (Rainfall, Sunlight, Wind) ---")
    df_crop_ext = df[df["Crop_Type"].str.strip().str.lower() == crop.lower()].copy()
    df_crop_ext["etapa_crecimiento"] = df_crop_ext["Crop_Growth_Stage"].map(stage_mapping)
    df_crop_ext["temperatura_suelo"] = (df_crop_ext["Temperature_C"] - 1.5).round(3)
    df_crop_ext = df_crop_ext.rename(columns={
        "Soil_Moisture": "humedad_suelo",
        "Temperature_C": "temperatura_ambiente",
        "Humidity": "humedad_ambiente",
        "Rainfall_mm": "lluvia",
        "Sunlight_Hours": "horas_sol",
        "Wind_Speed_kmh": "velocidad_viento"
    })
    df_crop_ext["Riego"] = df_crop_ext["Irrigation_Need"].apply(
        lambda x: 0 if str(x).strip().lower() == "low" else 1
    )

    features_ext = ["humedad_suelo", "humedad_ambiente", "temperatura_ambiente", "temperatura_suelo", "etapa_crecimiento", "lluvia", "horas_sol", "velocidad_viento"]
    X_ext = df_crop_ext[features_ext]
    y_ext = df_crop_ext["Riego"]

    X_train_ext, X_test_ext, y_train_ext, y_test_ext = train_test_split(
        X_ext, y_ext, test_size=0.2, random_state=42, stratify=y_ext
    )

    rf_ext = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_ext.fit(X_train_ext, y_train_ext)
    y_pred_rf_ext = rf_ext.predict(X_test_ext)
    print(f"RF Extendido - Accuracy: {accuracy_score(y_test_ext, y_pred_rf_ext):.4f}, Precision: {precision_score(y_test_ext, y_pred_rf_ext):.4f}")

    xgb_ext = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")
    xgb_ext.fit(X_train_ext, y_train_ext)
    y_pred_xgb_ext = xgb_ext.predict(X_test_ext)
    print(f"XGBoost Extendido - Accuracy: {accuracy_score(y_test_ext, y_pred_xgb_ext):.4f}, Precision: {precision_score(y_test_ext, y_pred_xgb_ext):.4f}")

    # 4. Probar tuning de hiperparámetros con 5 variables
    print("\n--- Búsqueda de hiperparámetros con 5 variables ---")
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 5, 8, None],
        'min_samples_split': [2, 5, 10],
    }
    grid_rf = GridSearchCV(RandomForestClassifier(random_state=42), param_grid, cv=3, scoring='precision')
    grid_rf.fit(X_train, y_train)
    best_rf = grid_rf.best_estimator_
    y_pred_best_rf = best_rf.predict(X_test)
    print(f"RF Optimizado (5 var) - Accuracy: {accuracy_score(y_test, y_pred_best_rf):.4f}, Precision: {precision_score(y_test, y_pred_best_rf):.4f}")
    print(f"Mejores parámetros RF: {grid_rf.best_params_}")

    param_grid_xgb = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 5, 8],
        'learning_rate': [0.01, 0.05, 0.1, 0.2]
    }
    grid_xgb = GridSearchCV(XGBClassifier(random_state=42, eval_metric="logloss"), param_grid_xgb, cv=3, scoring='precision')
    grid_xgb.fit(X_train, y_train)
    best_xgb = grid_xgb.best_estimator_
    y_pred_best_xgb = best_xgb.predict(X_test)
    print(f"XGBoost Optimizado (5 var) - Accuracy: {accuracy_score(y_test, y_pred_best_xgb):.4f}, Precision: {precision_score(y_test, y_pred_best_xgb):.4f}")
    print(f"Mejores parámetros XGB: {grid_xgb.best_params_}")

if __name__ == "__main__":
    tune()
