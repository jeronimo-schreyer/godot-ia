"""Image helpers: contact sheets and snapshot diffs (Pillow)."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


@dataclass
class Comparison:
    ratio: float  # fraction of pixels that differ beyond the tolerance
    changed: int
    diff_path: Path


def save_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def contact_sheet(files, out: Path, labels=None, columns: int = 4, crop=None, title: str = "",
                  max_width: int = 1920) -> Path:
    """Lays frames out in a grid with a label on each, scaled to fit [max_width]."""
    frames = [Image.open(f).convert("RGB") for f in files]
    if not frames:
        raise ValueError("no frames to put in a contact sheet")
    if crop:
        x, y, w, h = crop
        frames = [im.crop((x, y, x + w, y + h)) for im in frames]
    columns = max(1, min(columns, len(frames)))
    rows = (len(frames) + columns - 1) // columns
    fw, fh = frames[0].size
    scale = min(1.0, max_width / (fw * columns))
    tw, th = int(fw * scale), int(fh * scale)
    header = 26 if title else 0
    sheet = Image.new("RGB", (tw * columns, th * rows + header), (20, 20, 24))
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((8, 6), title, fill=(255, 255, 255))
    for i, frame in enumerate(frames):
        x, y = (i % columns) * tw, header + (i // columns) * th
        sheet.paste(frame.resize((tw, th)), (x, y))
        draw.rectangle([x, y, x + tw - 1, y + th - 1], outline=(0, 0, 0))
        if labels:
            draw.rectangle([x, y, x + 110, y + 16], fill=(0, 0, 0))
            draw.text((x + 4, y + 2), labels[i], fill=(255, 230, 120))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def compare(baseline: Path, current: Path, mask=(), tolerance: int = 24, diff_path: Path = None) -> Comparison:
    """Pixel comparison ignoring [mask] rectangles. Writes base | new | changes (red) to
    [diff_path] when anything differs."""
    base = Image.open(baseline).convert("RGB")
    new = Image.open(current).convert("RGB")
    if base.size != new.size:
        new = new.resize(base.size)
    for (x, y, w, h) in mask:
        for im in (base, new):
            ImageDraw.Draw(im).rectangle([x, y, x + w - 1, y + h - 1], fill=(0, 0, 0))
    diff = ImageChops.difference(base, new).convert("L").point(lambda v: 255 if v > tolerance else 0)
    changed = diff.histogram()[255]
    ratio = changed / (base.size[0] * base.size[1])
    if changed and diff_path:
        overlay = Image.blend(new.convert("L").convert("RGB"), Image.new("RGB", new.size, (0, 0, 0)), 0.5)
        overlay.paste((255, 40, 40), mask=diff)
        w, h = base.size
        out = Image.new("RGB", (w * 3, h))
        for i, im in enumerate((base, new, overlay)):
            out.paste(im, (i * w, 0))
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        out.save(diff_path)
    return Comparison(ratio=ratio, changed=changed, diff_path=diff_path)
