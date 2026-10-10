import io
import os
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
    <name>Sample Points</name>
    <Placemark>
      <name>Location Alpha</name>
      <description>First marker</description>
      <Point>
        <coordinates>-122.084,37.422,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Location Beta</name>
      <description>Second marker</description>
      <Point>
        <coordinates>-122.085,37.423,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""


def create_shapefile_zip(
    include_prj: bool = True,
    empty_features: bool = False,
    multiple_shp: bool = False,
    add_unsafe_member: bool = False,
) -> bytes:
    """Helper to create an in-memory zip containing Shapefile components."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        shp_stem = "test_features"

        if empty_features:
            gdf = gpd.GeoDataFrame({"id": [], "geometry": []}, crs="EPSG:4326" if include_prj else None)
        else:
            poly1 = Polygon([[-122.1, 37.4], [-122.0, 37.4], [-122.0, 37.5], [-122.1, 37.5], [-122.1, 37.4]])
            poly2 = Polygon([[-122.3, 37.2], [-122.2, 37.2], [-122.2, 37.3], [-122.3, 37.3], [-122.3, 37.2]])
            gdf = gpd.GeoDataFrame(
                [
                    {"name": "Zone A", "score": float("nan"), "created": datetime(2026, 1, 15, 10, 0), "geometry": poly1},
                    {"name": "Zone B", "score": 98.5, "created": datetime(2026, 2, 20, 12, 30), "geometry": poly2},
                ],
                crs="EPSG:4326" if include_prj else None,
            )

        shp_file = tmp_path / f"{shp_stem}.shp"
        gdf.to_file(shp_file, engine="pyogrio")

        # If include_prj is False, remove .prj
        if not include_prj:
            prj_file = tmp_path / f"{shp_stem}.prj"
            if prj_file.exists():
                prj_file.unlink()

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in tmp_path.iterdir():
                zf.write(item, arcname=item.name)

            if multiple_shp:
                # Add a second .shp file to trigger ambiguity
                zf.writestr("secondary_shape.shp", b"dummy")

            if add_unsafe_member:
                # Add zip slip path traversal member
                zf.writestr("../../unsafe_file.txt", b"malicious content")

        return zip_buf.getvalue()


def test_valid_kml_upload():
    """Verify parsing of a valid KML file."""
    files = {"file": ("sample.kml", SAMPLE_KML.encode("utf-8"), "application/vnd.google-earth.kml+xml")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == "sample.kml"
    assert data["file_type"] == "kml"
    assert "EPSG:4326" in data["crs"]
    assert data["feature_count"] == 2
    assert "Point" in data["geometry_types"]
    assert len(data["features"]) == 2
    assert data["features"][0]["geometry"]["type"] == "Point"
    assert data["features"][0]["properties"]["Name"] == "Location Alpha"


def test_valid_zipped_shapefile_upload():
    """Verify parsing of a valid zipped Shapefile with .shp, .shx, .dbf, and .prj."""
    zip_bytes = create_shapefile_zip(include_prj=True)
    files = {"file": ("complete_shapefile.zip", zip_bytes, "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["filename"] == "complete_shapefile.zip"
    assert data["file_type"] == "shapefile"
    assert "EPSG:4326" in data["crs"]
    assert data["feature_count"] == 2
    assert data["geometry_types"] == ["Polygon"]
    assert data["bounds"] is not None
    assert len(data["bounds"]) == 4

    # Check non-JSON-safe properties conversion:
    # NaN score should be converted to None / null
    # datetime created should be converted to ISO string
    feat0 = data["features"][0]
    feat1 = data["features"][1]

    assert feat0["properties"]["score"] is None
    assert "2026" in feat0["properties"]["created"] and "15" in feat0["properties"]["created"]

    assert feat1["properties"]["score"] == 98.5
    assert "2026" in feat1["properties"]["created"] and "20" in feat1["properties"]["created"]


def test_missing_crs_reported_as_error():
    """Verify that a Shapefile without .prj is rejected with 422 and NOT assumed to be EPSG:4326."""
    zip_bytes = create_shapefile_zip(include_prj=False)
    files = {"file": ("no_prj.zip", zip_bytes, "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "MISSING_CRS"
    assert "Coordinate Reference System" in data["detail"]


def test_empty_file_rejected():
    """Verify that an empty (0 byte) file is rejected with 400."""
    files = {"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "EMPTY_FILE"


def test_unsupported_file_extension():
    """Verify that unsupported extensions (.geojson, .txt, .csv) are rejected with 400."""
    files = {"file": ("data.geojson", b'{"type": "FeatureCollection", "features": []}', "application/json")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "UNSUPPORTED_FILE_TYPE"
    assert "Unsupported file extension" in data["detail"]


def test_invalid_zip_corrupt():
    """Verify that non-ZIP binary disguised as .zip is rejected with 400."""
    files = {"file": ("corrupt.zip", b"not a real zip content", "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "INVALID_ARCHIVE"


def test_zip_without_shp():
    """Verify that a ZIP archive without a .shp component is rejected with 400."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("notes.txt", b"Hello world")
    files = {"file": ("missing_shp.zip", zip_buf.getvalue(), "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "INVALID_ARCHIVE"
    assert "does not contain a .shp" in data["detail"]


def test_ambiguous_multiple_shp_in_zip():
    """Verify that a ZIP archive with multiple .shp files is rejected as ambiguous."""
    zip_bytes = create_shapefile_zip(include_prj=True, multiple_shp=True)
    files = {"file": ("multiple_shp.zip", zip_bytes, "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "AMBIGUOUS_ARCHIVE"
    assert "multiple Shapefiles" in data["detail"]


def test_unsafe_path_traversal_zip_slip():
    """Verify that a ZIP archive attempting path traversal is safely rejected with 400."""
    zip_bytes = create_shapefile_zip(include_prj=True, add_unsafe_member=True)
    files = {"file": ("zip_slip.zip", zip_bytes, "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "UNSAFE_ARCHIVE_PATH"
    assert "unsafe path traversal" in data["detail"]


def test_empty_dataset_no_features():
    """Verify that a dataset containing 0 features returns 422."""
    zip_bytes = create_shapefile_zip(include_prj=True, empty_features=True)
    files = {"file": ("empty_dataset.zip", zip_bytes, "application/zip")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code == 422
    data = response.json()
    assert data["error_code"] == "EMPTY_DATASET"
    assert "contains no features" in data["detail"]


def test_invalid_kml_content():
    """Verify that non-XML content disguised as .kml returns 422 or 400 error."""
    files = {"file": ("fake.kml", b"This is plain text with no XML", "text/plain")}
    response = client.post("/geospatial/parse", files=files)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "detail" in data
    assert "error_code" in data


def test_temporary_directories_cleaned_up():
    """Verify that processing does not leave files behind in the system temp directory."""
    temp_dir_before = set(os.listdir(tempfile.gettempdir()))

    # Process valid KML
    files = {"file": ("sample.kml", SAMPLE_KML.encode("utf-8"), "application/vnd.google-earth.kml+xml")}
    res = client.post("/geospatial/parse", files=files)
    assert res.status_code == 200

    # Process invalid ZIP
    bad_files = {"file": ("corrupt.zip", b"fake zip bytes", "application/zip")}
    res_bad = client.post("/geospatial/parse", files=bad_files)
    assert res_bad.status_code == 400

    temp_dir_after = set(os.listdir(tempfile.gettempdir()))
    # Ensure no lingering uncleaned directory created by our process
    new_dirs = [d for d in (temp_dir_after - temp_dir_before) if "tmp" in d.lower()]
    assert len(new_dirs) == 0
