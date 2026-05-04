from map_compositor import MapCompositor
from map_config import MAP_TILE_PATH, MAP_BOUNDS, MISSION_TARGET
import base64, os

compositor = MapCompositor(MAP_TILE_PATH, MAP_BOUNDS)

# simulate some aircraft state and trail
states = [
    {"lat": -35.360, "lon": 149.163, "heading": 45},
    {"lat": -35.361, "lon": 149.164, "heading": 90},
    {"lat": -35.362, "lon": 149.165, "heading": 135},
    {"lat": -35.363, "lon": 149.166, "heading": 180},
]

for state in states:
    compositor.update_trail(state["lat"], state["lon"])

image_b64 = compositor.compose(states[-1], MISSION_TARGET)

# save to file so we can inspect it
output_path = "test_map_output.png"
with open(output_path, "wb") as f:
    f.write(base64.b64decode(image_b64))

print(f"Test map saved to {output_path}")
print(f"Image size: {compositor.get_output_size()}")