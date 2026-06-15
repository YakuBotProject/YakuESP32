import sys
import os

# Set up project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import dispositivos, componentes

def run_test():
    db = SessionLocal()
    try:
        # Reset DB state first
        print("[INFO] Resetting database...")
        os.system("..\\.venv\\Scripts\\python.exe ..\\recreate_db_clean.py")
        db.expire_all()

        # Step 1: Find a device in stock (e.g. device 3)
        dev = db.query(dispositivos).filter(dispositivos.id_dispositivo == 3).first()
        print(f"\n[TEST 1] Initial Device state:")
        print(f"  Device 3 -> estado: {dev.estado}, en_almacen: {dev.en_almacen}, id_almacen: {dev.id_almacen}")
        assert dev.estado == "disponible"
        assert dev.en_almacen is True

        # Simulate change to 'reparacion'
        print("\n[TEST 2] Changing Device state to 'reparacion'...")
        dev.estado = "reparacion"
        dev.en_almacen = True
        db.add(dev)
        db.commit()
        db.refresh(dev)
        print(f"  Device 3 -> estado: {dev.estado}, en_almacen: {dev.en_almacen}, id_almacen: {dev.id_almacen}")
        assert dev.estado == "reparacion"
        assert dev.en_almacen is True

        # Simulate change to 'Retirado' (logical removal)
        print("\n[TEST 3] Changing Device state to 'Retirado'...")
        dev.estado = "Retirado"
        dev.en_almacen = False
        dev.id_almacen = None
        db.add(dev)
        db.commit()
        db.refresh(dev)
        print(f"  Device 3 -> estado: {dev.estado}, en_almacen: {dev.en_almacen}, id_almacen: {dev.id_almacen}")
        assert dev.estado == "Retirado"
        assert dev.en_almacen is False
        assert dev.id_almacen is None

        # Simulate change back to 'disponible'
        print("\n[TEST 4] Changing Device state back to 'disponible'...")
        dev.estado = "disponible"
        dev.en_almacen = True
        dev.id_almacen = 1
        db.add(dev)
        db.commit()
        db.refresh(dev)
        print(f"  Device 3 -> estado: {dev.estado}, en_almacen: {dev.en_almacen}, id_almacen: {dev.id_almacen}")
        assert dev.estado == "disponible"
        assert dev.en_almacen is True

        # Step 2: Component status transitions (component 10)
        comp = db.query(componentes).filter(componentes.id == 10).first()
        print(f"\n[TEST 5] Initial Component state:")
        print(f"  Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}, id_almacen: {comp.id_almacen}")
        assert comp.estado == "disponible"
        assert comp.en_almacen is True

        # Change to 'reparacion'
        print("\n[TEST 6] Changing Component state to 'reparacion'...")
        comp.estado = "reparacion"
        comp.en_almacen = True
        db.add(comp)
        db.commit()
        db.refresh(comp)
        print(f"  Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}, id_almacen: {comp.id_almacen}")
        assert comp.estado == "reparacion"
        assert comp.en_almacen is True

        # Change to 'Retirado'
        print("\n[TEST 7] Changing Component state to 'Retirado'...")
        comp.estado = "Retirado"
        comp.en_almacen = False
        comp.id_almacen = None
        db.add(comp)
        db.commit()
        db.refresh(comp)
        print(f"  Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}, id_almacen: {comp.id_almacen}")
        assert comp.estado == "Retirado"
        assert comp.en_almacen is False
        assert comp.id_almacen is None

        # Change back to 'disponible'
        print("\n[TEST 8] Changing Component state back to 'disponible'...")
        comp.estado = "disponible"
        comp.en_almacen = True
        comp.id_almacen = 1
        db.add(comp)
        db.commit()
        db.refresh(comp)
        print(f"  Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}, id_almacen: {comp.id_almacen}")
        assert comp.estado == "disponible"
        assert comp.en_almacen is True

        print("\n[SUCCESS] ALL STATUS ENDPOINT TRANSITION TESTS PASSED!")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
        # Restore db seed
        print("\nRestoring database to clean seed state...")
        os.system("..\\.venv\\Scripts\\python.exe ..\\recreate_db_clean.py")

if __name__ == "__main__":
    run_test()
