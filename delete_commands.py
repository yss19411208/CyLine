from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Iterable


COMMAND_SCOPES = ("global", "guild", "both")


def get_required_environment_variable(variable_name: str) -> str:
    variable_value = os.getenv(variable_name)
    if variable_value is None or variable_value.strip() == "":
        raise RuntimeError(f"{variable_name} が設定されていません。")
    return variable_value


def parse_command_names(command_names: Iterable[str]) -> set[str]:
    normalized_command_names = {
        command_name.strip().lstrip("/").casefold()
        for command_name in command_names
        if command_name.strip()
    }
    if not normalized_command_names:
        raise ValueError("削除対象のコマンド名を1つ以上指定してください。")
    return normalized_command_names


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discordに登録済みのSlash Commandを削除します。",
    )
    parser.add_argument(
        "--command",
        action="append",
        dest="command_names",
        default=[],
        help="削除するコマンド名です。例: --command playvalo",
    )
    parser.add_argument(
        "--scope",
        choices=COMMAND_SCOPES,
        default="global",
        help="削除対象の範囲です。既定値は global です。",
    )
    parser.add_argument(
        "--guild-id",
        default=os.getenv("DISCORD_GUILD_ID"),
        help="guild または both のときに使うサーバーIDです。",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際に削除します。指定しない場合は一覧表示だけです。",
    )
    return parser.parse_args()


async def fetch_and_delete_commands(
    command_tree: app_commands.CommandTree[discord.Client],
    command_names: set[str],
    guild: discord.Object | None,
    scope_label: str,
    apply_delete: bool,
) -> None:
    registered_commands = await command_tree.fetch_commands(guild=guild)
    matched_commands = [
        command
        for command in registered_commands
        if command.name.casefold() in command_names
    ]

    if not matched_commands:
        print(f"{scope_label}: 削除対象のコマンドは見つかりませんでした。")
        return

    for command in matched_commands:
        if not apply_delete:
            print(f"{scope_label}: /{command.name} が見つかりました。--apply で削除します。")
            continue

        await command.delete()
        print(f"{scope_label}: /{command.name} を削除しました。")


async def main() -> None:
    arguments = parse_arguments()
    command_names = parse_command_names(arguments.command_names)
    bot_token = get_required_environment_variable("DISCORD_TOKEN")

    client = discord.Client(intents=discord.Intents.none())
    command_tree = app_commands.CommandTree(client)

    try:
        await client.login(bot_token)

        if arguments.scope in ("global", "both"):
            await fetch_and_delete_commands(
                command_tree=command_tree,
                command_names=command_names,
                guild=None,
                scope_label="global",
                apply_delete=arguments.apply,
            )

        if arguments.scope in ("guild", "both"):
            if arguments.guild_id is None or arguments.guild_id.strip() == "":
                raise RuntimeError(
                    "guild または both を使う場合は --guild-id か DISCORD_GUILD_ID が必要です。"
                )

            try:
                guild_id = int(arguments.guild_id)
            except ValueError as error:
                raise RuntimeError("--guild-id は整数で指定してください。") from error

            await fetch_and_delete_commands(
                command_tree=command_tree,
                command_names=command_names,
                guild=discord.Object(id=guild_id),
                scope_label=f"guild:{guild_id}",
                apply_delete=arguments.apply,
            )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
