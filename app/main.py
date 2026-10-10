from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import Base, engine
from app.exceptions import GeospatialError
from app import models
from app.routers import files, geospatial, health
from app.schemas import RootResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown tasks."""
    # Ensure database tables exist upon startup
    Base.metadata.create_all(bind=engine)
    yield


tags_metadata = [
    {
        "name": "Health",
        "description": "System health and connectivity verification endpoints.",
    },
    {
        "name": "Files & Measurements",
        "description": "Endpoints to upload, persist, and retrieve geospatial files and calculated measurements.",
    },
    {
        "name": "Geospatial Processing",
        "description": "Validation, extraction, and parsing of geospatial datasets (KML and zipped Shapefiles).",
    },
    {
        "name": "General",
        "description": "General application information.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
# GeoMeasure API 🌍📐

A RESTful backend service designed to safely parse and process geospatial files (KML, zipped Shapefiles) and compute measurements in metric units.

## Core Capabilities:
* **Persistence & Retrieval**: Store file metadata and individual feature measurements in SQLite.
* **Format Validation**: Strict validation for `.kml` and `.zip` Shapefiles.
* **Archive Security**: Defense against Zip Slip traversal attacks and decompression bombs.
* **Strict CRS Enforcement**: Rejects unprojected files without assuming EPSG:4326.
* **Metric Calculations**: Reprojects to optimal projected CRS for accurate area and length measurements.
* **Resource Cleanup**: Guaranteed removal of all temporary processing artifacts.
    """,
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


@app.exception_handler(GeospatialError)
async def geospatial_error_handler(request: Request, exc: GeospatialError):
    """Ensure all geospatial domain validation errors return readable JSON responses without leaking stack traces."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
        },
    )


# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(health.router, prefix=settings.API_V1_STR)

# Files & Measurements API (POST /api/files/, GET /api/files/{id}/, GET /api/files/{id}/measurements/)
app.include_router(files.router, prefix="/api")
app.include_router(files.router, prefix=settings.API_V1_STR)

app.include_router(geospatial.router)
app.include_router(geospatial.router, prefix=settings.API_V1_STR)


@app.get("/", response_model=RootResponse, tags=["General"], summary="API Root")
def get_root() -> RootResponse:
    """Root endpoint welcoming clients and directing to docs and health checks."""
    return RootResponse(
        message=f"Welcome to {settings.PROJECT_NAME}",
        docs_url="/docs",
        health_url="/health",
    )
