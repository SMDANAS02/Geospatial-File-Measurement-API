import io
import os
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from app.config import settings
from app.main import app

client = TestClient(app)


def test_mixed_geometry_types_kml_succeeds():
    """Verify KML with mixed geometries (Polygon, LineString, Point) parses cleanly."""
    mixed_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>PolygonFeature</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>-122.1,37.4,0 -122.0,37.4,0 -122.0,37.5,0 -122.1,37.5,0 -122.1,37.4,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>LineFeature</name>
      <LineString>
        <coordinates>-122.1,37.4,0 -122.0,37.45,0</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>PointFeature</name>
      <Point>
        <coordinates>-122.05,37.45,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""

    res = client.post(
        "/api/files/",
        files={"file": ("mixed.kml", mixed_kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert res.status_code == 201, res.text
    file_id = res.json()["id"]

    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    items = meas_res.json()["items"]
    assert len(items) == 3

    types = {item["geometry_type"]: item["measurement"] for item in items}
    assert types["Polygon"]["status"] == "COMPLETED"
    assert types["Polygon"]["area_m2"] > 0
    assert types["LineString"]["status"] == "COMPLETED"
    assert types["LineString"]["length_m"] > 0
    assert types["Point"]["status"] == "NOT_APPLICABLE"


def test_malformed_kml_syntax_fails_safely():
    """Verify malformed XML in KML fails safely with 422/400 and no traceback."""
    broken_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Unclosed Tag
    </Placemark>
  </Document>
</kml>"""

    res = client.post(
        "/api/files/",
        files={"file": ("broken.kml", broken_kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert res.status_code in [400, 422]
    data = res.json()
    assert "detail" in data
    assert "error_code" in data
    # Ensure no internal traceback or paths leaked
    assert "Traceback" not in res.text
    assert "E:\\" not in res.text and "C:\\" not in res.text


def test_xxe_injection_attempt_rejected():
    """Verify KML with XML External Entity (XXE) injection is safely rejected."""
    xxe_kml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE kml [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>&xxe;</name>
      <Point><coordinates>0,0,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>"""

    res = client.post(
        "/api/files/",
        files={"file": ("xxe.kml", xxe_kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert res.status_code in [400, 422]
    assert "forbidden" in res.json()["detail"].lower() or "entity" in res.json()["detail"].lower()


def test_oversized_file_rejected_without_oom():
    """Verify files larger than MAX_UPLOAD_SIZE_BYTES are rejected with 413."""
    # Create content that exceeds max bytes
    original_limit = settings.MAX_UPLOAD_SIZE_BYTES
    try:
        # Temporarily set limit to 100KB for test speed
        settings.MAX_UPLOAD_SIZE_BYTES = 50 * 1024  # 50 KB
        large_content = b"A" * (60 * 1024)  # 60 KB

        res = client.post(
            "/api/files/",
            files={"file": ("oversized.kml", large_content, "application/vnd.google-earth.kml+xml")},
        )
        assert res.status_code == 413
        assert res.json()["error_code"] == "FILE_SIZE_EXCEEDED"
        assert "exceeds" in res.json()["detail"].lower()
    finally:
        settings.MAX_UPLOAD_SIZE_BYTES = original_limit


def test_zip_decompression_bomb_rejected():
    """Verify zip archives exceeding uncompressed limit are rejected with 413."""
    original_uncompressed_limit = settings.MAX_UNCOMPRESSED_SIZE_BYTES
    try:
        settings.MAX_UNCOMPRESSED_SIZE_BYTES = 100 * 1024  # 100 KB limit for test
        # Create a zip with high compression of zeros (small zip, large decompressed)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("test.shp", b"\x00" * (200 * 1024))  # 200 KB uncompressed

        res = client.post(
            "/api/files/",
            files={"file": ("bomb.zip", buf.getvalue(), "application/zip")},
        )
        assert res.status_code in [400, 413]
        assert "exceeds" in res.json()["detail"].lower()
    finally:
        settings.MAX_UNCOMPRESSED_SIZE_BYTES = original_uncompressed_limit


def test_zip_path_traversal_variations_rejected():
    """Verify various Zip Slip attacks (parent traversal, absolute paths) are blocked."""
    # 1. Parent traversal ../
    buf1 = io.BytesIO()
    with zipfile.ZipFile(buf1, "w") as zf:
        zf.writestr("../../../escape.shp", b"dummy")
    res1 = client.post("/api/files/", files={"file": ("slip1.zip", buf1.getvalue(), "application/zip")})
    assert res1.status_code == 400
    assert res1.json()["error_code"] == "UNSAFE_ARCHIVE_PATH"

    # 2. Absolute Unix path
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, "w") as zf:
        zf.writestr("/etc/evil.shp", b"dummy")
    res2 = client.post("/api/files/", files={"file": ("slip2.zip", buf2.getvalue(), "application/zip")})
    assert res2.status_code == 400
    assert res2.json()["error_code"] == "UNSAFE_ARCHIVE_PATH"

    # 3. Windows drive path
    buf3 = io.BytesIO()
    with zipfile.ZipFile(buf3, "w") as zf:
        zf.writestr("C:\\Windows\\system32\\evil.shp", b"dummy")
    res3 = client.post("/api/files/", files={"file": ("slip3.zip", buf3.getvalue(), "application/zip")})
    assert res3.status_code == 400
    assert res3.json()["error_code"] == "UNSAFE_ARCHIVE_PATH"


def test_invalid_shapefile_prj_rejected_with_422():
    """Verify Shapefile with corrupt or invalid .prj text is rejected with 422."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        shp = tmp_path / "corrupt_prj.shp"
        gdf = gpd.GeoDataFrame([{"name": "test", "geometry": Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])}], crs="EPSG:4326")
        gdf.to_file(shp, engine="pyogrio")

        # Overwrite .prj with invalid garbage
        prj = tmp_path / "corrupt_prj.prj"
        prj.write_text("CORRUPTED_NON_EXISTENT_PROJECTION_DATA", encoding="utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for f in tmp_path.iterdir():
                zf.write(f, arcname=f.name)

        res = client.post("/api/files/", files={"file": ("bad_prj.zip", buf.getvalue(), "application/zip")})
        assert res.status_code == 422
        assert "crs" in res.json()["detail"].lower() or "coordinate reference system" in res.json()["detail"].lower()
        # Verify no traceback leaked
        assert "Traceback" not in res.text


def test_cleanup_guaranteed_on_both_success_and_failure():
    """Verify temporary directories are cleaned up in both success and failure cases."""
    temp_dir = tempfile.gettempdir()
    initial_tmp_dirs = [d for d in os.listdir(temp_dir) if "tmp" in d.lower()]

    # Case 1: Successful upload
    valid_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark><name>T</name><Point><coordinates>0,0,0</coordinates></Point></Placemark></Document></kml>"""
    res1 = client.post("/api/files/", files={"file": ("ok.kml", valid_kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")})
    assert res1.status_code == 201

    # Case 2: Hostile/failing upload (Zip slip)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../bad.shp", b"bad")
    res2 = client.post("/api/files/", files={"file": ("bad.zip", buf.getvalue(), "application/zip")})
    assert res2.status_code == 400

    # Case 3: Malformed XML
    res3 = client.post("/api/files/", files={"file": ("broken.kml", b"<not-xml", "application/vnd.google-earth.kml+xml")})
    assert res3.status_code in [400, 422]

    # Verify no persistent temporary directories leaked
    final_tmp_dirs = [d for d in os.listdir(temp_dir) if "tmp" in d.lower()]
    leaked_dirs = set(final_tmp_dirs) - set(initial_tmp_dirs)
    assert len(leaked_dirs) == 0, f"Temporary directories were leaked: {leaked_dirs}"


def test_error_responses_never_expose_server_paths_or_tracebacks():
    """Verify multiple failure modes never expose server paths or stack traces."""
    test_cases = [
        ("bad_ext.exe", b"binary", "application/octet-stream"),
        ("empty.zip", b"", "application/zip"),
        ("corrupt.zip", b"garbage bytes", "application/zip"),
        ("corrupt.kml", b"not valid xml", "text/plain"),
    ]

    for fname, content, ctype in test_cases:
        res = client.post("/api/files/", files={"file": (fname, content, ctype)})
        assert res.status_code in [400, 422]
        body = res.text
        # Ensure no stack traces or server paths
        assert "Traceback (most recent call last)" not in body
        assert "E:\\" not in body
        assert "C:\\Users\\" not in body
        assert "/tmp/" not in body
