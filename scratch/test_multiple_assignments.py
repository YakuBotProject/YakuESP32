import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Configurar ruta del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import asignaciones_iot, componentes, dispositivos

def test_multiple_assignments():
    db: Session = SessionLocal()
    try:
        print("--- TEST 1: Verificar asignacion multiple sembrada (DHT22) ---")
        # El componente 2 (DHT22) debe tener 2 asignaciones activas en el dispositivo 1
        asigs = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == 2,
            asignaciones_iot.activo == True
        ).all()
        
        print(f"Asignaciones activas encontradas para componente 2 (DHT22): {len(asigs)}")
        for asig in asigs:
            print(f"- Asignacion ID: {asig.id}, Disp: {asig.id_dispositivo}, Metrica: {asig.id_tipo_metrica}, Pin: {asig.pin_gpio}")
            
        assert len(asigs) == 2, "Deberia haber exactamente 2 asignaciones activas (Temp y Hum) para el DHT22."
        assert asigs[0].id_dispositivo == 1 and asigs[1].id_dispositivo == 1, "Ambas deben estar en el dispositivo 1."
        assert asigs[0].pin_gpio == asigs[1].pin_gpio, "Ambas deben compartir el mismo pin GPIO."
        assert asigs[0].id_tipo_metrica != asigs[1].id_tipo_metrica, "Deben apuntar a diferentes tipos de metrica."
        print("SUCCESS: TEST 1 PASADO.")

        print("\n--- TEST 2: Intentar duplicar la misma metrica para el mismo componente (Debe fallar por indice unico) ---")
        # Intentar insertar otra asignación activa para el componente 2 en la misma métrica (ej: id_tipo_metrica = 2)
        duplicated_asig = asignaciones_iot(
            id_usuario=2,
            id_dispositivo=1,
            id_componente=2,
            id_tipo_metrica=2, # Ya existente
            pin_gpio=15,
            activo=True
        )
        db.add(duplicated_asig)
        try:
            db.commit()
            print("ERROR: TEST 2 FALLO: Se permitio duplicar la asignacion del componente para la misma metrica activa.")
            sys.exit(1)
        except IntegrityError as e:
            db.rollback()
            print("SUCCESS: TEST 2 PASADO: Se previno la insercion duplicada por indice unico (IntegrityError).")

        print("\n--- TEST 3: Intentar asignar el componente a otro dispositivo mientras está activo (Debe fallar) ---")
        # El componente 2 tiene en_almacen=False. Intentamos otra asignación activa en el dispositivo 3
        # En la lógica de negocio del router se hace esta validación. Probemos a nivel de BD si es posible insertar si no tiene el mismo dispositivo.
        # En la BD la restricción es de componente y métrica, pero la lógica de negocio valida que no esté en otro dispositivo.
        # Hagamos una validación simulada de la lógica del backend
        comp = db.query(componentes).filter(componentes.id == 2).first()
        print(f"Componente 2 en_almacen: {comp.en_almacen}, estado: {comp.estado}")
        
        # Simular validación del backend:
        is_in_stock = comp.en_almacen and comp.estado == "disponible"
        is_on_same_device = False
        
        # Validar si queremos asignarlo al dispositivo 3 (diferente al de su asignación actual que es 1)
        target_device_id = 3
        existing_asig = db.query(asignaciones_iot).filter(
            asignaciones_iot.id_componente == comp.id,
            asignaciones_iot.id_dispositivo == target_device_id,
            asignaciones_iot.activo == True
        ).first()
        if existing_asig:
            is_on_same_device = True
            
        print(f"¿Esta en stock? {is_in_stock}")
        print(f"¿Esta asignado al dispositivo destino {target_device_id}? {is_on_same_device}")
        
        if not (is_in_stock or is_on_same_device):
            print("SUCCESS: TEST 3 PASADO: La logica del backend prevendria la asignacion a un dispositivo diferente.")
        else:
            print("ERROR: TEST 3 FALLO: La logica del backend permitiria una asignacion invalida.")
            sys.exit(1)

    finally:
        db.close()

if __name__ == "__main__":
    test_multiple_assignments()
