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
            repo_root = Path(workspace_directory)
            docs_dir = repo_root / "docs"
            settings = Settings(
                repo_root=repo_root,
                docs_dir=docs_dir,
                data_dir=docs_dir / "data",
                lineups_dir=docs_dir / "data" / "lineups",
                assets_dir=docs_dir / "assets" / "lineups",
                public_base_url="",
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
                cors_allowed_origins=["*"],
                max_screenshot_bytes=10_000,
            )
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
            self.assertTrue((docs_dir / record["image_path"]).exists())
            self.assertTrue((docs_dir / record["data_path"]).exists())
            self.assertIn(docs_dir / "data" / "index.json", changed_paths)

def _build_png_bytes() -> bytes:
    try:
        from PIL import Image
    except ImportError:
        return b"pillow-not-installed"

    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(image_buffer, format="PNG")
    return image_buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
