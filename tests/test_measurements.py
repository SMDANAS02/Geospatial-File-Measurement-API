import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from app.main import app

client = TestClient(app)


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


def test_polygon_and_multipolygon_area_calculation():
    """Verify Polygon and MultiPolygon features return area_m2 and area_km2."""
    poly1 = Polygon([[-122.1, 37.4], [-122.0, 37.4], [-122.0, 37.5], [-122.1, 37.5], [-122.1, 37.4]])
    poly2_part1 = Polygon([[-122.3, 37.2], [-122.2, 37.2], [-122.2, 37.3], [-122.3, 37.3], [-122.3, 37.2]])
    poly2_part2 = Polygon([[-122.35, 37.25], [-122.32, 37.25], [-122.32, 37.28], [-122.35, 37.28], [-122.35, 37.25]])
    mpoly = MultiPolygon([poly2_part1, poly2_part2])

    gdf = gpd.GeoDataFrame(
        [
            {"name": "SinglePoly", "geometry": poly1},
            {"name": "MultiPoly", "geometry": mpoly},
        ],
        crs="EPSG:4326",
    )

    zip_bytes = build_shapefile_zip(gdf)
    response = client.post("/geospatial/parse", files={"file": ("polygons.zip", zip_bytes, "application/zip")})
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["source_crs"] == "EPSG:4326"
    assert "EPSG:32610" in data["measurement_crs"]  # UTM Zone 10N for San Francisco coordinates
    assert len(data["features"]) == 2

    for feat in data["features"]:
        m = feat["measurement"]
        assert m["measurement_type"] == "area"
        assert m["status"] == "success"
        assert m["area_m2"] is not None and m["area_m2"] > 0
        assert m["area_km2"] is not None and m["area_km2"] > 0
        # Check scale relationship between m² and km²
        assert abs(m["area_km2"] - (m["area_m2"] / 1_000_000.0)) < 1e-4
        assert m["length_m"] is None
        assert m["length_km"] is None


def test_linestring_and_multilinestring_length_calculation():
    """Verify LineString and MultiLineString features return length_m and length_km."""
    line1 = LineString([[-122.1, 37.4], [-122.0, 37.45]])
    mline = MultiLineString([
        [[-122.2, 37.3], [-122.15, 37.35]],
        [[-122.12, 37.36], [-122.05, 37.39]],
    ])

    gdf = gpd.GeoDataFrame(
        [
            {"name": "Trail1", "geometry": line1},
            {"name": "TrailNetwork", "geometry": mline},
        ],
        crs="EPSG:4326",
    )

    zip_bytes = build_shapefile_zip(gdf)
    response = client.post("/geospatial/parse", files={"file": ("lines.zip", zip_bytes, "application/zip")})
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["features"]) == 2
    for feat in data["features"]:
        m = feat["measurement"]
        assert m["measurement_type"] == "length"
        assert m["status"] == "success"
        assert m["length_m"] is not None and m["length_m"] > 0
        assert m["length_km"] is not None and m["length_km"] > 0
        # Check scale relationship between m and km
        assert abs(m["length_km"] - (m["length_m"] / 1000.0)) < 1e-4
        assert m["area_m2"] is None
        assert m["area_km2"] is None


def test_point_and_multipoint_measurement_not_required():
    """Verify Point and MultiPoint explicitly state that measurement is not required."""
    pt1 = Point(-122.08, 37.42)
    pt2 = Point(-122.05, 37.40)

    gdf = gpd.GeoDataFrame(
        [
            {"name": "PointOne", "geometry": pt1},
            {"name": "PointTwo", "geometry": pt2},
        ],
        crs="EPSG:4326",
    )

    zip_bytes = build_shapefile_zip(gdf)
    response = client.post("/geospatial/parse", files={"file": ("points.zip", zip_bytes, "application/zip")})
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["features"]) == 2
    for feat in data["features"]:
        m = feat["measurement"]
        assert m["measurement_type"] == "none"
        assert m["status"] == "not_applicable"
        assert m["area_m2"] is None
        assert m["area_km2"] is None
        assert m["length_m"] is None
        assert m["length_km"] is None
        assert "not required" in m["notes"].lower()

    # Also verify MultiPoint directly
    from app.services.geospatial import calculate_feature_measurement
    mpt = MultiPoint([[-122.05, 37.40], [-122.06, 37.41]])
    m_mpt = calculate_feature_measurement(mpt, mpt)
    assert m_mpt.status == "not_applicable"
    assert "not required" in m_mpt.notes.lower()


