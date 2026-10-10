from fastapi import APIRouter, File, UploadFile, status

from app.config import settings
from app.exceptions import FileSizeExceededError
from app.schemas import ErrorResponse, ParsedGeospatialResponse
from app.services.geospatial import process_geospatial_upload, read_upload_file_safely

router = APIRouter(prefix="/geospatial", tags=["Geospatial Processing"])


@router.post(
    "/parse",
    response_model=ParsedGeospatialResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate and Parse Geospatial File",
    description="""
Upload a **.kml** or zipped Shapefile (**complete archive containing at least .shp, .shx, .dbf, and .prj**).

### Validation & Processing:
* Enforces strict extension and content checks (.kml or .zip).
* Safeguards against Zip Slip path traversal and oversized archives.
* Requires an explicit Coordinate Reference System (CRS) - unprojected files will be rejected.
* Serializes dates and null-like properties to standard JSON types.
* Returns stable feature identifiers, geometry types, GeoJSON geometries, properties, and CRS.
    """,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid format, corrupt archive, or unsafe paths"},
        413: {"model": ErrorResponse, "description": "File exceeds maximum size limit"},
        422: {"model": ErrorResponse, "description": "Missing CRS, unreadable geometries, or empty dataset"},
    },
)
async def parse_geospatial_file(
    file: UploadFile = File(..., description="Geospatial file (.kml or .zip containing complete Shapefile set)"),
) -> ParsedGeospatialResponse:
    """Validate and parse an uploaded geospatial file."""
    # Safely stream file with immediate size limit enforcement
    content = await read_upload_file_safely(file, settings.MAX_UPLOAD_SIZE_BYTES)

    return process_geospatial_upload(filename=file.filename or "upload.bin", file_bytes=content)


@router.post(
    "/upload",
    response_model=ParsedGeospatialResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload Geospatial File (Alias)",
    description="Alias endpoint for validating and parsing a geospatial file.",
    include_in_schema=False,
)
async def upload_geospatial_file_alias(
    file: UploadFile = File(...),
) -> ParsedGeospatialResponse:
    """Alias for /parse endpoint."""
    return await parse_geospatial_file(file=file)
