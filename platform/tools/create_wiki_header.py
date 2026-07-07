from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
WIKI_ASSETS = ROOT / "docs" / "wiki" / "assets"
PACKAGING_ASSETS = ROOT / "packaging" / "assets"
WIDTH, HEIGHT = 1280, 420
SIDEBAR_WIDTH, SIDEBAR_HEIGHT = 420, 150


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    font_root = Path(
        r"C:\Users\tomsl\.cache\codex-runtimes\codex-primary-runtime\dependencies\python"
        r"\Lib\site-packages\reportlab\fonts"
    )
    return ImageFont.truetype(str(font_root / name), size)


TITLE = font("VeraBd.ttf", 62)
TITLE_BIG = font("VeraBd.ttf", 72)
TAG = font("Vera.ttf", 27)
SMALL = font("Vera.ttf", 18)
CHIP = font("VeraBd.ttf", 18)
MONO = font("Vera.ttf", 22)


def rounded_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


def gradient(radial_center: tuple[float, float], sweep_angle: float = 0.25) -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#090014")
    px = img.load()
    cx, cy = radial_center
    for y in range(HEIGHT):
        for x in range(WIDTH):
            nx = x / WIDTH
            ny = y / HEIGHT
            radial = max(0, 1 - math.hypot(nx - cx, ny - cy) * 1.45)
            sweep = max(0, 1 - abs((ny - 0.70) - (nx - 0.12) * sweep_angle) * 3.25)
            violet = int(42 + radial * 84 + sweep * 30)
            blue = int(28 + radial * 25 + sweep * 36)
            px[x, y] = (10 + int(radial * 11), int(sweep * 8), violet + blue, 255)
    return img


def glow_paste(base: Image.Image, layer: Image.Image, xy: tuple[int, int], color=(132, 54, 255), glow=30) -> None:
    alpha = layer.getchannel("A")
    glow_layer = Image.new("RGBA", layer.size, (*color, 0))
    glow_layer.putalpha(alpha.filter(ImageFilter.GaussianBlur(glow)))
    base.alpha_composite(glow_layer, xy)
    base.alpha_composite(layer, xy)


def icon(name: str, size: int, radius: int | None = 18) -> Image.Image:
    img = Image.open(PACKAGING_ASSETS / name).convert("RGBA")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    if radius is not None:
        img.putalpha(rounded_rect_mask(img.size, radius))
    return img


def chips(draw: ImageDraw.ImageDraw, labels: list[str], x: int, y: int, fill=(34, 13, 72, 210)) -> None:
    for label in labels:
        bbox = draw.textbbox((0, 0), label, font=CHIP)
        chip_w = bbox[2] - bbox[0] + 28
        draw.rounded_rectangle((x, y, x + chip_w, y + 42), 12, fill=fill, outline=(181, 123, 255, 150), width=1)
        draw.text((x + 14, y + 12), label, font=CHIP, fill=(243, 237, 255, 245))
        x += chip_w + 12


def frame(img: Image.Image, radius=34) -> Image.Image:
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(mask).rounded_rectangle((18, 18, WIDTH - 18, HEIGHT - 18), 30, fill=255)
    final = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    border_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(border_glow)
    glow_draw.rounded_rectangle(
        (20, 20, WIDTH - 20, HEIGHT - 20),
        30,
        fill=(255, 118, 216, 108),
    )
    final.alpha_composite(border_glow.filter(ImageFilter.GaussianBlur(18)))

    white_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    white_draw = ImageDraw.Draw(white_glow)
    white_draw.rounded_rectangle(
        (21, 21, WIDTH - 21, HEIGHT - 21),
        30,
        fill=(255, 255, 255, 52),
    )
    final.alpha_composite(white_glow.filter(ImageFilter.GaussianBlur(9)))
    final.paste(img, (0, 0), mask)
    return final


def save(name: str, img: Image.Image) -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    WIKI_ASSETS.mkdir(parents=True, exist_ok=True)
    for folder in (ASSETS, WIKI_ASSETS):
        img.save(folder / name, optimize=True)
        print(folder / name)


def save_wiki_only(name: str, img: Image.Image) -> None:
    WIKI_ASSETS.mkdir(parents=True, exist_ok=True)
    img.save(WIKI_ASSETS / name, optimize=True)
    print(WIKI_ASSETS / name)


