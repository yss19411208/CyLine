from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings
from .constants import ABILITIES, VALORANT_MAPS
from .lineup_index import filter_lineups, format_position, get_lineup_position, load_lineups
from .map_preview import build_search_preview
from .models import Author, LineupInput, ManualPosition
from .notifier import build_asset_url
from .service import LineupService


def create_bot(settings: Settings | None = None) -> commands.Bot:
    active_settings = settings or Settings.from_env()
    service = LineupService(active_settings)
    intents = discord.Intents.default()

    class CyLineBot(commands.Bot):
        async def setup_hook(self) -> None:
            if active_settings.discord_guild_id is not None:
                guild = discord.Object(id=active_settings.discord_guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()

    bot = CyLineBot(command_prefix="!", intents=intents)

    ability_choices = [
        app_commands.Choice(name=ability_label, value=ability_key)
        for ability_key, ability_label in ABILITIES.items()
    ]
    map_choices = [
        app_commands.Choice(name=map_name, value=map_name)
        for map_name in VALORANT_MAPS
    ]

    @bot.tree.command(name="register", description="Cypherの定点を登録します。")
    @app_commands.describe(
        screenshot="ミニマップが映っているスクリーンショット。",
        ability="Cypherのアビリティ。",
        jump="ジャンプする定点かどうか。",
        valorant_map="VALORANTのマップ。",
        title="任意のタイトル。",
        description="任意の説明。",
        position_x="任意の手動補正X座標。0から100。",
        position_y="任意の手動補正Y座標。0から100。",
    )
    @app_commands.rename(valorant_map="map")
    @app_commands.choices(ability=ability_choices, valorant_map=map_choices)
    async def register(
        interaction: discord.Interaction,
        screenshot: discord.Attachment,
        ability: app_commands.Choice[str],
        jump: bool,
        valorant_map: app_commands.Choice[str],
        title: Optional[str] = "",
        description: Optional[str] = "",
        position_x: Optional[float] = None,
        position_y: Optional[float] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            manual_position = _build_manual_position(position_x, position_y)
            if screenshot.size > active_settings.max_screenshot_bytes:
                raise ValueError(
                    "スクリーンショットが大きすぎます。"
                    f"上限: {active_settings.max_screenshot_bytes} bytes。"
                )

            screenshot_bytes = await screenshot.read()
            lineup_input = LineupInput(
                valorant_map=valorant_map.value,
                ability=ability.value,
                jump=jump,
                title=title or "",
                description=description or "",
                manual_position=manual_position,
            )
            author = Author(
                source="discord",
                user_id=str(interaction.user.id),
                display_name=str(interaction.user),
            )
            record, git_result = service.register_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=screenshot_bytes,
                original_filename=screenshot.filename,
                author=author,
            )

        except Exception as registration_error:
            await interaction.followup.send(
                f"登録に失敗しました: {registration_error}",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            _build_success_message(active_settings, record, git_result.message),
            ephemeral=True,
        )

        try:
            await _notify_channel(bot, active_settings, record)
        except Exception as notification_error:
            await interaction.followup.send(
                f"登録は完了しましたが、Discord通知に失敗しました: {notification_error}",
                ephemeral=True,
            )

    @bot.tree.command(name="search", description="登録済みのCypher定点を検索します。")
    @app_commands.describe(
        valorant_map="検索するマップ。",
        ability="検索するアビリティ。",
        jump="ジャンプする定点だけに絞るかどうか。",
        keyword="タイトル、説明、登録者名などで検索します。",
    )
    @app_commands.rename(valorant_map="map")
    @app_commands.choices(ability=ability_choices, valorant_map=map_choices)
    async def search(
        interaction: discord.Interaction,
        valorant_map: Optional[app_commands.Choice[str]] = None,
        ability: Optional[app_commands.Choice[str]] = None,
        jump: Optional[bool] = None,
        keyword: Optional[str] = "",
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        selected_map = valorant_map.value if valorant_map is not None else None
        selected_ability = ability.value if ability is not None else None
        all_lineups = load_lineups(active_settings.data_dir)
        matched_lineups = filter_lineups(
            all_lineups,
            valorant_map=selected_map,
            ability=selected_ability,
            jump=jump,
            keyword=keyword or "",
        )

        if not matched_lineups:
            await interaction.followup.send("条件に合う定点が見つかりませんでした。", ephemeral=True)
            return

        shown_lineups = matched_lineups[:25]
        embed = _build_search_embed(
            active_settings,
            shown_lineups,
            selected_map,
            len(matched_lineups),
        )
        view = SearchResultView(active_settings, shown_lineups)

        if selected_map:
            preview_buffer = build_search_preview(
                active_settings.maps_dir,
                selected_map,
                shown_lineups,
            )
            if preview_buffer is not None:
                discord_file = discord.File(
                    preview_buffer,
                    filename="cyline-search-map.png",
                )
                embed.set_image(url="attachment://cyline-search-map.png")
                await interaction.followup.send(
                    embed=embed,
                    file=discord_file,
                    view=view,
                    ephemeral=True,
                )
                return

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    return bot


class SearchResultView(discord.ui.View):
    def __init__(self, settings: Settings, lineups: list[dict]) -> None:
        super().__init__(timeout=180)
        self.add_item(SearchResultSelect(settings, lineups))


class SearchResultSelect(discord.ui.Select):
    def __init__(self, settings: Settings, lineups: list[dict]) -> None:
        self.settings = settings
        self.lineups_by_id = {
            str(lineup.get("id")): lineup
            for lineup in lineups
        }
        options = []
        for result_index, lineup in enumerate(lineups[:25], start=1):
            label = f"{result_index}. {lineup.get('title') or lineup.get('map')} {lineup.get('ability_label')}"
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=str(lineup.get("id")),
                    description=f"{lineup.get('jump_label', '')} / {lineup.get('created_at', '')}"[:100],
                )
            )

        super().__init__(
            placeholder="詳細を見る定点を選択",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        lineup = self.lineups_by_id.get(self.values[0])
        if lineup is None:
            await interaction.response.send_message("定点が見つかりませんでした。", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=_build_lineup_detail_embed(self.settings, lineup),
            ephemeral=True,
        )


def run() -> None:
    settings = Settings.from_env()
    if not settings.discord_token:
        raise RuntimeError("CYLINE_DISCORD_TOKENを.envに設定してください。")

    bot = create_bot(settings)
    bot.run(settings.discord_token)


def _build_manual_position(
    position_x: float | None,
    position_y: float | None,
) -> ManualPosition | None:
    if position_x is None and position_y is None:
        return None

    if position_x is None or position_y is None:
        raise ValueError("手動補正を使う場合はposition_xとposition_yを両方指定してください。")

    return ManualPosition(x_percent=position_x, y_percent=position_y)


def _build_success_message(settings: Settings, record: dict, git_message: str) -> str:
    image_url = build_asset_url(settings, record["image_path"])
    position = record.get("map_position") or record["detected_position"]
    review_text = "要確認" if position["needs_review"] else "確認済み"
    lines = [
        f"登録しました: {record['id']}",
        f"マップ: {record['map']}",
        f"アビリティ: {record['ability_label']}",
        f"ジャンプ: {record['jump_label']}",
        f"位置: {review_text}、信頼度 {position['confidence']}",
        f"Git: {git_message}",
        "GitHubへの反映に少々時間がかかる場合があります。",
    ]
    if image_url:
        lines.append(f"画像: {image_url}")
    return "\n".join(lines)


async def _notify_channel(
    bot: commands.Bot,
    settings: Settings,
    record: dict,
) -> None:
    if settings.discord_notify_channel_id is None:
        return

    channel = bot.get_channel(settings.discord_notify_channel_id)
    if channel is None:
        channel = await bot.fetch_channel(settings.discord_notify_channel_id)

    image_url = build_asset_url(settings, record["image_path"])
    embed = discord.Embed(
        title=record["title"] or f"{record['map']} {record['ability_label']}",
        description=record["description"] or "新しいCypher定点が登録されました。",
        color=discord.Color.teal(),
    )
    embed.add_field(name="マップ", value=record["map"], inline=True)
    embed.add_field(name="アビリティ", value=record["ability_label"], inline=True)
    embed.add_field(name="ジャンプ", value=record["jump_label"], inline=True)
    embed.add_field(
        name="位置推定の信頼度",
        value=str((record.get("map_position") or record["detected_position"])["confidence"]),
        inline=True,
    )
    embed.add_field(
        name="反映",
        value="GitHubへの反映に少々時間がかかる場合があります。",
        inline=False,
    )
    if image_url:
        embed.set_image(url=image_url)

    await channel.send(embed=embed)


def _build_search_embed(
    settings: Settings,
    lineups: list[dict],
    selected_map: str | None,
    total_count: int,
) -> discord.Embed:
    title = f"{selected_map} の検索結果" if selected_map else "定点検索結果"
    embed = discord.Embed(
        title=title,
        description=(
            f"{total_count}件中、最大25件を表示します。\n"
            "GitHubへの反映に少々時間がかかる場合があります。"
        ),
        color=discord.Color.teal(),
    )

    result_lines = []
    for result_index, lineup in enumerate(lineups[:25], start=1):
        position = get_lineup_position(lineup)
        result_lines.append(
            f"{result_index}. {lineup.get('map')} / {lineup.get('ability_label')} / "
            f"{lineup.get('jump_label')} / 座標 {format_position(position)}"
        )

    embed.add_field(
        name="結果",
        value="\n".join(result_lines)[:1024] or "表示できる結果がありません。",
        inline=False,
    )
    return embed


def _build_lineup_detail_embed(settings: Settings, lineup: dict) -> discord.Embed:
    image_url = build_asset_url(settings, lineup["image_path"])
    data_url = build_asset_url(settings, lineup["data_path"])
    position = get_lineup_position(lineup)
    embed = discord.Embed(
        title=lineup.get("title") or f"{lineup.get('map')} {lineup.get('ability_label')}",
        description=lineup.get("description") or "登録済みのCypher定点です。",
        url=data_url,
        color=discord.Color.teal(),
    )
    embed.add_field(name="マップ", value=lineup.get("map", "不明"), inline=True)
    embed.add_field(name="アビリティ", value=lineup.get("ability_label", "不明"), inline=True)
    embed.add_field(name="ジャンプ", value=lineup.get("jump_label", "不明"), inline=True)
    embed.add_field(name="座標", value=format_position(position), inline=True)
    embed.add_field(name="信頼度", value=str(position.get("confidence", "不明")), inline=True)
    embed.add_field(
        name="反映",
        value="GitHubへの反映に少々時間がかかる場合があります。",
        inline=False,
    )
    if image_url:
        embed.add_field(name="画像URL", value=image_url, inline=False)
        embed.set_image(url=image_url)
    return embed


if __name__ == "__main__":
    run()
