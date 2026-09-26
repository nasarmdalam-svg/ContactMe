import os
import argparse
import secrets
import qrcode
from PIL import Image, ImageDraw, ImageFont
import database

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "stickers_output")

def create_sticker_image(tag_id: str, base_url: str) -> str:
    """Generate a clean, high-resolution printable car sticker with QR code."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    scan_url = f"{base_url.rstrip('/')}/c/{tag_id}"

    # 1. Generate QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#0f172a", back_color="white").convert('RGBA')

    # 2. Setup Sticker Dimensions (600 x 750 px - High DPI printable card)
    width, height = 600, 760
    sticker = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sticker)

    # 3. Outer Border & Header Banner
    draw.rectangle([(10, 10), (width - 10, height - 10)], outline=(30, 41, 59, 255), width=4)
    draw.rectangle([(10, 10), (width - 10, 110)], fill=(15, 23, 42, 255)) # Dark navy header

    # Header Text
    draw.text((width // 2, 42), "PARKBUZZ", fill=(255, 255, 255, 255), anchor="mm")
    draw.text((width // 2, 80), "VEHICLE BLOCKED? SCAN TO ALERT OWNER", fill=(56, 189, 248, 255), anchor="mm")

    # Paste QR Code in center
    qr_w, qr_h = qr_img.size
    qr_x = (width - qr_w) // 2
    qr_y = 150
    sticker.paste(qr_img, (qr_x, qr_y))

    # Bottom Instructions
    draw.text((width // 2, qr_y + qr_h + 35), "Scan with any smartphone camera", fill=(15, 23, 42, 255), anchor="mm")
    draw.text((width // 2, qr_y + qr_h + 70), "Instant Alerts • Masked Voice Call • 100% Private", fill=(100, 116, 139, 255), anchor="mm")

    # Bottom Tag ID Bar
    draw.rectangle([(30, height - 85), (width - 30, height - 35)], fill=(241, 245, 249, 255), outline=(203, 213, 225, 255))
    draw.text((width // 2, height - 60), f"TAG ID: {tag_id}", fill=(15, 23, 42, 255), anchor="mm")

    output_path = os.path.join(OUTPUT_DIR, f"sticker_{tag_id}.png")
    sticker.save(output_path, "PNG")
    return output_path

def generate_batch(count: int = 5, base_url: str = "http://localhost:8000"):
    print(f"Generating {count} stickers for base URL: {base_url}")
    generated = []
    for _ in range(count):
        tag_id = "CAR-" + secrets.token_hex(3).upper()
        database.create_tag(tag_id)
        path = create_sticker_image(tag_id, base_url)
        generated.append((tag_id, path))
        print(f"  ✓ Created {tag_id} -> {path}")
    print(f"\nAll {count} stickers generated in {OUTPUT_DIR}/")
    return generated

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Printable QR Car Stickers")
    parser.add_argument("--count", type=int, default=5, help="Number of stickers to generate")
    parser.add_argument("--domain", type=str, default="http://localhost:8000", help="Deployment domain URL")
    args = parser.parse_args()

    generate_batch(args.count, args.domain)
