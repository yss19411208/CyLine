from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

from .map_catalog import get_attacker_up_transform, get_map_asset_path, get_map_metadata
from .models import ManualPosition


@dataclass(frozen=True)
class MinimapEstimate:
    x_percent: float | None
    y_percent: float | None
    confidence: float
    method: str
    needs_review: bool
    note: str


@dataclass(frozen=True)
class MapPosition:
    x: float | None
    y: float | None
    x_percent: float | None
    y_percent: float | None
    map_image_width: int | None
    map_image_height: int | None
    orientation: str
    confidence: float
    needs_review: bool
    method: str


@dataclass(frozen=True)
class PositionAnalysis:
    detected_position: MinimapEstimate
    map_position: MapPosition


def estimate_player_position(
    screenshot_bytes: bytes,
    manual_position: ManualPosition | None,
    valorant_map: str,
    maps_dir: Path,
) -> PositionAnalysis:
    map_width, map_height = _read_map_dimensions(valorant_map, maps_dir)

    if manual_position is not None:
        map_position = _build_map_position(
            x_percent=manual_position.x_percent,
            y_percent=manual_position.y_percent,
            map_width=map_width,
            map_height=map_height,
            confidence=1.0,
            needs_review=False,
            method="manual",
        )
        return PositionAnalysis(
            detected_position=MinimapEstimate(
                x_percent=round(manual_position.x_percent, 2),
                y_percent=round(manual_position.y_percent, 2),
                confidence=1.0,
                method="manual",
                needs_review=False,
                note="ユーザーが手動補正した位置です。",
            ),
            map_position=map_position,
        )

    try:
        from PIL import Image
    except ImportError:
        return _unavailable_analysis(
            map_width,
            map_height,
            "unavailable",
            "Pillowがインストールされていないため、ミニマップ解析をスキップしました。",
        )

    try:
        with Image.open(BytesIO(screenshot_bytes)) as source_image:
            rgb_image = source_image.convert("RGB")
            image_width, image_height = rgb_image.size
            if image_width < 320 or image_height < 240:
                return _unavailable_analysis(
                    map_width,
                    map_height,
                    "image_too_small",
                    "スクリーンショットが小さすぎるため、ミニマップ解析の信頼度を確保できません。",
                )

            minimap_crop = _crop_likely_minimap(rgb_image)
            marker_position = _find_player_marker(minimap_crop)
            if marker_position is None:
                return _unavailable_analysis(
                    map_width,
                    map_height,
                    "top_left_minimap_marker",
                    "信頼できるプレイヤーマーカー候補が見つかりませんでした。",
                )

            marker_x, marker_y, marker_confidence = marker_position
            crop_width, crop_height = minimap_crop.size
            detected_x_percent = round((marker_x / max(crop_width - 1, 1)) * 100, 2)
            detected_y_percent = round((marker_y / max(crop_height - 1, 1)) * 100, 2)

            detected_position = MinimapEstimate(
                x_percent=detected_x_percent,
                y_percent=detected_y_percent,
                confidence=marker_confidence,
                method="top_left_minimap_marker",
                needs_review=marker_confidence < 0.55,
                note="左上のミニマップからプレイヤーマーカー候補を検出しました。",
            )

            map_position = _estimate_map_position_from_template(
                minimap_crop=minimap_crop,
                marker_x=marker_x,
                marker_y=marker_y,
                marker_confidence=marker_confidence,
                valorant_map=valorant_map,
                maps_dir=maps_dir,
                fallback_x_percent=detected_x_percent,
                fallback_y_percent=detected_y_percent,
                map_width=map_width,
                map_height=map_height,
            )

            return PositionAnalysis(
                detected_position=detected_position,
                map_position=map_position,
            )
    except OSError:
        return _unavailable_analysis(
            map_width,
            map_height,
            "invalid_image",
            "アップロードされたファイルを画像として開けませんでした。",
        )


def _unavailable_analysis(
    map_width: int | None,
    map_height: int | None,
    method: str,
    note: str,
) -> PositionAnalysis:
    return PositionAnalysis(
        detected_position=MinimapEstimate(
            x_percent=None,
            y_percent=None,
            confidence=0.0,
            method=method,
            needs_review=True,
            note=note,
        ),
        map_position=_build_map_position(
            x_percent=None,
            y_percent=None,
            map_width=map_width,
            map_height=map_height,
            confidence=0.0,
            needs_review=True,
            method=method,
        ),
    )


