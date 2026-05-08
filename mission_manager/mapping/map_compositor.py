import math
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import os

class MapCompositor:
    def __init__(self, tile_path, bounds, vlm_size=(512, 512)):
        self.base = Image.open(tile_path).convert("RGB")
        self.bounds = bounds
        self.w, self.h = self.base.size
        self.vlm_size = vlm_size
        self.trail = []
        print(f"Map loaded: {self.w}x{self.h}px, bounds: {bounds}, vlm_size: {vlm_size}")

    def gps_to_pixel(self, lat, lon):
        min_lat, max_lat, min_lon, max_lon = self.bounds
        x = int((lon - min_lon) / (max_lon - min_lon) * self.w)
        y = int((max_lat - lat) / (max_lat - min_lat) * self.h)
        return x, y

    def pixel_to_gps(self, x, y):
        min_lat, max_lat, min_lon, max_lon = self.bounds
        full_x = int(x * self.w / self.vlm_size[0])
        full_y = int(y * self.h / self.vlm_size[1])
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
            draw = ImageDraw.Draw(img, "RGBA")

            lat = state.get("lat")
            lon = state.get("lon")
            heading = state.get("heading", 0)

            if lat and lon:
                self.update_trail(lat, lon)

            # Flight trail
            if len(self.trail) > 1:
                trail_pixels = [self.gps_to_pixel(la, lo) for la, lo in self.trail]
                for i in range(len(trail_pixels) - 1):
                    draw.line([trail_pixels[i], trail_pixels[i+1]],
                             fill=(55, 138, 221), width=12)

            # Mission target — filled green circle with white border
            if mission_target:
                tx, ty = self.gps_to_pixel(*mission_target)
                r = 50
                draw.ellipse([tx-r, ty-r, tx+r, ty+r],
                            fill=(50, 200, 50), outline=(255, 255, 255), width=12)

            # Aircraft arrow — white outline first, blue fill on top
            if lat and lon:
                ax, ay = self.gps_to_pixel(lat, lon)
                heading_rad = math.radians(heading)
                length = 100
                spread = 50
                tip_x = ax + length * math.sin(heading_rad)
                tip_y = ay - length * math.cos(heading_rad)
                left_x = ax + spread * math.sin(heading_rad - 2.4)
                left_y = ay - spread * math.cos(heading_rad - 2.4)
                right_x = ax + spread * math.sin(heading_rad + 2.4)
                right_y = ay - spread * math.cos(heading_rad + 2.4)
                poly = [(tip_x, tip_y), (left_x, left_y), (ax, ay), (right_x, right_y)]
                # White outline
                draw.polygon(poly, fill=None, outline=(255, 255, 255))
                draw.line([(tip_x, tip_y), (left_x, left_y)], fill=(255, 255, 255), width=10)
                draw.line([(left_x, left_y), (ax, ay)], fill=(255, 255, 255), width=10)
                draw.line([(ax, ay), (right_x, right_y)], fill=(255, 255, 255), width=10)
                draw.line([(right_x, right_y), (tip_x, tip_y)], fill=(255, 255, 255), width=10)
                # Blue fill
                draw.polygon(poly, fill=(55, 138, 221))

            # Compass rose — bottom-left corner, 120x120px circle equivalent on full-res image
            # Scale factor: full image is 2304px, compass circle diameter maps to ~120px at 512
            cr = 240  # radius in full-res pixels (~120px * 2304/512 scaling factor ~= 540, use 240 for compact)
            cx = 20 + cr  # left edge + radius
            cy = self.h - 20 - cr  # bottom edge - radius

            # Semi-transparent white background
            draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr],
                        fill=(255, 255, 255, 180), outline=(40, 40, 40), width=6)

            # North arrow — filled triangle pointing up
            arrow_len = int(cr * 0.7)
            draw.polygon(
                [(cx, cy - arrow_len),
                 (cx - arrow_len // 3, cy + arrow_len // 4),
                 (cx + arrow_len // 3, cy + arrow_len // 4)],
                fill=(30, 30, 30)
            )

            # "N" label just above the tip
            try:
                font = ImageFont.load_default(size=int(cr * 0.55))
            except TypeError:
                font = ImageFont.load_default()
            draw.text((cx, cy - arrow_len - int(cr * 0.55)),
                     "N", fill=(30, 30, 30), font=font, anchor="mm")

            img_rgb = img.convert("RGB")
            img_resized = img_rgb.resize(self.vlm_size, Image.LANCZOS)

            buf = io.BytesIO()
            img_resized.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()

        except Exception as e:
            print(f"compose() error: {e}")
            import traceback
            traceback.print_exc()
            return None
