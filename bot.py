from __future__ import annotations

import json
import logging
import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands


CONFIG_PATH = Path(__file__).with_name("data") / "valorant_config.json"


@dataclass(frozen=True)
class GameMode:
    label: str
    value: str


@dataclass(frozen=True)
class ValorantConfig:
    role_name: str
    custom_mode_value: str
    max_selected_players: int
    player_select_page_size: int
    setup_timeout_seconds: int
    note_max_length: int
    modes: tuple[GameMode, ...]
    maps: tuple[str, ...]
    agents: tuple[str, ...]


@dataclass
class PlayValoSession:
    owner_id: int
    config: ValorantConfig
    available_members: list[discord.Member]
    selected_member_ids: list[int] = field(default_factory=list)
    player_page_index: int = 0
    members: list[discord.Member] = field(default_factory=list)
    mode_label: str | None = None
    mode_value: str | None = None
    map_name: str | None = None
    voice_channel_id: int | None = None
    note: str | None = None
    sent: bool = False


def get_required_environment_variable(variable_name: str) -> str:
    variable_value = os.getenv(variable_name)
    if variable_value is None or variable_value.strip() == "":
        raise RuntimeError(f"{variable_name} が設定されていません。")
    return variable_value


def require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field_name} は空ではない文字列で指定してください。")
    return value.strip()


def require_positive_integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} は1以上の整数で指定してください。")
    return value


def parse_string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} は配列で指定してください。")

    parsed_values = tuple(
        require_non_empty_string(item, f"{field_name}[]")
        for item in value
    )
    if not parsed_values:
        raise ValueError(f"{field_name} は1件以上指定してください。")

    duplicated_values = {
        item.casefold()
        for item in parsed_values
        if sum(1 for candidate in parsed_values if candidate.casefold() == item.casefold()) > 1
    }
    if duplicated_values:
        raise ValueError(f"{field_name} に重複があります。")

    return parsed_values


def parse_modes(value: Any) -> tuple[GameMode, ...]:
    if not isinstance(value, list):
        raise ValueError("modes は配列で指定してください。")

    modes: list[GameMode] = []
    for mode_index, mode_value in enumerate(value, start=1):
        if not isinstance(mode_value, dict):
            raise ValueError(f"modes[{mode_index}] はオブジェクトで指定してください。")

        modes.append(
            GameMode(
                label=require_non_empty_string(mode_value.get("label"), "modes[].label"),
                value=require_non_empty_string(mode_value.get("value"), "modes[].value"),
            )
        )

    if not modes:
        raise ValueError("modes は1件以上指定してください。")

    duplicated_values = {
        mode.value.casefold()
        for mode in modes
        if sum(1 for candidate in modes if candidate.value.casefold() == mode.value.casefold()) > 1
    }
    if duplicated_values:
        raise ValueError("modes[].value に重複があります。")

    return tuple(modes)


def load_valorant_config() -> ValorantConfig:
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        raw_config = json.load(config_file)

    if not isinstance(raw_config, dict):
        raise ValueError("設定ファイルのルートはオブジェクトで指定してください。")

    modes = parse_modes(raw_config.get("modes"))
    custom_mode_value = require_non_empty_string(
        raw_config.get("custom_mode_value"),
        "custom_mode_value",
    )
    if custom_mode_value.casefold() not in {mode.value.casefold() for mode in modes}:
        raise ValueError("custom_mode_value は modes[].value のどれかと一致させてください。")

    return ValorantConfig(
        role_name=require_non_empty_string(raw_config.get("role_name"), "role_name"),
        custom_mode_value=custom_mode_value,
        max_selected_players=require_positive_integer(
            raw_config.get("max_selected_players"),
            "max_selected_players",
        ),
        player_select_page_size=min(
            25,
            require_positive_integer(
                raw_config.get("player_select_page_size"),
                "player_select_page_size",
            ),
        ),
        setup_timeout_seconds=require_positive_integer(
            raw_config.get("setup_timeout_seconds"),
            "setup_timeout_seconds",
        ),
        note_max_length=min(
            1000,
            require_positive_integer(raw_config.get("note_max_length"), "note_max_length"),
        ),
        modes=modes,
        maps=parse_string_list(raw_config.get("maps"), "maps"),
        agents=parse_string_list(raw_config.get("agents"), "agents"),
    )


