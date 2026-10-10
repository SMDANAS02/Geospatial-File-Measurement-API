import json
import math
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.exceptions import FileSizeExceededError
from app.models import StoredFeature, StoredFile
from app.schemas import (
    ErrorResponse,
    FileInfoResponse,
    FileUploadResponse,
    MeasurementFeatureItem,
    PaginatedMeasurementsResponse,
    StoredMeasurementDetail,
    SummaryMeasurements,
)
from app.services.geospatial import process_geospatial_upload, read_upload_file_safely

router = APIRouter(prefix="/files", tags=["Files & Measurements"])


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Process Geospatial File",
    description="""
Upload a `.kml` or `.zip` (containing a complete Shapefile set).
Validates, reprojects to an optimal metric projected CRS, computes measurements,
and stores the results in SQLite without exposing server paths.
    """,
    responses={
        201: {"model": FileUploadResponse, "description": "File processed and saved successfully"},
        400: {"model": ErrorResponse, "description": "Invalid format, corrupt archive, or unsafe paths"},
        413: {"model": ErrorResponse, "description": "File exceeds maximum size limit"},
        422: {"model": ErrorResponse, "description": "Missing CRS, unreadable geometries, or empty dataset"},
    },
)
async def upload_and_process_file(
    file: UploadFile = File(..., description="Geospatial file (.kml or .zip)"),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """Upload, process, and persist a geospatial dataset."""
    # Safely stream file with immediate size limit enforcement
    content = await read_upload_file_safely(file, settings.MAX_UPLOAD_SIZE_BYTES)

    filename = file.filename or "upload.bin"
    # Execute full Phase 2 & 3 pipeline (safe unpacking, CRS detection, metric measurement)
    parsed_result = process_geospatial_upload(filename=filename, file_bytes=content)

    # Persist dataset record in database
    summary_dict = parsed_result.summary_measurements.model_dump() if parsed_result.summary_measurements else None
    stored_file = StoredFile(
        filename=filename,
        file_type=parsed_result.file_type,
        size_bytes=len(content),
        source_crs=parsed_result.source_crs,
        measurement_crs=parsed_result.measurement_crs,
        projection_method=parsed_result.crs_info.projection_method if parsed_result.crs_info else None,
        feature_count=parsed_result.feature_count,
        status="COMPLETED",
        summary_json=json.dumps(summary_dict) if summary_dict else None,
    )
    db.add(stored_file)
    db.flush()  # Obtain generated stored_file.id

    # Persist feature records
    for idx, feat in enumerate(parsed_result.features):
        m = feat.measurement
        # Map unit and status
        unit = "m²" if m.measurement_type == "area" else ("m" if m.measurement_type == "length" else None)
        status_map = {
            "success": "COMPLETED",
            "not_applicable": "NOT_APPLICABLE",
            "unsupported": "UNSUPPORTED",
            "empty_geometry": "EMPTY_GEOMETRY",
            "invalid_geometry": "INVALID_GEOMETRY",
            "error": "FAILED",
        }
        measurement_status = status_map.get(m.status, m.status.upper())

        stored_feat = StoredFeature(
            file_id=stored_file.id,
            feature_index=idx,
            geometry_type=feat.geometry_type,
            geometry_json=json.dumps(feat.geometry) if feat.geometry else None,
            properties_json=json.dumps(feat.properties) if feat.properties else None,
            measurement_status=measurement_status,
            measurement_type=m.measurement_type,
            area_m2=m.area_m2,
            area_km2=m.area_km2,
            length_m=m.length_m,
            length_km=m.length_km,
            unit=unit,
            notes=m.notes,
        )
        db.add(stored_feat)

    db.commit()
    db.refresh(stored_file)

    return FileUploadResponse(
        id=stored_file.id,
        filename=stored_file.filename,
        feature_count=stored_file.feature_count,
        crs=stored_file.source_crs,
        measurement_crs=stored_file.measurement_crs,
        status=stored_file.status,
    )


@router.get(
    "/{file_id}",
    response_model=FileInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get File Metadata",
    description="Retrieve stored metadata and summary for a processed file by its generated ID.",
    responses={
        200: {"model": FileInfoResponse, "description": "Stored file metadata"},
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    include_in_schema=False,
)
def get_file_info(file_id: str, db: Session = Depends(get_db)) -> FileInfoResponse:
    """Retrieve metadata for a stored file."""
    stored_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not stored_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )

    summary_obj = None
    if stored_file.summary_json:
        try:
            summary_obj = SummaryMeasurements(**json.loads(stored_file.summary_json))
        except Exception:
            summary_obj = None

    return FileInfoResponse(
        id=stored_file.id,
        filename=stored_file.filename,
        file_type=stored_file.file_type,
        size_bytes=stored_file.size_bytes,
        feature_count=stored_file.feature_count,
        crs=stored_file.source_crs,
        source_crs=stored_file.source_crs,
        measurement_crs=stored_file.measurement_crs,
        projection_method=stored_file.projection_method,
        status=stored_file.status,
        created_at=stored_file.created_at,
        summary_measurements=summary_obj,
    )


@router.get(
    "/{file_id}/measurements",
    response_model=PaginatedMeasurementsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Feature Measurements",
    description="""
Retrieve paginated feature details, GeoJSON geometry, properties, and metric calculations for a file.
* **page**: Page number (default: 1, minimum: 1)
* **page_size**: Items per page (default: 50, maximum: 500)
    """,
    responses={
        200: {"model": PaginatedMeasurementsResponse, "description": "Paginated list of feature measurements"},
        404: {"model": ErrorResponse, "description": "File not found"},
    },
)
@router.get(
    "/{file_id}/measurements/",
    response_model=PaginatedMeasurementsResponse,
    include_in_schema=False,
)
def get_file_measurements(
    file_id: str,
    page: int = Query(1, ge=1, description="Page number (default: 1)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (default: 50, maximum: 500)"),
    db: Session = Depends(get_db),
) -> PaginatedMeasurementsResponse:
    """Retrieve paginated feature measurements for a stored file."""
    stored_file = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not stored_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )

    total = db.query(StoredFeature).filter(StoredFeature.file_id == file_id).count()
    pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    offset = (page - 1) * page_size
    features = (
        db.query(StoredFeature)
        .filter(StoredFeature.file_id == file_id)
        .order_by(StoredFeature.feature_index.asc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items: list[MeasurementFeatureItem] = []
    for f in features:
        geom = json.loads(f.geometry_json) if f.geometry_json else None
        props = json.loads(f.properties_json) if f.properties_json else {}

        detail = StoredMeasurementDetail(
            status=f.measurement_status,
            area_m2=f.area_m2,
            area_km2=f.area_km2,
            length_m=f.length_m,
            length_km=f.length_km,
            unit=f.unit,
            notes=f.notes,
        )

        items.append(
            MeasurementFeatureItem(
                feature_index=f.feature_index,
                geometry_type=f.geometry_type,
                geometry=geom,
                properties=props,
                measurement=detail,
            )
        )

    return PaginatedMeasurementsResponse(
        file_id=stored_file.id,
        filename=stored_file.filename,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=items,
    )
