import os
import argparse
import secrets
import qrcode
from PIL import Image, ImageDraw, ImageFont
import database

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "stickers_output")

def get_font(size: int, bold: bool = False):
    font_paths = [
        os.path.join(os.path.dirname(__file__), "static/fonts/Arial-Bold.ttf") if bold else os.path.join(os.path.dirname(__file__), "static/fonts/Arial.ttf"),
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
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

def generate_metallic_sticker_card(tag_id: str, base_url: str) -> Image.Image:
    """
    Renders the official luxury brushed aluminum windshield card.
    Exact dimensions: 898 x 1134 px (76 mm x 96 mm at 300 DPI).
    Features:
      - Photorealistic brushed metal with chamfered bevel & rainbow holographic rim
      - High-contrast scannable QR code in a micro-beveled frame
      - Center-embedded elevated 3D Chrome ParkingBuzz badge
      - Laser-engraved Vehicle ID, security subtitles, and windshield mounting instructions
    """
    scan_url = f"{base_url.rstrip('/')}/c/{tag_id}"
    substrate_path = os.path.join(os.path.dirname(__file__), "static/images/official_metallic_card_substrate.png")

    W, H = 898, 1134
    if os.path.exists(substrate_path):
        base = Image.open(substrate_path).convert("RGBA")
        card = base.resize((W, H), Image.Resampling.LANCZOS)
    else:
        card = Image.new("RGBA", (W, H), (230, 233, 238, 255))

    draw = ImageDraw.Draw(card)

    # 1. Generate scannable QR code
    qr_size = 530
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1
    )
    qr.add_data(scan_url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color=(15, 23, 42), back_color="white").convert("RGBA")
    qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.NEAREST)

    # 2. Embed 3D Chrome Emblem in center of QR
    badge_path = os.path.join(os.path.dirname(__file__), "static/images/official_chrome_p_badge.png")
    if os.path.exists(badge_path):
        badge = Image.open(badge_path).convert("RGBA")
        b_size = 148
        badge = badge.resize((b_size, b_size), Image.Resampling.LANCZOS)
        b_pos = ((qr_size - b_size) // 2, (qr_size - b_size) // 2)
        qr_resized.paste(badge, b_pos, badge)

    # 3. Micro-beveled precision plate for QR
    qr_mask = Image.new("L", (qr_size, qr_size), 0)
    qr_mask_draw = ImageDraw.Draw(qr_mask)
    qr_mask_draw.rounded_rectangle([(0, 0), (qr_size, qr_size)], radius=32, fill=255)

    qr_plate = Image.new("RGBA", (qr_size + 16, qr_size + 16), (0, 0, 0, 0))
    plate_draw = ImageDraw.Draw(qr_plate)
    plate_draw.rounded_rectangle([(0, 0), (qr_size + 15, qr_size + 15)], radius=36, fill=(0, 0, 0, 45))
    plate_draw.rounded_rectangle([(4, 4), (qr_size + 11, qr_size + 11)], radius=34, fill=(240, 243, 246, 255), outline=(180, 185, 195, 255), width=2)
    qr_plate.paste(qr_resized, (8, 8), qr_mask)

    qr_x = (W - (qr_size + 16)) // 2
    qr_y = 225
    card.paste(qr_plate, (qr_x, qr_y), qr_plate)

    # 4. Clean Laser-Engraved Typography
    font_id = get_font(42, bold=True)
    font_sub = get_font(23, bold=True)
    font_sub2 = get_font(20, bold=False)

    tag_text = f"VEHICLE ID: {tag_id}"
    bbox = draw.textbbox((0, 0), tag_text, font=font_id)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 815), tag_text, fill=(15, 23, 42), font=font_id)

    sub1 = "100% PRIVACY PROTECTED • INSTANT CONNECT"
    bbox1 = draw.textbbox((0, 0), sub1, font=font_sub)
    tw1 = bbox1[2] - bbox1[0]
    draw.text(((W - tw1) // 2, 878), sub1, fill=(51, 65, 85), font=font_sub)

    sub2 = "PLACE ON WINDSHIELD (FACING OUTWARD)"
    bbox2 = draw.textbbox((0, 0), sub2, font=font_sub2)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) // 2, 924), sub2, fill=(100, 116, 139), font=font_sub2)

    brand = "PARKINGBUZZ CONNECT"
    bbox_b = draw.textbbox((0, 0), brand, font=font_sub2)
    tw_b = bbox_b[2] - bbox_b[0]
    draw.text(((W - tw_b) // 2, 990), brand, fill=(148, 163, 184), font=font_sub2)

    return card.convert("RGB")

def generate_single_sticker_a4_pdf(tag_id: str, base_url: str) -> str:
    """
    Generates a ready-to-print standard A4 PDF (210mm x 297mm) at 300 DPI for a single tag.
    Includes EXACTLY TWO pieces (76 mm x 96 mm each) side-by-side at 100% physical scale.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_path = os.path.join(OUTPUT_DIR, f"sticker_{tag_id}_A4.pdf")
    a4_w, a4_h = 2480, 3508  # A4 at 300 DPI
    page = Image.new("RGB", (a4_w, a4_h), (255, 255, 255))
    draw = ImageDraw.Draw(page)

    font_header = get_font(52, bold=True)
    font_subhead = get_font(28, bold=False)
    font_cut = get_font(24, bold=True)
    font_guide_title = get_font(36, bold=True)
    font_guide_body = get_font(26, bold=False)

    # Top Sheet Header
    draw.text((a4_w // 2, 170), "PARKINGBUZZ — OFFICIAL VEHICLE SECURITY STICKER", fill=(15, 23, 42), font=font_header, anchor="mm")
    draw.text((a4_w // 2, 235), '100% Scale Printable Sheet • Exactly 76 mm x 96 mm (3.0" x 3.8") per sticker', fill=(100, 116, 139), font=font_subhead, anchor="mm")
    draw.line([(180, 280), (a4_w - 180, 280)], fill=(226, 232, 240), width=3)

    # Load high-res metallic sticker (exact 898 x 1134 px = 76mm x 96mm @ 300 DPI)
    st_im = generate_metallic_sticker_card(tag_id, base_url)
    st_w, st_h = st_im.size

    # Position 2 Pieces side-by-side
    gap = 140
    total_w = (st_w * 2) + gap
    start_x = (a4_w - total_w) // 2
    pos_y = 420

    labels = ["PIECE 1: FRONT WINDSHIELD", "PIECE 2: REAR WINDSHIELD / SPARE"]
    for idx, label in enumerate(labels):
        x = start_x + idx * (st_w + gap)
        draw.text((x + st_w // 2, pos_y - 45), label, fill=(14, 165, 233), font=font_cut, anchor="mm")

        # Scissor guideline around sticker
        m = 16
        draw.rounded_rectangle([(x - m, pos_y - m), (x + st_w + m, pos_y + st_h + m)], radius=36, outline=(148, 163, 184), width=3)
        draw.text((x + 20, pos_y - m - 20), "CUT ALONG DOTTED LINE (76 mm x 96 mm)", fill=(100, 116, 139), font=font_cut)

        # Paste card at 100% exact size
        page.paste(st_im, (x, pos_y))

    # Mounting & Printing Guide Box below
    box_y = pos_y + st_h + 120
    draw.rounded_rectangle(
        [(200, box_y), (a4_w - 200, box_y + 450)],
        radius=24,
        fill=(248, 250, 252),
        outline=(226, 232, 240),
        width=3
    )

    draw.text((260, box_y + 45), "Printing & Installation Guide", fill=(15, 23, 42), font=font_guide_title)

    steps = [
        '1. Printer Setting: Select "Actual Size" or "Scale: 100%" (Do NOT select "Fit to Page" or "Shrink to Printable Area").',
        '2. Paper Choice: High-grade photo paper, transparent sticker sheet, or self-adhesive vinyl for best results.',
        '3. Cutting: Cut neatly around the rounded scissor guideline for an exact 76 mm x 96 mm fit.',
        '4. Placement: Affix to the inside of your windshield facing outward (behind rearview mirror or passenger corner).',
        '5. Instant Buzz: Anyone blocking your vehicle scans to privately send an instant audible buzzer or initiate a voice call.'
    ]
    for s_idx, step in enumerate(steps):
        draw.text((260, box_y + 115 + s_idx * 58), step, fill=(51, 65, 85), font=font_guide_body)

    # Footer
    draw.text((a4_w // 2, a4_h - 120), "ParkingBuzz Protection Network • https://contactme-go9v.onrender.com", fill=(148, 163, 184), font=font_subhead, anchor="mm")

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

