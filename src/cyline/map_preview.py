from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

from .lineup_index import get_lineup_position
from .map_catalog import get_attacker_up_transform, get_map_asset_path, get_map_metadata


def build_search_preview(
    maps_dir: Path,
    valorant_map: str,
    lineups: list[dict],
) -> BytesIO | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    map_image = _load_map_image(maps_dir, valorant_map)
    if map_image is None:
        return None

    preview_image = _orient_map_image(map_image.convert("RGBA"), valorant_map)
    draw = ImageDraw.Draw(preview_image)
    pin_radius = max(12, preview_image.width // 64)
    font = ImageFont.load_default()

    for result_index, lineup in enumerate(lineups[:25], start=1):
        position = get_lineup_position(lineup)
        x_percent = position.get("x_percent")
        y_percent = position.get("y_percent")
        if not isinstance(x_percent, (int, float)) or not isinstance(y_percent, (int, float)):
            continue

        pin_x = int((x_percent / 100) * preview_image.width)
        pin_y = int((y_percent / 100) * preview_image.height)
        fill_color = (45, 212, 191, 235)
        if position.get("needs_review", True):
            fill_color = (251, 191, 36, 235)

        draw.ellipse(
            (
                pin_x - pin_radius,
                pin_y - pin_radius,
                pin_x + pin_radius,
                pin_y + pin_radius,
            ),
            fill=fill_color,
            outline=(3, 19, 18, 255),
            width=3,
        )
        label = str(result_index)
        text_box = draw.textbbox((0, 0), label, font=font)
        text_width = text_box[2] - text_box[0]
        text_height = text_box[3] - text_box[1]
        draw.text(
            (pin_x - text_width / 2, pin_y - text_height / 2),
            label,
            fill=(3, 19, 18, 255),
            font=font,
        )

    output_buffer = BytesIO()
    preview_image.save(output_buffer, format="PNG")
    output_buffer.seek(0)
    return output_buffer


def _orient_map_image(map_image, valorant_map: str):
    transform = get_attacker_up_transform(valorant_map)
    if transform == "rotate_clockwise_90":
        return map_image.rotate(-90)

    if transform == "rotate_counterclockwise_90":
        return map_image.rotate(90)

    if transform == "rotate_180":
        return map_image.rotate(180)

    if transform in {"flip_horizontal", "flip_vertical"}:
        try:
            from PIL import ImageOps
        except ImportError:
            return map_image

        if transform == "flip_horizontal":
            return ImageOps.mirror(map_image)
        return ImageOps.flip(map_image)

    return map_image


def _load_map_image(maps_dir: Path, valorant_map: str):
    try:
        from PIL import Image
    except ImportError:
        return None

    map_asset_path = get_map_asset_path(maps_dir, valorant_map)
    try:
        if map_asset_path.exists():
            with Image.open(map_asset_path) as map_image:
                return map_image.copy()

        metadata = get_map_metadata(valorant_map)
        if metadata is None:
            return None

        with urlopen(metadata["display_icon"], timeout=10) as response:
            image_bytes = BytesIO(response.read())
        with Image.open(image_bytes) as map_image:
            return map_image.copy()
    except OSError:
        return None
