from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
WIKI_ASSETS = ROOT / "docs" / "wiki" / "assets"
PACKAGING_ASSETS = ROOT / "packaging" / "assets"
WIDTH, HEIGHT = 1280, 420


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


if __name__ == "__main__":
    main()
