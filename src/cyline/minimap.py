from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from .models import ManualPosition


@dataclass(frozen=True)
class MinimapEstimate:
    x_percent: float | None
    y_percent: float | None
    confidence: float
    method: str
    needs_review: bool
    note: str


def estimate_player_position(
    screenshot_bytes: bytes,
    manual_position: ManualPosition | None,
) -> MinimapEstimate:
    if manual_position is not None:
        return MinimapEstimate(
            x_percent=round(manual_position.x_percent, 2),
            y_percent=round(manual_position.y_percent, 2),
            confidence=1.0,
            method="manual",
            needs_review=False,
            note="ユーザーが手動補正した位置です。",
        )

    try:
        from PIL import Image
    except ImportError:
        return MinimapEstimate(
            x_percent=None,
            y_percent=None,
            confidence=0.0,
            method="unavailable",
            needs_review=True,
            note="Pillowがインストールされていないため、ミニマップ解析をスキップしました。",
        )

    try:
        with Image.open(BytesIO(screenshot_bytes)) as source_image:
            rgb_image = source_image.convert("RGB")
            image_width, image_height = rgb_image.size
            if image_width < 320 or image_height < 240:
                return MinimapEstimate(
                    x_percent=None,
                    y_percent=None,
                    confidence=0.0,
                    method="image_too_small",
                    needs_review=True,
                    note="スクリーンショットが小さすぎるため、ミニマップ解析の信頼度を確保できません。",
                )

            minimap_crop = _crop_likely_minimap(rgb_image)
            marker_position = _find_bright_marker(minimap_crop)
            if marker_position is None:
                return MinimapEstimate(
                    x_percent=None,
                    y_percent=None,
                    confidence=0.0,
                    method="top_left_minimap_bright_marker",
                    needs_review=True,
                    note="信頼できるプレイヤーマーカー候補が見つかりませんでした。",
                )

            marker_x, marker_y, confidence = marker_position
            crop_width, crop_height = minimap_crop.size
            x_percent = round((marker_x / max(crop_width - 1, 1)) * 100, 2)
            y_percent = round((marker_y / max(crop_height - 1, 1)) * 100, 2)

            return MinimapEstimate(
                x_percent=x_percent,
                y_percent=y_percent,
                confidence=confidence,
                method="top_left_minimap_bright_marker",
                needs_review=confidence < 0.55,
                note=(
                    "左上のミニマップ候補から推定した初期版の結果です。"
                    "回転したミニマップを高精度に扱うには、マップ別テンプレートが必要です。"
                ),
            )
    except OSError:
        return MinimapEstimate(
            x_percent=None,
            y_percent=None,
            confidence=0.0,
            method="invalid_image",
            needs_review=True,
            note="アップロードされたファイルを画像として開けませんでした。",
        )


def _crop_likely_minimap(rgb_image):
    image_width, image_height = rgb_image.size
    crop_size = int(min(image_width, image_height) * 0.34)
    crop_size = max(160, min(crop_size, image_width, image_height))
    return rgb_image.crop((0, 0, crop_size, crop_size))


def _find_bright_marker(rgb_image):
    image_width, image_height = rgb_image.size
    pixel_access = rgb_image.load()
    search_step = max(1, min(image_width, image_height) // 220)

    weighted_x_sum = 0.0
    weighted_y_sum = 0.0
    weight_sum = 0.0
    strongest_weight = 0.0

    # The exact VALORANT marker color can vary with UI settings. This heuristic
    # only looks for compact bright UI pixels and deliberately returns low
    # confidence unless the cluster is strong.
    for pixel_y in range(0, image_height, search_step):
        for pixel_x in range(0, image_width, search_step):
            red_value, green_value, blue_value = pixel_access[pixel_x, pixel_y]
            brightness = (red_value + green_value + blue_value) / 3
            channel_spread = max(red_value, green_value, blue_value) - min(
                red_value, green_value, blue_value
            )

            if brightness < 185:
                continue

            if channel_spread > 95:
                continue

            edge_margin = min(pixel_x, pixel_y, image_width - pixel_x, image_height - pixel_y)
            if edge_margin < 8:
                continue

            weight = (brightness - 184) / 71
            weighted_x_sum += pixel_x * weight
            weighted_y_sum += pixel_y * weight
            weight_sum += weight
            strongest_weight = max(strongest_weight, weight)

    if weight_sum <= 0:
        return None

    marker_x = weighted_x_sum / weight_sum
    marker_y = weighted_y_sum / weight_sum
    density_score = min(weight_sum / 240, 1.0)
    confidence = round(min(0.2 + density_score * 0.45 + strongest_weight * 0.2, 0.65), 2)
    return marker_x, marker_y, confidence
