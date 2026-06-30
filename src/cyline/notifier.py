from __future__ import annotations

from urllib.parse import urljoin

from .config import Settings


def build_public_url(settings: Settings, relative_path: str) -> str:
    if not settings.public_base_url:
        return ""
    return urljoin(settings.public_base_url.rstrip("/") + "/", relative_path)


def send_webhook_notification(settings: Settings, record: dict) -> str:
    if not settings.discord_webhook_url:
        return "Discord Webhook URLが未設定のため、通知をスキップしました。"

    try:
        import requests
    except ImportError:
        return "requestsがインストールされていないため、Discord通知に失敗しました。"

    image_url = build_public_url(settings, record["image_path"])
    data_url = build_public_url(settings, record["data_path"])
    embed = {
        "title": record["title"] or f"{record['map']} {record['ability_label']}",
        "description": record["description"] or "新しいCypher定点が登録されました。",
        "fields": [
            {"name": "マップ", "value": record["map"], "inline": True},
            {"name": "アビリティ", "value": record["ability_label"], "inline": True},
            {"name": "ジャンプ", "value": record["jump_label"], "inline": True},
            {
                "name": "位置推定の信頼度",
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
        return f"Discord Webhook通知に失敗しました: HTTP {response.status_code}"

    return "Discord Webhook通知を送信しました。"