def get_mode_label(config: ValorantConfig, mode_value: str) -> str:
    for mode in config.modes:
        if mode.value == mode_value:
            return mode.label
    raise ValueError(f"未定義のモードです: {mode_value}")


def get_valorant_role(guild: discord.Guild, role_name: str) -> discord.Role | None:
    return discord.utils.get(guild.roles, name=role_name)


async def fetch_role_members(
    guild: discord.Guild,
    role: discord.Role,
) -> list[discord.Member]:
    fetched_members: list[discord.Member] = []

    try:
        async for member in guild.fetch_members(limit=None):
            if role in member.roles and not member.bot:
                fetched_members.append(member)
    except (discord.Forbidden, discord.HTTPException):
        fetched_members = [member for member in role.members if not member.bot]

    unique_members = {member.id: member for member in fetched_members}
    return sorted(
        unique_members.values(),
        key=lambda member: (member.display_name.casefold(), member.id),
    )


def get_total_player_pages(session: PlayValoSession) -> int:
    return max(
        1,
        math.ceil(len(session.available_members) / session.config.player_select_page_size),
    )


def get_current_page_members(session: PlayValoSession) -> list[discord.Member]:
    total_pages = get_total_player_pages(session)
    session.player_page_index = min(max(session.player_page_index, 0), total_pages - 1)
    page_start = session.player_page_index * session.config.player_select_page_size
    page_end = page_start + session.config.player_select_page_size
    return session.available_members[page_start:page_end]


def get_selected_members(session: PlayValoSession) -> list[discord.Member]:
    members_by_id = {member.id: member for member in session.available_members}
    return [
        members_by_id[member_id]
        for member_id in session.selected_member_ids
        if member_id in members_by_id
    ]


def get_player_select_content(session: PlayValoSession) -> str:
    total_pages = get_total_player_pages(session)
    selected_count = len(session.selected_member_ids)
    return "\n".join(
        (
            f"{session.config.role_name}ロールの人を選択してください。",
            f"ページ: {session.player_page_index + 1}/{total_pages}",
            f"選択中: {selected_count}/{session.config.max_selected_players}",
            "選択後に確定を押してください。",
        )
    )


def truncate_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def build_announcement_message(session: PlayValoSession) -> str:
    if session.voice_channel_id is None:
        raise RuntimeError("VCチャンネルが未選択です。")

    member_mentions = " ".join(member.mention for member in session.members)
    map_text = session.map_name if session.map_name is not None else "指定なし"

    message_lines = [
        member_mentions,
        "VALORANTの募集です。",
        f"モード: {session.mode_label}",
        f"マップ: {map_text}",
        f"VC: <#{session.voice_channel_id}>",
    ]

    note_text = (session.note or "").strip()
    if note_text:
        message_lines.append(f"備考: {note_text}")

    message_lines.append("参加できる方はVCに集合してください。")
    return "\n".join(message_lines)


async def send_announcement(
    session: PlayValoSession,
    announcement_channel: object,
) -> bool:
    if session.sent:
        return False

    if not hasattr(announcement_channel, "send"):
        raise RuntimeError("募集メッセージを送信できるチャンネルではありません。")

    announcement_message = build_announcement_message(session)
    await announcement_channel.send(
        announcement_message,
        allowed_mentions=discord.AllowedMentions(
            users=session.members,
            roles=False,
            everyone=False,
        ),
    )
    session.sent = True
    return True


