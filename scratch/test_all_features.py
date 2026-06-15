import os
import sys
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score
from xgboost import XGBClassifier

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_all_features():
    dataset_path = "src/ML/dataset/irrigation_prediction.csv"
    df = pd.read_csv(dataset_path)
    df.columns = df.columns.str.strip()

    crops = ["Rice", "Maize", "Sugarcane", "Potato", "Wheat", "Cotton"]
    
    # Preprocesar columnas categóricas del dataset mediante get_dummies
    df_encoded = pd.get_dummies(df, columns=[
        "Soil_Type", "Season", "Mulching_Used", "Region", "Crop_Growth_Stage", 
        "Irrigation_Type", "Water_Source"
    ], drop_first=True)
    
    df_encoded["Riego"] = df_encoded["Irrigation_Need"].apply(
        lambda x: 0 if str(x).strip().lower() == "low" else 1
    )

    for crop in crops:
        df_crop = df_encoded[df_encoded["Crop_Type"].str.strip().str.lower() == crop.lower()].copy()
        
        # Eliminar columnas de control/meta
        X = df_crop.drop(columns=["Crop_Type", "Irrigation_Need", "Riego"])
        y = df_crop["Riego"]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)
        y_pred_rf = rf.predict(X_test)
        acc_rf = accuracy_score(y_test, y_pred_rf)
        prec_rf = precision_score(y_test, y_pred_rf)

        xgb = XGBClassifier(n_estimators=100, random_state=42, eval_metric="logloss")
        xgb.fit(X_train, y_train)
        y_pred_xgb = xgb.predict(X_test)
        acc_xgb = accuracy_score(y_test, y_pred_xgb)
        prec_xgb = precision_score(y_test, y_pred_xgb)

        print(f"{crop:10} (All Cols) | RF Acc={acc_rf:.4f} Prec={prec_rf:.4f} | XGB Acc={acc_xgb:.4f} Prec={prec_xgb:.4f}")

if __name__ == "__main__":
    test_all_features()
