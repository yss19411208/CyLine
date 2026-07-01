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

    def update_lineup(self, lineup_id: str, updates: dict) -> tuple[dict, GitResult]:
        record, changed_paths = self.storage.update_lineup(lineup_id, updates)
        commit_message = f"Update Cypher lineup {record['id']}"
        git_result = self.git_publisher.publish(changed_paths, commit_message)
        return record, git_result

    def delete_lineup(self, lineup_id: str) -> tuple[dict, GitResult]:
        record, changed_paths = self.storage.delete_lineup(lineup_id)
        commit_message = f"Delete Cypher lineup {record['id']}"
        git_result = self.git_publisher.publish(changed_paths, commit_message)
        return record, git_result

    def report_lineup(self, report_input: dict) -> tuple[dict, GitResult]:
        report_record, changed_paths = self.storage.save_report(report_input)
        commit_message = f"Report Cypher lineup {report_record['lineup_id']}"
        git_result = self.git_publisher.publish(changed_paths, commit_message)
        return report_record, git_result
