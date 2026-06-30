from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .config import Settings
from .constants import ABILITIES, VALORANT_MAPS
from .models import Author, LineupInput, ManualPosition
from .notifier import build_public_url
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

    @bot.tree.command(name="register", description="Register a Cypher lineup.")
    @app_commands.describe(
        screenshot="Screenshot with the minimap visible.",
        ability="Cypher ability.",
        jump="Whether the lineup uses a jump.",
        valorant_map="VALORANT map.",
        title="Optional lineup title.",
        description="Optional memo.",
        position_x="Optional manual minimap X position, 0 to 100.",
        position_y="Optional manual minimap Y position, 0 to 100.",
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
                    "Screenshot is too large. "
                    f"Limit: {active_settings.max_screenshot_bytes} bytes."
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
                f"Registration failed: {registration_error}",
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
                f"Registered, but Discord notification failed: {notification_error}",
                ephemeral=True,
            )

    return bot


def run() -> None:
    settings = Settings.from_env()
    if not settings.discord_token:
        raise RuntimeError("CYLINE_DISCORD_TOKEN is required.")

    bot = create_bot(settings)
    bot.run(settings.discord_token)


def _build_manual_position(
    position_x: float | None,
    position_y: float | None,
) -> ManualPosition | None:
    if position_x is None and position_y is None:
        return None

    if position_x is None or position_y is None:
        raise ValueError("Both position_x and position_y are required for manual correction.")

    return ManualPosition(x_percent=position_x, y_percent=position_y)


def _build_success_message(settings: Settings, record: dict, git_message: str) -> str:
    image_url = build_public_url(settings, record["image_path"])
    review_text = "needs review" if record["detected_position"]["needs_review"] else "confirmed"
    lines = [
        f"Registered: {record['id']}",
        f"Map: {record['map']}",
        f"Ability: {record['ability_label']}",
        f"Jump: {record['jump_label']}",
        f"Position: {review_text}, confidence {record['detected_position']['confidence']}",
        f"Git: {git_message}",
    ]
    if image_url:
        lines.append(f"Image: {image_url}")
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

    image_url = build_public_url(settings, record["image_path"])
    embed = discord.Embed(
        title=record["title"] or f"{record['map']} {record['ability_label']}",
        description=record["description"] or "New Cypher lineup registered.",
        color=discord.Color.teal(),
    )
    embed.add_field(name="Map", value=record["map"], inline=True)
    embed.add_field(name="Ability", value=record["ability_label"], inline=True)
    embed.add_field(name="Jump", value=record["jump_label"], inline=True)
    embed.add_field(
        name="Position confidence",
        value=str(record["detected_position"]["confidence"]),
        inline=True,
    )
    if image_url:
        embed.set_image(url=image_url)

    await channel.send(embed=embed)


if __name__ == "__main__":
    run()
