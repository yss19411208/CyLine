from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from .config import Settings
from .constants import ABILITIES, JUMP_LABELS
from .minimap import build_manual_map_position, estimate_player_position
from .models import Author, LineupInput, ManualPosition


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

        position_analysis = estimate_player_position(
            screenshot_bytes,
            lineup_input.manual_position,
            lineup_input.valorant_map,
            self.settings.maps_dir,
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
            "detected_position": asdict(position_analysis.detected_position),
            "map_position": asdict(position_analysis.map_position),
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
            "map_position": record["map_position"],
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

    def update_lineup(self, lineup_id: str, updates: dict) -> tuple[dict, list[Path]]:
        record, json_path = self._read_lineup_record(lineup_id)

        if "title" in updates:
            record["title"] = str(updates.get("title") or "").strip()

        if "description" in updates:
            record["description"] = str(updates.get("description") or "").strip()

        if "map" in updates:
            valorant_map = str(updates.get("map") or "").strip()
            # Old records may contain maps that are no longer in the catalog.
            # Admins can keep editing those records, but changing to another
            # unknown map is still rejected.
            if valorant_map not in self._valid_maps() and valorant_map != record.get("map"):
                raise ValueError(f"不明なマップです: {valorant_map}")
            record["map"] = valorant_map

        if "ability" in updates:
            ability = str(updates.get("ability") or "").strip()
            if ability not in ABILITIES:
                raise ValueError(f"不明なアビリティです: {ability}")
            record["ability"] = ability
            record["ability_label"] = ABILITIES[ability]

        if "jump" in updates:
            record["jump"] = _coerce_bool(updates.get("jump"))
            record["jump_label"] = JUMP_LABELS[record["jump"]]

        has_position_x = "position_x" in updates
        has_position_y = "position_y" in updates
        if has_position_x or has_position_y:
            if not has_position_x or not has_position_y:
                raise ValueError("position_xとposition_yは両方指定してください。")

            manual_position = ManualPosition(
                x_percent=_coerce_percent(updates.get("position_x"), "position_x"),
                y_percent=_coerce_percent(updates.get("position_y"), "position_y"),
            )
            map_position = build_manual_map_position(
                manual_position,
                str(record["map"]),
                self.settings.maps_dir,
                method="admin_manual",
            )
            record["map_position"] = asdict(map_position)

        if "needs_review" in updates and isinstance(record.get("map_position"), dict):
            record["map_position"]["needs_review"] = _coerce_bool(updates.get("needs_review"))

        _write_json(json_path, record)
        self._update_index(record)
        return record, [json_path, self.settings.data_dir / "index.json"]

    def delete_lineup(self, lineup_id: str) -> tuple[dict, list[Path]]:
        record, json_path = self._read_lineup_record(lineup_id)
        changed_paths = [json_path]

        image_relative_path = str(record.get("image_path") or "")
        if image_relative_path:
            image_path = _resolve_docs_relative_path(self.settings.docs_dir, image_relative_path)
            if image_path.exists():
                image_path.unlink()
                changed_paths.append(image_path)

        json_path.unlink()
        index_path = self._remove_from_index(lineup_id)
        changed_paths.append(index_path)
        return record, changed_paths

    def save_report(self, report_input: dict) -> tuple[dict, list[Path]]:
        lineup_id = str(report_input.get("lineup_id") or "").strip()
        lineup_record, _json_path = self._read_lineup_record(lineup_id)
        reason = _coerce_limited_text(report_input.get("reason"), "reason", 120, required=True)
        message = _coerce_limited_text(report_input.get("message"), "message", 1200, required=False)
        reporter_name = _coerce_limited_text(
            report_input.get("reporter_name"),
            "reporter_name",
            120,
            required=False,
        )

        created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        report_id = _build_lineup_id(created_at)
        report_relative_path = f"data/reports/{report_id}.json"
        report_path = self.settings.docs_dir / report_relative_path

        self.settings.reports_dir.mkdir(parents=True, exist_ok=True)
        report_record = {
            "schema_version": 1,
            "id": report_id,
            "lineup_id": lineup_id,
            "lineup_title": lineup_record.get("title") or "",
            "lineup_map": lineup_record.get("map") or "",
            "reason": reason,
            "message": message,
            "reporter_name": reporter_name,
            "status": "open",
            "data_path": report_relative_path,
            "created_at": created_at,
        }

        _write_json(report_path, report_record)
        reports_index_path = self._update_reports_index(report_record)
        return report_record, [report_path, reports_index_path]

    def _valid_maps(self) -> set[str]:
        from .constants import VALORANT_MAPS

        return set(VALORANT_MAPS)

    def _read_lineup_record(self, lineup_id: str) -> tuple[dict, Path]:
        if not lineup_id or "/" in lineup_id or "\\" in lineup_id:
            raise ValueError("定点IDが不正です。")

        json_path = self.settings.lineups_dir / f"{lineup_id}.json"
        if not json_path.exists():
            raise ValueError(f"定点が見つかりません: {lineup_id}")

        try:
            record = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as json_error:
            raise ValueError("定点JSONを読み込めません。") from json_error

        if record.get("id") != lineup_id:
            raise ValueError("定点JSONのIDが一致しません。")

        return record, json_path

    def _remove_from_index(self, lineup_id: str) -> Path:
        index_path = self.settings.data_dir / "index.json"
        if not index_path.exists():
            index_data = {"schema_version": 1, "generated_at": None, "lineups": []}
        else:
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                index_data = {"schema_version": 1, "generated_at": None, "lineups": []}

        index_data["schema_version"] = 1
        index_data["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
        index_data["lineups"] = [
            lineup for lineup in index_data.get("lineups", []) if lineup.get("id") != lineup_id
        ]
        _write_json(index_path, index_data)
        return index_path

    def _update_reports_index(self, report_record: dict) -> Path:
        reports_index_path = self.settings.data_dir / "reports.json"
        if reports_index_path.exists():
            try:
                reports_index_data = json.loads(reports_index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                reports_index_data = {"schema_version": 1, "generated_at": None, "reports": []}
        else:
            reports_index_data = {"schema_version": 1, "generated_at": None, "reports": []}

        existing_reports = reports_index_data.get("reports", [])
        reports_index_data["schema_version"] = 1
        reports_index_data["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
        reports_index_data["reports"] = [
            report
            for report in existing_reports
            if report.get("id") != report_record["id"]
        ]
        reports_index_data["reports"].append(report_record)
        reports_index_data["reports"].sort(
            key=lambda report: report.get("created_at", ""),
            reverse=True,
        )
        _write_json(reports_index_path, reports_index_data)
        return reports_index_path


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


def _resolve_docs_relative_path(docs_dir: Path, relative_path: str) -> Path:
    resolved_docs_dir = docs_dir.resolve()
    resolved_path = (docs_dir / relative_path).resolve()
    try:
        resolved_path.relative_to(resolved_docs_dir)
    except ValueError as path_error:
        raise ValueError(f"docs外のファイルは削除できません: {relative_path}") from path_error
    return resolved_path


def _coerce_limited_text(
    value: object,
    field_name: str,
    max_length: int,
    required: bool,
) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{field_name}は必須です。")
    if len(text) > max_length:
        raise ValueError(f"{field_name}は{max_length}文字以内で指定してください。")
    return text


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "jump"}
    return bool(value)


def _coerce_percent(value: object, field_name: str) -> float:
    try:
        percent = float(value)
    except (TypeError, ValueError) as conversion_error:
        raise ValueError(f"{field_name}は数値で指定してください。") from conversion_error

    if not 0 <= percent <= 100:
        raise ValueError(f"{field_name}は0から100の範囲で指定してください。")
    return percent
