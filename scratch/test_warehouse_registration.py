import sys
import os

# Set up project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import componentes, almacenes, tipos_componente

def test_registration():
    db = SessionLocal()
    try:
        # Check if warehouse with ID 1 exists
        almacen = db.query(almacenes).filter(almacenes.id == 1).first()
        if not almacen:
            print("[ERROR] Warehouse with ID 1 does not exist in DB.")
            return

        print(f"[INFO] Using Warehouse: {almacen.nombre}")

        # Check if component type with ID 1 exists
        tipo = db.query(tipos_componente).filter(tipos_componente.id == 1).first()
        if not tipo:
            print("[ERROR] Component type with ID 1 does not exist in DB.")
            return

        print(f"[INFO] Using Component Type: {tipo.nombre_modelo}")

        # Clean existing test component if any
        serial = "TEST-SERIAL-999"
        existing = db.query(componentes).filter(componentes.numero_serie == serial).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Simulate registration
        nuevo = componentes(
            id_tipo_componente=tipo.id,
            numero_serie=serial,
            id_almacen=almacen.id,
            estado="activo"
        )
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)

        print(f"[SUCCESS] Component registered with ID: {nuevo.id}")
        print(f"  id_almacen in memory object: {nuevo.id_almacen}")

        # Fetch clean from DB
        db.expire_all()
        fetched = db.query(componentes).filter(componentes.id == nuevo.id).first()
        print(f"  id_almacen fetched from DB: {fetched.id_almacen}")

        if fetched.id_almacen == almacen.id:
            print("[PASS] The id_almacen was correctly saved and verified in the database!")
        else:
            print("[FAIL] The id_almacen was NOT correctly saved in the database.")

        # Clean up
        db.delete(fetched)
        db.commit()
        print("[INFO] Cleaned up test component.")

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_registration()
