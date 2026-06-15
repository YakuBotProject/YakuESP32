from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Acepta y almacena una conexión de WebSocket."""
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Nueva conexión de alerta aceptada. Total activas: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Elimina una conexión de WebSocket cerrada."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Conexión de alerta cerrada. Total activas: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Envía un JSON a todos los clientes WebSockets conectados."""
        print(f"[WS] Transmitiendo evento de alerta a {len(self.active_connections)} clientes activos...")
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                print(f"[WS] Error al enviar mensaje a cliente WebSocket: {e}")

manager = ConnectionManager()
