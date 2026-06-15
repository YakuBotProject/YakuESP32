import json
import os
from typing import Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from src.services import crud
from src.models.database import SessionLocal
from src.schemas.schemas import TelemetriaTanqueModel, RiegoDatosModel, PrediccionRiegoModel
from src.routers.ml import obtener_prediccion_riego

load_dotenv()

# ── Credenciales desde .env con HiveMQ Cloud ──────────────────────
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC_RIEGO_DATOS = os.getenv("MQTT_TOPIC_RIEGO_DATOS", "yaku/riego/datos")
MQTT_TOPIC_CONTROL_CMD = os.getenv("MQTT_TOPIC_CONTROL_CMD", "yaku/riego/comando")
MQTT_TOPIC_CONTROL_AGUA = os.getenv("MQTT_TOPIC_CONTROL_AGUA", "yaku/tanque/datos")
MQTT_TLS_ENABLED = os.getenv("MQTT_TLS_ENABLED", "true").lower() in {"1", "true", "yes"}
MQTT_TLS_CA_CERT = os.getenv("MQTT_TLS_CA_CERT", "")

_mqtt_client: mqtt.Client | None = None


def publish_mqtt_message(topic: str, payload: str, qos: int = 1, retain: bool = False) -> None:
    """Publica un mensaje MQTT usando el cliente compartido de la aplicación."""
    global _mqtt_client

    if _mqtt_client is None:
        _mqtt_client = start_mqtt()

    if _mqtt_client is None:
        raise RuntimeError("No fue posible inicializar el cliente MQTT")

    result = _mqtt_client.publish(topic, payload, qos=qos, retain=retain)
    result.wait_for_publish()

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"Error publicando en {topic}: {result.rc}")


import datetime
import asyncio
from src.services.email import enviar_correo_alerta
from src.services.websocket_manager import manager
from src.services.webpush import enviar_webpush
from src.models.models import (
    asignaciones_iot,
    umbrales_config,
    tipos_metrica,
    alertas,
    tipos_alerta,
    configuracion_notificaciones,
    notificaciones,
    usuarios,
    suscripciones_push
)