def _read_map_dimensions(valorant_map: str, maps_dir: Path) -> tuple[int | None, int | None]:
    map_asset_path = get_map_asset_path(maps_dir, valorant_map)
    if not map_asset_path.exists():
        return 1024, 1024

    try:
        from PIL import Image

        with Image.open(map_asset_path) as map_image:
            return map_image.size
    except OSError:
        return 1024, 1024


def _crop_likely_minimap(rgb_image):
    image_width, image_height = rgb_image.size
    crop_left = int(image_width * 0.06)
    crop_top = int(image_height * 0.07)
    crop_size = int(min(image_width * 0.20, image_height * 0.38))
    crop_size = max(160, min(crop_size, image_width - crop_left, image_height - crop_top))
    return rgb_image.crop(
        (
            crop_left,
            crop_top,
            crop_left + crop_size,
            crop_top + crop_size,
        )
    )


def _find_player_marker(rgb_image):
    image_width, image_height = rgb_image.size
    pixel_access = rgb_image.load()
    search_step = max(1, min(image_width, image_height) // 260)

    marker_candidates: list[tuple[float, float, float]] = []
    for pixel_y in range(0, image_height, search_step):
        for pixel_x in range(0, image_width, search_step):
            red_value, green_value, blue_value = pixel_access[pixel_x, pixel_y]
            brightness = (red_value + green_value + blue_value) / 3
            saturation = _saturation(red_value, green_value, blue_value)

            is_yellow_green = (
                green_value >= 120
                and red_value >= 110
                and blue_value <= 140
                and saturation >= 0.22
            )
            is_clean_white_marker = (
                brightness >= 210
                and saturation <= 0.2
                and min(red_value, green_value, blue_value) >= 185
            )

            if not is_yellow_green and not is_clean_white_marker:
                continue

            edge_margin = min(pixel_x, pixel_y, image_width - pixel_x, image_height - pixel_y)
            if edge_margin < 8:
                continue

            marker_weight = 1.0
            if is_yellow_green:
                marker_weight += saturation * 2
            if pixel_y > image_height * 0.42:
                marker_weight += 0.6

            marker_candidates.append((float(pixel_x), float(pixel_y), marker_weight))

    if not marker_candidates:
        return _find_bright_marker(rgb_image)

    clustered_candidates = _largest_marker_cluster(marker_candidates)
    if not clustered_candidates:
        return _find_bright_marker(rgb_image)

    weight_sum = sum(candidate[2] for candidate in clustered_candidates)
    marker_x = sum(candidate[0] * candidate[2] for candidate in clustered_candidates) / weight_sum
    marker_y = sum(candidate[1] * candidate[2] for candidate in clustered_candidates) / weight_sum
    confidence = round(min(0.35 + len(clustered_candidates) / 90 + weight_sum / 380, 0.82), 2)
    return marker_x, marker_y, confidence


def _largest_marker_cluster(candidates: list[tuple[float, float, float]]):
    clusters: list[list[tuple[float, float, float]]] = []
    for candidate in candidates:
        candidate_x, candidate_y, _candidate_weight = candidate
        matched_cluster = None
        for cluster in clusters:
            cluster_x = sum(point[0] for point in cluster) / len(cluster)
            cluster_y = sum(point[1] for point in cluster) / len(cluster)
            if abs(candidate_x - cluster_x) <= 18 and abs(candidate_y - cluster_y) <= 18:
                matched_cluster = cluster
                break
        if matched_cluster is None:
            clusters.append([candidate])
        else:
            matched_cluster.append(candidate)

    if not clusters:
        return []
    return max(clusters, key=lambda cluster: (len(cluster), sum(point[2] for point in cluster)))


def _saturation(red_value: int, green_value: int, blue_value: int) -> float:
    max_channel = max(red_value, green_value, blue_value)
    min_channel = min(red_value, green_value, blue_value)
    if max_channel == 0:
        return 0.0
    return (max_channel - min_channel) / max_channel


def _find_bright_marker(rgb_image):
    image_width, image_height = rgb_image.size
    pixel_access = rgb_image.load()
    search_step = max(1, min(image_width, image_height) // 220)

    weighted_x_sum = 0.0
    weighted_y_sum = 0.0
    weight_sum = 0.0
    strongest_weight = 0.0

    for pixel_y in range(0, image_height, search_step):
        for pixel_x in range(0, image_width, search_step):
            red_value, green_value, blue_value = pixel_access[pixel_x, pixel_y]
            brightness = (red_value + green_value + blue_value) / 3
            channel_spread = max(red_value, green_value, blue_value) - min(
                red_value, green_value, blue_value
            )

            if brightness < 185 or channel_spread > 95:
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


def _estimate_map_position_from_template(
    minimap_crop,
    marker_x: float,
    marker_y: float,
    marker_confidence: float,
    valorant_map: str,
    maps_dir: Path,
    fallback_x_percent: float,
    fallback_y_percent: float,
    map_width: int | None,
    map_height: int | None,
) -> MapPosition:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return _build_map_position(
            x_percent=fallback_x_percent,
            y_percent=fallback_y_percent,
            map_width=map_width,
            map_height=map_height,
            confidence=round(marker_confidence * 0.5, 2),
            needs_review=True,
            method="marker_percent_without_opencv",
        )

    crop_array = np.array(minimap_crop.convert("RGB"))
    crop_mask = _build_minimap_shape_mask(crop_array, cv2, np)
    map_asset_path = get_map_asset_path(maps_dir, valorant_map)
    template_image = _load_template_image(map_asset_path, valorant_map, cv2, np)
    if template_image is None:
        return _build_map_position(
            x_percent=fallback_x_percent,
            y_percent=fallback_y_percent,
            map_width=map_width,
            map_height=map_height,
            confidence=round(marker_confidence * 0.45, 2),
            needs_review=True,
            method="marker_percent_unreadable_map_asset",
        )

    template_mask = _build_template_shape_mask(template_image, cv2, np)
    best_match = _find_best_template_match(crop_mask, template_mask, cv2)
    if best_match is None:
        return _build_map_position(
            x_percent=fallback_x_percent,
            y_percent=fallback_y_percent,
            map_width=map_width,
            map_height=map_height,
            confidence=round(marker_confidence * 0.45, 2),
            needs_review=True,
            method="marker_percent_no_template_match",
        )

    match_x, match_y, match_size, score, operations = best_match
    oriented_x_percent = ((marker_x - match_x) / max(match_size - 1, 1)) * 100
    oriented_y_percent = ((marker_y - match_y) / max(match_size - 1, 1)) * 100
    base_x_percent, base_y_percent = _invert_operations(
        oriented_x_percent,
        oriented_y_percent,
        operations,
    )
    base_x_percent, base_y_percent = _apply_attacker_up_transform(
        base_x_percent,
        base_y_percent,
        valorant_map,
    )
    base_x_percent = _clamp_percent(base_x_percent)
    base_y_percent = _clamp_percent(base_y_percent)

    confidence = round(min(score * 0.65 + marker_confidence * 0.35, 0.95), 2)
    needs_review = (
        confidence < 0.62
        or marker_x < match_x
        or marker_y < match_y
        or marker_x > match_x + match_size
        or marker_y > match_y + match_size
    )

    if needs_review:
        return _build_map_position(
            x_percent=fallback_x_percent,
            y_percent=fallback_y_percent,
            map_width=map_width,
            map_height=map_height,
            confidence=round(marker_confidence * 0.5, 2),
            needs_review=True,
            method=f"marker_percent_low_template_confidence:{'+'.join(operations) or 'identity'}",
        )

    return _build_map_position(
        x_percent=base_x_percent,
        y_percent=base_y_percent,
        map_width=map_width,
        map_height=map_height,
        confidence=confidence,
        needs_review=needs_review,
        method=f"template_match:{'+'.join(operations) or 'identity'}",
    )


def _build_minimap_shape_mask(crop_array, cv2, np):
    hsv_image = cv2.cvtColor(crop_array, cv2.COLOR_RGB2HSV)
    saturation = hsv_image[:, :, 1]
    value = hsv_image[:, :, 2]
    gray_mask = cv2.inRange(crop_array, np.array([55, 55, 55]), np.array([205, 205, 205]))
    low_saturation_mask = cv2.inRange(saturation, 0, 65)
    visible_mask = cv2.inRange(value, 45, 235)
    combined_mask = cv2.bitwise_and(gray_mask, low_saturation_mask)
    combined_mask = cv2.bitwise_and(combined_mask, visible_mask)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)


def _build_template_shape_mask(template_image, cv2, np):
    if template_image.shape[2] == 4:
        alpha_mask = template_image[:, :, 3]
        _, template_mask = cv2.threshold(alpha_mask, 10, 255, cv2.THRESH_BINARY)
        return template_mask

    gray_image = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)
    _, template_mask = cv2.threshold(gray_image, 20, 255, cv2.THRESH_BINARY)
    return template_mask


