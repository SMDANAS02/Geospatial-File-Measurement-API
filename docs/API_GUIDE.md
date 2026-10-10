# GeoMeasure API Developer Guide

This guide provides practical examples for integrating with the GeoMeasure API using cURL, Python, and JavaScript.

## Base URLs

- **Local Development**: `http://127.0.0.1:8000`
- **Interactive OpenAPI Documentation**: `http://127.0.0.1:8000/docs`

---

## 1. Health Check

### cURL
```bash
curl -s http://127.0.0.1:8000/health
```

### Python
```python
import requests

response = requests.get("http://127.0.0.1:8000/health")
print(response.json())
```

---

## 2. Upload Geospatial File (KML / Shapefile ZIP)

### cURL (KML Upload)
```bash
curl -X POST "http://127.0.0.1:8000/api/files/" \
  -H "Accept: application/json" \
  -F "file=@samples/new_york_central_park.kml"
```

### cURL (Shapefile ZIP Upload)
```bash
curl -X POST "http://127.0.0.1:8000/api/files/" \
  -H "Accept: application/json" \
  -F "file=@samples/paris_gardens_shapefile.zip"
```

### Python
```python
import requests

url = "http://127.0.0.1:8000/api/files/"
with open("samples/new_york_central_park.kml", "rb") as f:
    files = {"file": ("new_york_central_park.kml", f, "application/vnd.google-earth.kml+xml")}
    response = requests.post(url, files=files)

data = response.json()
print("Uploaded File ID:", data["id"])
print("Feature Count:", data["feature_count"])
print("Measurement CRS:", data["measurement_crs"])
```

---

## 3. Retrieve Calculated Measurements

### cURL
```bash
curl -s "http://127.0.0.1:8000/api/files/{FILE_ID}/measurements/?page=1&page_size=50"
```

### Python
```python
import requests

file_id = "YOUR_FILE_ID"
url = f"http://127.0.0.1:8000/api/files/{file_id}/measurements/?page=1&page_size=50"
res = requests.get(url).json()

for item in res["items"]:
    geom_type = item["geometry_type"]
    meas = item["measurement"]
    if meas["area_m2"] is not None:
        print(f"[{geom_type}] Area: {meas['area_m2']:,.2f} m² ({meas['area_km2']:.4f} km²)")
    elif meas["length_m"] is not None:
        print(f"[{geom_type}] Length: {meas['length_m']:,.2f} m ({meas['length_km']:.4f} km)")
    else:
        print(f"[{geom_type}] Status: {meas['status']}")
```

---

## 4. Error Responses Reference

| Status | Error Code | Description |
|:---|:---|:---|
| `400` | `UNSUPPORTED_FILE_TYPE` | File extension is not `.kml` or `.zip` |
| `400` | `INVALID_ARCHIVE` | ZIP file is corrupt or empty |
| `400` | `MISSING_SHAPEFILE` | ZIP archive does not contain `.shp` |
| `400` | `AMBIGUOUS_SHAPEFILES` | Multiple `.shp` files found in archive |
| `400` | `UNSAFE_ZIP_PATH` | Path traversal detected (Zip Slip) |
| `413` | `FILE_TOO_LARGE` | Upload exceeds 50 MB limit |
| `413` | `ZIP_BOMB_DETECTED` | Uncompressed archive exceeds 150 MB |
| `422` | `MISSING_CRS` | Dataset lacks an explicit CRS projection |
| `404` | `NOT_FOUND` | File ID does not exist |
