# Geospatial Sample Datasets

This directory contains pre-built, standards-compliant geospatial sample files used for integration testing and live demonstration.

## Included Files

### 1. `new_york_central_park.kml`
- **Format**: OGC KML 2.2 (`.kml`)
- **Location**: Manhattan, New York, United States
- **Source CRS**: EPSG:4326 (WGS 84 Geographic)
- **Computed Metric CRS**: EPSG:32618 (UTM Zone 18N)
- **Features**:
  1. `Central Park Boundary` (Polygon): Area ≈ 3,504,518 m² (3.50 km²)
  2. `Reservoir Running Track` (LineString): Length ≈ 1,715 m (1.72 km)
  3. `Bethesda Terrace & Fountain` (Point): Zero-dimensional point marker (`NOT_APPLICABLE`)

### 2. `taj_mahal_heritage.kml`
- **Format**: OGC KML 2.2 (`.kml`)
- **Location**: Agra, Uttar Pradesh, India
- **Source CRS**: EPSG:4326 (WGS 84 Geographic)
- **Computed Metric CRS**: EPSG:32644 (UTM Zone 44N)
- **Features**:
  1. `Taj Mahal Charbagh Gardens Complex` (Polygon): Area ≈ 134,299 m² (0.134 km²)
  2. `Yamuna Riverbank Promenade` (LineString): Length ≈ 744 m (0.74 km)
  3. `Main Marble Dome Center` (Point): Heritage marker (`NOT_APPLICABLE`)

### 3. `paris_gardens_shapefile.zip`
- **Format**: ESRI Shapefile Archive (`.zip`) containing `.shp`, `.shx`, `.dbf`, `.prj`
- **Location**: Paris, France
- **Source CRS**: EPSG:4326 (with explicit WKT PRJ definition)
- **Computed Metric CRS**: EPSG:32631 (UTM Zone 31N)
- **Features**:
  1. `Champ de Mars Parklands` (Polygon): Area ≈ 226,358 m² (0.226 km²)
  2. `Jardins du Trocadéro` (Polygon): Area ≈ 197,120 m² (0.197 km²)
  3. `Esplanade des Invalides` (Polygon): Area ≈ 243,892 m² (0.244 km²)
