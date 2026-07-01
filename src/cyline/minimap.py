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


@dataclass(frozen=True)
class MapAlignment:
    match_x: float
    match_y: float
    match_size: float
    score: float
    operations: tuple[str, ...]
    template_left: int
    template_top: int
    template_width: int
    template_height: int
    template_image_width: int
    template_image_height: int


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
            map_alignment = _match_minimap_to_selected_map(
                minimap_crop,
                lineup_map=valorant_map,
                maps_dir=maps_dir,
            )
            marker_position = _find_player_marker(
                minimap_crop,
                search_bounds=_alignment_search_bounds(map_alignment, minimap_crop.size),
            )
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

            map_position = _build_position_from_alignment(
                marker_x=marker_x,
                marker_y=marker_y,
                marker_confidence=marker_confidence,
                map_alignment=map_alignment,
                valorant_map=valorant_map,
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
    crop_left = int(image_width * 0.03)
    crop_top = int(image_height * 0.09)
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


def _find_player_marker(rgb_image, search_bounds: tuple[int, int, int, int] | None = None):
    if search_bounds is not None:
        left, top, right, bottom = search_bounds
        if right <= left or bottom <= top:
            return None

        bounded_image = rgb_image.crop((left, top, right, bottom))
        bounded_marker = _find_player_marker(bounded_image)
        if bounded_marker is None:
            return None

        marker_x, marker_y, confidence = bounded_marker
        return marker_x + left, marker_y + top, confidence

    pin_marker = _find_red_white_pin_marker(rgb_image)
    if pin_marker is not None:
        return pin_marker

    compact_marker = _find_compact_bright_marker(rgb_image)
    if compact_marker is not None:
        return compact_marker

    return None


def _find_red_white_pin_marker(rgb_image):
    image_width, image_height = rgb_image.size
    pixel_access = rgb_image.load()

    red_pixels: list[tuple[int, int]] = []
    for pixel_y in range(image_height):
        for pixel_x in range(image_width):
            red_value, green_value, blue_value = pixel_access[pixel_x, pixel_y]
            brightness = (red_value + green_value + blue_value) / 3
            saturation = _saturation(red_value, green_value, blue_value)

            is_red_pin_accent = (
                brightness >= 80
                and red_value >= 135
                and red_value >= green_value + 18
                and red_value >= blue_value + 18
                and saturation >= 0.16
            )
            if is_red_pin_accent:
                red_pixels.append((pixel_x, pixel_y))

    best_marker = None
    for red_component in _connected_components(red_pixels, image_width, image_height):
        red_count = len(red_component)
        red_min_x, red_min_y, red_max_x, red_max_y = _component_bounds(red_component)
        red_width = red_max_x - red_min_x + 1
        red_height = red_max_y - red_min_y + 1
        if red_count < 3 or red_count > 120 or red_width > 22 or red_height > 22:
            continue

        edge_margin = min(red_min_x, red_min_y, image_width - red_max_x, image_height - red_max_y)
        if edge_margin < 5:
            continue

        white_pixels = _nearby_white_pin_pixels(
            pixel_access,
            image_width,
            image_height,
            red_min_x,
            red_min_y,
            red_max_x,
            red_max_y,
        )
        if len(white_pixels) < 20:
            continue

        combined_pixels = [(x, y, 2.0) for x, y in red_component]
        combined_pixels.extend((x, y, 1.0) for x, y in white_pixels)
        weight_sum = sum(weight for _x, _y, weight in combined_pixels)
        marker_x = sum(x * weight for x, _y, weight in combined_pixels) / weight_sum
        marker_y = sum(y * weight for _x, y, weight in combined_pixels) / weight_sum
        marker_score = red_count * 2.0 + min(len(white_pixels), 220) * 0.35
        confidence = round(min(0.62 + red_count / 80 + len(white_pixels) / 420, 0.92), 2)
        candidate = (marker_score, marker_x, marker_y, confidence)
        if best_marker is None or candidate[0] > best_marker[0]:
            best_marker = candidate

    if best_marker is None:
        return None

    _marker_score, marker_x, marker_y, confidence = best_marker
    return marker_x, marker_y, confidence


def _saturation(red_value: int, green_value: int, blue_value: int) -> float:
    max_channel = max(red_value, green_value, blue_value)
    min_channel = min(red_value, green_value, blue_value)
    if max_channel == 0:
        return 0.0
    return (max_channel - min_channel) / max_channel


def _connected_components(
    pixels: list[tuple[int, int]],
    image_width: int,
    image_height: int,
) -> list[list[tuple[int, int]]]:
    pixel_set = set(pixels)
    components: list[list[tuple[int, int]]] = []

    while pixel_set:
        start_pixel = pixel_set.pop()
        stack = [start_pixel]
        component = [start_pixel]
        while stack:
            current_x, current_y = stack.pop()
            for neighbor_y in range(current_y - 1, current_y + 2):
                for neighbor_x in range(current_x - 1, current_x + 2):
                    if (
                        0 <= neighbor_x < image_width
                        and 0 <= neighbor_y < image_height
                        and (neighbor_x, neighbor_y) in pixel_set
                    ):
                        pixel_set.remove((neighbor_x, neighbor_y))
                        stack.append((neighbor_x, neighbor_y))
                        component.append((neighbor_x, neighbor_y))
        components.append(component)

    return components


def _component_bounds(component: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    x_values = [pixel[0] for pixel in component]
    y_values = [pixel[1] for pixel in component]
    return min(x_values), min(y_values), max(x_values), max(y_values)


def _nearby_white_pin_pixels(
    pixel_access,
    image_width: int,
    image_height: int,
    red_min_x: int,
    red_min_y: int,
    red_max_x: int,
    red_max_y: int,
) -> list[tuple[int, int]]:
    search_min_x = max(0, red_min_x - 16)
    search_min_y = max(0, red_min_y - 16)
    search_max_x = min(image_width - 1, red_max_x + 16)
    search_max_y = min(image_height - 1, red_max_y + 18)
    white_pixels: list[tuple[int, int]] = []

    for pixel_y in range(search_min_y, search_max_y + 1):
        for pixel_x in range(search_min_x, search_max_x + 1):
            red_value, green_value, blue_value = pixel_access[pixel_x, pixel_y]
            brightness = (red_value + green_value + blue_value) / 3
            saturation = _saturation(red_value, green_value, blue_value)
            channel_spread = max(red_value, green_value, blue_value) - min(
                red_value,
                green_value,
                blue_value,
            )
            is_pin_white = (
                brightness >= 165
                and saturation <= 0.34
                and channel_spread <= 95
            )
            if is_pin_white:
                white_pixels.append((pixel_x, pixel_y))

    return white_pixels


def _find_compact_bright_marker(rgb_image):
    image_width, image_height = rgb_image.size
    pixel_access = rgb_image.load()
    bright_pixels: list[tuple[int, int]] = []

    for pixel_y in range(image_height):
        for pixel_x in range(image_width):
            red_value, green_value, blue_value = pixel_access[pixel_x, pixel_y]
            brightness = (red_value + green_value + blue_value) / 3
            channel_spread = max(red_value, green_value, blue_value) - min(
                red_value, green_value, blue_value
            )

            if brightness >= 185 and channel_spread <= 80:
                bright_pixels.append((pixel_x, pixel_y))

    best_component = None
    for component in _connected_components(bright_pixels, image_width, image_height):
        component_size = len(component)
        min_x, min_y, max_x, max_y = _component_bounds(component)
        component_width = max_x - min_x + 1
        component_height = max_y - min_y + 1
        edge_margin = min(min_x, min_y, image_width - max_x, image_height - max_y)
        if (
            12 <= component_size <= 260
            and component_width <= 28
            and component_height <= 28
            and edge_margin >= 5
        ):
            score = component_size - abs(component_width - component_height) * 2
            candidate = (score, component)
            if best_component is None or candidate[0] > best_component[0]:
                best_component = candidate

    if best_component is None:
        return None

    _score, component = best_component
    marker_x = sum(pixel[0] for pixel in component) / len(component)
    marker_y = sum(pixel[1] for pixel in component) / len(component)
    confidence = round(min(0.48 + len(component) / 420, 0.72), 2)
    return marker_x, marker_y, confidence


def _match_minimap_to_selected_map(
    minimap_crop,
    lineup_map: str,
    maps_dir: Path,
) -> MapAlignment | None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    crop_array = np.array(minimap_crop.convert("RGB"))
    map_asset_path = get_map_asset_path(maps_dir, lineup_map)
    template_image = _load_template_image(map_asset_path, lineup_map, cv2, np)
    if template_image is None:
        return None

    template_mask, template_bounds, template_size = _prepare_template_shape_mask(
        template_image,
        cv2,
        np,
    )
    if template_mask is None:
        return None

    best_match = _find_best_color_template_match(
        crop_array,
        template_image,
        template_bounds,
        cv2,
        np,
    )
    if best_match is None:
        crop_mask = _build_minimap_shape_mask(crop_array, cv2, np)
        best_match = _find_best_template_match(crop_mask, template_mask, cv2)
    if best_match is None:
        return None

    match_x, match_y, match_size, score, operations = best_match
    if score < 0.35:
        return None

    return MapAlignment(
        match_x=match_x,
        match_y=match_y,
        match_size=match_size,
        score=score,
        operations=operations,
        template_left=template_bounds[0],
        template_top=template_bounds[1],
        template_width=template_bounds[2],
        template_height=template_bounds[3],
        template_image_width=template_size[0],
        template_image_height=template_size[1],
    )


def _alignment_search_bounds(
    map_alignment: MapAlignment | None,
    crop_size: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    if map_alignment is None:
        return None

    crop_width, crop_height = crop_size
    margin = max(6, int(map_alignment.match_size * 0.04))
    left = max(0, int(map_alignment.match_x) - margin)
    top = max(0, int(map_alignment.match_y) - margin)
    right = min(crop_width, int(map_alignment.match_x + map_alignment.match_size) + margin)
    bottom = min(crop_height, int(map_alignment.match_y + map_alignment.match_size) + margin)
    return left, top, right, bottom


def _build_position_from_alignment(
    marker_x: float,
    marker_y: float,
    marker_confidence: float,
    map_alignment: MapAlignment | None,
    valorant_map: str,
    fallback_x_percent: float,
    fallback_y_percent: float,
    map_width: int | None,
    map_height: int | None,
) -> MapPosition:
    if map_alignment is None:
        return _build_fallback_map_position(
            x_percent=fallback_x_percent,
            y_percent=fallback_y_percent,
            map_width=map_width,
            map_height=map_height,
            confidence=round(marker_confidence * 0.5, 2),
            needs_review=True,
            method="marker_percent_without_map_alignment",
            valorant_map=valorant_map,
        )

    oriented_x_percent = (
        (marker_x - map_alignment.match_x)
        / max(map_alignment.match_size - 1, 1)
    ) * 100
    oriented_y_percent = (
        (marker_y - map_alignment.match_y)
        / max(map_alignment.match_size - 1, 1)
    ) * 100
    base_x_percent, base_y_percent = _invert_operations(
        oriented_x_percent,
        oriented_y_percent,
        map_alignment.operations,
    )
    base_x_percent, base_y_percent = _template_content_percent_to_display_percent(
        base_x_percent,
        base_y_percent,
        map_alignment,
    )
    base_x_percent, base_y_percent = _apply_attacker_up_transform(
        base_x_percent,
        base_y_percent,
        valorant_map,
    )
    base_x_percent = _clamp_percent(base_x_percent)
    base_y_percent = _clamp_percent(base_y_percent)

    confidence = round(min(map_alignment.score * 0.65 + marker_confidence * 0.35, 0.95), 2)
    needs_review = (
        confidence < 0.62
        or oriented_x_percent < 0
        or oriented_y_percent < 0
        or oriented_x_percent > 100
        or oriented_y_percent > 100
    )

    return _build_map_position(
        x_percent=base_x_percent,
        y_percent=base_y_percent,
        map_width=map_width,
        map_height=map_height,
        confidence=confidence,
        needs_review=needs_review,
        method=f"map_alignment:{'+'.join(map_alignment.operations) or 'identity'}",
    )


def _template_content_percent_to_display_percent(
    x_percent: float,
    y_percent: float,
    map_alignment: MapAlignment,
) -> tuple[float, float]:
    content_x = map_alignment.template_left + (x_percent / 100) * max(
        map_alignment.template_width - 1,
        1,
    )
    content_y = map_alignment.template_top + (y_percent / 100) * max(
        map_alignment.template_height - 1,
        1,
    )
    display_x_percent = (
        content_x / max(map_alignment.template_image_width - 1, 1)
    ) * 100
    display_y_percent = (
        content_y / max(map_alignment.template_image_height - 1, 1)
    ) * 100
    return display_x_percent, display_y_percent


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


def _find_best_color_template_match(crop_array, template_image, template_bounds, cv2, np):
    template_rgb, template_alpha = _template_rgb_and_alpha(
        template_image,
        template_bounds,
        cv2,
        np,
    )
    if template_rgb is None or template_alpha is None:
        return None

    crop_height, crop_width = crop_array.shape[:2]
    maximum_size = min(crop_width, crop_height)
    candidate_sizes = sorted(
        {
            int(maximum_size * ratio)
            for ratio in (0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)
            if int(maximum_size * ratio) >= 90
        }
    )
    if not candidate_sizes:
        return None

    outline_distance = _build_minimap_outline_distance(crop_array, cv2, np)
    best_match = None
    preferred_operations = _preferred_orientation_operations()
    preferred_operation_set = set(preferred_operations)
    operation_batches = [
        preferred_operations,
        [
            operations
            for operations in _orientation_operations()
            if operations not in preferred_operation_set
        ],
    ]
    for batch_index, operation_batch in enumerate(operation_batches):
        for operations in operation_batch:
            transformed_rgb = _apply_template_image_operations(
                template_rgb,
                operations,
                cv2,
                cv2.INTER_LINEAR,
            )
            transformed_alpha = _apply_template_operations(template_alpha, operations, cv2)
            for candidate_size in candidate_sizes:
                resized_rgb = cv2.resize(
                    transformed_rgb,
                    (candidate_size, candidate_size),
                    interpolation=cv2.INTER_AREA,
                )
                resized_alpha = cv2.resize(
                    transformed_alpha,
                    (candidate_size, candidate_size),
                    interpolation=cv2.INTER_NEAREST,
                )
                if np.count_nonzero(resized_alpha) < 50:
                    continue

                try:
                    match_result = cv2.matchTemplate(
                        crop_array,
                        resized_rgb,
                        cv2.TM_CCORR_NORMED,
                        mask=resized_alpha,
                    )
                except cv2.error:
                    continue

                match_result = np.nan_to_num(match_result, nan=-1.0, posinf=-1.0, neginf=-1.0)
                _min_value, color_score, _min_location, max_location = cv2.minMaxLoc(match_result)
                edge_score = _score_outline_alignment(
                    outline_distance,
                    resized_alpha,
                    max_location,
                    cv2,
                    np,
                )
                coverage_score = candidate_size / maximum_size
                combined_score = (
                    float(color_score) * 0.68
                    + float(coverage_score) * 0.22
                    + float(edge_score) * 0.10
                ) - _operation_complexity_penalty(operations)
                candidate = (
                    float(max_location[0]),
                    float(max_location[1]),
                    float(candidate_size),
                    combined_score,
                    operations,
                )
                if best_match is None or candidate[3] > best_match[3]:
                    best_match = candidate

        if batch_index == 0 and best_match is not None and best_match[3] >= 0.88:
            return best_match

    return best_match


def _operation_complexity_penalty(operations: tuple[str, ...]) -> float:
    penalty = 0.0
    for operation in operations:
        if operation.startswith("rot:"):
            angle = float(operation.split(":", 1)[1])
            if angle % 90 != 0:
                penalty += 0.02
        elif operation in {"flip_h", "flip_v"}:
            penalty += 0.006
    return penalty


def _preferred_orientation_operations() -> list[tuple[str, ...]]:
    operations: list[tuple[str, ...]] = []
    flip_sets = [
        tuple(),
        ("flip_h",),
        ("flip_v",),
        ("flip_h", "flip_v"),
    ]
    for angle in (0, 90, 180, 270):
        rotation = tuple() if angle == 0 else (f"rot:{angle}",)
        for flip_set in flip_sets:
            operations.append(flip_set + rotation)
    return operations


def _template_rgb_and_alpha(template_image, template_bounds, cv2, np):
    crop_left, crop_top, crop_width, crop_height = template_bounds
    if crop_width <= 0 or crop_height <= 0:
        return None, None

    if template_image.shape[2] == 4:
        template_rgb = cv2.cvtColor(template_image[:, :, :3], cv2.COLOR_BGR2RGB)
        template_alpha = template_image[:, :, 3]
    else:
        template_rgb = cv2.cvtColor(template_image, cv2.COLOR_BGR2RGB)
        gray_image = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)
        _, template_alpha = cv2.threshold(gray_image, 20, 255, cv2.THRESH_BINARY)

    crop_right = crop_left + crop_width
    crop_bottom = crop_top + crop_height
    cropped_rgb = template_rgb[crop_top:crop_bottom, crop_left:crop_right]
    cropped_alpha = template_alpha[crop_top:crop_bottom, crop_left:crop_right]
    return cropped_rgb, cropped_alpha.astype(np.uint8)


def _build_minimap_outline_distance(crop_array, cv2, np):
    hsv_image = cv2.cvtColor(crop_array, cv2.COLOR_RGB2HSV)
    saturation = hsv_image[:, :, 1]
    value = hsv_image[:, :, 2]
    channel_spread = crop_array.max(axis=2) - crop_array.min(axis=2)
    outline_mask = (
        (channel_spread <= 45)
        & (saturation <= 50)
        & (value >= 150)
        & (value <= 230)
    ).astype(np.uint8) * 255
    kernel = np.ones((2, 2), np.uint8)
    outline_mask = cv2.morphologyEx(outline_mask, cv2.MORPH_OPEN, kernel)
    outline_mask = cv2.dilate(outline_mask, kernel, iterations=1)
    if np.count_nonzero(outline_mask) == 0:
        return None

    return cv2.distanceTransform(255 - outline_mask, cv2.DIST_L2, 3)


def _score_outline_alignment(outline_distance, resized_alpha, max_location, cv2, np) -> float:
    if outline_distance is None:
        return 0.0

    template_edge = cv2.morphologyEx(
        resized_alpha,
        cv2.MORPH_GRADIENT,
        np.ones((3, 3), np.uint8),
    )
    edge_weights = (template_edge > 0).astype(np.float32)
    edge_count = float(edge_weights.sum())
    if edge_count <= 0:
        return 0.0

    location_x, location_y = max_location
    patch = outline_distance[
        location_y : location_y + resized_alpha.shape[0],
        location_x : location_x + resized_alpha.shape[1],
    ]
    if patch.shape != resized_alpha.shape:
        return 0.0

    mean_distance = float((patch * edge_weights).sum() / edge_count)
    return 1.0 / (1.0 + mean_distance / 12.0)


def _prepare_template_shape_mask(template_image, cv2, np):
    if template_image.shape[2] == 4:
        alpha_mask = template_image[:, :, 3]
        _, template_mask = cv2.threshold(alpha_mask, 10, 255, cv2.THRESH_BINARY)
    else:
        gray_image = cv2.cvtColor(template_image, cv2.COLOR_BGR2GRAY)
        _, template_mask = cv2.threshold(gray_image, 20, 255, cv2.THRESH_BINARY)

    non_zero_points = cv2.findNonZero(template_mask)
    if non_zero_points is None:
        return None, (0, 0, 0, 0), (template_image.shape[1], template_image.shape[0])

    bounds_x, bounds_y, bounds_width, bounds_height = cv2.boundingRect(non_zero_points)
    padding = max(2, int(max(bounds_width, bounds_height) * 0.015))
    crop_left = max(0, bounds_x - padding)
    crop_top = max(0, bounds_y - padding)
    crop_right = min(template_mask.shape[1], bounds_x + bounds_width + padding)
    crop_bottom = min(template_mask.shape[0], bounds_y + bounds_height + padding)
    cropped_mask = template_mask[crop_top:crop_bottom, crop_left:crop_right]

    return (
        cropped_mask,
        (
            crop_left,
            crop_top,
            crop_right - crop_left,
            crop_bottom - crop_top,
        ),
        (template_image.shape[1], template_image.shape[0]),
    )


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
            for ratio in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)
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
    operations: list[tuple[str, ...]] = []
    flip_sets = [
        tuple(),
        ("flip_h",),
        ("flip_v",),
        ("flip_h", "flip_v"),
    ]
    for angle in range(0, 360, 15):
        rotation = tuple() if angle == 0 else (f"rot:{angle}",)
        for flip_set in flip_sets:
            operations.append(flip_set + rotation)
    return operations


def _apply_template_operations(template_mask, operations: tuple[str, ...], cv2):
    return _apply_template_image_operations(
        template_mask,
        operations,
        cv2,
        cv2.INTER_NEAREST,
    )


def _apply_template_image_operations(template_image, operations: tuple[str, ...], cv2, interpolation):
    transformed_template = template_image
    for operation in operations:
        if operation.startswith("rot:"):
            angle = float(operation.split(":", 1)[1])
            template_height, template_width = transformed_template.shape[:2]
            center = (template_width / 2, template_height / 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            border_value = 0
            if len(transformed_template.shape) == 3:
                border_value = (0, 0, 0)
            transformed_template = cv2.warpAffine(
                transformed_template,
                rotation_matrix,
                (template_width, template_height),
                flags=interpolation,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=border_value,
            )
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
        if operation.startswith("rot:"):
            angle = float(operation.split(":", 1)[1])
            base_x_percent, base_y_percent = _rotate_percent_point(
                base_x_percent,
                base_y_percent,
                -angle,
            )
        elif operation == "flip_h":
            base_x_percent = 100 - base_x_percent
        elif operation == "flip_v":
            base_y_percent = 100 - base_y_percent
    return base_x_percent, base_y_percent


def _rotate_percent_point(
    x_percent: float,
    y_percent: float,
    angle_degrees: float,
) -> tuple[float, float]:
    import math

    radians = math.radians(angle_degrees)
    cos_value = math.cos(radians)
    sin_value = math.sin(radians)
    centered_x = x_percent - 50.0
    centered_y = y_percent - 50.0
    rotated_x = centered_x * cos_value + centered_y * sin_value
    rotated_y = -centered_x * sin_value + centered_y * cos_value
    return rotated_x + 50.0, rotated_y + 50.0


def _apply_attacker_up_transform(
    x_percent: float,
    y_percent: float,
    valorant_map: str,
) -> tuple[float, float]:
    transform = get_attacker_up_transform(valorant_map)
    if transform == "rotate_clockwise_90":
        return _rotate_percent_point(x_percent, y_percent, 270)
    if transform == "rotate_counterclockwise_90":
        return _rotate_percent_point(x_percent, y_percent, 90)
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


def _build_fallback_map_position(
    x_percent: float | None,
    y_percent: float | None,
    map_width: int | None,
    map_height: int | None,
    confidence: float,
    needs_review: bool,
    method: str,
    valorant_map: str,
) -> MapPosition:
    return _build_map_position(
        x_percent=x_percent,
        y_percent=y_percent,
        map_width=map_width,
        map_height=map_height,
        confidence=confidence,
        needs_review=needs_review,
        method=method,
    )


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, value))
