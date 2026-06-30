from __future__ import annotations

from urllib.parse import urljoin

from .config import Settings


def build_public_url(settings: Settings, relative_path: str) -> str:
    if not settings.public_base_url:
        return ""
    return urljoin(settings.public_base_url.rstrip("/") + "/", relative_path)


def send_webhook_notification(settings: Settings, record: dict) -> str:
    if not settings.discord_webhook_url:
        return "Discord webhook notification was skipped because no webhook URL is set."

    try:
        import requests
    except ImportError:
        return "Discord webhook notification failed because requests is not installed."

    image_url = build_public_url(settings, record["image_path"])
    data_url = build_public_url(settings, record["data_path"])
    embed = {
        "title": record["title"] or f"{record['map']} {record['ability_label']}",
        "description": record["description"] or "New Cypher lineup registered.",
        "fields": [
            {"name": "Map", "value": record["map"], "inline": True},
            {"name": "Ability", "value": record["ability_label"], "inline": True},
            {"name": "Jump", "value": record["jump_label"], "inline": True},
            {
                "name": "Position confidence",
                "value": str(record["detected_position"]["confidence"]),
                "inline": True,
            },
        ],
        "url": data_url,
    }
    if image_url:
        embed["image"] = {"url": image_url}

    response = requests.post(
        settings.discord_webhook_url,
        json={"embeds": [embed]},
        timeout=10,
    )
    if response.status_code >= 400:
        return f"Discord webhook notification failed: HTTP {response.status_code}"

    return "Discord webhook notification sent."