def sidebar_shell() -> Image.Image:
    img = Image.new("RGBA", (SIDEBAR_WIDTH, SIDEBAR_HEIGHT), (0, 0, 0, 0))
    base = Image.new("RGBA", (SIDEBAR_WIDTH, SIDEBAR_HEIGHT), "#080012")
    px = base.load()
    for y in range(SIDEBAR_HEIGHT):
        for x in range(SIDEBAR_WIDTH):
            nx = x / SIDEBAR_WIDTH
            ny = y / SIDEBAR_HEIGHT
            radial = max(0, 1 - math.hypot(nx - 0.72, ny - 0.42) * 1.25)
            px[x, y] = (9 + int(radial * 12), 0, 30 + int(radial * 86), 255)

    glow = Image.new("RGBA", (SIDEBAR_WIDTH, SIDEBAR_HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.rounded_rectangle((8, 8, SIDEBAR_WIDTH - 8, SIDEBAR_HEIGHT - 8), 20, fill=(255, 118, 216, 100))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))

    mask = Image.new("L", (SIDEBAR_WIDTH, SIDEBAR_HEIGHT), 0)
    ImageDraw.Draw(mask).rounded_rectangle((12, 12, SIDEBAR_WIDTH - 12, SIDEBAR_HEIGHT - 12), 18, fill=255)
    img.paste(base, (0, 0), mask)
    return img


def sidebar_badge_console() -> Image.Image:
    img = sidebar_shell()
    draw = ImageDraw.Draw(img)
    logo = icon("blacklight-studio-icon-flashlight-ring-clean-square-hires.png", 84, radius=10)
    glow_paste(img, logo, (28, 34), color=(255, 118, 216), glow=18)
    draw.text((132, 38), "BLACKLIGHT", font=font("VeraBd.ttf", 25), fill=(255, 255, 255, 255))
    draw.text((132, 68), "WIKI", font=font("VeraBd.ttf", 25), fill=(205, 119, 255, 255))
    draw.text((134, 106), "$ demo --verbose", font=font("Vera.ttf", 17), fill=(242, 219, 255, 230))
    return img


def sidebar_badge_map() -> Image.Image:
    img = sidebar_shell()
    draw = ImageDraw.Draw(img)
    logo = icon("blacklight-studio-icon-clean-square-hires.png", 76, radius=10)
    glow_paste(img, logo, (31, 37), color=(255, 118, 216), glow=18)
    draw.text((126, 35), "START", font=font("VeraBd.ttf", 21), fill=(255, 255, 255, 255))
    draw.text((126, 63), "BUILD", font=font("VeraBd.ttf", 21), fill=(201, 116, 255, 255))
    draw.text((126, 91), "OPERATE", font=font("VeraBd.ttf", 21), fill=(255, 188, 232, 255))
    draw.line((278, 46, 376, 46), fill=(255, 118, 216, 150), width=3)
    draw.line((278, 74, 376, 74), fill=(170, 96, 255, 135), width=3)
    draw.line((278, 102, 376, 102), fill=(255, 255, 255, 105), width=3)
    return img


def sidebar_badge_minimal() -> Image.Image:
    img = sidebar_shell()
    draw = ImageDraw.Draw(img)
    logo = icon("blacklight-studio-icon-clean-square-hires.png", 70, radius=10)
    glow_paste(img, logo, (32, 40), color=(255, 118, 216), glow=18)
    draw.text((124, 45), ".Blacklight", font=font("VeraBd.ttf", 30), fill=(255, 255, 255, 255))
    draw.text((126, 88), "mock -> prompt -> trace", font=font("Vera.ttf", 16), fill=(239, 217, 255, 230))
    return img


