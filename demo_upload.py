"""
Phase 8 demo script: creates real KML and ZIP files,
uploads them to the running API, and prints a structured summary.
Run with: .venv/Scripts/python demo_upload.py
"""
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

# Force UTF-8 output on Windows terminals
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8")

import geopandas as gpd
import requests
from shapely.geometry import LineString, Point, Polygon

BASE_URL = "http://127.0.0.1:8000"
SEP = "=" * 60


def section(title: str):
    print(f"\n{SEP}\n  {title}\n{SEP}")


# -- 1. Health check ----------------------------------------------------------
section("GET /health")
r = requests.get(f"{BASE_URL}/health")
print(json.dumps(r.json(), indent=2))
assert r.status_code == 200

# -- 2. Build demo KML (Polygon + LineString + Point) -------------------------
DEMO_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>GeoMeasure Demo - San Francisco Bay Area</name>
    <Placemark>
      <name>Golden Gate Park</name>
      <description>Approximate park boundary polygon</description>
      <Polygon>
        <outerBoundaryIs><LinearRing>
          <coordinates>
            -122.511,37.769,0 -122.458,37.769,0 -122.458,37.773,0
            -122.511,37.773,0 -122.511,37.769,0
          </coordinates>
        </LinearRing></outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Bay Trail Segment</name>
      <description>Example trail line</description>
      <LineString>
        <coordinates>
          -122.395,37.810,0 -122.380,37.820,0 -122.365,37.825,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Ferry Terminal</name>
      <description>Reference point marker</description>
      <Point>
        <coordinates>-122.394,37.795,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

kml_bytes = DEMO_KML.encode("utf-8")
Path("demo_sample.kml").write_bytes(kml_bytes)
print("\n[OK] Created demo_sample.kml (3 features: Polygon, LineString, Point)")

