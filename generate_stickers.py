import os
import argparse
import secrets
import qrcode
from PIL import Image, ImageDraw, ImageFont
import database

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "stickers_output")

def get_font(size: int, bold: bool = False):
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Geneva.ttf"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def create_sticker_image(tag_id: str, base_url: str) -> str:
    """
    Standard Real-World Windshield Sticker Size:
    Dimensions: 75mm x 95mm (~3.0 x 3.75 inches).
    High-Resolution Print: 900 x 1140 px (300 DPI Ultra Sharp).
    Design:
      - Thin vibrant gradient / rainbow outer border.
      - Top bold callout: 'BUZZme'
      - High-contrast QR code with embedded colorful 'P' logo in center.
      - Clear call-to-action: 'SCAN IF VEHICLE IS BLOCKED'.
      - Bottom footer branding: 'ParkingBuzz' + Tag ID.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    scan_url = f"{base_url.rstrip('/')}/c/{tag_id}"

    width, height = 900, 1140
    sticker = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sticker)

    # Fonts
    font_buzzme = get_font(56, bold=True)
    font_sub_top = get_font(21, bold=True)
    font_instruction = get_font(24, bold=True)
    font_features = get_font(20, bold=False)
    font_brand_bottom = get_font(42, bold=True)
    font_tag_bottom = get_font(26, bold=True)
    font_footer_sub = get_font(18, bold=False)

    # 1. Thin Vibrant Rainbow / Gradient Border (Multi-color outline)
    rainbow_colors = [
        (34, 197, 94, 255),    # Lime Green
        (14, 165, 233, 255),   # Sky Cyan
        (168, 85, 247, 255),   # Purple
        (236, 72, 153, 255),   # Hot Pink
        (239, 68, 68, 255),    # Bright Red
        (245, 158, 11, 255)    # Amber Yellow
    ]

    border_thickness = 10
    for i in range(border_thickness):
        c_idx = int((i / border_thickness) * len(rainbow_colors)) % len(rainbow_colors)
        color = rainbow_colors[c_idx]
        draw.rounded_rectangle(
            [(8 + i, 8 + i), (width - 8 - i, height - 8 - i)],
            radius=26,
            outline=color,
            width=1
        )

    # 2. Modern Dark Navy Header Banner
    banner_margin = 24
    draw.rounded_rectangle(
        [(banner_margin, banner_margin), (width - banner_margin, 185)],
        radius=18,
        fill=(15, 23, 42, 255) # Sleek Slate/Navy
    )

    # Accent thin rainbow stripe right under the banner
    stripe_y = 181
    stripe_w = (width - 2 * banner_margin) / len(rainbow_colors)
    for idx, c in enumerate(rainbow_colors):
        sx = banner_margin + (idx * stripe_w)
        draw.rectangle([(sx, stripe_y), (sx + stripe_w, stripe_y + 4)], fill=c)

    # Top Header Text: BUZZme (Bold & friendly)
    draw.text((width // 2, 85), "BUZZme", fill=(255, 255, 255, 255), font=font_buzzme, anchor="mm")
    draw.text((width // 2, 145), "VEHICLE BLOCKED? SCAN TO CONTACT OWNER", fill=(56, 189, 248, 255), font=font_sub_top, anchor="mm")

    # 3. Generate QR Code (High error correction to allow center emblem)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=13,
        border=2,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#0f172a", back_color="white").convert('RGBA')

    # Embed colorful 'P' logo in center of QR
    logo_path = os.path.join(os.path.dirname(__file__), "android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png")
    if os.path.exists(logo_path):
        try:
            p_logo = Image.open(logo_path).convert("RGBA")
            logo_size = int(qr_img.size[0] * 0.23)
            p_logo = p_logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            
            plate = Image.new("RGBA", (logo_size + 14, logo_size + 14), (255, 255, 255, 255))
            plate_draw = ImageDraw.Draw(plate)
            plate_draw.rounded_rectangle([(0, 0), (logo_size + 13, logo_size + 13)], radius=12, fill="white")
            plate.paste(p_logo, (7, 7), p_logo)
            
            pos = ((qr_img.size[0] - plate.size[0]) // 2, (qr_img.size[1] - plate.size[1]) // 2)
            qr_img.paste(plate, pos, plate)
        except Exception as e:
            print("Logo paste error:", e)

    qr_w, qr_h = qr_img.size
    qr_x = (width - qr_w) // 2
    qr_y = 230
    sticker.paste(qr_img, (qr_x, qr_y), qr_img)

    # 4. Instructions under QR
    draw.text((width // 2, qr_y + qr_h + 38), "Point phone camera to scan • No app needed for bystander", fill=(15, 23, 42, 255), font=font_instruction, anchor="mm")
    draw.text((width // 2, qr_y + qr_h + 75), "Instant Alarm & Masked Voice Call • 100% Private", fill=(100, 116, 139, 255), font=font_features, anchor="mm")

    # 5. Bottom Card / Branding: ParkingBuzz
    card_top = height - 195
    draw.rounded_rectangle(
        [(banner_margin, card_top), (width - banner_margin, height - banner_margin)],
        radius=18,
        fill=(248, 250, 252, 255),
        outline=(226, 232, 240, 255),
        width=2
    )

    # ParkingBuzz branding line
    draw.text((width // 2, card_top + 45), "ParkingBuzz", fill=(15, 23, 42, 255), font=font_brand_bottom, anchor="mm")
    draw.text((width // 2, card_top + 95), f"VEHICLE SECURITY ID:  {tag_id}", fill=(59, 130, 246, 255), font=font_tag_bottom, anchor="mm")
    draw.text((width // 2, card_top + 135), "STICK ON CAR WINDSHIELD (INSIDE FACING OUT)", fill=(148, 163, 184, 255), font=font_footer_sub, anchor="mm")

    output_path = os.path.join(OUTPUT_DIR, f"sticker_{tag_id}.png")
    sticker.save(output_path, "PNG", dpi=(300, 300))
    return output_path

def generate_printable_pdf_sheet(tag_ids: list, base_url: str, output_pdf_name: str = "parkingbuzz_stickers_sheet.pdf") -> str:
    """
    Arranges stickers onto standard A4 printable sheets (6 per page: 2 columns x 3 rows).
    At 300 DPI, each sticker is 75mm x 95mm (standard vehicle windshield sticker size).
    """
    pdf_path = os.path.join(OUTPUT_DIR, output_pdf_name)
    a4_w, a4_h = 2480, 3508 # A4 at 300 DPI
    cols, rows = 2, 3
    margin_x = 180
    margin_y = 120
    spacing_x = 100
    spacing_y = 90
    
    # Calculate sticker target render size on sheet
    st_w = 900
    st_h = 1140
    target_w = (a4_w - (2 * margin_x) - spacing_x) // 2
    target_h = int(st_h * (target_w / st_w))

    pages = []
    current_page = None
    draw_page = None
    count_on_page = 0

    for idx, tag_id in enumerate(tag_ids):
        if count_on_page == 0:
            current_page = Image.new("RGB", (a4_w, a4_h), (255, 255, 255))
            pages.append(current_page)

        sticker_path = create_sticker_image(tag_id, base_url)
        st_im = Image.open(sticker_path).convert("RGB")
        st_resized = st_im.resize((target_w, target_h), Image.Resampling.LANCZOS)

        col = count_on_page % cols
        row = count_on_page // cols
        pos_x = margin_x + col * (target_w + spacing_x)
        pos_y = margin_y + row * (target_h + spacing_y)

        current_page.paste(st_resized, (pos_x, pos_y))
        count_on_page += 1

        if count_on_page == (cols * rows):
            count_on_page = 0

    if pages:
        pages[0].save(pdf_path, save_all=True, append_images=pages[1:], resolution=300)
    return pdf_path

def generate_batch(count: int = 5, base_url: str = "http://localhost:8000"):
    print(f"Generating {count} stickers for base URL: {base_url}")
    generated_ids = []
    for _ in range(count):
        tag_id = "CAR-" + secrets.token_hex(3).upper()
        database.create_tag(tag_id)
        generated_ids.append(tag_id)
    
    # Also generate the ready-to-print A4 PDF sheet
    pdf_path = generate_printable_pdf_sheet(generated_ids, base_url, f"batch_{count}_stickers.pdf")
    print(f"\nAll {count} stickers generated! Printable A4 PDF sheet ready at: {pdf_path}")
    return generated_ids, pdf_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Printable QR Car Stickers")
    parser.add_argument("--count", type=int, default=5, help="Number of stickers to generate")
    parser.add_argument("--domain", type=str, default="http://localhost:8000", help="Deployment domain URL")
    args = parser.parse_args()

    generate_batch(args.count, args.domain)
