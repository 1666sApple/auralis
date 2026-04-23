import os
from PIL import ImageFont

class TypographyManager:
    """Handles font loading and Unicode support for Airtel Branding (Tondo, Kongsho)."""

    # Use the new consolidated assets directory
    FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "assets", "fonts")
    
    # Font Mapping based on provided assets
    FONTS = {
        "en_regular": "Tondo_Std_Rg.ttf",
        "en_light": "Tondo_Std_Lt.ttf",
        "en_std": "Tondo_Std.ttf",
        "bn_regular": "KongshoMJ.ttf",
        "bn_bold": "Shahid KongshoMJ-Bold.ttf",
        "bn_italic": "Shahid KongshoMJ-Italic.ttf",
        "bn_bold_italic": "Shahid KongshoMJ-BoldItalic.ttf"
    }

    def __init__(self, font_dir=None):
        self.font_dir = font_dir or self.FONT_DIR
        if not os.path.exists(self.font_dir):
            raise FileNotFoundError(f"Font directory not found: {self.font_dir}")

    def get_font(self, font_key, size=32):
        """
        Loads the specified font with the given size.
        :param font_key: Key from the FONTS mapping.
        :param size: Font size in pixels/points.
        :return: ImageFont object.
        """
        font_filename = self.FONTS.get(font_key)
        if not font_filename:
            raise ValueError(f"Unknown font key: {font_key}. Available: {list(self.FONTS.keys())}")
        
        font_path = os.path.join(self.font_dir, font_filename)
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found: {font_path}")
            
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            # Fallback to default if load fails (though rare for TTF)
            print(f"Warning: Failed to load {font_path}. Error: {e}")
            return ImageFont.load_default()

    @staticmethod
    def is_bengali(text):
        """Simple check to see if the text contains Bengali characters."""
        for char in text:
            if '\u0980' <= char <= '\u09FF':
                return True
        return False

    def select_font(self, text, style="regular", size=32):
        """Automatically selects Bengali or English font based on text content."""
        if self.is_bengali(text):
            key = f"bn_{style}"
        else:
            key = f"en_{style}"
        
        # Fallback to regular if style doesn't exist for that language
        if key not in self.FONTS:
            key = "bn_regular" if self.is_bengali(text) else "en_regular"
            
        return self.get_font(key, size)
