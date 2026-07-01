from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_lineups(data_dir: Path) -> list[dict[str, Any]]:
    index_path = data_dir / "index.json"
    if not index_path.exists():
        return []

    try:
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    lineups = index_data.get("lineups", [])
    if not isinstance(lineups, list):
        return []

    return [lineup for lineup in lineups if isinstance(lineup, dict)]


def filter_lineups(
    lineups: list[dict[str, Any]],
    valorant_map: str | None,
    ability: str | None,
    jump: bool | None,
    keyword: str,
) -> list[dict[str, Any]]:
    normalized_keyword = keyword.strip().casefold()
    filtered_lineups = []

    for lineup in lineups:
        if valorant_map and lineup.get("map") != valorant_map:
            continue

        if ability and lineup.get("ability") != ability:
            continue

        if jump is not None and bool(lineup.get("jump")) != jump:
            continue

        if normalized_keyword and normalized_keyword not in _lineup_search_text(lineup):
            continue

        filtered_lineups.append(lineup)

    filtered_lineups.sort(key=lambda lineup: lineup.get("created_at", ""), reverse=True)
    return filtered_lineups


def get_lineup_position(lineup: dict[str, Any]) -> dict[str, Any]:
    map_position = lineup.get("map_position")
    if isinstance(map_position, dict):
        return map_position

    detected_position = lineup.get("detected_position")
    if isinstance(detected_position, dict):
        return {
            "x": None,
            "y": None,
            "x_percent": detected_position.get("x_percent"),
            "y_percent": detected_position.get("y_percent"),
            "map_image_width": None,
            "map_image_height": None,
            "orientation": "attacker_up",
            "confidence": detected_position.get("confidence", 0.0),
            "needs_review": detected_position.get("needs_review", True),
            "method": detected_position.get("method", "legacy_detected_position"),
        }

    return {
        "x": None,
        "y": None,
        "x_percent": None,
        "y_percent": None,
        "map_image_width": None,
        "map_image_height": None,
        "orientation": "attacker_up",
        "confidence": 0.0,
        "needs_review": True,
        "method": "missing_position",
    }


def format_position(position: dict[str, Any]) -> str:
    x_percent = position.get("x_percent")
    y_percent = position.get("y_percent")
    if not isinstance(x_percent, (int, float)) or not isinstance(y_percent, (int, float)):
        return "要確認"

    review_suffix = " / 要確認" if position.get("needs_review", True) else ""
    return f"{x_percent:.2f}, {y_percent:.2f}{review_suffix}"


def _lineup_search_text(lineup: dict[str, Any]) -> str:
    parts = [
        lineup.get("id", ""),
        lineup.get("title", ""),
        lineup.get("description", ""),
        lineup.get("map", ""),
        lineup.get("ability", ""),
        lineup.get("ability_label", ""),
        lineup.get("jump_label", ""),
        lineup.get("author", {}).get("display_name", "")
        if isinstance(lineup.get("author"), dict)
        else "",
    ]
    return " ".join(str(part) for part in parts).casefold()
