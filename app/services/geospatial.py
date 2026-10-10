import io
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from fastapi import UploadFile
from shapely.geometry import mapping
from shapely.validation import explain_validity

from app.config import settings
from app.exceptions import (
    AmbiguousArchiveError,
    EmptyDatasetError,
    EmptyFileError,
    FileSizeExceededError,
    InvalidArchiveError,
    InvalidGeospatialDataError,
    MissingCRSError,
    UnsafeArchiveError,
    UnsupportedFileTypeError,
)
from app.schemas import (
    CRSInfo,
    FeatureItem,
    FeatureMeasurement,
    ParsedGeospatialResponse,
    SummaryMeasurements,
)
from app.services.projections import select_measurement_crs


def sanitize_driver_error(err_str: str) -> str:
    """Sanitize third-party driver and system error messages to prevent leaking server filesystem paths."""
    if not err_str:
        return "Unknown geospatial parsing error"
    # Redact Windows drive paths (e.g., C:\..., E:\...)
    sanitized = re.sub(r"[A-Za-z]:\\[^:\s\n,;\"']+", "[redacted-path]", err_str)
    # Redact Unix and temp paths (e.g., /tmp/..., \tmp\..., /var/...)
    sanitized = re.sub(r"(?:/|\\)tmp(?:/|\\)[^:\s\n,;\"']+", "[redacted-path]", sanitized)
    sanitized = re.sub(r"/(?:var|tmp|etc|usr|home|Users)/[^\s\n,;\"']+", "[redacted-path]", sanitized)
    return sanitized


async def read_upload_file_safely(file: UploadFile, max_bytes: int) -> bytes:
    """
    Safely stream uploaded file in chunks and abort immediately if size limit is exceeded.
    Protects memory against oversized payloads (DoS/OOM mitigation).
    """
    chunks: List[bytes] = []
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB chunks

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise FileSizeExceededError(
                f"File '{file.filename}' ({total_bytes} bytes) exceeds the maximum allowed limit of {max_bytes} bytes."
            )
        chunks.append(chunk)

    return b"".join(chunks)


