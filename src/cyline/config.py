from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ASSET_BASE_URL = "https://raw.githubusercontent.com/yss19411208/CyLine/refs/heads/main/docs/"


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - allows syntax checks before install.
    load_dotenv = None


def _read_bool(environment_name: str, default_value: bool) -> bool:
    raw_value = os.getenv(environment_name)
    if raw_value is None:
        return default_value

    normalized_value = raw_value.strip().lower()
    return normalized_value in {"1", "true", "yes", "on"}


def _read_optional_int(environment_name: str) -> int | None:
    raw_value = os.getenv(environment_name)
    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError as conversion_error:
        raise ValueError(f"{environment_name} must be an integer.") from conversion_error


def _read_optional_path(environment_name: str, default_value: str) -> str:
    raw_value = os.getenv(environment_name)
    if not raw_value:
        return default_value
    return raw_value


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    docs_dir: Path
    data_dir: Path
    lineups_dir: Path
    assets_dir: Path
    maps_dir: Path
    public_base_url: str
    asset_base_url: str
    discord_token: str
    discord_guild_id: int | None
    discord_notify_channel_id: int | None
    discord_webhook_url: str
    auto_git_commit: bool
    auto_git_push: bool
    git_remote: str
    git_branch: str
    git_executable: str
    web_api_token: str
    cors_allowed_origins: list[str]
    max_screenshot_bytes: int

    @classmethod
    def from_env(cls) -> "Settings":
        if load_dotenv is not None:
            load_dotenv()

        repo_root = Path(__file__).resolve().parents[2]
        docs_dir = repo_root / "docs"
        data_dir = docs_dir / "data"

        raw_cors_origins = os.getenv("CYLINE_CORS_ALLOWED_ORIGINS", "*")
        cors_allowed_origins = [
            origin.strip()
            for origin in raw_cors_origins.split(",")
            if origin.strip()
        ]

        raw_max_screenshot_bytes = os.getenv("CYLINE_MAX_SCREENSHOT_BYTES", "15728640")
        try:
            max_screenshot_bytes = int(raw_max_screenshot_bytes)
        except ValueError as conversion_error:
            raise ValueError("CYLINE_MAX_SCREENSHOT_BYTES must be an integer.") from conversion_error

        if max_screenshot_bytes <= 0:
            raise ValueError("CYLINE_MAX_SCREENSHOT_BYTES must be greater than zero.")

        return cls(
            repo_root=repo_root,
            docs_dir=docs_dir,
            data_dir=data_dir,
            lineups_dir=data_dir / "lineups",
            assets_dir=docs_dir / "assets" / "lineups",
            maps_dir=docs_dir / "assets" / "maps",
            public_base_url=os.getenv("CYLINE_PUBLIC_BASE_URL", "").strip(),
            asset_base_url=os.getenv(
                "CYLINE_ASSET_BASE_URL",
                DEFAULT_ASSET_BASE_URL,
            ).strip() or DEFAULT_ASSET_BASE_URL,
            discord_token=os.getenv("CYLINE_DISCORD_TOKEN", "").strip(),
            discord_guild_id=_read_optional_int("CYLINE_DISCORD_GUILD_ID"),
            discord_notify_channel_id=_read_optional_int(
                "CYLINE_DISCORD_NOTIFY_CHANNEL_ID"
            ),
            discord_webhook_url=os.getenv("CYLINE_DISCORD_WEBHOOK_URL", "").strip(),
            auto_git_commit=_read_bool("CYLINE_AUTO_GIT_COMMIT", True),
            auto_git_push=_read_bool("CYLINE_AUTO_GIT_PUSH", False),
            git_remote=os.getenv("CYLINE_GIT_REMOTE", "origin").strip() or "origin",
            git_branch=os.getenv("CYLINE_GIT_BRANCH", "").strip(),
            git_executable=_read_optional_path("CYLINE_GIT_EXECUTABLE", "git"),
            web_api_token=os.getenv("CYLINE_WEB_API_TOKEN", "").strip(),
            cors_allowed_origins=cors_allowed_origins or ["*"],
            max_screenshot_bytes=max_screenshot_bytes,
        )
