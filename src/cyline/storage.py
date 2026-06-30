from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from .config import Settings
from .constants import ABILITIES, JUMP_LABELS
from .minimap import estimate_player_position
from .models import Author, LineupInput


ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class LineupStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def save_lineup(
        self,
        lineup_input: LineupInput,
        screenshot_bytes: bytes,
        original_filename: str,
        author: Author,
    ) -> tuple[dict, list[Path]]:
        lineup_input.validate()
        _validate_screenshot_size(
            screenshot_bytes,
            self.settings.max_screenshot_bytes,
        )
        _validate_screenshot_image(screenshot_bytes)

        created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        lineup_id = _build_lineup_id(created_at)
        image_extension = _safe_image_extension(original_filename)
        image_relative_path = f"assets/lineups/{lineup_id}{image_extension}"
        json_relative_path = f"data/lineups/{lineup_id}.json"
        image_path = self.settings.docs_dir / image_relative_path
        json_path = self.settings.docs_dir / json_relative_path

        self.settings.assets_dir.mkdir(parents=True, exist_ok=True)
        self.settings.lineups_dir.mkdir(parents=True, exist_ok=True)

        minimap_estimate = estimate_player_position(
            screenshot_bytes,
            lineup_input.manual_position,
        )
        record = {
            "schema_version": 1,
            "id": lineup_id,
            "title": lineup_input.title.strip(),
            "description": lineup_input.description.strip(),
            "map": lineup_input.valorant_map,
            "ability": lineup_input.ability,
            "ability_label": ABILITIES[lineup_input.ability],
            "jump": lineup_input.jump,
            "jump_label": JUMP_LABELS[lineup_input.jump],
            "image_path": image_relative_path,
            "data_path": json_relative_path,
            "detected_position": asdict(minimap_estimate),
            "author": asdict(author),
            "created_at": created_at,
        }

        image_path.write_bytes(screenshot_bytes)
        _write_json(json_path, record)
        self._update_index(record)

        return record, [image_path, json_path, self.settings.data_dir / "index.json"]

    def _update_index(self, record: dict) -> None:
        index_path = self.settings.data_dir / "index.json"
        if index_path.exists():
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                index_data = {"schema_version": 1, "generated_at": None, "lineups": []}
        else:
            index_data = {"schema_version": 1, "generated_at": None, "lineups": []}

        existing_lineups = index_data.get("lineups", [])
        public_record = {
            "id": record["id"],
            "title": record["title"],
            "description": record["description"],
            "map": record["map"],
            "ability": record["ability"],
            "ability_label": record["ability_label"],
            "jump": record["jump"],
            "jump_label": record["jump_label"],
            "image_path": record["image_path"],
            "data_path": record["data_path"],
            "detected_position": record["detected_position"],
            "author": record["author"],
            "created_at": record["created_at"],
        }

        index_data["schema_version"] = 1
        index_data["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
        index_data["lineups"] = [
            lineup
            for lineup in existing_lineups
            if lineup.get("id") != public_record["id"]
        ]
        index_data["lineups"].append(public_record)
        index_data["lineups"].sort(key=lambda lineup: lineup.get("created_at", ""), reverse=True)
        _write_json(index_path, index_data)


def _build_lineup_id(created_at: str) -> str:
    compact_timestamp = (
        created_at.replace("+00:00", "Z")
        .replace("-", "")
        .replace(":", "")
    )
    return f"{compact_timestamp}-{secrets.token_hex(4)}"


def _safe_image_extension(original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    if suffix in ALLOWED_IMAGE_EXTENSIONS:
        return suffix
    return ".png"


def _validate_screenshot_size(screenshot_bytes: bytes, max_screenshot_bytes: int) -> None:
    if not screenshot_bytes:
        raise ValueError("スクリーンショットが空です。")

    if len(screenshot_bytes) > max_screenshot_bytes:
        raise ValueError(
            f"スクリーンショットが大きすぎます。上限: {max_screenshot_bytes} bytes。"
        )


def _validate_screenshot_image(screenshot_bytes: bytes) -> None:
    try:
        from PIL import Image
    except ImportError:
        return

    try:
        with Image.open(BytesIO(screenshot_bytes)) as image:
            image.verify()
    except (OSError, SyntaxError) as image_error:
        raise ValueError("スクリーンショットは有効なPNG、JPEG、WEBP画像にしてください。") from image_error


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
