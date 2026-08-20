import sys
import os
from PIL import Image, ImageDraw, ImageFont

def make_icon():
    sys.stdout.reconfigure(encoding='utf-8')
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app_icon.ico"))
    
    # Create 256x256 image with smooth rounded corners and dark blue gradient
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle background (Royal Navy Blue / Cyan theme)
    margin = 8
    radius = 48
    draw.rounded_rectangle([margin, margin, 256 - margin, 256 - margin], radius=radius, fill=(30, 42, 68, 255), outline=(78, 140, 255, 255), width=6)

    # Draw Robot / ERP Symbol inside icon
    # Head box
    draw.rounded_rectangle([64, 70, 192, 170], radius=16, fill=(78, 140, 255, 255))
    # Eyes
    draw.ellipse([88, 100, 114, 126], fill=(255, 255, 255, 255))
    draw.ellipse([142, 100, 168, 126], fill=(255, 255, 255, 255))
    # Pupils (Neon Cyan)
    draw.ellipse([96, 108, 106, 118], fill=(0, 229, 255, 255))
    draw.ellipse([150, 108, 160, 118], fill=(0, 229, 255, 255))
    # Mouth line
    draw.rounded_rectangle([100, 142, 156, 150], radius=4, fill=(255, 255, 255, 255))

    # Antenna
    draw.line([128, 40, 128, 70], fill=(78, 140, 255, 255), width=8)
    draw.ellipse([118, 30, 138, 50], fill=(0, 229, 255, 255))

    # Text "ERP" at bottom
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    
    draw.text((128, 205), "ERP", fill=(255, 255, 255, 255), font=font, anchor="mm")

    # Save as .ico containing multiple sizes for Windows OS
    img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"✅ ĐÃ TẠO THÀNH CÔNG ICON TỆP '.ico': '{icon_path}'")

if __name__ == '__main__':
    make_icon()
