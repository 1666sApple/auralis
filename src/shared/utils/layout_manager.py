from PIL import ImageDraw

class LayoutManager:
    """Handles text wrapping and relative coordinate calculations for image overlays."""

    ANCHORS = {
        "top_left": "la",
        "top_center": "ma",
        "top_right": "ra",
        "center_left": "lm",
        "center": "mm",
        "center_right": "rm",
        "bottom_left": "ld",
        "bottom_right": "rd",
        "bottom_center": "md"
    }

    @staticmethod
    def wrap_text(text, font, max_width):
        """
        Wraps text to fit within a maximum width.
        :param text: The text to wrap.
        :param font: ImageFont object.
        :param max_width: Maximum width in pixels.
        :return: List of lines.
        """
        lines = []
        words = text.split()
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            # getbbox returns (left, top, right, bottom)
            width = font.getbbox(test_line)[2]
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    # Single word is wider than max_width, force it
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(" ".join(current_line))
            
        return lines

    @staticmethod
    def get_relative_coords(image_size, rel_x=0.5, rel_y=0.5, margin=0.05):
        """
        Calculates absolute coordinates from relative (0-1) values.
        :param image_size: (width, height).
        :param rel_x: Relative x (0.0 to 1.0).
        :param rel_y: Relative y (0.0 to 1.0).
        :param margin: Safety margin (0.05 means 5% from edges).
        :return: (x, y).
        """
        img_w, img_h = image_size
        
        # Clamp relative values to respect margins
        rel_x = max(margin, min(1.0 - margin, rel_x))
        rel_y = max(margin, min(1.0 - margin, rel_y))
        
        abs_x = int(img_w * rel_x)
        abs_y = int(img_h * rel_y)
        
        return abs_x, abs_y

    @staticmethod
    def find_intelligent_placement(image, margin=0.08):
        """
        Analyzes the image for the lowest clutter density (Edges + Variance).
        :param image: PIL Image object.
        :param margin: Safety margin from edges.
        :return: (rel_x, rel_y, anchor) for the best placement.
        """
        from PIL import ImageFilter, ImageStat
        
        img_w, img_h = image.size
        
        # 1. Edge Density Map
        gray = image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        
        # 2. Potential Regions: Top-Left, Top-Right, Bottom-Left, Bottom-Right, Top-Center, Bottom-Center
        regions = {
            "top_left": (margin, margin, "top_left"),
            "top_right": (1.0 - margin, margin, "top_right"),
            "bottom_left": (margin, 1.0 - margin, "bottom_left"),
            "bottom_right": (1.0 - margin, 1.0 - margin, "bottom_right"),
            "top_center": (0.5, margin, "top_center"),
            "bottom_center": (0.5, 1.0 - margin, "bottom_center")
        }
        
        # We also check the center but give it a "clutter penalty" (advertising convention)
        regions["center"] = (0.5, 0.5, "center")
        
        region_size_w = int(img_w * 0.2)
        region_size_h = int(img_h * 0.15)
        
        scored_regions = []
        
        for name, (rel_x, rel_y, anchor) in regions.items():
            # Define crop box
            left = int(img_w * rel_x) - (region_size_w // 2) if rel_x == 0.5 else (int(img_w * rel_x) if rel_x < 0.5 else int(img_w * rel_x) - region_size_w)
            top = int(img_h * rel_y) - (region_size_h // 2) if rel_y == 0.5 or rel_y == 1.0-margin else (int(img_h * rel_y) if rel_y < 0.5 else int(img_h * rel_y) - region_size_h)
            
            # Boundary check
            left = max(0, min(img_w - region_size_w, left))
            top = max(0, min(img_h - region_size_h, top))
            right = left + region_size_w
            bottom = top + region_size_h
            
            # Crop stats
            crop_edges = edges.crop((left, top, right, bottom))
            crop_orig = image.crop((left, top, right, bottom))
            
            stat_edges = ImageStat.Stat(crop_edges)
            stat_orig = ImageStat.Stat(crop_orig)
            
            # Complexity score: High Edge Mean + High Standard Deviation in color
            complexity = stat_edges.mean[0] + (sum(stat_orig.stddev) / 3.0)
            
            # Penalty for "Subject Center" (assuming high importance is center)
            if name == "center":
                complexity *= 2.0
            
            scored_regions.append({
                "name": name,
                "score": complexity,
                "rel_x": rel_x,
                "rel_y": rel_y,
                "anchor": anchor
            })
            
        # 3. Avoid busy areas at all costs. Pick the one with the lowest complexity.
        # But prefer Top-Right or Bottom-Center for brand aesthetics if scores are close.
        scored_regions.sort(key=lambda x: x["score"])
        
        best = scored_regions[0]
        return best["rel_x"], best["rel_y"], best["name"]

    @staticmethod
    def get_anchor(anchor_name):
        """Returns the Pillow anchor code for the given friendly name."""
        return LayoutManager.ANCHORS.get(anchor_name.lower(), "mm")
