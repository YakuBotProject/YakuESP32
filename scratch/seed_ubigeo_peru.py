import sys
import os
import json
import urllib.request
from sqlalchemy import text
from sqlalchemy.orm import Session

# Set up project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.database import SessionLocal
from src.models.models import regiones, provincias, distritos

DEPS_URL = "https://raw.githubusercontent.com/ernestorivero/Ubigeo-Peru/master/json/ubigeo_peru_2016_departamentos.json"
PROVS_URL = "https://raw.githubusercontent.com/ernestorivero/Ubigeo-Peru/master/json/ubigeo_peru_2016_provincias.json"
DISTS_URL = "https://raw.githubusercontent.com/ernestorivero/Ubigeo-Peru/master/json/ubigeo_peru_2016_distritos.json"

def fetch_json(url: str):
    print(f"Downloading from {url}...")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as response:
        if response.status == 200:
            return json.loads(response.read().decode("utf-8"))
        else:
            raise Exception(f"Failed to fetch data: HTTP {response.status}")

def seed_geography():
    db: Session = SessionLocal()
    try:
        # 1. Download datasets
        deps_data = fetch_json(DEPS_URL)
        provs_data = fetch_json(PROVS_URL)
        dists_data = fetch_json(DISTS_URL)

        print(f"Loaded {len(deps_data)} departments, {len(provs_data)} provinces, and {len(dists_data)} districts from source.")

        # 2. Clear existing entries to prevent duplicates or key conflicts
        print("Clearing existing geography references in crops and warehouses...")
        db.execute(text("UPDATE cultivos SET id_distrito = NULL"))
        db.execute(text("UPDATE almacenes SET id_distrito = NULL"))
        db.commit()

        print("Clearing existing geography data...")
        db.query(distritos).delete()
        db.query(provincias).delete()
        db.query(regiones).delete()
        db.commit()

        # 3. Seed Regions (Departments)
        print("Seeding regions...")
        for item in deps_data:
            id_val = int(item["id"])
            db.add(regiones(id=id_val, nombre=item["name"]))
        db.commit()

        # 4. Seed Provinces
        print("Seeding provinces...")
        for item in provs_data:
            id_val = int(item["id"])
            id_reg = int(item["department_id"])
            db.add(provincias(id=id_val, id_region=id_reg, nombre=item["name"]))
        db.commit()

        # 5. Seed Districts
        print("Seeding districts...")
        for item in dists_data:
            id_val = int(item["id"])
            id_prov = int(item["province_id"])
            db.add(distritos(id=id_val, id_provincia=id_prov, nombre=item["name"]))
        db.commit()

        # 6. Reconnect crops and warehouses to the correct new UBIGEO codes
        print("Reconnecting crops and warehouses to real UBIGEO codes...")
        db.execute(text("UPDATE almacenes SET id_distrito = 150140 WHERE id = 1"))
        db.execute(text("UPDATE almacenes SET id_distrito = 40520 WHERE id = 2"))
        db.execute(text("UPDATE cultivos SET id_distrito = 40520 WHERE id IN (1, 2, 3, 4)"))
        db.execute(text("UPDATE cultivos SET id_distrito = 130106 WHERE id = 5"))
        db.commit()

        print("[SUCCESS] Seeding of UBIGEO Peru complete!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_geography()
