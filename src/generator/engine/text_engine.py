import os
from PIL import Image, ImageDraw, ImageFont, ImageStat
from src.shared.utils.typography_manager import TypographyManager
from src.shared.utils.layout_manager import LayoutManager
from src.shared.utils.bijoy_converter import BijoyConverter

class TextEngine:
    """Core engine for applying programmatic text overlays with brand styles."""

    BRAND_COLORS = {
        "airtel_red": (255, 0, 0),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "semi_black": (0, 0, 0, 160),  # With Alpha for highlights
        "shadow": (30, 30, 30, 180)
    }

    def __init__(self, font_dir=None):
        self.typo = TypographyManager(font_dir)
        self.layout = LayoutManager()

    def apply_overlay(self, 
                      image_path, 
                      text, 
                      rel_x=None, 
                      rel_y=None, 
                      anchor=None, 
                      font_size=80, 
                      color=None, 
                      style="bold",
                      max_width_pct=0.8,
                      shadow=True,
                      box=False,
                      stroke=False,
                      output_path=None):
        """
        Applies a text overlay to an existing image.
        :param image_path: Path to the base AI image.
        :param text: Text to overlay (supports English/Bengali).
        :param rel_x: Relative horizontal position (0-1).
        :param rel_y: Relative vertical position (0-1).
        :param anchor: Friendly anchor name (e.g., 'bottom_center').
        :param font_size: Size of font in pixels.
        :param color: Text color (from BRAND_COLORS key or hex).
        :param style: Font style (regular, bold, light).
        :param max_width_pct: Text wrapping width as % of image width.
        :param shadow: Whether to add a subtle drop shadow.
        :param box: Whether to add a semi-transparent box behind text.
        :param stroke: Whether to add a stroke (outline) to text.
        :param output_path: Where to save the final image.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Open image and convert to RGBA if needed for transparency effects
        img = Image.open(image_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        img_w, img_h = img.size

        # 0. Intelligent Placement & Color Detection
        if rel_x is None or rel_y is None:
            rel_x, rel_y, auto_anchor = self.layout.find_intelligent_placement(img)
            if anchor is None:
                anchor = auto_anchor
        
        if anchor is None:
            anchor = "bottom_center"
            
        # 0.1 Automatic Color Contrast
        base_x, base_y = self.layout.get_relative_coords(img.size, rel_x, rel_y)
        # Sample a small area around the text point to see background brightness
        sample_box = (max(0, base_x-100), max(0, base_y-100), min(img_w, base_x+100), min(img_h, base_y+100))
        crop_sample = img.crop(sample_box)
        stat = ImageStat.Stat(crop_sample)
        brightness = sum(stat.mean) / 3
        
        if color is None:
            color = "white" if brightness < 128 else "airtel_red"

        # 0.2 Clutter-aware Readability Boost
        # If the sample area is very "busy", force a background box or higher contrast
        clutter = sum(stat.stddev) / 3
        if clutter > 35: # Tightened threshold for "busy"
            box = True
            box_opacity = 160 # Darker for better contrast on busy backgrounds
        else:
            box_opacity = 110

        # 1. Font Selection & Bijoy Conversion
        is_bn = TypographyManager.is_bengali(text)
        if is_bn:
            # Convert Unicode to Bijoy for MJ Fonts
            text = BijoyConverter.convert(text)
        
        font = self.typo.select_font(text, style=style, size=font_size)

        # 2. Handle Text Wrapping
        max_px_width = int(img_w * max_width_pct)
        lines = self.layout.wrap_text(text, font, max_px_width)
        
        # 3. Calculate Base Position
        base_x, base_y = self.layout.get_relative_coords((img_w, img_h), rel_x, rel_y)
        anchor_code = self.layout.get_anchor(anchor)

        # Calculate total height of all lines
        line_spacing = int(font_size * 0.2)
        total_text_height = sum([font.getbbox(l)[3] - font.getbbox(l)[1] for l in lines]) + (len(lines)-1) * line_spacing
        
        # Adjust Y based on anchor if multiple lines
        # Pillow handles anchor per line, but for multi-line we might need fine control
        # For simplicity, we'll draw line by line
        
        current_y = base_y
        if "d" in anchor_code: # Bottom anchors
            current_y = base_y - total_text_height
        elif "m" in anchor_code[1:]: # Middle anchors
            current_y = base_y - (total_text_height // 2)

        fill_color = self.BRAND_COLORS.get(color, color)

        # 4. Optional: Draw Background Box
        if box:
            padding = 20
            # Calculate total box dimensions
            max_l_w = max([font.getbbox(l)[2] for l in lines])
            box_coords = [
                base_x - (max_l_w // 2) - padding if "m" in anchor_code else base_x - padding,
                current_y - padding,
                base_x + (max_l_w // 2) + padding if "m" in anchor_code else base_x + max_l_w + padding,
                current_y + total_text_height + padding
            ]
            # Simple rectangle for now
            overlay = Image.new('RGBA', img.size, (0,0,0,0))
            d_overlay = ImageDraw.Draw(overlay)
            d_overlay.rectangle(box_coords, fill=(0, 0, 0, box_opacity))  # Use dynamic opacity
            img = Image.alpha_composite(img, overlay)
            draw = ImageDraw.Draw(img)

        # 5. Draw Text Lines
        for line in lines:
            line_w = font.getbbox(line)[2]
            line_h = font.getbbox(line)[3] - font.getbbox(line)[1]
            
            # Draw Shadow or Stroke
            if shadow:
                s_off = int(font_size * 0.05)
                draw.text((base_x + s_off, current_y + s_off), line, font=font, fill=(0,0,0,180), anchor=anchor_code)
            
            if stroke:
                s_width = max(1, int(font_size * 0.05))
                draw.text((base_x, current_y), line, font=font, fill=fill_color, anchor=anchor_code, 
                          stroke_width=s_width, stroke_fill=(0,0,0))
            else:
                draw.text((base_x, current_y), line, font=font, fill=fill_color, anchor=anchor_code)
            
            current_y += (line_h + line_spacing)

        # Finalize
        final_img = img.convert("RGB") # Back to RGB for JPEG/PNG standard
        if output_path:
            final_img.save(output_path)
            return output_path
        
        return final_img
