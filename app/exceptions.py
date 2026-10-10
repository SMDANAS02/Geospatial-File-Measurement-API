"""Custom exception classes for geospatial validation and processing."""

from typing import Optional


class GeospatialError(Exception):
    """Base exception for all geospatial processing errors."""

    def __init__(self, message: str, status_code: int = 400, error_code: str = "GEOSPATIAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class UnsupportedFileTypeError(GeospatialError):
    """Raised when an uploaded file does not match accepted extensions (.kml, .zip)."""

    def __init__(self, message: str = "Unsupported file type. Only .kml and .zip archives containing a Shapefile are accepted."):
        super().__init__(message=message, status_code=400, error_code="UNSUPPORTED_FILE_TYPE")


class EmptyFileError(GeospatialError):
    """Raised when an uploaded file is empty (0 bytes)."""

    def __init__(self, message: str = "Uploaded file is empty."):
        super().__init__(message=message, status_code=400, error_code="EMPTY_FILE")


class FileSizeExceededError(GeospatialError):
    """Raised when an uploaded file exceeds the configured maximum size limit."""

    def __init__(self, message: str = "Uploaded file exceeds maximum permitted size limit."):
        super().__init__(message=message, status_code=413, error_code="FILE_SIZE_EXCEEDED")


class InvalidArchiveError(GeospatialError):
    """Raised when a zip archive is corrupted, invalid, or missing essential shapefile components."""

    def __init__(self, message: str = "Invalid ZIP archive or missing required .shp file."):
        super().__init__(message=message, status_code=400, error_code="INVALID_ARCHIVE")


class AmbiguousArchiveError(GeospatialError):
    """Raised when an archive contains multiple shapefiles."""

    def __init__(self, message: str = "Ambiguous archive: multiple Shapefiles found. Exactly one Shapefile is required per archive."):
        super().__init__(message=message, status_code=400, error_code="AMBIGUOUS_ARCHIVE")


class UnsafeArchiveError(GeospatialError):
    """Raised when an archive member contains unsafe paths (path traversal / Zip Slip)."""

    def __init__(self, message: str = "ZIP archive contains unsafe path traversal members."):
        super().__init__(message=message, status_code=400, error_code="UNSAFE_ARCHIVE_PATH")


class MissingCRSError(GeospatialError):
    """Raised when the geospatial data does not specify a Coordinate Reference System."""

    def __init__(self, message: str = "Geospatial file does not define a Coordinate Reference System (CRS). An explicit CRS is required and cannot be assumed."):
        super().__init__(message=message, status_code=422, error_code="MISSING_CRS")


class EmptyDatasetError(GeospatialError):
    """Raised when the geospatial file contains no features."""

    def __init__(self, message: str = "Geospatial file contains no features or empty dataset."):
        super().__init__(message=message, status_code=422, error_code="EMPTY_DATASET")


class InvalidGeospatialDataError(GeospatialError):
    """Raised when the geospatial data cannot be parsed or contains invalid geometry."""

    def __init__(self, message: str = "Failed to parse geospatial data or invalid geometry encountered."):
        super().__init__(message=message, status_code=422, error_code="INVALID_GEOSPATIAL_DATA")