def _load_template_image(map_asset_path: Path, valorant_map: str, cv2, np):
    if map_asset_path.exists():
        return cv2.imread(str(map_asset_path), cv2.IMREAD_UNCHANGED)

    metadata = get_map_metadata(valorant_map)
    if metadata is None:
        return None

    try:
        with urlopen(metadata["display_icon"], timeout=10) as response:
            image_bytes = response.read()
    except OSError:
        return None

    image_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(image_buffer, cv2.IMREAD_UNCHANGED)


def _find_best_template_match(crop_mask, template_mask, cv2):
    crop_height, crop_width = crop_mask.shape[:2]
    maximum_size = min(crop_width, crop_height)
    candidate_sizes = sorted(
        {
            int(maximum_size * ratio)
            for ratio in (0.58, 0.66, 0.74, 0.82, 0.9, 0.98)
            if int(maximum_size * ratio) >= 90
        }
    )
    best_match = None
    for operations in _orientation_operations():
        transformed_template = _apply_template_operations(template_mask, operations, cv2)
        for candidate_size in candidate_sizes:
            resized_template = cv2.resize(
                transformed_template,
                (candidate_size, candidate_size),
                interpolation=cv2.INTER_AREA,
            )
            if resized_template.shape[0] > crop_height or resized_template.shape[1] > crop_width:
                continue
            match_result = cv2.matchTemplate(
                crop_mask,
                resized_template,
                cv2.TM_CCOEFF_NORMED,
            )
            _min_value, max_value, _min_location, max_location = cv2.minMaxLoc(match_result)
            if best_match is None or max_value > best_match[3]:
                best_match = (
                    float(max_location[0]),
                    float(max_location[1]),
                    float(candidate_size),
                    float(max_value),
                    operations,
                )
    return best_match


