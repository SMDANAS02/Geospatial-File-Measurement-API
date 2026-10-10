import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Point, Polygon

from app.main import app

client = TestClient(app)

SAMPLE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Survey Parcels</name>
    <Placemark>
      <name>Parcel Alpha</name>
      <description>Commercial site</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -122.1,37.4,0 -122.0,37.4,0 -122.0,37.5,0 -122.1,37.5,0 -122.1,37.4,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Survey Benchmark</name>
      <Point>
        <coordinates>-122.05,37.45,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""


def build_shapefile_zip(gdf: gpd.GeoDataFrame) -> bytes:
    """Helper to convert a GeoDataFrame into a zipped Shapefile buffer."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        shp_file = tmp_path / "dataset.shp"
        gdf.to_file(shp_file, engine="pyogrio")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmp_path.iterdir():
                zf.write(f, arcname=f.name)
        return buf.getvalue()


def test_upload_and_persistence_lifecycle():
    """Test POST /api/files/, GET /api/files/{id}/, and GET /api/files/{id}/measurements/."""
    # 1. Upload file
    files = {"file": ("survey.kml", SAMPLE_KML.encode("utf-8"), "application/vnd.google-earth.kml+xml")}
    res_upload = client.post("/api/files/", files=files)
    assert res_upload.status_code == 201, res_upload.text
    data_upload = res_upload.json()

    assert "id" in data_upload
    assert data_upload["filename"] == "survey.kml"
    assert data_upload["feature_count"] == 2
    assert "EPSG:4326" in data_upload["crs"]
    assert "measurement_crs" in data_upload and data_upload["measurement_crs"] is not None
    assert data_upload["status"] == "COMPLETED"

    # CRITICAL: Verify NO server paths exist in response
    resp_text = res_upload.text
    assert "C:\\" not in resp_text and "E:\\" not in resp_text and "/tmp" not in resp_text and "\\tmp" not in resp_text

    file_id = data_upload["id"]

    # 2. Get File Info (GET /api/files/{id}/)
    res_info = client.get(f"/api/files/{file_id}/")
    assert res_info.status_code == 200, res_info.text
    data_info = res_info.json()

    assert data_info["id"] == file_id
    assert data_info["filename"] == "survey.kml"
    assert data_info["feature_count"] == 2
    assert data_info["status"] == "COMPLETED"
    assert "created_at" in data_info
    assert "summary_measurements" in data_info
    assert data_info["summary_measurements"]["measured_polygons"] == 1

    # Verify no server path
    assert "C:\\" not in res_info.text and "E:\\" not in res_info.text

    # 3. Get Measurements (GET /api/files/{id}/measurements/)
    res_meas = client.get(f"/api/files/{file_id}/measurements/")
    assert res_meas.status_code == 200, res_meas.text
    data_meas = res_meas.json()

    assert data_meas["file_id"] == file_id
    assert data_meas["total"] == 2
    assert data_meas["page"] == 1
    assert data_meas["page_size"] == 50
    assert len(data_meas["items"]) == 2

    # Verify polygon feature
    poly_item = next(item for item in data_meas["items"] if item["geometry_type"] == "Polygon")
    assert poly_item["measurement"]["status"] == "COMPLETED"
    assert poly_item["measurement"]["area_m2"] is not None and poly_item["measurement"]["area_m2"] > 0
    assert poly_item["measurement"]["area_km2"] is not None and poly_item["measurement"]["area_km2"] > 0
    assert poly_item["measurement"]["unit"] == "m²"
    assert poly_item["properties"]["Name"] == "Parcel Alpha"

    # Verify point feature
    point_item = next(item for item in data_meas["items"] if item["geometry_type"] == "Point")
    assert point_item["measurement"]["status"] == "NOT_APPLICABLE"
    assert point_item["measurement"]["area_m2"] is None
    assert point_item["measurement"]["unit"] is None
    assert "not required" in point_item["measurement"]["notes"].lower()


def test_pagination_on_measurements():
    """Verify pagination defaults and parameters on /api/files/{id}/measurements/."""
    # Create Shapefile with 5 polygons
    polys = [
        {"name": f"Parcel_{i}", "geometry": Polygon([[-122.1 + i*0.01, 37.4], [-122.0 + i*0.01, 37.4], [-122.0 + i*0.01, 37.5], [-122.1 + i*0.01, 37.5], [-122.1 + i*0.01, 37.4]])}
        for i in range(5)
    ]
    gdf = gpd.GeoDataFrame(polys, crs="EPSG:4326")
    zip_bytes = build_shapefile_zip(gdf)

    upload_res = client.post("/api/files/", files={"file": ("parcels.zip", zip_bytes, "application/zip")})
    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]

    # Request page 1 with page_size=2
    res_p1 = client.get(f"/api/files/{file_id}/measurements/?page=1&page_size=2")
    assert res_p1.status_code == 200
    d_p1 = res_p1.json()
    assert d_p1["total"] == 5
    assert d_p1["page"] == 1
    assert d_p1["page_size"] == 2
    assert d_p1["pages"] == 3
    assert len(d_p1["items"]) == 2
    assert d_p1["items"][0]["feature_index"] == 0
    assert d_p1["items"][1]["feature_index"] == 1

    # Request page 3 with page_size=2 (should have 1 item)
    res_p3 = client.get(f"/api/files/{file_id}/measurements/?page=3&page_size=2")
    assert res_p3.status_code == 200
    d_p3 = res_p3.json()
    assert len(d_p3["items"]) == 1
    assert d_p3["items"][0]["feature_index"] == 4


def test_file_not_found_returns_404():
    """Verify unknown file IDs return 404 for metadata and measurements."""
    res_meta = client.get("/api/files/non-existent-id-999/")
    assert res_meta.status_code == 404
    assert "not found" in res_meta.json()["detail"].lower()

    res_meas = client.get("/api/files/non-existent-id-999/measurements/")
    assert res_meas.status_code == 404
    assert "not found" in res_meas.json()["detail"].lower()


def test_invalid_upload_returns_clear_client_error():
    """Verify invalid uploads receive clear 4xx errors without stack traces."""
    # Unsupported extension
    res_ext = client.post("/api/files/", files={"file": ("invalid.txt", b"plain text", "text/plain")})
    assert res_ext.status_code == 400
    assert "Unsupported file extension" in res_ext.json()["detail"]

    # Empty file
    res_empty = client.post("/api/files/", files={"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")})
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()

    # Corrupted ZIP
    res_corrupt = client.post("/api/files/", files={"file": ("corrupt.zip", b"not a zip", "application/zip")})
    assert res_corrupt.status_code == 400
    assert "not a valid zip" in res_corrupt.json()["detail"].lower()
