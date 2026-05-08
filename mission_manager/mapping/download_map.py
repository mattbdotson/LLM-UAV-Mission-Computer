import requests
import math
import os
from PIL import Image
from io import BytesIO

# SITL default location - Canberra
CENTER_LAT = -35.3632
CENTER_LON = 149.1652
ZOOM = 15
TILE_SIZE = 256

TILE_SOURCES = {
    'osm':      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    'terrain':  'https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png',
    'toner':    'https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}.png',
    'positron': 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
}

def lat_lon_to_tile(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) +
             1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y

def tile_to_lat_lon(x, y, zoom):
    n = 2 ** zoom
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon

def download_map(center_lat, center_lon, zoom, radius_tiles=2, tile_source='osm'):
    if tile_source not in TILE_SOURCES:
        raise ValueError(f"Unknown tile_source '{tile_source}'. Options: {list(TILE_SOURCES)}")

    url_template = TILE_SOURCES[tile_source]
    cx, cy = lat_lon_to_tile(center_lat, center_lon, zoom)

    tiles_wide = radius_tiles * 2 + 1
    tiles_tall = radius_tiles * 2 + 1

    composite = Image.new('RGB', (tiles_wide * TILE_SIZE, tiles_tall * TILE_SIZE))

    for dy in range(-radius_tiles, radius_tiles + 1):
        for dx in range(-radius_tiles, radius_tiles + 1):
            tx, ty = cx + dx, cy + dy
            url = url_template.format(z=zoom, x=tx, y=ty)

            headers = {'User-Agent': 'LLM-UAV-Mission-Computer/1.0'}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                tile = Image.open(BytesIO(response.content))
                px = (dx + radius_tiles) * TILE_SIZE
                py = (dy + radius_tiles) * TILE_SIZE
                composite.paste(tile, (px, py))
                print(f"Downloaded tile {tx},{ty} ({tile_source})")
            else:
                print(f"Failed tile {tx},{ty}: {response.status_code}")

    # Calculate GPS bounds
    min_lat = tile_to_lat_lon(cx - radius_tiles, cy + radius_tiles + 1, zoom)[0]
    max_lat = tile_to_lat_lon(cx - radius_tiles, cy - radius_tiles, zoom)[0]
    min_lon = tile_to_lat_lon(cx - radius_tiles, cy - radius_tiles, zoom)[1]
    max_lon = tile_to_lat_lon(cx + radius_tiles + 1, cy - radius_tiles, zoom)[1]

    output_filename = f"map_tile_{tile_source}.png"
    output_path = os.path.join(os.path.dirname(__file__), '..', 'assets', output_filename)
    composite.save(output_path)

    print(f"\nMap saved to {output_path}")
    print(f"Bounds ({tile_source}):")
    print(f"  min_lat: {min_lat}")
    print(f"  max_lat: {max_lat}")
    print(f"  min_lon: {min_lon}")
    print(f"  max_lon: {max_lon}")
    print(f"  size: {composite.size}")

    return (min_lat, max_lat, min_lon, max_lon)


if __name__ == "__main__":
    print("=== Downloading OSM tile ===")
    bounds_osm = download_map(CENTER_LAT, CENTER_LON, ZOOM, radius_tiles=1, tile_source='osm')
    print("\n=== Downloading Terrain tile ===")
    bounds_terrain = download_map(CENTER_LAT, CENTER_LON, ZOOM, radius_tiles=1, tile_source='terrain')
    print("\n=== Done ===")
    print(f"OSM bounds:     {bounds_osm}")
    print(f"Terrain bounds: {bounds_terrain}")
