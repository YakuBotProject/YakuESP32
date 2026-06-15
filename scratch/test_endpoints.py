import urllib.request
import json

try:
    # Get OpenAPI spec to see if new endpoints are present
    with urllib.request.urlopen("http://127.0.0.1:8000/openapi.json") as response:
        spec = json.loads(response.read().decode())
        paths = spec.get("paths", {})
        
        expected_paths = [
            "/ubicacion/regiones",
            "/ubicacion/provincias",
            "/ubicacion/distritos",
            "/ubicacion/cultivos",
            "/plantas",
            "/dispositivos",
            "/dispositivos/tipos",
            "/dispositivos/componentes",
            "/dispositivos/componentes/tipos"
        ]
        
        print("[INFO] Checking registered endpoints in FastAPI OpenAPI spec:")
        for path in expected_paths:
            is_registered = path in paths
            status_str = "REGISTERED" if is_registered else "NOT FOUND"
            print(f"  {path}: {status_str}")
            if is_registered:
                methods = list(paths[path].keys())
                print(f"    Methods: {methods}")
                
except Exception as e:
    print(f"[ERROR] Error connecting to backend: {e}")
