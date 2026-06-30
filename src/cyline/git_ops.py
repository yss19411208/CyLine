from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Settings


@dataclass(frozen=True)
class GitResult:
    attempted: bool
    committed: bool
    pushed: bool
    message: str


class GitPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def publish(self, changed_paths: list[Path], commit_message: str) -> GitResult:
        if not self.settings.auto_git_commit and not self.settings.auto_git_push:
            return GitResult(
                attempted=False,
                committed=False,
                pushed=False,
                message="設定によりGit公開処理をスキップしました。",
            )

        relative_paths = [
            _to_repo_relative_path(self.settings.repo_root, changed_path)
            for changed_path in changed_paths
        ]

        add_result = self._run_git(["add", "--", *relative_paths])
        if add_result.returncode != 0:
            return GitResult(
                attempted=True,
                committed=False,
                pushed=False,
                message=f"git addに失敗しました: {add_result.stderr.strip()}",
            )

        diff_result = self._run_git(["diff", "--cached", "--quiet"])
        if diff_result.returncode == 0:
            return GitResult(
                attempted=True,
                committed=False,
                pushed=False,
                message="ステージ済みの変更はありませんでした。",
            )

        committed = False
        if self.settings.auto_git_commit:
            commit_result = self._run_git(["commit", "-m", commit_message])
            if commit_result.returncode != 0:
                return GitResult(
                    attempted=True,
                    committed=False,
                    pushed=False,
                    message=f"git commitに失敗しました: {commit_result.stderr.strip()}",
                )
            committed = True

        pushed = False
        if self.settings.auto_git_push:
            current_branch = self.settings.git_branch or self._current_branch()
            push_result = self._run_git(
                ["push", self.settings.git_remote, current_branch]
            )
            if push_result.returncode != 0:
                return GitResult(
                    attempted=True,
                    committed=committed,
                    pushed=False,
                    message=f"git pushに失敗しました: {push_result.stderr.strip()}",
                )
            pushed = True

        return GitResult(
            attempted=True,
            committed=committed,
            pushed=pushed,
            message="Git公開処理が完了しました。",
        )

    def _current_branch(self) -> str:
        branch_result = self._run_git(["branch", "--show-current"])
        branch_name = branch_result.stdout.strip()
        if branch_result.returncode != 0 or not branch_name:
            raise RuntimeError("現在のGitブランチを判定できませんでした。")
        return branch_name

    def _run_git(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.settings.git_executable, *arguments],
            cwd=self.settings.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )


def _to_repo_relative_path(repo_root: Path, changed_path: Path) -> str:
    resolved_repo_root = repo_root.resolve()
    resolved_changed_path = changed_path.resolve()
    try:
        return resolved_changed_path.relative_to(resolved_repo_root).as_posix()
    except ValueError as path_error:
        raise ValueError(
            f"Refusing to publish a path outside the repository: {changed_path}"
        ) from path_error