def make_json_safe(val: Any) -> Any:
    """Recursively convert pandas/numpy/datetime types and null-likes into standard JSON-serializable primitives."""
    if val is None:
        return None
    if pd.isna(val):
        return None
    if isinstance(val, (np.floating, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.isoformat()
    if isinstance(val, np.datetime64):
        return pd.Timestamp(val).isoformat()
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            return val.hex()
    if isinstance(val, (list, tuple, np.ndarray)):
        return [make_json_safe(item) for item in val]
    if isinstance(val, dict):
        return {str(k): make_json_safe(v) for k, v in val.items()}
    if not isinstance(val, (str, int, float, bool)):
        return str(val)
    return val


def validate_file_metadata(filename: Optional[str], size: int) -> str:
    """Validate initial file constraints including extension and size limit."""
    if not filename:
        raise UnsupportedFileTypeError("Filename was not provided.")

    clean_filename = Path(filename).name
    ext = Path(clean_filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file extension '{ext}'. Only {', '.join(settings.ALLOWED_EXTENSIONS)} files are supported."
        )

    if size == 0:
        raise EmptyFileError(f"Uploaded file '{clean_filename}' is empty (0 bytes).")

    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise FileSizeExceededError(
            f"File '{clean_filename}' ({size} bytes) exceeds the allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES} bytes."
        )

    return ext


def validate_and_extract_zip(zip_bytes: bytes, extract_dir: Path) -> Path:
    """
    Validate a ZIP archive for safety (Zip Slip, symlinks, decompression bombs),
    check Shapefile integrity, and extract safely into extract_dir.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as e:
        raise InvalidArchiveError(f"Uploaded file is not a valid ZIP archive: {str(e)}")

    with zf:
        # Check total uncompressed size (zip bomb protection)
        total_uncompressed = sum(info.file_size for info in zf.infolist())
        if total_uncompressed > settings.MAX_UNCOMPRESSED_SIZE_BYTES:
            raise FileSizeExceededError(
                f"Uncompressed archive size ({total_uncompressed} bytes) exceeds maximum limit ({settings.MAX_UNCOMPRESSED_SIZE_BYTES} bytes)."
            )

        extract_dir_resolved = extract_dir.resolve()

        # Check member paths for traversal attacks (Zip Slip) and symlinks
        for info in zf.infolist():
            raw_name = info.filename
            # Reject absolute paths or drive letters
            if raw_name.startswith("/") or raw_name.startswith("\\") or ":" in raw_name:
                raise UnsafeArchiveError(f"ZIP archive contains unsafe absolute member path: '{raw_name}'.")

            # Check for parent directory navigation in path components
            parts = Path(raw_name).parts
            if ".." in parts:
                raise UnsafeArchiveError(f"ZIP archive contains unsafe path traversal member: '{raw_name}'.")

            target_path = (extract_dir / raw_name).resolve()
            if not target_path.is_relative_to(extract_dir_resolved):
                raise UnsafeArchiveError(f"ZIP archive contains unsafe path traversal member: '{raw_name}'.")

            # Check for symlinks inside zip
            if (info.external_attr >> 16) & 0o120000 == 0o120000:
                raise UnsafeArchiveError(f"ZIP archive contains unsupported symbolic link: '{raw_name}'.")

        # Find shapefile components (.shp)
        shp_members = [
            info.filename
            for info in zf.infolist()
            if not info.is_dir()
            and not Path(info.filename).name.startswith("._")
            and "__MACOSX" not in info.filename
            and info.filename.lower().endswith(".shp")
        ]

        if len(shp_members) == 0:
            raise InvalidArchiveError(
                "ZIP archive does not contain a .shp Shapefile component. "
                "Ensure your ZIP archive contains a complete Shapefile set (.shp, .shx, .dbf, and .prj)."
            )

        if len(shp_members) > 1:
            raise AmbiguousArchiveError(
                f"Ambiguous archive: multiple Shapefiles found ({shp_members}). Exactly one Shapefile is required per archive."
            )

        shp_info = zf.getinfo(shp_members[0])
        if shp_info.file_size == 0:
            raise EmptyFileError(f"Shapefile component '{shp_members[0]}' is empty (0 bytes).")

        # Safely extract members
        zf.extractall(extract_dir)

    target_shp_path = extract_dir / shp_members[0]
    return target_shp_path


def validate_kml_content(kml_bytes: bytes, target_path: Path) -> Path:
    """Validate KML file header, structure, and XML security before saving."""
    if len(kml_bytes) == 0:
        raise EmptyFileError("Uploaded KML file is empty.")

    # Guard against binary files renamed to .kml
    head_bytes = kml_bytes[:2048]
    if b"\x00" in head_bytes:
        raise UnsupportedFileTypeError("File has .kml extension but contains invalid binary content.")

    head_text = head_bytes.decode("utf-8", errors="ignore").lower()

    # XXE Attack Mitigation: Disallow inline entity declarations and DTD schemas
    if "<!entity" in head_text or "<!doctype" in head_text:
        raise InvalidGeospatialDataError("KML file contains forbidden XML entity or DTD declarations.")

    if "<kml" not in head_text and "<?xml" not in head_text and "<document" not in head_text:
        raise InvalidGeospatialDataError("Uploaded file does not appear to be a valid XML/KML document.")

    # Verify XML well-formedness
    try:
        ET.fromstring(kml_bytes)
    except ET.ParseError as pe:
        raise InvalidGeospatialDataError(f"Malformed KML document: XML parsing failed ({pe.msg}).")

    target_path.write_bytes(kml_bytes)
    return target_path


def calculate_feature_measurement(orig_geom: Any, proj_geom: Any) -> FeatureMeasurement:
    """
    Calculate feature measurement in metric units from the reprojected geometry.
    - Polygon / MultiPolygon -> area in m² and km²
    - LineString / MultiLineString -> length in m and km
    - Point / MultiPoint -> measurement: null with clear note
    - Unsupported types -> unsupported status without failing request
    - Empty / Invalid -> reported without hiding failure
    """
    if orig_geom is None or getattr(orig_geom, "is_empty", True):
        return FeatureMeasurement(
            measurement_type="none",
            status="empty_geometry",
            notes="Geometry is empty; cannot compute measurements.",
        )

    if not orig_geom.is_valid:
        reason = explain_validity(orig_geom)
        return FeatureMeasurement(
            measurement_type="none",
            status="invalid_geometry",
            notes=f"Geometry is invalid ({reason}). Calculation failed.",
        )

    geom_type = orig_geom.geom_type

    try:
        if geom_type in ("Polygon", "MultiPolygon"):
            area_m2 = float(proj_geom.area)
            area_km2 = area_m2 / 1_000_000.0
            return FeatureMeasurement(
                measurement_type="area",
                status="success",
                area_m2=round(area_m2, 2),
                area_km2=round(area_km2, 6),
                notes=None,
            )

        elif geom_type in ("LineString", "MultiLineString"):
            length_m = float(proj_geom.length)
            length_km = length_m / 1_000.0
            return FeatureMeasurement(
                measurement_type="length",
                status="success",
                length_m=round(length_m, 2),
                length_km=round(length_km, 5),
                notes=None,
            )

        elif geom_type in ("Point", "MultiPoint"):
            return FeatureMeasurement(
                measurement_type="none",
                status="not_applicable",
                notes="Measurement is not required: Points and MultiPoints do not have area or length dimensions.",
            )

        else:
            return FeatureMeasurement(
                measurement_type="unsupported",
                status="unsupported",
                notes=f"Geometry type '{geom_type}' is unsupported for direct area or length measurement.",
            )

    except Exception as exc:
        return FeatureMeasurement(
            measurement_type="error",
            status="error",
            notes=f"Calculation error occurred: {str(exc)}",
        )


def parse_geodataframe(gdf: gpd.GeoDataFrame, filename: str, file_type: str) -> ParsedGeospatialResponse:
    """
    Validate, reproject, and extract features, CRS, and measurements from a GeoDataFrame.
    Strictly checks that source CRS is present and reprojects to an appropriate metric CRS.
    """
    if len(gdf) == 0:
        raise EmptyDatasetError(f"The geospatial file '{filename}' contains no features.")

    # Strict CRS verification: Do NOT guess EPSG:4326 if None
    if gdf.crs is None or not str(gdf.crs).strip():
        raise MissingCRSError(
            f"The uploaded geospatial file '{filename}' does not define a Coordinate Reference System (CRS). "
            "For Shapefiles, ensure a valid .prj file is included in the ZIP archive. An explicit CRS cannot be assumed."
        )

    # Format source CRS string
    try:
        epsg = gdf.crs.to_epsg()
        source_crs_str = f"EPSG:{epsg}" if epsg else gdf.crs.to_string()
    except Exception:
        source_crs_str = str(gdf.crs)

    # Select appropriate projected metric CRS for measurement calculations
    selected_crs_info = select_measurement_crs(gdf)

    # Reproject to projected metric CRS
    try:
        projected_gdf = gdf.to_crs(selected_crs_info.crs)
    except Exception as e:
        clean_err = sanitize_driver_error(str(e))
        raise InvalidGeospatialDataError(
            f"Failed to reproject dataset from source CRS ({source_crs_str}) to measurement CRS ({selected_crs_info.crs_str}): {clean_err}"
        )

    # Source bounds [minx, miny, maxx, maxy]
    bounds_list: Optional[List[float]] = None
    try:
        tb = gdf.total_bounds
        if len(tb) == 4 and not any(np.isnan(tb)):
            bounds_list = [float(val) for val in tb]
    except Exception:
        bounds_list = None

    geometry_types_set = set()
    features: List[FeatureItem] = []

    geom_col_name = gdf.geometry.name if hasattr(gdf, "geometry") else "geometry"
    prop_cols = [c for c in gdf.columns if c != geom_col_name]

    total_area_m2 = 0.0
    polygon_count = 0
    total_length_m = 0.0
    line_count = 0

    for idx, row in gdf.iterrows():
        orig_geom = row[geom_col_name] if geom_col_name in row else None
        proj_geom = projected_gdf.loc[idx, geom_col_name] if geom_col_name in projected_gdf else None

        geom_type = "None"
        geom_json = None

        if orig_geom is not None and not orig_geom.is_empty:
            geom_type = orig_geom.geom_type
            geometry_types_set.add(geom_type)
            geom_json = mapping(orig_geom)

        measurement = calculate_feature_measurement(orig_geom, proj_geom)

        if measurement.status == "success":
            if measurement.measurement_type == "area" and measurement.area_m2 is not None:
                total_area_m2 += measurement.area_m2
                polygon_count += 1
            elif measurement.measurement_type == "length" and measurement.length_m is not None:
                total_length_m += measurement.length_m
                line_count += 1

        properties: Dict[str, Any] = {}
        for col in prop_cols:
            properties[str(col)] = make_json_safe(row[col])

        features.append(
            FeatureItem(
                id=idx if isinstance(idx, (int, str)) else int(idx),
                geometry_type=geom_type,
                geometry=geom_json,
                properties=properties,
                measurement=measurement,
            )
        )

    summary = SummaryMeasurements(
        total_features=len(features),
        measured_polygons=polygon_count,
        total_area_m2=round(total_area_m2, 2) if polygon_count > 0 else None,
        total_area_km2=round(total_area_m2 / 1_000_000.0, 6) if polygon_count > 0 else None,
        measured_lines=line_count,
        total_length_m=round(total_length_m, 2) if line_count > 0 else None,
        total_length_km=round(total_length_m / 1_000.0, 5) if line_count > 0 else None,
    )

    crs_metadata = CRSInfo(
        source_crs=source_crs_str,
        measurement_crs=selected_crs_info.crs_str,
        projection_method=selected_crs_info.projection_method,
        selection_reason=selected_crs_info.selection_reason,
        limitations=selected_crs_info.limitations,
    )

    return ParsedGeospatialResponse(
        filename=filename,
        file_type=file_type,
        crs=source_crs_str,
        source_crs=source_crs_str,
        measurement_crs=selected_crs_info.crs_str,
        crs_info=crs_metadata,
        feature_count=len(features),
        geometry_types=sorted(list(geometry_types_set)),
        bounds=bounds_list,
        summary_measurements=summary,
        features=features,
    )


def process_geospatial_upload(filename: str, file_bytes: bytes) -> ParsedGeospatialResponse:
    """
    Main entry point for safely processing geospatial uploads.
    Creates an isolated temporary directory, parses KML or zipped Shapefile,
    calculates measurements in projected metric CRS, and guarantees complete cleanup.
    """
    size = len(file_bytes)
    ext = validate_file_metadata(filename, size)

    # Isolated temporary directory with guaranteed cleanup via context manager
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)

        if ext == ".zip":
            file_type = "shapefile"
            shp_path = validate_and_extract_zip(file_bytes, temp_dir_path)
            try:
                gdf = gpd.read_file(shp_path, engine="pyogrio")
            except Exception as e:
                clean_err = sanitize_driver_error(str(e))
                raise InvalidGeospatialDataError(f"Failed to read Shapefile: {clean_err}")

        elif ext == ".kml":
            file_type = "kml"
            kml_path = temp_dir_path / Path(filename).name
            validate_kml_content(file_bytes, kml_path)
            try:
                gdf = gpd.read_file(kml_path, engine="pyogrio")
            except Exception as e:
                clean_err = sanitize_driver_error(str(e))
                raise InvalidGeospatialDataError(f"Failed to read KML file: {clean_err}")

        else:
            raise UnsupportedFileTypeError(f"Unsupported file extension '{ext}'.")

        return parse_geodataframe(gdf, filename, file_type)
