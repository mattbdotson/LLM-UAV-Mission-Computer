import math
import io
import base64
from PIL import Image, ImageDraw
import os

class MapCompositor:
    def __init__(self, tile_path, bounds):
        self.base = Image.open(tile_path).convert("RGB")
        self.bounds = bounds
        self.w, self.h = self.base.size
        self.trail = []
        print(f"Map loaded: {self.w}x{self.h}px, bounds: {bounds}")

    def gps_to_pixel(self, lat, lon):
        min_lat, max_lat, min_lon, max_lon = self.bounds
        x = int((lon - min_lon) / (max_lon - min_lon) * self.w)
        y = int((max_lat - lat) / (max_lat - min_lat) * self.h)
        return x, y

    def pixel_to_gps(self, x, y):
        min_lat, max_lat, min_lon, max_lon = self.bounds
        # x, y are in 384x384 space, scale back to full resolution first
        full_x = int(x * self.w / 384)
        full_y = int(y * self.h / 384)
        lon = min_lon + (full_x / self.w) * (max_lon - min_lon)
        lat = max_lat - (full_y / self.h) * (max_lat - min_lat)
        return lat, lon

    def update_trail(self, lat, lon):
        self.trail.append((lat, lon))
        if len(self.trail) > 50:
            self.trail.pop(0)

    def compose(self, state, mission_target=None):
     try:
        img = self.base.copy()
        draw = ImageDraw.Draw(img)

        lat = state.get("lat")
        lon = state.get("lon")
        heading = state.get("heading", 0)

        if lat and lon:
            self.update_trail(lat, lon)

        if len(self.trail) > 1:
            trail_pixels = [self.gps_to_pixel(la, lo) for la, lo in self.trail]
            for i in range(len(trail_pixels) - 1):
                draw.line([trail_pixels[i], trail_pixels[i+1]],
                         fill=(55, 138, 221), width=12)

        if mission_target:
            tx, ty = self.gps_to_pixel(*mission_target)
            r = 50
            draw.ellipse([tx-r, ty-r, tx+r, ty+r],
                        outline=(226, 75, 74), width=10)
            draw.line([tx-r-15, ty, tx+r+15, ty], fill=(226, 75, 74), width=8)
            draw.line([tx, ty-r-15, tx, ty+r+15], fill=(226, 75, 74), width=8)

        if lat and lon:
            ax, ay = self.gps_to_pixel(lat, lon)
            heading_rad = math.radians(heading)
            length = 70
            tip_x = ax + length * math.sin(heading_rad)
            tip_y = ay - length * math.cos(heading_rad)
            left_x = ax + 35 * math.sin(heading_rad - 2.4)
            left_y = ay - 35 * math.cos(heading_rad - 2.4)
            right_x = ax + 35 * math.sin(heading_rad + 2.4)
            right_y = ay - 35 * math.cos(heading_rad + 2.4)
            draw.polygon(
                [(tip_x, tip_y), (left_x, left_y), (ax, ay), (right_x, right_y)],
                fill=(55, 138, 221),
                outline=(255, 255, 255)
            )

        draw.ellipse([20, 20, 160, 160],
                    fill=(255, 255, 255), outline=(0, 0, 0), width=4)
        draw.text((85, 30), "N", fill=(0, 0, 0))
        draw.text((85, 115), "S", fill=(0, 0, 0))
        draw.text((30, 72), "W", fill=(0, 0, 0))
        draw.text((128, 72), "E", fill=(0, 0, 0))

        vlm_size = (384, 384)
        img_resized = img.resize(vlm_size, Image.LANCZOS)

        buf = io.BytesIO()
        img_resized.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

     except Exception as e:
        print(f"compose() error: {e}")
        import traceback
        traceback.print_exc()
        return None