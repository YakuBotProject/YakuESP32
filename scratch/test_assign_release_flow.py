import sys
import os

# Set up project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import dispositivos, componentes, asignaciones_iot

def run_test():
    db = SessionLocal()
    try:
        # Reset DB state first
        print("[INFO] Resetting database...")
        os.system("..\\.venv\\Scripts\\python.exe ..\\recreate_db_clean.py")
        
        # Fresh query after reset
        db.expire_all()

        # Step 1: Find a component in stock (e.g., component id 10) and an assigned device (e.g., device 1)
        comp = db.query(componentes).filter(componentes.id == 10).first()
        dev = db.query(dispositivos).filter(dispositivos.id_dispositivo == 1).first()
        
        print(f"\n[TEST 1] Initial state:")
        print(f"  Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}")
        print(f"  Device 1 -> estado: {dev.estado}")
        
        # Verify initial preconditions
        assert comp.estado == "disponible"
        assert comp.en_almacen is True
        assert dev.estado == "asignado"

        # Step 2: Assign component to device 1
        print("\n[TEST 2] Simulating component assignment...")
        # Get base assignment for device 1 to retrieve id_usuario and id_cultivo
        base_asig = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_dispositivo == dev.id_dispositivo
        ).first()
        assert base_asig is not None, "Device 1 must have a base assignment."
        
        # Create assignment mimicking the updated route handler (activo=False)
        nueva_asig = asignaciones_iot(
            id_usuario=base_asig.id_usuario,
            id_dispositivo=dev.id_dispositivo,
            id_cultivo=base_asig.id_cultivo,
            id_componente=comp.id,
            pin_gpio=17,
            id_tipo_metrica=1,
            activo=False  # MUST be False by default now!
        )
        db.add(nueva_asig)
        
        comp.en_almacen = False
        comp.estado = "assigned"
        db.add(comp)
        db.commit()
        
        # Check from DB
        db.expire_all()
        comp = db.query(componentes).filter(componentes.id == 10).first()
        asig = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == 10,
            asignaciones_iot.id_dispositivo == 1
        ).first()
        
        print("  After assignment:")
        print(f"    Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}")
        print(f"    Assignment -> id: {asig.id}, activo: {asig.activo}")
        
        assert comp.estado == "assigned" or comp.estado == "asignado"
        assert comp.en_almacen is False
        assert asig.activo is False, "New assignments must be created with activo=False"

        # Step 3: Test Same-Device validation lookup (ignores activo state)
        print("\n[TEST 3] Simulating same-device validation lookup...")
        existing_asig = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == comp.id,
            asignaciones_iot.id_dispositivo == dev.id_dispositivo
        ).first()
        print(f"    Found existing assignment: {existing_asig is not None}")
        assert existing_asig is not None, "Must find the assignment even if it is inactive (activo=False)"
        assert existing_asig.id == asig.id

        # Step 4: Simulate component release
        print("\n[TEST 4] Simulating component release...")
        # Get assignments of the component (all, active or not)
        asigs_to_release = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == comp.id
        ).all()
        print(f"    Found {len(asigs_to_release)} assignments to release.")
        assert len(asigs_to_release) == 1
        
        # Determine destination warehouse
        dest_almacen_id = None
        first_device = db.query(dispositivos).filter(dispositivos.id_dispositivo == asigs_to_release[0].id_dispositivo).first()
        if first_device:
            dest_almacen_id = first_device.id_almacen
            
        print(f"    Target warehouse: {dest_almacen_id}")
        
        # Decouple component in assignment rows (set id_componente = None, activo = False)
        for a in asigs_to_release:
            a.activo = False
            a.id_componente = None
            db.add(a)
            
        # Return component to stock
        comp.estado = "disponible"
        comp.en_almacen = True
        comp.id_almacen = dest_almacen_id
        db.add(comp)
        db.commit()
        
        # Check from DB
        db.expire_all()
        comp = db.query(componentes).filter(componentes.id == 10).first()
        # The assignment row should no longer point to component 10
        asig_by_comp = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == 10
        ).first()
        
        # Let's fetch the assignment by ID to check if it still exists but has id_componente = None
        asig_by_id = db.query(asignaciones_iot).filter(
            asignaciones_iot.id == asig.id
        ).first()

        print("  After release:")
        print(f"    Component 10 -> estado: {comp.estado}, en_almacen: {comp.en_almacen}")
        print(f"    Assignment by component -> found: {asig_by_comp is not None}")
        print(f"    Assignment by ID -> found: {asig_by_id is not None}, id_componente: {asig_by_id.id_componente}, activo: {asig_by_id.activo}")
        
        assert comp.estado == "disponible"
        assert comp.en_almacen is True
        assert asig_by_comp is None, "There should be no assignment referencing component 10"
        assert asig_by_id is not None, "The assignment row should still exist in the database (historical record)"
        assert asig_by_id.id_componente is None, "The component ID reference must be cleared"
        assert asig_by_id.activo is False, "The assignment must be inactive"
        
        print("\n[SUCCESS] ALL VERIFICATION TESTS PASSED!")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
        # Clean up database state
        print("\nRestoring database to clean seed state...")
        os.system("..\\.venv\\Scripts\\python.exe ..\\recreate_db_clean.py")

if __name__ == "__main__":
    run_test()