def evaluar_y_disparar_alerta(db, id_asignacion: int, codigo_metrica: str, valor_actual: float):
    """Evalúa si el valor excede los umbrales configurados y envía notificaciones."""
    asig = db.query(asignaciones_iot).filter(asignaciones_iot.id == id_asignacion).first()
    if not asig:
        return

    umbral = db.query(umbrales_config).join(tipos_metrica).filter(
        umbrales_config.id_usuario == asig.id_usuario,
        tipos_metrica.codigo == codigo_metrica
    )
    if asig.id_cultivo:
        umbral = umbral.filter(umbrales_config.id_cultivo == asig.id_cultivo)
    
    umbral = umbral.first()
    if not umbral:
        return

    es_bajo = umbral.valor_minimo is not None and valor_actual < umbral.valor_minimo
    es_alto = umbral.valor_maximo is not None and valor_actual > umbral.valor_maximo

    if not (es_bajo or es_alto):
        return

    valor_limite = umbral.valor_minimo if es_bajo else umbral.valor_maximo
    
    # Mapear metrica y direccion de alerta a id_tipo_alerta (IDs en base de datos)
    mapping = {
        ('HUM_SUELO', True): 1,   # es_bajo
        ('HUM_SUELO', False): 2,  # es_alto
        ('TEMP_SUELO', True): 3,
        ('TEMP_SUELO', False): 4,
        ('TEMP_AMB', True): 5,
        ('TEMP_AMB', False): 6,
        ('HUM_AMB', True): 7,
        ('HUM_AMB', False): 8,
        ('NIVEL_AGUA', True): 9,
        ('NIVEL_AGUA', False): 10,
    }
    id_tipo_alerta = mapping.get((codigo_metrica, es_bajo))
    if not id_tipo_alerta:
        return

    tipo_alerta = db.query(tipos_alerta).filter(tipos_alerta.id == id_tipo_alerta).first()
    if not tipo_alerta:
        return

    metrica_info = {
        'HUM_SUELO': ('Humedad de suelo', '%'),
        'TEMP_SUELO': ('Temperatura de suelo', '°C'),
        'TEMP_AMB': ('Temperatura ambiente', '°C'),
        'HUM_AMB': ('Humedad ambiente', '%'),
        'NIVEL_AGUA': ('Nivel del tanque', '%'),
    }
    nombre_metrica, unidad = metrica_info.get(codigo_metrica, ("Métrica", ""))

    signo = "<" if es_bajo else ">"
    mensaje = f"¡Alerta de {nombre_metrica}! Valor detectado: {valor_actual:.2f}{unidad} (Umbral: {signo} {valor_limite:.2f}{unidad})"

    # Control de spam / Throttling: Reducido a 30 segundos en desarrollo/pruebas
    hace_tiempo = datetime.datetime.now() - datetime.timedelta(seconds=30)
    alerta_reciente = db.query(alertas).filter(
        alertas.id_usuario == asig.id_usuario,
        alertas.id_tipo_alerta == id_tipo_alerta,
        alertas.fecha >= hace_tiempo
    ).first()

    if alerta_reciente:
        print(f"[ALERTA] Throttled: Ya se notificó recientemente sobre {tipo_alerta.codigo}.")
        return

    nueva_alerta = alertas(
        id_usuario=asig.id_usuario,
        id_asignacion=id_asignacion,
        id_tipo_alerta=id_tipo_alerta,
        id_tipo_metrica=umbral.id_tipo_metrica,
        mensaje=mensaje,
        prioridad="alta" if tipo_alerta.severidad == "critico" else "media",
        valor_detectado=valor_actual,
        umbral=valor_limite,
        estado="pendiente"
    )
    db.add(nueva_alerta)
    db.commit()
    db.refresh(nueva_alerta)
    print(f"[ALERTA] Nueva alerta de base de datos creada (ID: {nueva_alerta.id})")

    pref = db.query(configuracion_notificaciones).filter(
        configuracion_notificaciones.id_usuario == asig.id_usuario,
        configuracion_notificaciones.id_tipo_alerta == id_tipo_alerta
    ).first()

    notificar_email = pref.canal_email if pref else True
    notificar_dashboard = pref.canal_dashboard if pref else True

    if notificar_dashboard:
        notif_dash = notificaciones(
            id_alerta=nueva_alerta.id,
            id_usuario=asig.id_usuario,
            canal="dashboard",
            asunto=f"Alerta: {tipo_alerta.nombre}",
            mensaje=mensaje,
            enviado=True,
            enviado_en=datetime.datetime.now()
        )
        db.add(notif_dash)
        db.commit()

        # 1. Enviar vía WebSocket (Alerta flotante interna en tiempo real)
        payload = {
            "id": str(nueva_alerta.id),
            "titulo": tipo_alerta.nombre,
            "mensaje": mensaje,
            "severidad": "critica" if tipo_alerta.severidad == "critico" else "advertencia",
            "valor": float(valor_actual)
        }
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(payload))
            else:
                asyncio.run(manager.broadcast(payload))
        except Exception as ws_err:
            print(f"[WS] Error al transmitir alerta WebSocket: {ws_err}")

        # 2. Enviar vía Web Push (Notificación push nativa del navegador)
        try:
            suscripciones = db.query(suscripciones_push).filter(suscripciones_push.id_usuario == asig.id_usuario).all()
            for sub in suscripciones:
                sub_info = {
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.key_p256dh,
                        "auth": sub.key_auth
                    }
                }
                res_push = enviar_webpush(sub_info, tipo_alerta.nombre, mensaje)
                if res_push == "EXPIRED":
                    print(f"[WEBPUSH] Limpiando suscripción obsoleta ID: {sub.id}")
                    db.delete(sub)
                    db.commit()
        except Exception as wp_err:
            print(f"[WEBPUSH] Error al despachar notificaciones Push: {wp_err}")


    if notificar_email:
        usuario = db.query(usuarios).filter(usuarios.id_usuario == asig.id_usuario).first()
        if usuario and usuario.correo:
            asunto_mail = f"YAKU: {tipo_alerta.nombre}"
            cuerpo_mail = f"Hola {usuario.nombre},\n\nSe ha detectado una anomalía en tu cultivo:\n\n{mensaje}\n\nPor favor ingresa al panel para tomar medidas.\n\nAtentamente,\nEquipo Yaku"
            
            exito = enviar_correo_alerta(usuario.correo, asunto_mail, cuerpo_mail)
            
            notif_email = notificaciones(
                id_alerta=nueva_alerta.id,
                id_usuario=asig.id_usuario,
                canal="email",
                asunto=asunto_mail,
                mensaje=cuerpo_mail,
                enviado=exito,
                enviado_en=datetime.datetime.now() if exito else None,
                error=None if exito else "Error en el servidor de correo"
            )
            db.add(notif_email)
            db.commit()


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """Procesa mensajes MQTT y guarda en PostgreSQL según el tópico."""
    db = SessionLocal()
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        print(f"[MQTT] Recibido en {msg.topic}: {payload}")

        if msg.topic == MQTT_TOPIC_RIEGO_DATOS:
            data = RiegoDatosModel(**payload)

            # Resolver la asignación primero antes de guardar para verificar si está activa
            from src.models.models import asignaciones_iot
            asig = db.query(asignaciones_iot).filter(
                asignaciones_iot.id == data.humedad_suelo.id_asignacion
            ).first()

            crud.crear_datos_riego(db, data)
            print("[OK] Datos de riego guardados en PostgreSQL")
 
            # EVALUAR ALERTAS DE SUELO Y AMBIENTE
            try:
                if data.humedad_suelo.id_asignacion and data.humedad_suelo.porcentaje is not None:
                    evaluar_y_disparar_alerta(db, data.humedad_suelo.id_asignacion, 'HUM_SUELO', float(data.humedad_suelo.porcentaje))
                if data.humedad_ambiente.id_asignacion and data.humedad_ambiente.porcentaje is not None:
                    evaluar_y_disparar_alerta(db, data.humedad_ambiente.id_asignacion, 'HUM_AMB', float(data.humedad_ambiente.porcentaje))
                if data.temperatura_ambiente.id_asignacion and data.temperatura_ambiente.temperatura is not None:
                    evaluar_y_disparar_alerta(db, data.temperatura_ambiente.id_asignacion, 'TEMP_AMB', float(data.temperatura_ambiente.temperatura))
                if data.temperatura_suelo.id_asignacion and data.temperatura_suelo.temperatura is not None:
                    evaluar_y_disparar_alerta(db, data.temperatura_suelo.id_asignacion, 'TEMP_SUELO', float(data.temperatura_suelo.temperatura))
            except Exception as eval_exc:
                print(f"[ERROR] Evaluando alertas de telemetría: {eval_exc}")

            if asig and not asig.activo:
                print(f"[PAUSED] Asignación '{asig.id}' inactiva. Saltando control e inferencia.")
                return

            # Enviar los valores al modelo ML para obtener decisión de riego
            try:
                dispositivo = asig.dispositivo if asig else None
                id_usuario = dispositivo.id_usuario if dispositivo else None
                if not id_usuario:
                    from src.models.models import usuarios
                    primer_usuario = db.query(usuarios).order_by(usuarios.id_usuario.asc()).first()
                    if primer_usuario:
                        id_usuario = primer_usuario.id_usuario

                # Verificar si el modo de control Predictivo (ML) está activo (cultivo_modelo.activo == True)
                id_cultivo = asig.id_cultivo if asig else None
                if id_usuario and id_cultivo:
                    from src.models.models import cultivo_modelo
                    usr_mod = db.query(cultivo_modelo).filter(
                        cultivo_modelo.id_usuario == id_usuario,
                        cultivo_modelo.id_cultivo == id_cultivo,
                        cultivo_modelo.activo == True
                    ).first()
                    if not usr_mod:
                        print(f"[CONTROL] El modo Predictivo (ML) no está activo para el cultivo {id_cultivo} del usuario {id_usuario}. Saltando inferencia y control automático de ML.")
                        return
                else:
                    print(f"[CONTROL] No se resolvió id_usuario o id_cultivo. Saltando control automático de ML.")
                    return

                # IMPLEMENTACIÓN DEL COOLDOWN DE INFILTRACIÓN AGRONÓMICA:
                # Si se completó un riego hace menos de 15 minutos, esperar antes de volver a regar.
                import datetime as dt
                from src.models.models import riego
                tiempo_cooldown = datetime.datetime.now() - dt.timedelta(minutes=15)
                riego_reciente = db.query(riego).filter(
                    riego.id_asignacion == asig.id,
                    riego.estado == True,  # Completado
                    riego.fecha >= tiempo_cooldown
                ).first()
                if riego_reciente:
                    print(f"[CONTROL] Cooldown de infiltración activo. Riego completado a las {riego_reciente.fecha}. Esperando para re-evaluar.")
                    return

                pred_input = PrediccionRiegoModel(
                    humedad_suelo=float(data.humedad_suelo.valor) if data.humedad_suelo.valor is not None else 0.0,
                    humedad_ambiente=float(data.humedad_ambiente.valor) if data.humedad_ambiente.valor is not None else 0.0,
                    temperatura_ambiente=float(data.temperatura_ambiente.temperatura) if data.temperatura_ambiente.temperatura is not None else 0.0,
                    temperatura_suelo=float(data.temperatura_suelo.temperatura) if data.temperatura_suelo.temperatura is not None else 0.0,
                )
                id_dispositivo = dispositivo.id_dispositivo if dispositivo else None
                resultado = obtener_prediccion_riego(
                    pred_input,
                    db,
                    id_usuario=id_usuario,
                    id_dispositivo=id_dispositivo,
                    id_cultivo=id_cultivo,
                    persistir=True
                )
                print(f"[ML] Resultado ML: {resultado}")

                # Publicar comando de control al ESP32 (ON/OFF)
                try:
                    comando = "ON" if int(resultado.get("riego", 0)) == 1 else "OFF"
                    client.publish(MQTT_TOPIC_CONTROL_CMD, comando, qos=1, retain=True)
                    print(f"[MQTT] Publicado comando '{comando}' en {MQTT_TOPIC_CONTROL_CMD}")
                except Exception as pub_exc:
                    print(f"[ERROR] Publicando comando MQTT: {pub_exc}")

            except Exception as ml_exc:
                print(f"[ERROR] Al invocar ML para predicción: {ml_exc}")

        elif msg.topic == MQTT_TOPIC_CONTROL_AGUA:
            data = TelemetriaTanqueModel(**payload)

            # Verificar si el dispositivo de la asignación está activo
            from src.models.models import asignaciones_iot
            asig = db.query(asignaciones_iot).filter(
                asignaciones_iot.id == data.id_asignacion
            ).first()

            registro_tanque = crud.crear_telemetria_tanque(
                db=db,
                id_asignacion=data.id_asignacion,
                distancia_cm=data.distancia_cm,
                estado_bomba=data.estado_bomba,
                motivo_cierre=data.motivo_cierre,
                fecha=data.fecha,
            )
            print("[OK] Telemetría de tanque guardada en PostgreSQL")

            # EVALUAR ALERTA DE TANQUE BAJO
            try:
                if registro_tanque and registro_tanque.porcentaje_nivel is not None:
                    evaluar_y_disparar_alerta(db, data.id_asignacion, 'NIVEL_AGUA', float(registro_tanque.porcentaje_nivel))
            except Exception as eval_exc:
                print(f"[ERROR] Evaluando alertas de tanque: {eval_exc}")

        elif msg.topic.endswith("/config/req"):
            # Determinar client_id
            parts = msg.topic.split("/")
            if len(parts) >= 3:
                client_id = parts[2]
            else:
                client_id = "ESP32_Yaku_002"

            id_asignacion = payload.get("id_asignacion")
            if not id_asignacion:
                print(f"[MQTT] Falta id_asignacion en peticion de config")
                return

            # Consultar base de datos
            from src.models.models import asignaciones_iot, fuentes_agua, dispositivos
            asig = db.query(asignaciones_iot).filter(asignaciones_iot.id == id_asignacion).first()
            if asig:
                # 1. Obtener fuente de agua
                fuente = None
                if asig.id_fuente_agua is not None:
                    fuente = db.query(fuentes_agua).filter(fuentes_agua.id == asig.id_fuente_agua).first()
                
                if fuente is None:
                    # Buscar en cualquier asignacion activa del mismo dispositivo
                    otro_asig = db.query(asignaciones_iot).filter(
                        asignaciones_iot.id_dispositivo == asig.id_dispositivo,
                        asignaciones_iot.id_fuente_agua != None,
                        asignaciones_iot.activo == True
                    ).first()
                    if otro_asig:
                        fuente = db.query(fuentes_agua).filter(fuentes_agua.id == otro_asig.id_fuente_agua).first()

                altura_total_cm = 50.0
                distancia_sin_agua_cm = 45.0
                if fuente:
                    altura_total_cm = float(fuente.altura_tanque_cm or 50.0)
                    distancia_sin_agua_cm = float(fuente.altura_seguridad_cm or (altura_total_cm - 5.0))

                # 2. Obtener funcionamiento activo de la asignación
                funcionamiento_activo = asig.activo

                # 3. Determinar modo de riego actual
                from src.models.models import cultivo_modelo, programacion_riego
                usr_mod = db.query(cultivo_modelo).filter(
                    cultivo_modelo.id_usuario == asig.id_usuario,
                    cultivo_modelo.id_cultivo == asig.id_cultivo,
                    cultivo_modelo.activo == True
                ).first()

                prog_act = db.query(programacion_riego).filter(
                    programacion_riego.id_asignacion == asig.id,
                    programacion_riego.activo == True
                ).first() is not None

                modo_actual = "manual"
                if usr_mod:
                    modo_actual = "predictivo"
                elif prog_act:
                    modo_actual = "programado"

                # 4. Responder via MQTT
                response_payload = {
                    "funcionamiento_activo": funcionamiento_activo,
                    "altura_total_cm": altura_total_cm,
                    "distancia_sin_agua_cm": distancia_sin_agua_cm,
                    "modo": modo_actual,
                    "topic_sub": asig.dispositivo.topic_sub or "yaku/riego/comando"
                }
                response_topic = f"yaku/dispositivo/{client_id}/config"
                client.publish(response_topic, json.dumps(response_payload), qos=1, retain=True)
                print(f"[MQTT] Respondida config para {client_id} en {response_topic}: {response_payload}")
            else:
                print(f"[MQTT] Asignacion {id_asignacion} no encontrada para config req")
        else:
            print(f"[WARNING] Topico no manejado: {msg.topic}")

    except json.JSONDecodeError:
        print(f"[ERROR] Payload MQTT inválido en {msg.topic}")
    except Exception as e:
        print(f"[ERROR] Procesando mensaje MQTT: {e}")
    finally:
        db.close()


