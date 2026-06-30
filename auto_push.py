from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


DEFAULT_PATHS = (
    ".env.example",
    ".gitignore",
    "requirements.txt",
    "bot.py",
    "delete_commands.py",
    "auto_push.py",
    "data/valorant_config.json",
    "docs/index.html",
    ".github/workflows/pages.yml",
    "README.md",
)


def run_git_command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        check=True,
        text=True,
        capture_output=True,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="指定ファイルをcommitしてGitHubへpushします。",
    )
    parser.add_argument(
        "--message",
        default="Update VALOMASTER config and Pages editor",
        help="commit messageです。",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="push先remoteです。",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="push先branchです。未指定なら現在のbranchを使います。",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=list(DEFAULT_PATHS),
        help="stageするファイルです。",
    )
    return parser.parse_args()


def get_current_branch() -> str:
    result = run_git_command(["branch", "--show-current"])
    current_branch = result.stdout.strip()
    if not current_branch:
        raise RuntimeError("現在のbranch名を取得できませんでした。")
    return current_branch


def ensure_paths_exist(paths: list[str]) -> list[str]:
    existing_paths: list[str] = []
    missing_paths: list[str] = []

    for path_text in paths:
        path = Path(path_text)
        if path.exists():
            existing_paths.append(path_text)
        else:
            missing_paths.append(path_text)

    if missing_paths:
        missing_text = ", ".join(missing_paths)
        raise RuntimeError(f"存在しないpathが指定されています: {missing_text}")

    return existing_paths


def has_staged_changes() -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        text=True,
        capture_output=True,
    )
    return result.returncode == 1


def main() -> None:
    arguments = parse_arguments()
    branch = arguments.branch or get_current_branch()
    paths = ensure_paths_exist(arguments.paths)

    run_git_command(["add", "--", *paths])
    if not has_staged_changes():
        print("commitする変更はありません。")
        return

    run_git_command(["commit", "-m", arguments.message])
    run_git_command(["push", arguments.remote, branch])
    print(f"{arguments.remote}/{branch} にpushしました。")


if __name__ == "__main__":
    main()