# -- 3. Upload KML ------------------------------------------------------------
section("POST /api/files/ -- demo_sample.kml")
r_kml = requests.post(
    f"{BASE_URL}/api/files/",
    files={"file": ("demo_sample.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
)
print(f"Status: {r_kml.status_code}")
kml_data = r_kml.json()
print(json.dumps(kml_data, indent=2))
assert r_kml.status_code == 201, f"Expected 201, got {r_kml.status_code}: {r_kml.text}"
kml_id = kml_data["id"]

# -- 4. Get KML file info -----------------------------------------------------
section(f"GET /api/files/{kml_id}/")
r_info = requests.get(f"{BASE_URL}/api/files/{kml_id}/")
print(json.dumps(r_info.json(), indent=2))
assert r_info.status_code == 200

# -- 5. Get KML measurements --------------------------------------------------
section(f"GET /api/files/{kml_id}/measurements/")
r_meas = requests.get(f"{BASE_URL}/api/files/{kml_id}/measurements/")
meas_data = r_meas.json()
print(json.dumps(meas_data, indent=2))
assert r_meas.status_code == 200

# -- 6. Build demo Shapefile ZIP (3 polygons across London region) ------------
parcels = [
    {
        "name": "Parcel A - Office District",
        "zone": "commercial",
        "area_ha": 12.4,
        "geometry": Polygon([
            [-0.12, 51.50], [-0.10, 51.50], [-0.10, 51.52],
            [-0.12, 51.52], [-0.12, 51.50]
        ]),
    },
    {
        "name": "Parcel B - Residential Block",
        "zone": "residential",
        "area_ha": 5.8,
        "geometry": Polygon([
            [-0.08, 51.51], [-0.06, 51.51], [-0.06, 51.53],
            [-0.08, 51.53], [-0.08, 51.51]
        ]),
    },
    {
        "name": "Parcel C - Mixed Use Quarter",
        "zone": "mixed",
        "area_ha": 8.1,
        "geometry": Polygon([
            [-0.14, 51.53], [-0.12, 51.53], [-0.12, 51.55],
            [-0.14, 51.55], [-0.14, 51.53]
        ]),
    },
]
gdf = gpd.GeoDataFrame(parcels, crs="EPSG:4326")

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    shp_path = tmp_path / "london_parcels.shp"
    gdf.to_file(shp_path, engine="pyogrio")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in tmp_path.iterdir():
            zf.write(f, arcname=f.name)
    zip_bytes = buf.getvalue()

Path("demo_parcels.zip").write_bytes(zip_bytes)
print("\n[OK] Created demo_parcels.zip (3 London polygon parcels)")

# -- 7. Upload Shapefile ZIP --------------------------------------------------
section("POST /api/files/ -- demo_parcels.zip")
r_zip = requests.post(
    f"{BASE_URL}/api/files/",
    files={"file": ("demo_parcels.zip", zip_bytes, "application/zip")},
)
print(f"Status: {r_zip.status_code}")
zip_data = r_zip.json()
print(json.dumps(zip_data, indent=2))
assert r_zip.status_code == 201, f"Expected 201, got {r_zip.status_code}: {r_zip.text}"
zip_id = zip_data["id"]

# -- 8. Get shapefile measurements --------------------------------------------
section(f"GET /api/files/{zip_id}/measurements/")
r_zmeas = requests.get(f"{BASE_URL}/api/files/{zip_id}/measurements/")
zmeas_data = r_zmeas.json()
print(json.dumps(zmeas_data, indent=2))
assert r_zmeas.status_code == 200

# -- 9. Invalid file -- confirm safe error ------------------------------------
section("POST /api/files/ -- report.exe  (expect 400 UNSUPPORTED_FILE_TYPE)")
r_bad = requests.post(
    f"{BASE_URL}/api/files/",
    files={"file": ("report.exe", b"MZ\x90\x00binary content", "application/octet-stream")},
)
bad_data = r_bad.json()
print(f"Status: {r_bad.status_code}")
print(json.dumps(bad_data, indent=2))
assert r_bad.status_code == 400
assert bad_data["error_code"] == "UNSUPPORTED_FILE_TYPE"
assert "Traceback" not in r_bad.text
assert "C:\\" not in r_bad.text and "E:\\" not in r_bad.text
print("\n[OK] Error response is safe - no traceback, no server paths leaked")

# -- 10. Unknown ID -- 404 ----------------------------------------------------
section("GET /api/files/nonexistent-id/ (expect 404)")
r_404 = requests.get(f"{BASE_URL}/api/files/nonexistent-id/")
print(f"Status: {r_404.status_code}")
print(json.dumps(r_404.json(), indent=2))
assert r_404.status_code == 404

# -- Summary ------------------------------------------------------------------
section("DEMO COMPLETE")
print(f"  KML file ID   : {kml_id}")
print(f"  ZIP file ID   : {zip_id}")

print(f"\n  KML measurements (San Francisco Bay Area):")
for item in meas_data["items"]:
    m = item["measurement"]
    gt = item["geometry_type"]
    name = item["properties"].get("Name", f"feature-{item['feature_index']}")
    if m["status"] in ("COMPLETED",):
        if m.get("area_m2") is not None:
            print(f"    [{gt:15s}] {name:30s}  area_m2    = {m['area_m2']:>16,.2f}")
        elif m.get("length_m") is not None:
            print(f"    [{gt:15s}] {name:30s}  length_m   = {m['length_m']:>16,.2f}")
    else:
        print(f"    [{gt:15s}] {name:30s}  status     = {m['status']}")

print(f"\n  ZIP measurements (London parcels):")
for item in zmeas_data["items"]:
    m = item["measurement"]
    name = item["properties"].get("name", f"feature-{item['feature_index']}")
    print(f"    {name}")
    print(f"      area_m2 = {m['area_m2']:>14,.2f}   area_km2 = {m['area_km2']:.6f}")

print("\n[OK] All demo assertions passed.\n")
