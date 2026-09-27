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
    Dimensions: 76mm x 96mm (~3.0 x 3.8 inches).
    High-Resolution Print: 900 x 1140 px (300 DPI Ultra Sharp).
    Design:
      - 100% Pure white background (no dark patches, no grey boxes).
      - Top bold callout: 'Scan to BuzzMe'
      - High-contrast QR code with embedded colorful 'P' logo in center.
      - Bold instructions: 'Point Camera to Scan • No App Needed'
      - Feature highlights: Sound Horn Alarm + Masked Audio Call.
      - Footer: ParkingBuzz + Tag ID.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    scan_url = f"{base_url.rstrip('/')}/c/{tag_id}"

    width, height = 900, 1140
    sticker = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(sticker)

    font_title = get_font(62, bold=True)
    font_sub = get_font(23, bold=True)
    font_big_inst = get_font(30, bold=True)
    font_feature = get_font(23, bold=True)
    font_brand = get_font(30, bold=True)
    font_footer_sub = get_font(18, bold=False)

    # 1. Subtle Elegant Rainbow Border
    rainbow_colors = [
        (14, 165, 233),   # Cyan
        (59, 130, 246),   # Blue
        (168, 85, 247),   # Purple
        (236, 72, 153),   # Pink
        (239, 68, 68),    # Red
        (245, 158, 11),   # Amber
        (34, 197, 94)     # Green
    ]
    border_thick = 8
    for i in range(border_thick):
        c = rainbow_colors[int((i / border_thick) * len(rainbow_colors)) % len(rainbow_colors)]
        draw.rounded_rectangle([(10 + i, 10 + i), (width - 10 - i, height - 10 - i)], radius=24, outline=c, width=1)

    # Inner subtle boundary line
    draw.rounded_rectangle([(24, 24), (width - 24, height - 24)], radius=18, outline=(226, 232, 240), width=2)

    # 2. Top Header (Pure White Background, Big Bold: 'Scan to BuzzMe')
    draw.text((width // 2, 68), "Scan to BuzzMe", fill=(15, 23, 42), font=font_title, anchor="mm")
    draw.text((width // 2, 120), "VEHICLE BLOCKED? SCAN TO CONTACT OWNER", fill=(2, 132, 199), font=font_sub, anchor="mm")
    draw.line([(50, 146), (width - 50, 146)], fill=(226, 232, 240), width=2)

    # 3. QR Code with centered P Logo
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=13,
        border=1,
    )
    qr.add_data(scan_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#0f172a", back_color="white").convert("RGBA")

    logo_path = os.path.join(os.path.dirname(__file__), "android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png")
    if os.path.exists(logo_path):
        try:
            p_logo = Image.open(logo_path).convert("RGBA")
            l_size = int(qr_img.size[0] * 0.23)
            p_logo = p_logo.resize((l_size, l_size), Image.Resampling.LANCZOS)
            plate = Image.new("RGBA", (l_size + 14, l_size + 14), (255, 255, 255, 255))
            plate_draw = ImageDraw.Draw(plate)
            plate_draw.rounded_rectangle([(0, 0), (plate.size[0] - 1, plate.size[1] - 1)], radius=12, fill="white")
            plate.paste(p_logo, (7, 7), p_logo)
            pos = ((qr_img.size[0] - plate.size[0]) // 2, (qr_img.size[1] - plate.size[1]) // 2)
            qr_img.paste(plate, pos, plate)
        except Exception as e:
            print("Logo paste error:", e)

    qr_w, qr_h = qr_img.size
    qr_x = (width - qr_w) // 2
    qr_y = 175
    sticker.paste(qr_img, (qr_x, qr_y), qr_img)

    # 4. Big Clear Instructions Under QR
    y_text = qr_y + qr_h + 38
    draw.text((width // 2, y_text), "Point Camera to Scan • No App Needed", fill=(15, 23, 42), font=font_big_inst, anchor="mm")

    # Feature Badges
    y_text += 50
    pill_h = 44
    draw.rounded_rectangle([(50, y_text - 12), (width - 50, y_text + pill_h - 12)], radius=10, fill=(240, 249, 255), outline=(186, 230, 253), width=1)
    draw.text((width // 2, y_text + 10), "SOUND ALARM: Instant Car Horn Alert on Owner Phone", fill=(3, 105, 161), font=font_feature, anchor="mm")

    y_text += 58
    draw.rounded_rectangle([(50, y_text - 12), (width - 50, y_text + pill_h - 12)], radius=10, fill=(240, 253, 244), outline=(187, 247, 208), width=1)
    draw.text((width // 2, y_text + 10), "FREE AUDIO CALL: 100% Private (No Phone Numbers Shared)", fill=(21, 128, 61), font=font_feature, anchor="mm")

    # 5. Footer: Tag ID & Mounting Guide
    y_text += 68
    draw.line([(50, y_text), (width - 50, y_text)], fill=(226, 232, 240), width=2)

    y_text += 32
    draw.text((width // 2, y_text), f"ParkingBuzz • Security Tag: {tag_id}", fill=(15, 23, 42), font=font_brand, anchor="mm")

    y_text += 36
    draw.text((width // 2, y_text), "STICK ON CAR WINDSHIELD (INSIDE FACING OUT)", fill=(100, 116, 139), font=font_footer_sub, anchor="mm")

    output_path = os.path.join(OUTPUT_DIR, f"sticker_{tag_id}.png")
    sticker.save(output_path, "PNG", dpi=(300, 300))
    return output_path

def generate_single_sticker_a4_pdf(tag_id: str, base_url: str) -> str:
    """
    Generates a ready-to-print standard A4 PDF (210mm x 297mm) at 300 DPI for a single tag.
    Includes the official 76mm x 96mm windshield sticker with cut marks and mounting instructions.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, f"sticker_{tag_id}_A4.pdf")
    a4_w, a4_h = 2480, 3508  # A4 at 300 DPI
    page = Image.new("RGB", (a4_w, a4_h), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    font_header = get_font(52, bold=True)
    font_subhead = get_font(28, bold=False)
    font_guide_title = get_font(32, bold=True)
    font_guide_body = get_font(24, bold=False)

    # Top Sheet Header
    draw.text((a4_w // 2, 160), "ParkingBuzz — Official Vehicle Security Sticker", fill=(15, 23, 42), font=font_header, anchor="mm")
    draw.text((a4_w // 2, 220), "Printable A4 Sheet • Standard Windshield Size: 76 mm x 96 mm (3.0\" x 3.8\")", fill=(100, 116, 139), font=font_subhead, anchor="mm")
    draw.line([(180, 260), (a4_w - 180, 260)], fill=(226, 232, 240), width=3)

    # Create the high-res sticker
    sticker_path = create_sticker_image(tag_id, base_url)
    st_im = Image.open(sticker_path).convert("RGB")

    # Center position for primary sticker
    st_w, st_h = st_im.size
    pos_x = (a4_w - st_w) // 2
    pos_y = 350

    # Draw dashed cut lines around the sticker
    cut_margin = 12
    draw.rounded_rectangle(
        [(pos_x - cut_margin, pos_y - cut_margin), (pos_x + st_w + cut_margin, pos_y + st_h + cut_margin)],
        radius=30,
        outline=(148, 163, 184),
        width=3
    )
    draw.text((pos_x - cut_margin + 20, pos_y - cut_margin - 16), "✂️ CUT ALONG DOTTED LINE", fill=(100, 116, 139), font=font_guide_body)

    # Paste sticker
    page.paste(st_im, (pos_x, pos_y))

    # Mounting & Printing Guide Box
    box_y = pos_y + st_h + 100
    draw.rounded_rectangle(
        [(220, box_y), (a4_w - 220, box_y + 420)],
        radius=18,
        fill=(248, 250, 252),
        outline=(203, 213, 225),
        width=2
    )

    draw.text((260, box_y + 40), "📋 Easy Printing & Windshield Installation Guide", fill=(15, 23, 42), font=font_guide_title)
    draw.text((260, box_y + 100), "1. Printing: Set your printer scale to '100%' or 'Actual Size' (Do not shrink / fit to page).", fill=(51, 65, 85), font=font_guide_body)
    draw.text((260, box_y + 155), "2. Material: Print on standard A4 paper, transparent sticker sheet, or self-adhesive vinyl.", fill=(51, 65, 85), font=font_guide_body)
    draw.text((260, box_y + 210), "3. Cutting: Cut neatly around the rounded border following the scissor guide.", fill=(51, 65, 85), font=font_guide_body)
    draw.text((260, box_y + 265), "4. Affixing: Stick on the inside of the front windshield facing outward (top-left or behind rearview mirror).", fill=(51, 65, 85), font=font_guide_body)
    draw.text((260, box_y + 320), "5. Ready: Anyone blocking your vehicle scans to alert you instantly with sound and voice call!", fill=(14, 165, 233), font=font_guide_body)

    # Second / Spare Sticker at the bottom
    spare_scale = 0.82
    spare_w = int(st_w * spare_scale)
    spare_h = int(st_h * spare_scale)
    st_spare = st_im.resize((spare_w, spare_h), Image.Resampling.LANCZOS)
    spare_x = (a4_w - spare_w) // 2
    spare_y = box_y + 480

    draw.rounded_rectangle(
        [(spare_x - 10, spare_y - 10), (spare_x + spare_w + 10, spare_y + spare_h + 10)],
        radius=24,
        outline=(203, 213, 225),
        width=2
    )
    draw.text((spare_x, spare_y - 32), "✂️ SPARE / BACKUP STICKER (FOR SECOND VEHICLE OR GLOVEBOX)", fill=(100, 116, 139), font=font_guide_body)
    page.paste(st_spare, (spare_x, spare_y))

    page.save(pdf_path, "PDF", resolution=300)
    return pdf_path

def generate_printable_pdf_sheet(tag_ids: list, base_url: str, output_pdf_name: str = "parkingbuzz_stickers_sheet.pdf") -> str:
    """
    Arranges stickers onto standard A4 printable sheets (6 per page: 2 columns x 3 rows).
    At 300 DPI, each sticker is 76mm x 96mm (standard vehicle windshield sticker size).
    """
    pdf_path = os.path.join(OUTPUT_DIR, output_pdf_name)
    a4_w, a4_h = 2480, 3508 # A4 at 300 DPI
    cols, rows = 2, 3
    margin_x = 180
    margin_y = 120
    spacing_x = 100
    spacing_y = 90
    
    st_w = 900
    st_h = 1140
    target_w = (a4_w - (2 * margin_x) - spacing_x) // 2
    target_h = int(st_h * (target_w / st_w))

    pages = []
    current_page = None
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
    
    pdf_path = generate_printable_pdf_sheet(generated_ids, base_url, f"batch_{count}_stickers.pdf")
    print(f"\nAll {count} stickers generated! Printable A4 PDF sheet ready at: {pdf_path}")
    return generated_ids, pdf_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Printable QR Car Stickers")
    parser.add_argument("--count", type=int, default=5, help="Number of stickers to generate")
    parser.add_argument("--domain", type=str, default="http://localhost:8000", help="Deployment domain URL")
    args = parser.parse_args()

    generate_batch(args.count, args.domain)