class SessionView(discord.ui.View):
    def __init__(self, session: PlayValoSession) -> None:
        super().__init__(timeout=session.config.setup_timeout_seconds)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.session.owner_id:
            return True

        await interaction.response.send_message(
            "この募集を操作できるのは、コマンドを実行した人だけです。",
            ephemeral=True,
        )
        return False


class PlayerPageSelect(discord.ui.Select):
    def __init__(self, session: PlayValoSession) -> None:
        page_members = get_current_page_members(session)
        selected_member_id_set = set(session.selected_member_ids)
        options = [
            discord.SelectOption(
                label=truncate_text(member.display_name, 100),
                value=str(member.id),
                description=truncate_text(member.name, 100),
                default=member.id in selected_member_id_set,
            )
            for member in page_members
        ]

        super().__init__(
            placeholder=f"{session.config.role_name}ロールの人だけを表示中",
            min_values=0,
            max_values=min(session.config.max_selected_players, len(options)),
            options=options,
            row=0,
        )
        self.session = session

    async def callback(self, interaction: discord.Interaction) -> None:
        page_members = get_current_page_members(self.session)
        page_member_ids = {member.id for member in page_members}
        selected_on_page_ids = {int(member_id) for member_id in self.values}

        next_selected_member_ids = [
            member_id
            for member_id in self.session.selected_member_ids
            if member_id not in page_member_ids
        ]
        next_selected_member_ids.extend(
            member.id
            for member in page_members
            if member.id in selected_on_page_ids
        )

        if len(next_selected_member_ids) > self.session.config.max_selected_players:
            await interaction.response.send_message(
                f"選択できる人数は最大{self.session.config.max_selected_players}人です。",
                ephemeral=True,
            )
            return

        self.session.selected_member_ids = next_selected_member_ids
        await interaction.response.edit_message(
            content=get_player_select_content(self.session),
            view=PlayerSelectView(self.session),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class PlayerPageButton(discord.ui.Button):
    def __init__(self, session: PlayValoSession, page_delta: int) -> None:
        self.session = session
        self.page_delta = page_delta
        total_pages = get_total_player_pages(session)
        next_page_index = session.player_page_index + page_delta
        label = "前へ" if page_delta < 0 else "次へ"

        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            disabled=next_page_index < 0 or next_page_index >= total_pages,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        total_pages = get_total_player_pages(self.session)
        self.session.player_page_index = min(
            max(self.session.player_page_index + self.page_delta, 0),
            total_pages - 1,
        )
        await interaction.response.edit_message(
            content=get_player_select_content(self.session),
            view=PlayerSelectView(self.session),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ConfirmPlayersButton(discord.ui.Button):
    def __init__(self, session: PlayValoSession) -> None:
        self.session = session
        super().__init__(
            label="確定",
            style=discord.ButtonStyle.primary,
            disabled=len(session.selected_member_ids) == 0,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_members = get_selected_members(self.session)
        if not selected_members:
            await interaction.response.send_message(
                "1人以上選択してください。",
                ephemeral=True,
            )
            return

        self.session.members = selected_members
        await interaction.response.edit_message(
            content="モードを選択してください。",
            view=ModeSelectView(self.session),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class PlayerSelectView(SessionView):
    def __init__(self, session: PlayValoSession) -> None:
        super().__init__(session)
        self.add_item(PlayerPageSelect(session))
        self.add_item(PlayerPageButton(session, -1))
        self.add_item(PlayerPageButton(session, 1))
        self.add_item(ConfirmPlayersButton(session))


class ModeSelect(discord.ui.Select):
    def __init__(self, session: PlayValoSession) -> None:
        mode_options = [
            discord.SelectOption(label=mode.label, value=mode.value)
            for mode in session.config.modes
        ]
        super().__init__(
            placeholder="モードを選択",
            min_values=1,
            max_values=1,
            options=mode_options,
        )
        self.session = session

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_mode_value = self.values[0]
        self.session.mode_value = selected_mode_value
        self.session.mode_label = get_mode_label(self.session.config, selected_mode_value)
        self.session.map_name = None

        if selected_mode_value == self.session.config.custom_mode_value:
            await interaction.response.edit_message(
                content="カスタムのマップを選択してください。",
                view=MapSelectView(self.session),
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.response.edit_message(
            content="VCチャンネルを選択してください。",
            view=VoiceChannelSelectView(self.session),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class ModeSelectView(SessionView):
    def __init__(self, session: PlayValoSession) -> None:
        super().__init__(session)
        self.add_item(ModeSelect(session))


class MapSelect(discord.ui.Select):
    def __init__(self, session: PlayValoSession) -> None:
        map_options = [
            discord.SelectOption(label=map_name, value=map_name)
            for map_name in session.config.maps
        ]
        super().__init__(
            placeholder="マップを選択",
            min_values=1,
            max_values=1,
            options=map_options,
        )
        self.session = session

    async def callback(self, interaction: discord.Interaction) -> None:
        self.session.map_name = self.values[0]
        await interaction.response.edit_message(
            content="VCチャンネルを選択してください。",
            view=VoiceChannelSelectView(self.session),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class MapSelectView(SessionView):
    def __init__(self, session: PlayValoSession) -> None:
        super().__init__(session)
        self.add_item(MapSelect(session))


class VoiceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, session: PlayValoSession) -> None:
        super().__init__(
            placeholder="VCチャンネルを選択",
            channel_types=[discord.ChannelType.voice],
            min_values=1,
            max_values=1,
        )
        self.session = session

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_channel = self.values[0]
        self.session.voice_channel_id = selected_channel.id

        await interaction.response.edit_message(
            content="備考を入力して送信してください。備考がなければ空欄で送信できます。",
            view=NotesActionView(self.session, interaction.channel),
            allowed_mentions=discord.AllowedMentions.none(),
        )


class VoiceChannelSelectView(SessionView):
    def __init__(self, session: PlayValoSession) -> None:
        super().__init__(session)
        self.add_item(VoiceChannelSelect(session))


class NotesModal(discord.ui.Modal):
    def __init__(
        self,
        session: PlayValoSession,
        announcement_channel: object,
        source_message: discord.Message | None,
    ) -> None:
        super().__init__(title="備考", timeout=session.config.setup_timeout_seconds)
        self.session = session
        self.announcement_channel = announcement_channel
        self.source_message = source_message
        self.note_input = discord.ui.TextInput(
            label="備考",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=session.config.note_max_length,
            placeholder="必要な連絡事項があれば入力してください",
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.session.note = str(self.note_input.value).strip()

        try:
            announcement_sent = await send_announcement(
                self.session,
                self.announcement_channel,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Botにこのチャンネルへ送信する権限がありません。",
                ephemeral=True,
            )
            return
        except (discord.HTTPException, RuntimeError):
            await interaction.response.send_message(
                "募集メッセージの送信に失敗しました。少し待って再実行してください。",
                ephemeral=True,
            )
            return

        response_text = "募集を送信しました。" if announcement_sent else "この募集は送信済みです。"
        await interaction.response.send_message(response_text, ephemeral=True)

        if self.source_message is not None:
            try:
                await self.source_message.edit(
                    content=response_text,
                    view=None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                pass


class OpenNotesModalButton(discord.ui.Button):
    def __init__(
        self,
        session: PlayValoSession,
        announcement_channel: object,
    ) -> None:
        self.session = session
        self.announcement_channel = announcement_channel
        super().__init__(
            label="備考を入力",
            style=discord.ButtonStyle.primary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.session.sent:
            await interaction.response.send_message(
                "この募集は送信済みです。",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            NotesModal(
                self.session,
                self.announcement_channel,
                interaction.message,
            )
        )


class SendWithoutNotesButton(discord.ui.Button):
    def __init__(
        self,
        session: PlayValoSession,
        announcement_channel: object,
    ) -> None:
        self.session = session
        self.announcement_channel = announcement_channel
        super().__init__(
            label="備考なしで送信",
            style=discord.ButtonStyle.secondary,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.session.note = None

        try:
            announcement_sent = await send_announcement(
                self.session,
                self.announcement_channel,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "Botにこのチャンネルへ送信する権限がありません。",
                ephemeral=True,
            )
            return
        except (discord.HTTPException, RuntimeError):
            await interaction.response.send_message(
                "募集メッセージの送信に失敗しました。少し待って再実行してください。",
                ephemeral=True,
            )
            return

        response_text = "募集を送信しました。" if announcement_sent else "この募集は送信済みです。"
        await interaction.response.edit_message(
            content=response_text,
            view=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class NotesActionView(SessionView):
    def __init__(
        self,
        session: PlayValoSession,
        announcement_channel: object,
    ) -> None:
        super().__init__(session)
        self.add_item(OpenNotesModalButton(session, announcement_channel))
        self.add_item(SendWithoutNotesButton(session, announcement_channel))


class PlayValoBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
        )

    async def setup_hook(self) -> None:
        guild_id_text = os.getenv("DISCORD_GUILD_ID")
        if guild_id_text is None or guild_id_text.strip() == "":
            await self.tree.sync()
            return

        try:
            guild_id = int(guild_id_text)
        except ValueError as error:
            raise RuntimeError("DISCORD_GUILD_ID は整数で指定してください。") from error

        guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)


bot = PlayValoBot()


@bot.tree.command(name="playvalo", description="VALORANT募集を作成します")
async def play_valo(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "このコマンドはサーバー内でのみ使用できます。",
            ephemeral=True,
        )
        return

    try:
        config = load_valorant_config()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        await interaction.response.send_message(
            f"設定ファイルの読み込みに失敗しました: {error}",
            ephemeral=True,
        )
        return

    valorant_role = get_valorant_role(interaction.guild, config.role_name)
    if valorant_role is None:
        await interaction.response.send_message(
            f"サーバーに {config.role_name} ロールが見つかりません。",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    valorant_members = await fetch_role_members(interaction.guild, valorant_role)
    if not valorant_members:
        await interaction.edit_original_response(
            content=f"{config.role_name} ロールが付いたメンバーが見つかりません。",
            view=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return

    session = PlayValoSession(
        owner_id=interaction.user.id,
        config=config,
        available_members=valorant_members,
    )
    await interaction.edit_original_response(
        content=get_player_select_content(session),
        view=PlayerSelectView(session),
        allowed_mentions=discord.AllowedMentions.none(),
    )


@bot.tree.command(name="random_pick", description="指定人数分のランダムエージェントを選びます")
@app_commands.describe(number="選ぶ人数")
async def random_pick(interaction: discord.Interaction, number: int) -> None:
    try:
        config = load_valorant_config()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        await interaction.response.send_message(
            f"設定ファイルの読み込みに失敗しました: {error}",
            ephemeral=True,
        )
        return

    if number < 1:
        await interaction.response.send_message(
            "number は1以上で指定してください。",
            ephemeral=True,
        )
        return

    if number > len(config.agents):
        await interaction.response.send_message(
            f"設定ファイルに登録されているエージェントは{len(config.agents)}人です。"
            f"number は{len(config.agents)}以下で指定してください。",
            ephemeral=True,
        )
        return

    selected_agents = random.sample(config.agents, number)
    message = "\n".join(
        f"{index}.{agent_name.lower()}"
        for index, agent_name in enumerate(selected_agents, start=1)
    )
    await interaction.response.send_message(message)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot_token = get_required_environment_variable("DISCORD_TOKEN")
    bot.run(bot_token)


if __name__ == "__main__":
    main()