def sidebar_orb() -> Image.Image:
    final_size = 192
    scale = 4
    size = final_size * scale
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    def s(value: float) -> int:
        return int(value * scale)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((s(44), s(139), s(158), s(176)), fill=(0, 0, 0, 105))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s(11))))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((s(29), s(26), s(163), s(162)), fill=(255, 118, 216, 78))
    gdraw.ellipse((s(48), s(43), s(148), s(147)), fill=(138, 70, 255, 145))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(12))))

    sphere = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = sphere.load()
    cx, cy = s(96), s(92)
    radius = s(61)
    light = (-0.55, -0.64, 0.72)
    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.hypot(dx, dy)
            if dist > radius:
                continue
            nx = dx / radius
            ny = dy / radius
            z = math.sqrt(max(0, 1 - nx * nx - ny * ny))
            diffuse = max(0, nx * light[0] + ny * light[1] + z * light[2])
            rim = max(0, (dist / radius - 0.62) / 0.38)
            lower = max(0, ny)
            spec = max(0, nx * -0.46 + ny * -0.62 + z * 0.92) ** 20
            core = max(0, 1 - dist / radius)

            red = int(8 + diffuse * 38 + rim * 44 + spec * 82 + core * 8 + lower * 12)
            green = int(0 + diffuse * 14 + rim * 8 + spec * 58)
            blue = int(38 + diffuse * 114 + rim * 118 + spec * 112 + core * 22 + lower * 26)
            alpha = int(255 * min(1, (radius - dist + s(1.4)) / s(1.4)))
            pixels[x, y] = (min(255, red), min(255, green), min(255, blue), alpha)
    img.alpha_composite(sphere)

    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse((s(37), s(33), s(155), s(151)), outline=(255, 255, 255, 52), width=s(1.1))
    odraw.arc((s(38), s(34), s(154), s(150)), 206, 320, fill=(255, 255, 255, 132), width=s(2.0))
    odraw.arc((s(41), s(37), s(151), s(147)), 315, 44, fill=(255, 118, 216, 92), width=s(1.4))
    odraw.ellipse((s(58), s(45), s(99), s(68)), fill=(255, 255, 255, 38))
    odraw.ellipse((s(68), s(49), s(90), s(60)), fill=(255, 255, 255, 42))
    odraw.ellipse((s(59), s(119), s(137), s(151)), fill=(8, 0, 28, 34))
    img.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(s(0.35))))

    mark_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark_draw = ImageDraw.Draw(mark_layer)
    mark_font = font("VeraBd.ttf", s(43))
    bbox = mark_draw.textbbox((0, 0), ".B", font=mark_font)
    mark_w = bbox[2] - bbox[0]
    mark_h = bbox[3] - bbox[1]
    mark_x = (size - mark_w) / 2 + s(7)
    mark_y = (size - mark_h) / 2 - s(1)
    mark_draw.text((mark_x + s(1.2), mark_y + s(1.5)), ".B", font=mark_font, fill=(18, 0, 42, 155))
    mark_draw.text((mark_x, mark_y), ".B", font=mark_font, fill=(255, 255, 255, 255))

    mark_mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mark_mask).ellipse((cx - radius + s(2), cy - radius + s(2), cx + radius - s(2), cy + radius - s(2)), fill=255)
    img.alpha_composite(mark_layer, (0, 0))

    return img.resize((final_size, final_size), Image.Resampling.LANCZOS)


def variant_classic() -> Image.Image:
    img = gradient((0.78, 0.38))
    soft = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(soft)
    sdraw.polygon([(640, 170), (1110, 30), (1280, 92), (760, 230)], fill=(125, 69, 255, 52))
    sdraw.polygon([(606, 225), (1280, 262), (1280, 382), (690, 292)], fill=(170, 102, 255, 36))
    sdraw.ellipse((860, -110, 1450, 470), fill=(116, 42, 255, 55))
    sdraw.ellipse((-260, 120, 520, 680), fill=(38, 12, 95, 72))
    img.alpha_composite(soft.filter(ImageFilter.GaussianBlur(32)))
    draw = ImageDraw.Draw(img)
    draw.line((54, 350, 1228, 350), fill=(151, 88, 255, 68), width=2)
    logo = icon("blacklight-studio-icon-flashlight-ring-clean-square-hires.png", 275)
    glow_paste(img, logo, (905, 72), glow=34)
    draw.rounded_rectangle((905, 72, 1179, 346), 18, outline=(190, 130, 255, 72), width=1)
    draw.text((74, 82), "BLACKLIGHT", font=TITLE, fill=(255, 255, 255, 255))
    draw.text((74, 146), "STUDIO", font=TITLE, fill=(172, 96, 255, 255))
    draw.text((78, 228), "AI workflow platform starter", font=TAG, fill=(232, 222, 255, 245))
    draw.text((79, 266), "Provider routing, prompts, evals, guardrails, and traces in one compact kit.", font=SMALL, fill=(190, 176, 220, 235))
    chips(draw, ["PROVIDERS", "PROMPTS", "EVALS", "GUARDRAILS", "TRACES"], 74, 332)
    beams = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(beams)
    for offset, alpha in [(0, 180), (9, 64), (-9, 64)]:
        bdraw.line((585, 189 + offset, 920, 154 + offset), fill=(142, 68, 255, alpha), width=4)
        bdraw.line((588, 231 + offset, 920, 236 + offset), fill=(142, 68, 255, alpha), width=4)
    img.alpha_composite(beams.filter(ImageFilter.GaussianBlur(2)))
    return frame(img)