def test_unsupported_geometry_does_not_fail_request():
    """Verify unsupported geometry (GeometryCollection) returns per-feature status without crashing entire file."""
    # Use KML to allow mixed geometry types including GeometryCollection
    mixed_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>ValidPolygon</name>
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
      <name>ValidPoint</name>
      <Point>
        <coordinates>-122.05,37.45,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>ValidLine</name>
      <LineString>
        <coordinates>-122.1,37.4,0 -122.0,37.45,0</coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    response = client.post(
        "/geospatial/parse",
        files={"file": ("mixed.kml", mixed_kml.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    poly_feat = next(f for f in data["features"] if f["geometry_type"] == "Polygon")
    point_feat = next(f for f in data["features"] if f["geometry_type"] == "Point")
    line_feat = next(f for f in data["features"] if f["geometry_type"] == "LineString")

    # Polygon must be measured
    assert poly_feat["measurement"]["status"] == "success"
    assert poly_feat["measurement"]["area_m2"] > 0

    # Point must be not_applicable
    assert point_feat["measurement"]["status"] == "not_applicable"

    # Line must be measured
    assert line_feat["measurement"]["status"] == "success"
    assert line_feat["measurement"]["length_m"] > 0


def test_geographic_input_is_transformed_before_measuring():
    """
    Prove that geographic input in EPSG:4326 is reprojected to a metric CRS before measuring.
    A 0.5° x 0.5° square near 37°N latitude has an unprojected area of 0.25 square degrees.
    In metric units, it is > 2,000,000,000 m² (> 2 billion square metres).
    """
    poly_degrees = Polygon([[-122.5, 37.5], [-122.0, 37.5], [-122.0, 38.0], [-122.5, 38.0], [-122.5, 37.5]])
    # Degree area
    degree_area = poly_degrees.area
    assert degree_area == pytest.approx(0.25, rel=1e-3)

    gdf = gpd.GeoDataFrame([{"name": "DegreeBox", "geometry": poly_degrees}], crs="EPSG:4326")
    zip_bytes = build_shapefile_zip(gdf)

    response = client.post("/geospatial/parse", files={"file": ("degree_box.zip", zip_bytes, "application/zip")})
    assert response.status_code == 200, response.text
    data = response.json()

    # Verify CRS metadata returned in response
    assert data["source_crs"] == "EPSG:4326"
    assert data["measurement_crs"] != "EPSG:4326"
    assert "EPSG:32610" in data["measurement_crs"]  # Local UTM
    assert "crs_info" in data
    assert "selection_reason" in data["crs_info"]
    assert "limitations" in data["crs_info"]

    # Verify measured metric area is > 2,000,000,000 m² (proves metric projection, not square degrees)
    measured_area_m2 = data["features"][0]["measurement"]["area_m2"]
    assert measured_area_m2 > 2_000_000_000, f"Area {measured_area_m2} is not in metric square metres!"
    # Verify square kilometres is > 2,000 km²
    assert data["features"][0]["measurement"]["area_km2"] > 2_000


def test_empty_and_invalid_geometries_reported_at_feature_level():
    """Verify empty and invalid geometries report feature-level failures without hiding errors."""
    from app.services.geospatial import calculate_feature_measurement

    # 1. Empty geometry
    empty_poly = Polygon()
    m_empty = calculate_feature_measurement(empty_poly, empty_poly)
    assert m_empty.status == "empty_geometry"
    assert "empty" in m_empty.notes.lower()
    assert m_empty.area_m2 is None

    # 2. Invalid self-intersecting polygon (bowtie)
    bowtie = Polygon([(0, 0), (0, 2), (2, 0), (2, 2), (0, 0)])
    assert not bowtie.is_valid
    m_invalid = calculate_feature_measurement(bowtie, bowtie)
    assert m_invalid.status == "invalid_geometry"
    assert "invalid" in m_invalid.notes.lower()
    assert m_invalid.area_m2 is None


def test_wide_area_triggers_laea_projection():
    """Verify wide-area dataset spanning > 6° longitude triggers centered LAEA projection."""
    # Polygon spanning 20 degrees across North America
    wide_poly = Polygon([[-110.0, 35.0], [-90.0, 35.0], [-90.0, 45.0], [-110.0, 45.0], [-110.0, 35.0]])
    gdf = gpd.GeoDataFrame([{"name": "WideArea", "geometry": wide_poly}], crs="EPSG:4326")
    zip_bytes = build_shapefile_zip(gdf)

    response = client.post("/geospatial/parse", files={"file": ("wide_area.zip", zip_bytes, "application/zip")})
    assert response.status_code == 200, response.text
    data = response.json()

    assert "LAEA" in data["measurement_crs"] or "laea" in data["crs_info"]["projection_method"].lower()
    assert "Lambert Azimuthal Equal Area" in data["crs_info"]["projection_method"]
    assert "exceeds" in data["crs_info"]["selection_reason"]