def on_connect(client: mqtt.Client, userdata: Any, flags: dict[str, Any], rc: int, _properties: Any = None) -> None:
    """Callback al conectar al broker MQTT."""
    if rc == 0:
        print(f"[OK] Conectado a MQTT broker {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC_RIEGO_DATOS, qos=1)
        client.subscribe(MQTT_TOPIC_CONTROL_AGUA, qos=1)
        client.subscribe("yaku/dispositivo/+/config/req", qos=1)
        print(f"   Suscrito a: {MQTT_TOPIC_RIEGO_DATOS}, {MQTT_TOPIC_CONTROL_AGUA}, yaku/dispositivo/+/config/req")
    else:
        print(f"[ERROR] Conexión MQTT falló con código: {rc}")


def start_mqtt() -> mqtt.Client | None:
    """Inicia el cliente MQTT con TLS y credenciales desde .env."""
    global _mqtt_client

    if _mqtt_client is not None:
        return _mqtt_client

    client = mqtt.Client()

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if MQTT_TLS_ENABLED:
        tls_kwargs = {}
        if MQTT_TLS_CA_CERT and os.path.isfile(MQTT_TLS_CA_CERT):
            tls_kwargs["ca_certs"] = MQTT_TLS_CA_CERT

        try:
            client.tls_set(**tls_kwargs)
            print("[OK] TLS habilitado para MQTT")
        except Exception as e:
            print(f"Advertencia: TLS setup falló ({e}); continuando sin validar certificado")

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        _mqtt_client = client
        print(f"[MQTT] Cliente iniciado (async)")
        return client
    except Exception as e:
        print(f"[ERROR] Iniciando cliente MQTT: {e}")
        return None


def stop_mqtt() -> None:
    """Detiene el cliente MQTT."""
    global _mqtt_client

    if _mqtt_client is None:
        return

    try:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
        print("[OK] Cliente MQTT detenido")
    except Exception as e:
        print(f"Advertencia al detener MQTT: {e}")