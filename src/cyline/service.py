from __future__ import annotations

from .config import Settings
from .git_ops import GitPublisher, GitResult
from .models import Author, LineupInput
from .storage import LineupStorage


class LineupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = LineupStorage(settings)
        self.git_publisher = GitPublisher(settings)

    def register_lineup(
        self,
        lineup_input: LineupInput,
        screenshot_bytes: bytes,
        original_filename: str,
        author: Author,
    ) -> tuple[dict, GitResult]:
        record, changed_paths = self.storage.save_lineup(
            lineup_input=lineup_input,
            screenshot_bytes=screenshot_bytes,
            original_filename=original_filename,
            author=author,
        )
        commit_message = f"Add Cypher lineup {record['id']}"
        git_result = self.git_publisher.publish(changed_paths, commit_message)
        return record, git_result

