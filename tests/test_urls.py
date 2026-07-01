import unittest
from pathlib import Path

from cyline.config import Settings
from cyline.notifier import build_asset_url, build_public_url


class UrlTest(unittest.TestCase):
    def test_asset_url_uses_raw_base_url(self) -> None:
        settings = Settings(
            repo_root=Path("."),
            docs_dir=Path("docs"),
            data_dir=Path("docs/data"),
            lineups_dir=Path("docs/data/lineups"),
            assets_dir=Path("docs/assets/lineups"),
            maps_dir=Path("docs/assets/maps"),
            public_base_url="https://yss19411208.github.io/CyLine/",
            asset_base_url="https://raw.githubusercontent.com/yss19411208/CyLine/refs/heads/main/docs/",
            discord_token="",
            discord_guild_id=None,
            discord_notify_channel_id=None,
            discord_webhook_url="",
            auto_git_commit=False,
            auto_git_push=False,
            git_remote="origin",
            git_branch="main",
            git_executable="git",
            web_api_token="",
            admin_api_token="",
            cors_allowed_origins=["*"],
            max_screenshot_bytes=1000,
        )

        asset_url = build_asset_url(settings, "assets/lineups/example.png")
        public_url = build_public_url(settings, "assets/lineups/example.png")

        self.assertEqual(
            asset_url,
            "https://raw.githubusercontent.com/yss19411208/CyLine/refs/heads/main/docs/assets/lineups/example.png",
        )
        self.assertEqual(
            public_url,
            "https://yss19411208.github.io/CyLine/assets/lineups/example.png",
        )


if __name__ == "__main__":
    unittest.main()
