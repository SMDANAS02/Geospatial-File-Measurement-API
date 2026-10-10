from dataclasses import dataclass
from typing import Optional
import geopandas as gpd
import numpy as np
from pyproj import CRS

from app.exceptions import MissingCRSError


@dataclass
class SelectedCRS:
    """Represents a chosen measurement projected CRS with justification and limits."""
    crs: CRS
    crs_str: str
    projection_method: str
    selection_reason: str
    limitations: str


def select_measurement_crs(gdf: gpd.GeoDataFrame) -> SelectedCRS:
    """
    Select an optimal projected metric CRS based on dataset extent.

    Strategy:
    1. Determine geographic bounds in EPSG:4326.
    2. Polar regions (|lat| > 80°): Use Universal Polar Stereographic (UPS)
       North (EPSG:32661) or South (EPSG:32761).
    3. Wide-area or Multi-zone extents (lon span > 6.0°): Use centered
       Lambert Azimuthal Equal Area (LAEA). This preserves true surface area
       without the severe scale distortions caused by forcing wide extents into a single UTM strip.
    4. Compact extents (lon span <= 6.0° between 80°S and 84°N): Use the local
       standard UTM Zone, which has minimal distortion (<0.1%) within its 6° corridor.
    """
    if gdf.crs is None or not str(gdf.crs).strip():
        raise MissingCRSError("Cannot select measurement CRS: Source dataset lacks a Coordinate Reference System.")

    # Convert extent to WGS84 for geographic coordinate analysis
    try:
        if gdf.crs.to_epsg() == 4326:
            gdf_wgs84 = gdf
        else:
            gdf_wgs84 = gdf.to_crs("EPSG:4326")
        
        total_bounds = gdf_wgs84.total_bounds
        if len(total_bounds) != 4 or any(np.isnan(total_bounds)):
            raise ValueError("Invalid bounding coordinates")
            
        minx, miny, maxx, maxy = total_bounds
        center_lon = (minx + maxx) / 2.0
        center_lat = (miny + maxy) / 2.0
        lon_span = abs(maxx - minx)
        lat_span = abs(maxy - miny)
    except Exception:
        # Fallback to center point or equator if transformation encounters issues
        minx, miny, maxx, maxy = -180.0, -80.0, 180.0, 80.0
        center_lon, center_lat = 0.0, 0.0
        lon_span, lat_span = 360.0, 160.0

    # 1. Polar regions
    if center_lat > 84.0:
        target_crs = CRS.from_epsg(32661)
        return SelectedCRS(
            crs=target_crs,
            crs_str="EPSG:32661",
            projection_method="Universal Polar Stereographic (UPS North)",
            selection_reason=(
                f"Dataset center latitude ({center_lat:.2f}°N) exceeds 84°N where standard UTM is mathematically undefined. "
                "Universal Polar Stereographic North was selected."
            ),
            limitations=(
                "UPS maintains conformal shape in the Arctic, but scale distortion increases with distance from the North Pole."
            ),
        )
    elif center_lat < -80.0:
        target_crs = CRS.from_epsg(32761)
        return SelectedCRS(
            crs=target_crs,
            crs_str="EPSG:32761",
            projection_method="Universal Polar Stereographic (UPS South)",
            selection_reason=(
                f"Dataset center latitude ({center_lat:.2f}°S) lies south of 80°S where standard UTM is mathematically undefined. "
                "Universal Polar Stereographic South was selected."
            ),
            limitations=(
                "UPS maintains conformal shape in the Antarctic, but scale distortion increases with distance from the South Pole."
            ),
        )

    # 2. Wide-area extent (> 6° longitude span or global dataset)
    if lon_span > 6.0 or lat_span > 15.0:
        proj4_str = (
            f"+proj=laea +lat_0={center_lat:.4f} +lon_0={center_lon:.4f} "
            "+datum=WGS84 +units=m +no_defs"
        )
        target_crs = CRS.from_proj4(proj4_str)
        return SelectedCRS(
            crs=target_crs,
            crs_str=f"Custom-LAEA(lat_0={center_lat:.2f},lon_0={center_lon:.2f})",
            projection_method="Centered Lambert Azimuthal Equal Area (LAEA)",
            selection_reason=(
                f"Dataset span ({lon_span:.2f}° longitude, {lat_span:.2f}° latitude) exceeds the 6° width of a standard UTM zone. "
                "Centered Lambert Azimuthal Equal Area (LAEA) was selected to preserve true surface area across wide extents."
            ),
            limitations=(
                "LAEA preserves true geographic area across large regions with zero area distortion, "
                f"but introduces shape and directional distortion away from the projection center ({center_lat:.2f}°, {center_lon:.2f}°)."
            ),
        )

    # 3. Compact extent: Local standard UTM zone
    zone = int((center_lon + 180.0) // 6.0) + 1
    zone = max(1, min(60, zone))
    epsg_code = (32600 + zone) if center_lat >= 0 else (32700 + zone)
    target_crs = CRS.from_epsg(epsg_code)
    hemi = "N" if center_lat >= 0 else "S"

    return SelectedCRS(
        crs=target_crs,
        crs_str=f"EPSG:{epsg_code}",
        projection_method=f"Local UTM Zone {zone}{hemi}",
        selection_reason=(
            f"Compact dataset within a single 6° longitude strip ({lon_span:.2f}° span, center at {center_lon:.2f}° lon, {center_lat:.2f}° lat). "
            f"Local UTM Zone {zone}{hemi} (EPSG:{epsg_code}) provides high metric fidelity in metres."
        ),
        limitations=(
            f"UTM Zone {zone}{hemi} is optimized for local areas within its 6° longitudinal strip (central scale factor 0.9996). "
            "Scale distortion increases up to ~0.1% near the outer boundary of the zone and should not be used for continental-scale data."
        ),
    )