def _orientation_operations() -> list[tuple[str, ...]]:
    return [
        tuple(),
        ("rot90",),
        ("rot90", "rot90"),
        ("rot90", "rot90", "rot90"),
        ("flip_h",),
        ("flip_v",),
        ("flip_h", "rot90"),
        ("flip_v", "rot90"),
    ]


def _apply_template_operations(template_mask, operations: tuple[str, ...], cv2):
    transformed_template = template_mask
    for operation in operations:
        if operation == "rot90":
            transformed_template = cv2.rotate(transformed_template, cv2.ROTATE_90_CLOCKWISE)
        elif operation == "flip_h":
            transformed_template = cv2.flip(transformed_template, 1)
        elif operation == "flip_v":
            transformed_template = cv2.flip(transformed_template, 0)
    return transformed_template


def _invert_operations(
    x_percent: float,
    y_percent: float,
    operations: tuple[str, ...],
) -> tuple[float, float]:
    base_x_percent = x_percent
    base_y_percent = y_percent
    for operation in reversed(operations):
        if operation == "rot90":
            base_x_percent, base_y_percent = base_y_percent, 100 - base_x_percent
        elif operation == "flip_h":
            base_x_percent = 100 - base_x_percent
        elif operation == "flip_v":
            base_y_percent = 100 - base_y_percent
    return base_x_percent, base_y_percent


def _apply_attacker_up_transform(
    x_percent: float,
    y_percent: float,
    valorant_map: str,
) -> tuple[float, float]:
    transform = get_attacker_up_transform(valorant_map)
    if transform == "rotate_180":
        return 100 - x_percent, 100 - y_percent
    if transform == "flip_horizontal":
        return 100 - x_percent, y_percent
    if transform == "flip_vertical":
        return x_percent, 100 - y_percent
    return x_percent, y_percent


def _build_map_position(
    x_percent: float | None,
    y_percent: float | None,
    map_width: int | None,
    map_height: int | None,
    confidence: float,
    needs_review: bool,
    method: str,
) -> MapPosition:
    if x_percent is None or y_percent is None or map_width is None or map_height is None:
        return MapPosition(
            x=None,
            y=None,
            x_percent=None,
            y_percent=None,
            map_image_width=map_width,
            map_image_height=map_height,
            orientation="attacker_up",
            confidence=confidence,
            needs_review=True,
            method=method,
        )

    clamped_x_percent = round(_clamp_percent(x_percent), 2)
    clamped_y_percent = round(_clamp_percent(y_percent), 2)
    return MapPosition(
        x=round((clamped_x_percent / 100) * map_width, 2),
        y=round((clamped_y_percent / 100) * map_height, 2),
        x_percent=clamped_x_percent,
        y_percent=clamped_y_percent,
        map_image_width=map_width,
        map_image_height=map_height,
        orientation="attacker_up",
        confidence=confidence,
        needs_review=needs_review,
        method=method,
    )


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))
