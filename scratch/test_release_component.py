import os
import sys
from sqlalchemy.orm import Session

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import asignaciones_iot, componentes, dispositivos

def test_release_component():
    db: Session = SessionLocal()
    try:
        print("--- TEST 1: Verificar asignaciones antes de liberar ---")
        # El componente 2 (DHT22) debe tener 2 asignaciones activas
        asigs_antes = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == 2,
            asignaciones_iot.activo == True
        ).all()
        print(f"Asignaciones activas encontradas para componente 2: {len(asigs_antes)}")
        assert len(asigs_antes) == 2, "Debería tener 2 asignaciones activas antes de liberar."
        
        comp_antes = db.query(componentes).filter(componentes.id == 2).first()
        print(f"Componente 2 antes -> en_almacen: {comp_antes.en_almacen}, estado: {comp_antes.estado}, almacen: {comp_antes.id_almacen}")
        assert comp_antes.en_almacen is False, "El componente no debería estar en el almacén."
        assert comp_antes.estado == "asignado", "El componente debería estar en estado 'asignado'."

        print("\n--- TEST 2: Ejecutar desvinculación (simulando backend) ---")
        # 1. Obtener almacén de destino del dispositivo
        dest_almacen_id = None
        first_device = db.query(dispositivos).filter(dispositivos.id_dispositivo == asigs_antes[0].id_dispositivo).first()
        if first_device:
            dest_almacen_id = first_device.id_almacen
            
        print(f"Almacén de origen del dispositivo: {dest_almacen_id}")

        # 2. Desactivar asignaciones
        for asig in asigs_antes:
            asig.activo = False
            db.add(asig)

        # 3. Regresar componente a stock
        comp_antes.estado = "disponible"
        comp_antes.en_almacen = True
        comp_antes.id_almacen = dest_almacen_id
        db.add(comp_antes)

        db.commit()
        print("Transacción de desvinculación confirmada en la BD.")

        print("\n--- TEST 3: Verificar estado después de liberar ---")
        comp_despues = db.query(componentes).filter(componentes.id == 2).first()
        print(f"Componente 2 después -> en_almacen: {comp_despues.en_almacen}, estado: {comp_despues.estado}, almacen: {comp_despues.id_almacen}")
        assert comp_despues.en_almacen is True, "El componente debería estar en el almacén ahora."
        assert comp_despues.estado == "disponible", "El componente debería estar disponible."
        assert comp_despues.id_almacen == 1, "Debería haber retornado al almacén 1 del dispositivo."

        asigs_despues = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == 2,
            asignaciones_iot.activo == True
        ).all()
        print(f"Asignaciones activas encontradas después de liberar: {len(asigs_despues)}")
        assert len(asigs_despues) == 0, "No debería haber asignaciones activas para el componente desvinculado."

        print("SUCCESS: TEST DE LIBERACIÓN PASADO.")

    finally:
        # Reestablecemos los datos originales volviendo a correr el seed para dejar la base limpia
        db.close()
        print("\nRestaurando base de datos limpia con semillas originales...")
        os.system("..\\.venv\\Scripts\\python.exe ..\\recreate_db_clean.py")

if __name__ == "__main__":
    test_release_component()
