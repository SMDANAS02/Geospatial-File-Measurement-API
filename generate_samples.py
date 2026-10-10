
"""
Script to generate realistic, accurate geospatial sample datasets:
1. new_york_central_park.kml - New York Central Park perimeter, reservoir loop, and Bethesda fountain.
2. taj_mahal_heritage.kml - Taj Mahal complex quadrangle, Yamuna riverfront, and main dome.
3. paris_eiffel_champ_de_mars.zip - Complete Shapefile archive of Champ de Mars & Pont d'Iena in Paris.
"""
import os
import zipfile
import geopandas as gpd
from shapely.geometry import Polygon, LineString, Point

os.makedirs("samples", exist_ok=True)

# =====================================================================
# 1. New York Central Park (KML)
# =====================================================================
central_park_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>New York Central Park &amp; Landmarks</name>
    <description>Central Park perimeter boundary, reservoir running loop, and Bethesda Terrace in Manhattan, New York.</description>
    <Placemark>
      <name>Central Park Boundary</name>
      <description>The world-famous 843-acre urban park in Manhattan.</description>
      <Polygon>
        <extrude>0</extrude>
        <tessellate>1</tessellate>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -73.981886,40.768095,0.0
              -73.958043,40.800569,0.0
              -73.949280,40.796853,0.0
              -73.973059,40.764379,0.0
              -73.981886,40.768095,0.0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Reservoir Running Track</name>
      <description>Jacqueline Kennedy Onassis Reservoir popular 2.5km running track.</description>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>
          -73.963289,40.784232,0.0
          -73.959255,40.789124,0.0
          -73.957539,40.787693,0.0
          -73.961315,40.782801,0.0
          -73.963289,40.784232,0.0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Bethesda Terrace &amp; Fountain</name>
      <description>Architectural heart of Central Park overlooking the Lake.</description>
      <Point>
        <coordinates>-73.971166,40.773828,0.0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

with open("samples/new_york_central_park.kml", "w", encoding="utf-8") as f:
    f.write(central_park_kml)
print("[OK] Created samples/new_york_central_park.kml")

# =====================================================================
# 2. Taj Mahal Heritage Complex (KML)
# =====================================================================
taj_mahal_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Taj Mahal UNESCO World Heritage Complex</name>
    <description>Monumental complex and gardens on the south bank of the Yamuna River in Agra, India.</description>
    <Placemark>
      <name>Taj Mahal Charbagh Gardens Complex</name>
      <description>The walled monumental complex including the Mughal four-quadrant garden (Charbagh).</description>
      <Polygon>
        <extrude>0</extrude>
        <tessellate>1</tessellate>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              78.040210,27.173150,0.0
              78.040210,27.176250,0.0
              78.044150,27.176250,0.0
              78.044150,27.173150,0.0
              78.040210,27.173150,0.0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Yamuna Riverbank Promenade</name>
      <description>Northern riverside walkway bordering the Yamuna riverfront.</description>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>
          78.038500,27.176300,0.0
          78.042180,27.176400,0.0
          78.046000,27.176200,0.0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Main Marble Dome Center</name>
      <description>Center point of the white marble dome mausoleum.</description>
      <Point>
        <coordinates>78.042142,27.175015,0.0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

with open("samples/taj_mahal_heritage.kml", "w", encoding="utf-8") as f:
    f.write(taj_mahal_kml)
print("[OK] Created samples/taj_mahal_heritage.kml")

# =====================================================================
# 3. Paris Landmarks & Gardens (Zipped Shapefile - homogeneous Polygons per ESRI spec)
champ_de_mars_poly = Polygon([
    (2.2933, 48.8556),
    (2.2985, 48.8582),
    (2.3050, 48.8535),
    (2.2998, 48.8509),
    (2.2933, 48.8556),
])

trocadero_poly = Polygon([
    (2.2850, 48.8610),
    (2.2895, 48.8635),
    (2.2930, 48.8605),
    (2.2885, 48.8580),
    (2.2850, 48.8610),
])

esplanade_poly = Polygon([
    (2.3080, 48.8570),
    (2.3140, 48.8600),
    (2.3180, 48.8560),
    (2.3120, 48.8530),
    (2.3080, 48.8570),
])

gdf = gpd.GeoDataFrame(
    {
        "name": ["Champ de Mars Parklands", "Jardins du Trocadero", "Esplanade des Invalides"],
        "category": ["Public Green Space", "Fountain Gardens", "Historic Esplanade"],
        "city": ["Paris", "Paris", "Paris"],
        "country": ["France", "France", "France"],
    },
    geometry=[champ_de_mars_poly, trocadero_poly, esplanade_poly],
    crs="EPSG:4326"
)

temp_shp_dir = "samples/temp_paris_shp"
os.makedirs(temp_shp_dir, exist_ok=True)
shp_path = os.path.join(temp_shp_dir, "paris_gardens.shp")
gdf.to_file(shp_path)

zip_path = "samples/paris_gardens_shapefile.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for filename in os.listdir(temp_shp_dir):
        full_p = os.path.join(temp_shp_dir, filename)
        zf.write(full_p, arcname=filename)
        os.remove(full_p)
os.rmdir(temp_shp_dir)

print("[OK] Created samples/paris_gardens_shapefile.zip")
print("[ALL SAMPLES READY IN samples/]")
