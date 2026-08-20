import sys
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

def make_clean_ico():
    sys.stdout.reconfigure(encoding='utf-8')
    project_dir = r"C:\Users\Admin\OneDrive\Tài liệu\ERP BOT\erp_automation"
    icon_path = os.path.join(project_dir, "app_icon.ico")

    # Create 256x256 image with smooth rounded corners and dark blue gradient
    size = (256, 256)
    img = Image.new("RGBA", size, (30, 42, 68, 255))
    draw = ImageDraw.Draw(img)

    # Draw rounded border
    margin = 8
    draw.rounded_rectangle([margin, margin, 256 - margin, 256 - margin], radius=40, fill=(30, 42, 68, 255), outline=(78, 140, 255, 255), width=8)

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

    # Save cleanly as ICO
    img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"✅ ĐÃ LƯU TỆP ICON CHUẨN: '{icon_path}'")

if __name__ == '__main__':
    make_clean_ico()
