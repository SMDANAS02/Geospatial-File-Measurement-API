# GeoMeasure API 🌍📐

A FastAPI backend and React + TypeScript frontend for uploading, validating, and measuring geospatial files. Accepts KML files and zipped ESRI Shapefiles, calculates polygon area and line length in metric units using a dynamically selected projected CRS, and persists results in SQLite.

Built as a portfolio project demonstrating geospatial data handling, security-conscious file processing, and API design in Python.

---

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [API Reference](#api-reference)
  - [Health](#health)
  - [Upload and Process a File](#1-upload-and-process-a-file)
  - [Get File Metadata](#2-get-file-metadata)
  - [Get Feature Measurements](#3-get-feature-measurements)
  - [Parse Without Persistence](#4-parse-without-persistence-preview)
- [Shapefile Upload Requirements](#shapefile-upload-requirements)
- [Supported Geometry Types](#supported-geometry-types)
- [CRS Handling Strategy](#crs-handling-strategy)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [File Processing Flow](#file-processing-flow)
- [Measurement Flow](#measurement-flow)
- [Error Codes Reference](#error-codes-reference)
- [Measurement Units and Precision](#measurement-units-and-precision)
- [Known Limitations](#known-limitations)
- [Design Decisions and Alternatives Considered](#design-decisions-and-alternatives-considered)
- [What I Learned](#what-i-learned)
- [Future Scope](#future-scope)
- [GitHub Submission Instructions](#github-submission-instructions)

---

## Features

- **Two supported input formats**: `.kml` (Google Earth KML) and `.zip` (zipped ESRI Shapefile set)
- **Strict validation**: Extension checking, empty file detection, size limits, corrupt archive detection, missing CRS rejection
- **Zip Slip protection**: Rejects archives containing path-traversal members (`../`, absolute paths, Windows drive paths)
- **Decompression bomb mitigation**: Rejects archives whose uncompressed total exceeds 150 MB (configurable)
- **XXE injection mitigation**: KML files containing `<!DOCTYPE>` or `<!ENTITY>` declarations are rejected before parsing
- **CRS enforcement**: Files without an explicit Coordinate Reference System are rejected with `422`. The API never silently assumes `EPSG:4326`
- **Metric measurement**: Geometries are reprojected to a locally-optimal projected CRS before computing area or length — never calculated in angular degrees
- **Per-feature fault tolerance**: Unsupported, empty, or invalid geometries report a per-feature status; the rest of the file still processes
- **Persistence**: File metadata and per-feature measurements stored in SQLite via SQLAlchemy
- **Paginated retrieval**: Feature measurements are returned page-by-page (default 50, max 500 per page)
- **Safe error responses**: Server filesystem paths are sanitized from all third-party driver error messages before being returned to clients
- **Interactive API docs**: FastAPI's built-in `/docs` (Swagger UI) and `/redoc`
- **React frontend**: Upload interface with drag-and-drop, results dashboard, feature filtering, and a property inspector

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| **API Framework** | FastAPI | ≥ 0.110.0 |
| **ASGI Server** | Uvicorn (with standard extras) | ≥ 0.28.0 |
| **Settings** | pydantic-settings | ≥ 2.2.0 |
| **Database ORM** | SQLAlchemy | ≥ 2.0.28 |
| **Database** | SQLite (file-based) | — |
| **Geospatial I/O** | GeoPandas + pyogrio | ≥ 1.0.0 / ≥ 0.9.0 |
| **Geometry Engine** | Shapely | ≥ 2.0.0 |
| **CRS / Projection** | pyproj | ≥ 3.6.0 |
| **Testing** | pytest + HTTPX | ≥ 8.0.0 / ≥ 0.27.0 |
| **Frontend** | React 19 + TypeScript 6 + Vite 8 | — |
| **Frontend Icons** | lucide-react | — |

---

## Prerequisites

- **Python 3.10+** (developed and tested on Python 3.14)
- **pip**
- **Node.js 18+** and **npm** (for the frontend)
- **Git**

> **Windows note**: The backend runs on Windows without any special configuration. All paths in tests and code use `pathlib.Path` for cross-platform compatibility.

---

## Quick Start

### Backend Setup

```powershell
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/geospatial-measurement-api.git
cd geospatial-measurement-api

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1       # PowerShell
# source .venv/bin/activate         # macOS / Linux

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Create your local environment file from the template
copy .env.example .env              # Windows
# cp .env.example .env              # macOS / Linux

# 5. Start the backend server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at:
- **API root**: http://127.0.0.1:8000
- **Interactive docs (Swagger UI)**: http://127.0.0.1:8000/docs
- **Alternative docs (ReDoc)**: http://127.0.0.1:8000/redoc
- **Health check**: http://127.0.0.1:8000/health

Verify the backend is running:
```powershell
curl http://127.0.0.1:8000/health
```

### Frontend Setup

Open a **separate terminal** in the `frontend/` directory:

```powershell
cd frontend
npm install
npm run dev
```

The frontend will start at **http://localhost:5173** and connects to the backend at `http://localhost:8000` by default. The API base URL can be changed in the frontend's settings panel if you are running the backend on a different port.

---

## Environment Variables

Copy `.env.example` to `.env` before starting the server. All variables have sensible defaults for local development.

```env
# Application Settings
PROJECT_NAME="Geospatial File Measurement API"
APP_ENV=development
DEBUG=true
API_V1_STR=/api/v1

# Database
# SQLite file path relative to working directory
DATABASE_URL=sqlite:///./geospatial.db

# CORS — comma-separated or JSON array of allowed frontend origins
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# File size limits
MAX_UPLOAD_SIZE_BYTES=52428800      # 50 MB (compressed upload limit)
MAX_UNCOMPRESSED_SIZE_BYTES=157286400  # 150 MB (decompression bomb limit)
```

| Variable | Default | Purpose |
|---|---|---|
| `PROJECT_NAME` | `Geospatial File Measurement API` | Shown in API docs title |
| `APP_ENV` | `development` | Included in health response |
| `DEBUG` | `true` | FastAPI debug mode |
| `API_V1_STR` | `/api/v1` | Versioned route prefix |
| `DATABASE_URL` | `sqlite:///./geospatial.db` | SQLAlchemy DB connection string |
| `CORS_ORIGINS` | localhost:3000 and 5173 | Allowed frontend origins |
| `MAX_UPLOAD_SIZE_BYTES` | `52428800` (50 MB) | Per-file compressed upload limit |
| `MAX_UNCOMPRESSED_SIZE_BYTES` | `157286400` (150 MB) | ZIP decompression bomb limit |

> **Note**: `.env` is listed in `.gitignore`. Never commit your `.env` file to version control.

---

## Running Tests

The full test suite requires the backend dependencies to be installed in the active virtual environment.

```powershell
# Run all tests with verbose output
pytest -v

# Run a single test file
pytest tests/test_health.py -v

# Run a specific test by name
pytest tests/test_measurements.py::test_polygon_and_multipolygon_area_calculation -v
```

**Current test results (36 tests):**

```
tests/test_health.py                    4 passed   Health endpoint, /api/v1, root, /docs
tests/test_geospatial.py               12 passed   KML, ZIP, CRS, traversal, corruption, cleanup
tests/test_files_api.py                 4 passed   Upload lifecycle, pagination, 404, invalid upload
tests/test_measurements.py              7 passed   Area, length, point N/A, UTM/LAEA, invalid geoms
tests/test_security_and_hardening.py    9 passed   XXE, zip bomb, traversal, path leaking, cleanup

Total: 36 passed, 0 failed
```

---

## API Reference

All endpoints return `Content-Type: application/json`. Error responses always include `detail` (human-readable) and `error_code` (machine-readable).

### Health

#### `GET /health`

Verifies that the application and the database are reachable.

```bash
curl http://127.0.0.1:8000/health
```

**Response `200 OK`:**
```json
{
  "status": "healthy",
  "timestamp": "2026-10-10T10:20:00.123456+00:00",
  "app_name": "Geospatial File Measurement API",
  "environment": "development",
  "version": "0.1.0",
  "database_status": "connected"
}
```

Also available at `/api/v1/health`.

---

### 1. Upload and Process a File

#### `POST /api/files/`

Uploads, validates, processes, and persists a KML or zipped Shapefile. Returns a generated file ID and processing summary.

**Request**: `multipart/form-data` with field `file`.

```bash
# Upload a KML file
curl -X POST http://127.0.0.1:8000/api/files/ \
  -F "file=@survey.kml"

# Upload a zipped Shapefile
curl -X POST http://127.0.0.1:8000/api/files/ \
  -F "file=@parcels.zip"
```

**Response `201 Created`:**
```json
{
  "id": "geo-a1b2c3d4e5f6",
  "filename": "survey.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "measurement_crs": "EPSG:32610",
  "status": "COMPLETED"
}
```

**Error responses:**

| Code | `error_code` | Cause |
|---|---|---|
| `400` | `UNSUPPORTED_FILE_TYPE` | Extension is not `.kml` or `.zip` |
| `400` | `EMPTY_FILE` | Uploaded file is 0 bytes |
| `400` | `INVALID_ARCHIVE` | ZIP is corrupt or contains no `.shp` |
| `400` | `AMBIGUOUS_ARCHIVE` | ZIP contains more than one `.shp` file |
| `400` | `UNSAFE_ARCHIVE_PATH` | ZIP member attempts path traversal |
| `413` | `FILE_SIZE_EXCEEDED` | File exceeds 50 MB, or uncompressed archive exceeds 150 MB |
| `422` | `MISSING_CRS` | Shapefile has no `.prj` or KML has no CRS |
| `422` | `EMPTY_DATASET` | File parsed successfully but contains 0 features |
| `422` | `INVALID_GEOSPATIAL_DATA` | Geometry data is unreadable or projection fails |

---

### 2. Get File Metadata

#### `GET /api/files/{id}/`

Returns stored metadata and aggregated measurement summary for a processed file.

```bash
curl http://127.0.0.1:8000/api/files/geo-a1b2c3d4e5f6/
```

**Response `200 OK`:**
```json
{
  "id": "geo-a1b2c3d4e5f6",
  "filename": "survey.kml",
  "file_type": "kml",
  "size_bytes": 2048,
  "feature_count": 2,
  "crs": "EPSG:4326",
  "source_crs": "EPSG:4326",
  "measurement_crs": "EPSG:32610",
  "projection_method": "Local UTM Zone 10N",
  "status": "COMPLETED",
  "created_at": "2026-10-10T10:20:00.000000+00:00",
  "summary_measurements": {
    "total_features": 2,
    "measured_polygons": 1,
    "total_area_m2": 82547823.45,
    "total_area_km2": 82.547823,
    "measured_lines": 0,
    "total_length_m": null,
    "total_length_km": null
  }
}
```

Returns `404` if the ID is not found.

---

### 3. Get Feature Measurements

#### `GET /api/files/{id}/measurements/`

Returns a paginated list of per-feature measurements, GeoJSON geometry, and attribute properties.

**Query parameters:**

| Parameter | Type | Default | Max | Description |
|---|---|---|---|---|
| `page` | integer | `1` | — | Page number (1-based) |
| `page_size` | integer | `50` | `500` | Features per page |

```bash
# First page, default size
curl "http://127.0.0.1:8000/api/files/geo-a1b2c3d4e5f6/measurements/"

# Second page, 10 items per page
curl "http://127.0.0.1:8000/api/files/geo-a1b2c3d4e5f6/measurements/?page=2&page_size=10"
```

**Response `200 OK`:**
```json
{
  "file_id": "geo-a1b2c3d4e5f6",
  "filename": "survey.kml",
  "total": 2,
  "page": 1,
  "page_size": 50,
  "pages": 1,
  "items": [
    {
      "feature_index": 0,
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-122.1, 37.4], [-122.0, 37.4],
            [-122.0, 37.5], [-122.1, 37.5],
            [-122.1, 37.4]
          ]
        ]
      },
      "properties": {
        "Name": "Parcel Alpha",
        "description": "Commercial site"
      },
      "measurement": {
        "status": "COMPLETED",
        "area_m2": 82547823.45,
        "area_km2": 82.547823,
        "length_m": null,
        "length_km": null,
        "unit": "m²",
        "notes": null
      }
    },
    {
      "feature_index": 1,
      "geometry_type": "Point",
      "geometry": {
        "type": "Point",
        "coordinates": [-122.05, 37.45]
      },
      "properties": {
        "Name": "Survey Benchmark"
      },
      "measurement": {
        "status": "NOT_APPLICABLE",
        "area_m2": null,
        "area_km2": null,
        "length_m": null,
        "length_km": null,
        "unit": null,
        "notes": "Measurement is not required: Points and MultiPoints do not have area or length dimensions."
      }
    }
  ]
}
```

Returns `404` if the file ID is not found.

---

### 4. Parse Without Persistence (Preview)

#### `POST /geospatial/parse`

Validates and parses a geospatial file, returning the full parsed response including features and measurements — without storing anything in the database. Useful for previewing results before deciding to persist.

```bash
curl -X POST http://127.0.0.1:8000/geospatial/parse \
  -F "file=@survey.kml"
```

The response structure is the same as the processing pipeline result, including `source_crs`, `measurement_crs`, `crs_info`, `features[]`, and `summary_measurements`. Also available at `/api/v1/geospatial/parse`.

---

## Shapefile Upload Requirements

An ESRI Shapefile is **not a single file** — it is always a set of related files that share the same base name and must be used together. This API requires the complete Shapefile set to be packaged as a single ZIP archive.

**Required components inside the ZIP:**

| Extension | Purpose |
|---|---|
| `.shp` | Geometry data |
| `.shx` | Geometry index |
| `.dbf` | Attribute data |
| `.prj` | Projection / Coordinate Reference System |

> **Without a `.prj` file the upload will be rejected with `422 MISSING_CRS`.**
> The API does not guess the CRS or silently default to `EPSG:4326`.

**How to create a valid Shapefile ZIP:**

```bash
# On Linux / macOS
zip parcels.zip parcels.shp parcels.shx parcels.dbf parcels.prj

# The ZIP must contain exactly one .shp file.
# Multiple .shp files in the same archive are rejected as ambiguous.
```

---

## Supported Geometry Types

| Geometry Type | Measurement | Fields Returned |
|---|---|---|
| `Polygon` | Area | `area_m2`, `area_km2` |
| `MultiPolygon` | Area | `area_m2`, `area_km2` |
| `LineString` | Length | `length_m`, `length_km` |
| `MultiLineString` | Length | `length_m`, `length_km` |
| `Point` | Not applicable | `status: NOT_APPLICABLE`, `notes` |
| `MultiPoint` | Not applicable | `status: NOT_APPLICABLE`, `notes` |
| `GeometryCollection` | Unsupported | `status: UNSUPPORTED`, `notes` |
| Empty geometry | Empty | `status: EMPTY_GEOMETRY`, `notes` |
| Invalid geometry (e.g. bowtie) | Invalid | `status: INVALID_GEOMETRY`, `notes` |

Unsupported or invalid geometries are reported at the **feature level**. The rest of the file continues to process normally — the entire request is not failed.

---

## CRS Handling Strategy

### Why reprojection is required

Geospatial datasets are often stored in a geographic CRS such as `EPSG:4326` (WGS 84 latitude/longitude). In a geographic CRS, coordinates are angular measurements in degrees, not linear distances. Computing `.area` or `.length` directly on geographic coordinates produces values in square degrees or degrees — which are geometrically meaningless for measurement purposes.

The API always reprojects geometries into a locally-appropriate **projected metric CRS** before calculating area or length.

### Projection selection algorithm

The projected CRS is selected by analysing the geographic bounding box of the dataset:

```
Dataset CRS → Reproject bounds to EPSG:4326 → Compute centre lat/lon and span

  If centre_lat > 84°N            → UPS North (EPSG:32661)
  Elif centre_lat < -80°S         → UPS South (EPSG:32761)
  Elif lon_span > 6° or lat_span > 15° → Centred Lambert Azimuthal Equal Area (LAEA)
  Else                             → Local UTM Zone (EPSG:326xx / 327xx)
```

### Projection details and limitations

| Condition | Projection | EPSG / Definition | Limitations |
|---|---|---|---|
| Polar (centre > 84°N) | Universal Polar Stereographic North | `EPSG:32661` | Scale factor grows away from the pole |
| Polar (centre < 80°S) | Universal Polar Stereographic South | `EPSG:32761` | Scale factor grows away from the pole |
| Wide-area (lon span > 6° or lat span > 15°) | Centred Lambert Azimuthal Equal Area | Custom PROJ4 `+proj=laea` | Preserves true area; introduces shape/angular distortion away from the centre |
| Compact (lon span ≤ 6°, between 80°S–84°N) | Local UTM Zone | `EPSG:326xx` / `EPSG:327xx` | <0.1% distortion within the 6° strip; must not be used for multi-zone datasets |

**Key limitation**: This strategy is designed for local and regional datasets. A single file spanning multiple continents, or datasets that cross UTM zone boundaries by more than 6° of longitude, will be assigned the LAEA projection. LAEA preserves area faithfully for such datasets but introduces angular and shape distortion.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Client (Browser / curl)                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP (multipart/form-data or JSON)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI Application                      │
│                                                              │
│  ┌────────────┐  ┌──────────────────┐  ┌───────────────────┐ │
│  │ /health    │  │  /api/files/     │  │ /geospatial/parse │ │
│  │ (Router)   │  │  (Router)        │  │ (Router)          │ │
│  └────────────┘  └────────┬─────────┘  └────────┬──────────┘ │
│                           │                     │            │
│                  ┌────────▼─────────────────────▼──────┐     │
│                  │       GeospatialService              │     │
│                  │  1. read_upload_file_safely()        │     │
│                  │  2. validate_file_metadata()         │     │
│                  │  3. validate_kml_content()           │     │
│                  │     OR validate_and_extract_zip()    │     │
│                  │  4. geopandas.read_file()            │     │
│                  │  5. parse_geodataframe()             │     │
│                  │     └─ select_measurement_crs()      │     │
│                  │     └─ gdf.to_crs()                  │     │
│                  │     └─ calculate_feature_measurement()│     │
│                  └────────────────────┬────────────────-┘     │
│                                       │                       │
│                  ┌────────────────────▼────────────────┐      │
│                  │       SQLAlchemy ORM                 │      │
│                  │  StoredFile + StoredFeature models   │      │
│                  └────────────────────┬────────────────-┘      │
└──────────────────────────────────────┼───────────────────────┘
                                       │
                           ┌───────────▼───────────┐
                           │    SQLite Database     │
                           │    (geospatial.db)     │
                           └───────────────────────┘
```

---

## Project Structure

```text
geospatial-measurement-api/
│
├── app/
│   ├── __init__.py              Package version
│   ├── config.py                pydantic-settings: all env vars with defaults
│   ├── database.py              SQLAlchemy engine, session maker, Base, get_db()
│   ├── exceptions.py            Domain exception hierarchy (GeospatialError subclasses)
│   ├── models.py                StoredFile and StoredFeature ORM models
│   ├── schemas.py               Pydantic request/response schemas
│   ├── main.py                  FastAPI app: lifespan, CORS, exception handlers, routers
│   │
│   ├── routers/
│   │   ├── health.py            GET /health — DB ping and app status
│   │   ├── files.py             POST /api/files/, GET /api/files/{id}/, GET /api/files/{id}/measurements/
│   │   └── geospatial.py        POST /geospatial/parse — stateless parse/preview endpoint
│   │
│   └── services/
│       ├── geospatial.py        Core: validation, extraction, GeoPandas reading, measurement
│       └── projections.py       CRS selection logic: UTM / LAEA / UPS strategy
│
├── tests/
│   ├── conftest.py              Session-scoped DB setup fixture
│   ├── test_health.py           Health, root, docs endpoints
│   ├── test_geospatial.py       Upload validation, ZIP safety, CRS enforcement, cleanup
│   ├── test_files_api.py        Persistence lifecycle, pagination, 404, error cases
│   ├── test_measurements.py     Area, length, point N/A, UTM/LAEA, invalid geom cases
│   └── test_security_and_hardening.py  XXE, zip bomb, traversal, path leaking, cleanup
│
├── frontend/
│   ├── src/
│   │   ├── api.ts               Typed API client (configurable base URL)
│   │   ├── types.ts             TypeScript interfaces matching API response shapes
│   │   ├── App.tsx              Main application: upload, results, feature inspector
│   │   ├── index.css            Design system (CSS custom properties, layout, components)
│   │   └── main.tsx             React entry point
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── .env.example                 Template — copy to .env before running
├── .gitignore                   Excludes .env, *.db, .venv, node_modules, dist
├── requirements.txt             Pinned Python dependencies
└── README.md                    This file
```

---

## File Processing Flow

```
Client uploads file (multipart/form-data)
         │
         ▼
read_upload_file_safely()
  → Streams file in 1 MB chunks
  → Aborts immediately if total bytes > MAX_UPLOAD_SIZE_BYTES (50 MB)
         │
         ▼
validate_file_metadata()
  → Confirms filename and extension are present
  → Accepts only .kml or .zip
  → Rejects 0-byte files
         │
    ┌────┴──────────────────┐
    │                       │
    ▼ (.zip)                ▼ (.kml)
validate_and_extract_zip()  validate_kml_content()
  → Opens in-memory          → Checks for binary content
  → Checks total             → Rejects <!DOCTYPE> / <!ENTITY> (XXE)
    uncompressed size        → Verifies XML is well-formed
  → Inspects each member:    → Saves to temp dir
    - Rejects absolute paths
    - Rejects ../traversal
    - Rejects symlinks
  → Confirms exactly 1 .shp
  → Confirms .shp is non-empty
  → Extracts to temp dir
         │
         ▼
geopandas.read_file()  (via pyogrio engine)
  → Reads CRS, geometries, attributes
  → Driver errors are sanitized before returning to client
         │
         ▼
parse_geodataframe()
  → Rejects None CRS (MISSING_CRS)
  → Rejects 0-feature datasets (EMPTY_DATASET)
  → Selects measurement CRS via select_measurement_crs()
  → Reprojects to metric CRS
  → Iterates features → calculate_feature_measurement() per feature
  → Sanitizes properties: NaN → null, datetime → ISO string, etc.
         │
         ▼
Persist to SQLite (files endpoint only)
  → StoredFile record (metadata + summary JSON)
  → StoredFeature records (one per feature)
         │
         ▼
Return response to client
  → /api/files/ → FileUploadResponse (201)
  → /geospatial/parse → ParsedGeospatialResponse (200, not persisted)

Temp directory is deleted by context manager (success AND failure)
```

---

## Measurement Flow

```
For each feature:

  orig_geom = source geometry (in original CRS)
  proj_geom = same geometry reprojected to metric CRS

  If orig_geom is None or empty:
      → status: "empty_geometry"

  Elif not orig_geom.is_valid:
      → status: "invalid_geometry"
      → note: explain_validity(geom)

  Elif geom_type in (Polygon, MultiPolygon):
      area_m2  = proj_geom.area          ← Shapely area in m²
      area_km2 = area_m2 / 1_000_000
      → status: "success" (or "COMPLETED" when persisted)

  Elif geom_type in (LineString, MultiLineString):
      length_m  = proj_geom.length       ← Shapely length in m
      length_km = length_m / 1_000
      → status: "success"

  Elif geom_type in (Point, MultiPoint):
      → status: "not_applicable"
      → notes: "Measurement is not required..."

  Else (GeometryCollection, etc.):
      → status: "unsupported"
```

---

## Error Codes Reference

| `error_code` | HTTP Status | Meaning |
|---|---|---|
| `UNSUPPORTED_FILE_TYPE` | 400 | Extension is not `.kml` or `.zip` |
| `EMPTY_FILE` | 400 | File content is 0 bytes |
| `INVALID_ARCHIVE` | 400 | ZIP is not valid, or contains no `.shp` |
| `AMBIGUOUS_ARCHIVE` | 400 | ZIP contains more than one `.shp` |
| `UNSAFE_ARCHIVE_PATH` | 400 | ZIP member has a path traversal pattern |
| `FILE_SIZE_EXCEEDED` | 413 | Upload > 50 MB or uncompressed > 150 MB |
| `MISSING_CRS` | 422 | No CRS defined in the file |
| `EMPTY_DATASET` | 422 | File parsed but contains 0 features |
| `INVALID_GEOSPATIAL_DATA` | 422 | Data is unreadable, malformed, or projection fails |
| `GEOSPATIAL_ERROR` | 400 | Generic geospatial domain error (base class) |

All error responses follow this shape:

```json
{
  "detail": "Human-readable explanation of what went wrong.",
  "error_code": "MACHINE_READABLE_CODE"
}
```

---

## Measurement Units and Precision

| Geometry | Field | Unit | Decimal places |
|---|---|---|---|
| Polygon / MultiPolygon | `area_m2` | Square metres (m²) | 2 |
| Polygon / MultiPolygon | `area_km2` | Square kilometres (km²) | 6 |
| LineString / MultiLineString | `length_m` | Metres (m) | 2 |
| LineString / MultiLineString | `length_km` | Kilometres (km) | 5 |
| Point / MultiPoint | all fields | `null` | — |

---

## Known Limitations

1. **Local/regional CRS accuracy**: The UTM projection provides excellent metric fidelity within a 6° longitude corridor. For datasets spanning multiple UTM zones, LAEA is used instead, which preserves area but introduces angular distortion away from the projection centre.

2. **Global datasets**: This CRS selection strategy works well for city, regional, and national datasets. It is not designed for planetary or global-scale datasets that span more than one hemisphere.

3. **Polar edge cases**: The UPS projections handle centre latitudes above 84°N or below 80°S, but the transition boundary between UTM and UPS is approximate and may produce slightly different results than purpose-built polar GIS software.

4. **GeometryCollection**: This geometry type is detected and reported as `UNSUPPORTED` at the feature level rather than failing the entire request. A `GeometryCollection` that mixes polygon and line rings does not clearly belong to either measurement category.

5. **Single Shapefile per ZIP**: The archive must contain exactly one `.shp` file. Multiple Shapefiles in a single ZIP are rejected. This is a deliberate design constraint — it avoids silent selection ambiguity.

6. **KML style data**: KML feature properties (e.g. `<StyleUrl>`, `<ExtendedData>`) are extracted as raw text strings. Complex nested `ExtendedData` is not structurally parsed.

7. **SQLite concurrency**: SQLite is suitable for single-user local development and portfolio use. High-concurrency write workloads require switching to PostgreSQL.

8. **No authentication**: This API has no auth layer. It is intended for local development and portfolio demonstration only.

9. **In-memory file streaming**: Uploaded files are streamed into memory in 1 MB chunks up to the 50 MB limit. A production deployment should use a streaming upload to a temporary disk location instead.

---

## Design Decisions and Alternatives Considered

### FastAPI over Flask or Django REST Framework

FastAPI was selected because it generates interactive OpenAPI documentation (`/docs`, `/redoc`) automatically from type annotations and Pydantic schemas. This is directly useful for a portfolio API — reviewers can test endpoints without a separate client tool. It also supports async handlers natively, which is relevant for streaming uploads.

Flask would require third-party libraries (Flask-RESTX or Marshmallow) to get equivalent documentation generation. Django REST Framework was not selected because it carries a much heavier setup cost for a single-service API with no Django admin or ORM management commands needed.

### GeoPandas for geospatial I/O

GeoPandas was chosen because it reads KML and Shapefiles through a single API (`gpd.read_file()`), is CRS-aware, and integrates directly with Shapely for geometry operations and pyproj for CRS reprojection. This allowed the entire validation, parsing, and measurement pipeline to be expressed concisely without building geometry object models from scratch.

An alternative was to use `fiona` directly (GeoPandas's prior default I/O backend). `pyogrio` was chosen as the engine instead because it is consistently faster and recommended by GeoPandas for new projects.

### SQLite over PostgreSQL/PostGIS

SQLite was selected for zero-friction local setup. A reviewer cloning this repository can run the backend immediately without installing a database server.

The database URL is fully configurable via the `DATABASE_URL` environment variable. Switching to PostgreSQL for a production deployment requires only:
1. `pip install psycopg2-binary`
2. Setting `DATABASE_URL=postgresql://user:password@host/dbname` in `.env`

For geospatial persistence and spatial queries, PostgreSQL + PostGIS would be the natural upgrade path — enabling geometry storage in `GEOMETRY` columns, spatial index queries, and server-side bounding box filtering.

### Dynamic CRS selection over a fixed projection

A fixed global projection (e.g. Web Mercator / EPSG:3857 or Equal Earth) was considered. The problem with any single global projection is that its distortion characteristics are uneven across the Earth's surface. Web Mercator in particular produces extremely inflated areas near the poles.

The dynamic UTM / LAEA / UPS selection approach acknowledges that the best metric projection depends on where the data is located. For the expected use case (city, regional, or national datasets), UTM provides near-perfect metric fidelity within its local zone. LAEA is applied automatically for datasets that span multiple zones. The strategy and its limitations are documented alongside the measurements in the response.

### Per-feature failure isolation over all-or-nothing

Early drafts failed the entire request if any single feature had an unsupported geometry type or an invalid geometry. This was changed to per-feature status codes (`UNSUPPORTED`, `INVALID_GEOMETRY`, `EMPTY_GEOMETRY`) so that a dataset containing mostly valid polygons is not rejected because one incidental feature has a bad geometry.

### Custom exception hierarchy

A `GeospatialError` base class with HTTP status code and `error_code` attributes was introduced rather than raising `HTTPException` directly inside service code. This keeps service functions free of FastAPI dependencies and makes the error types testable without running an HTTP server. A single exception handler in `main.py` converts them to JSON responses.

---

## What I Learned

**Geospatial projection is not optional for measurements.** Early in the project I naively assumed a CRS check would be enough. Testing quickly revealed that calling `.area` on an `EPSG:4326` polygon returns a value in square degrees — a physically meaningless number. The deliberate rejection of files with no CRS, and the forced reprojection before any calculation, came directly from understanding this failure mode.

**ZIP security is genuinely complex.** Path traversal in archives ("Zip Slip") requires checking multiple attack vectors: `../` in path components, absolute Unix paths starting with `/`, Windows drive paths containing `:`, and symbolic links via external file attributes. Python's `zipfile` module does not prevent any of these by default.

**Pydantic settings simplify configuration hygiene significantly.** Having a single `Settings` class with field types, defaults, and environment variable loading in one place made it easy to add new configurable limits (e.g. `MAX_UNCOMPRESSED_SIZE_BYTES`) without scattering `os.getenv()` calls throughout the code.

**Third-party library error messages are not safe to return directly.** GeoPandas and pyogrio sometimes include temporary file paths in their exception strings. A sanitization step (`sanitize_driver_error()`) was needed to remove these before returning errors to API clients.

**Test design shapes the API contract.** Writing tests before the final API shapes forced decisions about what "success" and "failure" mean from the outside. For example, the decision to use machine-readable `error_code` fields in every error response was driven by the test assertions that check for specific codes rather than brittle string matching on `detail`.

---

## Future Scope

| Area | Improvement |
|---|---|
| **Streaming uploads** | Pipe uploads to disk rather than accumulating in memory |
| **Authentication** | API key or OAuth2 to restrict write access |
| **PostgreSQL + PostGIS** | Enable spatial index queries and server-side bounding box filtering |
| **Perimeter calculation** | Add perimeter (boundary length) for polygons as an additional measurement |
| **Async processing** | Move file processing to a background task queue (Celery / ARQ) for large files |
| **GeoJSON input** | Accept `.geojson` files directly as an additional input format |
| **Raster support** | Add area calculation for raster masks (e.g. `.tif` via rasterio) |
| **CRS override** | Allow an authenticated user to assert a CRS for undeclared files |
| **Frontend map preview** | Render feature geometries on a Leaflet/MapLibre map |
| **Docker Compose** | Package backend, frontend, and a database into a single `docker compose up` |
| **Deployment** | Cloud Run / Railway / Render deployment guide |

---

## GitHub Submission Instructions

### Before pushing

Verify that sensitive and generated files are excluded:

```powershell
# Check nothing sensitive is staged
git status

# These should NOT appear in git status as tracked files:
#   .env
#   geospatial.db  (or any *.db)
#   .venv/
#   frontend/node_modules/
#   frontend/dist/
#   __pycache__/
#   .pytest_cache/
```

Check `.gitignore` covers them:

```powershell
git check-ignore -v .env
git check-ignore -v geospatial.db
git check-ignore -v .venv
```

### Initial push

```bash
git init
git add .
git commit -m "Initial commit: GeoMeasure API — all phases complete"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/geospatial-measurement-api.git
git branch -M main
git push -u origin main
```

### Verify the published repository

After pushing, visit the repository on GitHub and confirm:

- [ ] `.env` is **not** present (only `.env.example`)
- [ ] `geospatial.db` is **not** present
- [ ] `.venv/` is **not** present
- [ ] `frontend/node_modules/` is **not** present
- [ ] `frontend/dist/` is **not** present
- [ ] `README.md` renders correctly with the table of contents and code blocks

### For a reviewer

A reviewer with Python 3.10+ and Node.js 18+ should be able to get the project running in under five minutes by following the [Quick Start](#quick-start) section. The full test suite runs in approximately 4–5 seconds:

```powershell
# After setup
pytest -v        # All 36 tests should pass
```

Interactive API testing is available at http://127.0.0.1:8000/docs once the backend is running.
