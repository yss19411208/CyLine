import json
import tempfile
from io import BytesIO
import unittest
from pathlib import Path

from cyline.config import Settings
from cyline.models import Author, LineupInput, ManualPosition
from cyline.storage import LineupStorage


class LineupStorageTest(unittest.TestCase):
    def test_save_lineup_writes_json_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_directory:
            settings = _build_settings(Path(workspace_directory))
            docs_dir = settings.docs_dir
            storage = LineupStorage(settings)
            lineup_input = LineupInput(
                valorant_map="Ascent",
                ability="camera",
                jump=False,
                title="",
                description="",
                manual_position=ManualPosition(x_percent=50, y_percent=25),
            )
            author = Author(source="test", user_id="1", display_name="Tester")

            screenshot_bytes = _build_png_bytes()

            record, changed_paths = storage.save_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=screenshot_bytes,
                original_filename="screenshot.png",
                author=author,
            )

            self.assertEqual(record["map"], "Ascent")
            self.assertEqual(record["detected_position"]["method"], "manual")
            self.assertEqual(record["map_position"]["method"], "manual")
            self.assertTrue((docs_dir / record["image_path"]).exists())
            self.assertTrue((docs_dir / record["data_path"]).exists())
            self.assertIn(docs_dir / "data" / "index.json", changed_paths)

    def test_update_lineup_updates_record_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_directory:
            settings = _build_settings(Path(workspace_directory))
            storage = LineupStorage(settings)
            lineup_input = LineupInput(
                valorant_map="Ascent",
                ability="camera",
                jump=False,
                title="before",
                description="old",
                manual_position=ManualPosition(x_percent=50, y_percent=25),
            )
            author = Author(source="test", user_id="1", display_name="Tester")
            record, _changed_paths = storage.save_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=_build_png_bytes(),
                original_filename="screenshot.png",
                author=author,
            )

            updated_record, changed_paths = storage.update_lineup(
                record["id"],
                {
                    "title": "after",
                    "description": "new",
                    "ability": "wire",
                    "jump": True,
                    "position_x": 82.5,
                    "position_y": 28.99,
                    "needs_review": False,
                },
            )

            self.assertEqual(updated_record["title"], "after")
            self.assertEqual(updated_record["ability"], "wire")
            self.assertEqual(updated_record["ability_label"], "トラップワイヤー")
            self.assertTrue(updated_record["jump"])
            self.assertEqual(updated_record["map_position"]["method"], "admin_manual")
            self.assertEqual(updated_record["map_position"]["x_percent"], 82.5)
            self.assertIn(settings.data_dir / "index.json", changed_paths)

    def test_update_lineup_keeps_existing_unknown_map(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_directory:
            settings = _build_settings(Path(workspace_directory))
            storage = LineupStorage(settings)
            lineup_input = LineupInput(
                valorant_map="Ascent",
                ability="camera",
                jump=False,
                title="before",
                description="old",
                manual_position=ManualPosition(x_percent=50, y_percent=25),
            )
            author = Author(source="test", user_id="1", display_name="Tester")
            record, _changed_paths = storage.save_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=_build_png_bytes(),
                original_filename="screenshot.png",
                author=author,
            )
            record_path = settings.docs_dir / record["data_path"]
            record_data = json.loads(record_path.read_text(encoding="utf-8"))
            record_data["map"] = "Legacy Map"
            record_path.write_text(
                json.dumps(record_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            updated_record, _changed_paths = storage.update_lineup(
                record["id"],
                {
                    "title": "after",
                    "map": "Legacy Map",
                    "position_x": 10,
                    "position_y": 20,
                },
            )

            self.assertEqual(updated_record["title"], "after")
            self.assertEqual(updated_record["map"], "Legacy Map")
            self.assertEqual(updated_record["map_position"]["method"], "admin_manual")

    def test_delete_lineup_removes_record_image_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_directory:
            settings = _build_settings(Path(workspace_directory))
            docs_dir = settings.docs_dir
            storage = LineupStorage(settings)
            lineup_input = LineupInput(
                valorant_map="Ascent",
                ability="camera",
                jump=False,
                title="delete me",
                description="old",
                manual_position=ManualPosition(x_percent=50, y_percent=25),
            )
            author = Author(source="test", user_id="1", display_name="Tester")
            record, _changed_paths = storage.save_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=_build_png_bytes(),
                original_filename="screenshot.png",
                author=author,
            )

            deleted_record, changed_paths = storage.delete_lineup(record["id"])
            index_data = json.loads((settings.data_dir / "index.json").read_text(encoding="utf-8"))

            self.assertEqual(deleted_record["id"], record["id"])
            self.assertFalse((docs_dir / record["image_path"]).exists())
            self.assertFalse((docs_dir / record["data_path"]).exists())
            self.assertEqual(index_data["lineups"], [])
            self.assertIn(settings.data_dir / "index.json", changed_paths)

    def test_save_report_writes_report_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_directory:
            settings = _build_settings(Path(workspace_directory))
            storage = LineupStorage(settings)
            lineup_input = LineupInput(
                valorant_map="Ascent",
                ability="camera",
                jump=False,
                title="reported",
                description="old",
                manual_position=ManualPosition(x_percent=50, y_percent=25),
            )
            author = Author(source="test", user_id="1", display_name="Tester")
            lineup_record, _changed_paths = storage.save_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=_build_png_bytes(),
                original_filename="screenshot.png",
                author=author,
            )

            report_record, changed_paths = storage.save_report(
                {
                    "lineup_id": lineup_record["id"],
                    "reason": "座標が違う",
                    "message": "右にずれています",
                    "reporter_name": "Reporter",
                }
            )
            reports_index_data = json.loads(
                (settings.data_dir / "reports.json").read_text(encoding="utf-8")
            )

            self.assertEqual(report_record["lineup_id"], lineup_record["id"])
            self.assertEqual(report_record["status"], "open")
            self.assertTrue((settings.docs_dir / report_record["data_path"]).exists())
            self.assertEqual(reports_index_data["reports"][0]["id"], report_record["id"])
            self.assertIn(settings.data_dir / "reports.json", changed_paths)


def _build_png_bytes() -> bytes:
    try:
        from PIL import Image
    except ImportError:
        return b"pillow-not-installed"

    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(image_buffer, format="PNG")
    return image_buffer.getvalue()


def _build_settings(repo_root: Path) -> Settings:
    docs_dir = repo_root / "docs"
    return Settings(
        repo_root=repo_root,
        docs_dir=docs_dir,
        data_dir=docs_dir / "data",
        lineups_dir=docs_dir / "data" / "lineups",
        reports_dir=docs_dir / "data" / "reports",
        assets_dir=docs_dir / "assets" / "lineups",
        maps_dir=docs_dir / "assets" / "maps",
        public_base_url="https://yss19411208.github.io/CyLine/",
        asset_base_url="https://raw.githubusercontent.com/yss19411208/CyLine/refs/heads/main/docs/",
        discord_token="",
        discord_guild_id=None,
        discord_notify_channel_id=None,
        discord_webhook_url="",
        auto_git_commit=False,
        auto_git_push=False,
        git_remote="origin",
        git_branch="",
        git_executable="git",
        web_api_token="",
        admin_api_token="",
        cors_allowed_origins=["*"],
        max_screenshot_bytes=10_000,
    )


if __name__ == "__main__":
    unittest.main()
