import os
import sys
from PIL import Image, ImageDraw, ImageFont

# Add current directory to path
sys.path.append(os.getcwd())

from src.shared.utils.typography_manager import TypographyManager

def create_font_grid():
    print("Creating Font Grid for Shahid KongshoMJ...")
    typo = TypographyManager()
    
    # We want to test Shahid KongshoMJ-Bold.ttf
    font_size = 40
    try:
        font = typo.get_font("bn_bold", font_size)
    except Exception as e:
        print(f"Error loading font: {e}")
        return

    # ASCII characters from 33 to 126
    chars = [chr(i) for i in range(33, 127)]
    
    # Create a grid image
    grid_cols = 10
    grid_rows = (len(chars) // grid_cols) + 1
    cell_size = 100
    
    img = Image.new("RGB", (grid_cols * cell_size, grid_rows * cell_size), "white")
    draw = ImageDraw.Draw(img)
    
    for idx, char in enumerate(chars):
        row = idx // grid_cols
        col = idx % grid_cols
        
        x = col * cell_size + 10
        y = row * cell_size + 10
        
        # Draw the ASCII char in a standard font first for reference
        draw.text((x, y), f"'{char}'", fill="black")
        
        # Draw the character in the MJ font below it
        draw.text((x, y + 40), char, font=font, fill="red")

    os.makedirs("test_outputs", exist_ok=True)
    img.save("test_outputs/font_grid_mj.png")
    print("Font grid saved to test_outputs/font_grid_mj.png")

if __name__ == "__main__":
    create_font_grid()
