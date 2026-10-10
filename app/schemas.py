from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Schema for API health status check."""
    status: str = Field(..., description="Application health status", examples=["healthy"])
    timestamp: datetime = Field(..., description="Current server time (UTC)")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Current environment (e.g. development, production)")
    version: str = Field(..., description="API version")
    database_status: str = Field(..., description="Database connectivity status", examples=["connected", "disconnected"])


class RootResponse(BaseModel):
    """Schema for root API greeting and documentation reference."""
    message: str
    docs_url: str
    health_url: str


class FeatureMeasurement(BaseModel):
    """Measurements computed for a specific geospatial feature in projected metric units."""
    measurement_type: str = Field(..., description="Type of measurement computed ('area', 'length', 'none', or 'unsupported')")
    status: str = Field(..., description="Status ('success', 'not_applicable', 'unsupported', 'empty_geometry', 'invalid_geometry', or 'error')")
    area_m2: Optional[float] = Field(None, description="Area in square metres (m²), rounded to 2 decimal places")
    area_km2: Optional[float] = Field(None, description="Area in square kilometres (km²), rounded to 6 decimal places")
    length_m: Optional[float] = Field(None, description="Length in metres (m), rounded to 2 decimal places")
    length_km: Optional[float] = Field(None, description="Length in kilometres (km), rounded to 5 decimal places")
    notes: Optional[str] = Field(None, description="Detailed explanation, notes, or error reason")


class FeatureItem(BaseModel):
    """Extracted geospatial feature item."""
    id: Union[int, str] = Field(..., description="Stable feature identifier or index")
    geometry_type: str = Field(..., description="Type of geometry (e.g., Point, Polygon, LineString)")
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON geometry representation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes normalized to JSON-safe primitives")
    measurement: FeatureMeasurement = Field(..., description="Projected metric measurements or reason if non-measurable")


class CRSInfo(BaseModel):
    """Detailed metadata on Coordinate Reference Systems used."""
    source_crs: str = Field(..., description="Original Coordinate Reference System extracted from source file")
    measurement_crs: str = Field(..., description="Projected metric Coordinate Reference System used for calculations")
    projection_method: str = Field(..., description="Projection class (e.g. Local UTM Zone, Centered LAEA, UPS)")
    selection_reason: str = Field(..., description="Why this projection was chosen for the dataset's extent")
    limitations: str = Field(..., description="Documented scale and distortion limits of the measurement CRS")


class SummaryMeasurements(BaseModel):
    """Dataset-level aggregated metrics."""
    total_features: int = Field(..., description="Total feature count")
    measured_polygons: int = Field(..., description="Number of measured polygons")
    total_area_m2: Optional[float] = Field(None, description="Sum of polygon areas in square metres")
    total_area_km2: Optional[float] = Field(None, description="Sum of polygon areas in square kilometres")
    measured_lines: int = Field(..., description="Number of measured lines")
    total_length_m: Optional[float] = Field(None, description="Sum of line lengths in metres")
    total_length_km: Optional[float] = Field(None, description="Sum of line lengths in kilometres")


class ParsedGeospatialResponse(BaseModel):
    """Result of validating, parsing, and calculating measurements for an uploaded geospatial file."""
    filename: str = Field(..., description="Original name of the uploaded file")
    file_type: str = Field(..., description="Detected format ('kml' or 'shapefile')")
    crs: str = Field(..., description="Source Coordinate Reference System (alias for source_crs)")
    source_crs: str = Field(..., description="Original Coordinate Reference System from input file")
    measurement_crs: str = Field(..., description="Projected metric CRS used for measurement calculations")
    crs_info: CRSInfo = Field(..., description="CRS selection strategy details and distortion limitations")
    feature_count: int = Field(..., description="Total number of valid features")
    geometry_types: List[str] = Field(default_factory=list, description="Unique geometry types found in the dataset")
    bounds: Optional[List[float]] = Field(None, description="Bounding box [minx, miny, maxx, maxy] in source CRS")
    summary_measurements: Optional[SummaryMeasurements] = Field(None, description="Aggregated dataset metrics")
    features: List[FeatureItem] = Field(default_factory=list, description="List of parsed features with individual measurements")


# --- Phase 4 Persistence and API Schemas ---

class FileUploadResponse(BaseModel):
    """Response returned upon successful file processing and persistence."""
    id: str = Field(..., description="Generated unique identifier for the uploaded file", examples=["geo-a1b2c3d4e5f6"])
    filename: str = Field(..., description="Original name of the uploaded file", examples=["survey.kml"])
    feature_count: int = Field(..., description="Total number of processed features", examples=[2])
    crs: str = Field(..., description="Source Coordinate Reference System", examples=["EPSG:4326"])
    measurement_crs: Optional[str] = Field(None, description="Projected metric Coordinate Reference System", examples=["EPSG:32643"])
    status: str = Field(..., description="Processing status", examples=["COMPLETED"])


class FileInfoResponse(BaseModel):
    """Metadata response for a stored file."""
    id: str = Field(..., description="Generated unique identifier")
    filename: str = Field(..., description="Original filename")
    file_type: str = Field(..., description="File format ('kml' or 'shapefile')")
    size_bytes: int = Field(..., description="Upload size in bytes")
    feature_count: int = Field(..., description="Total number of features")
    crs: str = Field(..., description="Source Coordinate Reference System")
    source_crs: str = Field(..., description="Source Coordinate Reference System")
    measurement_crs: Optional[str] = Field(None, description="Measurement Coordinate Reference System")
    projection_method: Optional[str] = Field(None, description="Projection strategy")
    status: str = Field(..., description="Processing status ('COMPLETED', 'FAILED')")
    created_at: datetime = Field(..., description="Upload timestamp")
    summary_measurements: Optional[SummaryMeasurements] = Field(None, description="Dataset measurement summary")


class StoredMeasurementDetail(BaseModel):
    """Detailed feature measurement returned by the API."""
    status: str = Field(..., description="Status ('COMPLETED', 'NOT_APPLICABLE', 'UNSUPPORTED', 'EMPTY_GEOMETRY', or 'FAILED')")
    area_m2: Optional[float] = Field(None, description="Area in square metres (m²)")
    area_km2: Optional[float] = Field(None, description="Area in square kilometres (km²)")
    length_m: Optional[float] = Field(None, description="Length in metres (m)")
    length_km: Optional[float] = Field(None, description="Length in kilometres (km)")
    unit: Optional[str] = Field(None, description="Measurement unit ('m²', 'm', etc.)")
    notes: Optional[str] = Field(None, description="Explanation or error reason")


class MeasurementFeatureItem(BaseModel):
    """Feature details and calculation record."""
    feature_index: int = Field(..., description="Zero-based feature index in the dataset")
    geometry_type: str = Field(..., description="Geometry type (e.g. Polygon, LineString, Point)")
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON geometry representation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attribute dictionary")
    measurement: StoredMeasurementDetail = Field(..., description="Computed metric measurement")


class PaginatedMeasurementsResponse(BaseModel):
    """Paginated list of feature measurements."""
    file_id: str = Field(..., description="Identifier of the parent file")
    filename: str = Field(..., description="Original filename")
    total: int = Field(..., description="Total number of features across all pages")
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")
    items: List[MeasurementFeatureItem] = Field(default_factory=list, description="Page of feature measurements")


class ErrorResponse(BaseModel):
    """Standardized error response payload."""
    detail: str = Field(..., description="Descriptive error explanation")
    error_code: str = Field(..., description="Machine-readable error classification code")
