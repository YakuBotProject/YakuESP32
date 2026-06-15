import sys
import os

# Set up project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import dispositivos, componentes, asignaciones_iot

def run_verification():
    db = SessionLocal()
    try:
        # 1. Fetch device 3 (starts as disponible, en_almacen=True, id_almacen=1)
        dev = db.query(dispositivos).filter(dispositivos.id_dispositivo == 3).first()
        print(f"[TEST 1] Initial Device status:")
        print(f"  nombre: {dev.nombre}")
        print(f"  estado: {dev.estado}")
        print(f"  en_almacen: {dev.en_almacen}")
        print(f"  id_almacen: {dev.id_almacen}")

        # Simulate assigning device 3 to user 2 and crop 2
        # (This replicates assigning devices logic)
        dev.estado = "asignado"
        dev.en_almacen = False
        nueva_asig = asignaciones_iot(
            id_usuario=2,
            id_dispositivo=dev.id_dispositivo,
            id_cultivo=2,
            activo=False
        )
        db.add(nueva_asig)
        db.commit()
        db.refresh(dev)

        print(f"\n[TEST 2] Device assigned:")
        print(f"  estado: {dev.estado} (Expected: asignado)")
        print(f"  en_almacen: {dev.en_almacen} (Expected: False)")
        print(f"  id_almacen: {dev.id_almacen} (Expected: 1 - kept!)")

        # Fetch component 10 (starts as disponible, en_almacen=True, id_almacen=1)
        comp = db.query(componentes).filter(componentes.id == 10).first()
        print(f"\n[TEST 3] Initial Component status:")
        print(f"  numero_serie: {comp.numero_serie}")
        print(f"  estado: {comp.estado}")
        print(f"  en_almacen: {comp.en_almacen}")
        print(f"  id_almacen: {comp.id_almacen}")

        # Simulate assigning component 10 to device 3 on pin 17
        comp.en_almacen = False
        comp.estado = "asignado"
        comp_asig = asignaciones_iot(
            id_usuario=2,
            id_dispositivo=dev.id_dispositivo,
            id_cultivo=2,
            id_componente=comp.id,
            pin_gpio=17,
            activo=True
        )
        db.add(comp_asig)
        db.commit()
        db.refresh(comp)

        print(f"\n[TEST 4] Component assigned:")
        print(f"  estado: {comp.estado} (Expected: asignado)")
        print(f"  en_almacen: {comp.en_almacen} (Expected: False)")
        print(f"  id_almacen: {comp.id_almacen} (Expected: 1 - kept!)")

        # Now simulate releasing device 3 back to stock
        # Replicates liberar_dispositivo_a_stock
        dev.estado = "disponible"
        dev.en_almacen = True
        dev.id_almacen = 1
        db.add(dev)

        # Deactivate assignments and return components
        asigs = db.query(asignaciones_iot).filter(asignaciones_iot.id_dispositivo == dev.id_dispositivo).all()
        for asig in asigs:
            asig.activo = False
            db.add(asig)
            if asig.id_componente:
                c = db.query(componentes).filter(componentes.id == asig.id_componente).first()
                if c:
                    c.estado = "disponible"
                    c.en_almacen = True
                    c.id_almacen = dev.id_almacen
                    db.add(c)
        db.commit()
        
        # Verify fresh from DB
        db.expire_all()
        dev_post = db.query(dispositivos).filter(dispositivos.id_dispositivo == 3).first()
        comp_post = db.query(componentes).filter(componentes.id == 10).first()

        print(f"\n[TEST 5] Post Release Device:")
        print(f"  estado: {dev_post.estado} (Expected: disponible)")
        print(f"  en_almacen: {dev_post.en_almacen} (Expected: True)")
        print(f"  id_almacen: {dev_post.id_almacen} (Expected: 1)")

        print(f"\n[TEST 6] Post Release Component:")
        print(f"  estado: {comp_post.estado} (Expected: disponible)")
        print(f"  en_almacen: {comp_post.en_almacen} (Expected: True)")
        print(f"  id_almacen: {comp_post.id_almacen} (Expected: 1)")

        # Cleanup assignments created during test
        for asig in asigs:
            db.delete(asig)
        db.delete(nueva_asig)
        db.commit()
        print(f"\n[INFO] Cleanup completed successfully.")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
