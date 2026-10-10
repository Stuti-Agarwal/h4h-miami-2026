"""Download Miami-Dade street lights, bus stops and 2021 land cover for the demo area into data/."""
import json
import pathlib
import urllib.parse
import urllib.request

BBOX = (-80.212, 25.765, -80.184, 25.807)  # keep in sync with fetch_overture.py
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
ARCGIS = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services"
LAYERS = {
    "lights": f"{ARCGIS}/StreetLightInventory_gdb/FeatureServer/0",
    "stops": f"{ARCGIS}/Bus_Stop_Maintenance_View_Layer/FeatureServer/1",
}
LANDCOVER = "https://gisweb.miamidade.gov/arcgis/rest/services/UrbanTreeCanopy/LandCover_2021/ImageServer/exportImage"


def get(url, params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=120) as r:
        return r.read()


def fetch_layer(url):
    features, offset = [], 0
    while True:
        page = json.loads(get(f"{url}/query", {
            "where": "1=1", "outFields": "*", "f": "geojson", "outSR": 4326,
            "geometry": ",".join(map(str, BBOX)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "resultOffset": offset, "resultRecordCount": 1000,
        }))
        features += page["features"]
        if len(page["features"]) < 1000:
            return features
        offset += 1000


def main():
    for name, url in LAYERS.items():
        features = fetch_layer(url)
        (DATA / f"{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))
        print(name, len(features))
    # Nearest-neighbour keeps class codes intact. ~2 m pixels.
    # Codes: 0 nodata, 1 impervious, 2 road, 3 bare, 4 building, 5 grass, 6 tree, 7 wetland, 8 water, 9 cropland
    (DATA / "landcover.tif").write_bytes(get(LANDCOVER, {
        "bbox": ",".join(map(str, BBOX)), "bboxSR": 4326, "imageSR": 4326, "size": "1400,2100",
        "format": "tiff", "pixelType": "U8", "interpolation": "RSP_NearestNeighbor", "noData": 0, "f": "image",
    }))
    print("landcover.tif ok")


if __name__ == "__main__":
    main()