def variant_spotlight() -> Image.Image:
    img = gradient((0.24, 0.46), 0.18)
    draw = ImageDraw.Draw(img)
    beam = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(beam)
    bdraw.polygon([(325, 116), (1200, 38), (1200, 174), (338, 244)], fill=(166, 102, 255, 54))
    bdraw.polygon([(320, 190), (1200, 218), (1200, 356), (346, 288)], fill=(102, 72, 255, 38))
    img.alpha_composite(beam.filter(ImageFilter.GaussianBlur(18)))
    logo = icon("blacklight-studio-icon-clean-square-hires.png", 240)
    glow_paste(img, logo, (68, 88), glow=36)
    draw.text((358, 88), "Blacklight Studio", font=TITLE_BIG, fill=(255, 255, 255, 255))
    draw.text((362, 176), "Route every model call through accountable workflow layers.", font=TAG, fill=(229, 220, 255, 245))
    draw.text((364, 240), "mock-first local dev / provider adapters / prompt versions / traceable evals", font=MONO, fill=(190, 176, 220, 235))
    chips(draw, ["LOCAL-FIRST", "AUDITABLE", "EXTENSIBLE"], 362, 314, fill=(15, 7, 34, 218))
    return frame(img)


def variant_console() -> Image.Image:
    img = gradient((0.62, 0.2), 0.42)
    draw = ImageDraw.Draw(img)
    logo = icon("blacklight-studio-icon-flashlight-ring-clean-square-hires.png", 190)
    glow_paste(img, logo, (948, 44), glow=40)
    panel = (76, 76, 835, 326)
    draw.rounded_rectangle(panel, 16, fill=(8, 5, 18, 218), outline=(167, 106, 255, 130), width=2)
    draw.text((104, 106), "$ blacklight demo --verbose", font=MONO, fill=(180, 119, 255, 255))
    draw.text((104, 152), "provider: mock-ticket-classifier", font=MONO, fill=(245, 242, 255, 245))
    draw.text((104, 196), "guardrail: accepted", font=MONO, fill=(245, 242, 255, 245))
    draw.text((104, 240), "trace: latency, tokens, cost, eval_case_id", font=MONO, fill=(245, 242, 255, 245))
    draw.text((902, 256), "BLACKLIGHT", font=font("VeraBd.ttf", 36), fill=(255, 255, 255, 255))
    draw.text((902, 296), "STUDIO WIKI", font=font("VeraBd.ttf", 36), fill=(176, 104, 255, 255))
    return frame(img)


def variant_minimal() -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), "#080012")
    draw = ImageDraw.Draw(img)
    for i in range(16):
        x = 40 + i * 82
        color = (91, 34, 191, 65 if i % 2 else 38)
        draw.line((x, 42, x + 260, 378), fill=color, width=2)
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((444, -230, 1380, 706), fill=(118, 45, 255, 76))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(55)))
    logo = icon("blacklight-studio-icon-clean-square-hires.png", 175)
    glow_paste(img, logo, (91, 118), glow=32)
    draw.text((308, 122), ".Blacklight", font=TITLE_BIG, fill=(255, 255, 255, 255))
    draw.text((312, 212), "Compact AI workflow infrastructure with receipts.", font=TAG, fill=(226, 216, 255, 245))
    chips(draw, ["PROMPTS", "PROVIDERS", "REVIEWS", "EVALS", "OBSERVABILITY"], 312, 296, fill=(11, 5, 27, 226))
    return frame(img)


def contact_sheet(names: list[str]) -> Image.Image:
    thumbs = []
    for name in names:
        im = Image.open(ASSETS / name).convert("RGB")
        im.thumbnail((560, 184), Image.Resampling.LANCZOS)
        thumbs.append((name, im))
    sheet = Image.new("RGB", (1200, 520), "#12071f")
    draw = ImageDraw.Draw(sheet)
    for idx, (name, im) in enumerate(thumbs):
        x = 36 + (idx % 2) * 590
        y = 36 + (idx // 2) * 240
        sheet.paste(im, (x, y))
        draw.text((x, y + im.height + 12), name, font=SMALL, fill=(235, 228, 255))
    return sheet


def main() -> None:
    variants = {
        "blacklight-studio-wiki-header.png": variant_classic(),
        "blacklight-studio-wiki-header-spotlight.png": variant_spotlight(),
        "blacklight-studio-wiki-header-console.png": variant_console(),
        "blacklight-studio-wiki-header-minimal.png": variant_minimal(),
    }
    for name, img in variants.items():
        save(name, img)
    save("blacklight-studio-wiki-header-variations.png", contact_sheet(list(variants)))
    save_wiki_only("blacklight-sidebar-console.png", sidebar_badge_console())
    save_wiki_only("blacklight-sidebar-map.png", sidebar_badge_map())
    save_wiki_only("blacklight-sidebar-minimal.png", sidebar_badge_minimal())
    save_wiki_only("blacklight-sidebar-orb.png", sidebar_orb())


if __name__ == "__main__":
    main()
