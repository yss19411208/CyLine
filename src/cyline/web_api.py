from __future__ import annotations

from flask import Flask, jsonify, request

from .config import Settings
from .constants import ABILITIES, VALORANT_MAPS
from .models import Author, LineupInput, ManualPosition
from .notifier import send_webhook_notification
from .service import LineupService


def create_app(settings: Settings | None = None) -> Flask:
    active_settings = settings or Settings.from_env()
    service = LineupService(active_settings)
    app = Flask(__name__)

    try:
        from flask_cors import CORS

        CORS(app, origins=active_settings.cors_allowed_origins)
    except ImportError:
        pass

    @app.get("/")
    def health():
        return jsonify(
            {
                "service": "CyLine API",
                "status": "ok",
                "endpoints": {
                    "admin_update_lineup": "/api/admin/lineups/<id>",
                    "options": "/api/options",
                    "register_lineup": "/api/lineups",
                },
                "note": "Discord botは別プロセスでcyline-botを起動してください。",
            }
        )

    @app.get("/api/options")
    def options():
        return jsonify(
            {
                "abilities": [
                    {"value": ability_key, "label": ability_label}
                    for ability_key, ability_label in ABILITIES.items()
                ],
                "maps": VALORANT_MAPS,
            }
        )

    @app.post("/api/lineups")
    def register_lineup():
        authorization_error = _check_authorization(active_settings)
        if authorization_error is not None:
            return authorization_error

        screenshot = request.files.get("screenshot")
        if screenshot is None:
            return jsonify({"error": "スクリーンショット画像が必要です。"}), 400

        try:
            screenshot_bytes = screenshot.read(active_settings.max_screenshot_bytes + 1)
            if len(screenshot_bytes) > active_settings.max_screenshot_bytes:
                return jsonify({"error": "スクリーンショットが大きすぎます。"}), 400

            lineup_input = _read_lineup_input_from_form()
            author = Author(
                source="web",
                user_id=request.form.get("author_id", "anonymous"),
                display_name=request.form.get("author_name", "Anonymous"),
            )
            record, git_result = service.register_lineup(
                lineup_input=lineup_input,
                screenshot_bytes=screenshot_bytes,
                original_filename=screenshot.filename or "screenshot.png",
                author=author,
            )
            notification_message = send_webhook_notification(active_settings, record)
            return jsonify(
                {
                    "record": record,
                    "git": git_result.__dict__,
                    "notification": notification_message,
                }
            ), 201
        except ValueError as validation_error:
            return jsonify({"error": str(validation_error)}), 400
        except Exception as unexpected_error:
            return jsonify({"error": str(unexpected_error)}), 500

    @app.patch("/api/admin/lineups/<lineup_id>")
    def update_lineup(lineup_id: str):
        authorization_error = _check_admin_authorization(active_settings)
        if authorization_error is not None:
            return authorization_error

        updates = request.get_json(silent=True)
        if not isinstance(updates, dict):
            return jsonify({"error": "JSON bodyが必要です。"}), 400

        try:
            record, git_result = service.update_lineup(lineup_id, updates)
            return jsonify(
                {
                    "record": record,
                    "git": git_result.__dict__,
                }
            )
        except ValueError as validation_error:
            return jsonify({"error": str(validation_error)}), 400
        except Exception as unexpected_error:
            return jsonify({"error": str(unexpected_error)}), 500

    return app


def run() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=8000, debug=False)


def _check_authorization(settings: Settings):
    if not settings.web_api_token:
        return None

    submitted_token = request.headers.get("X-CyLine-Token", "")
    if submitted_token != settings.web_api_token:
        return jsonify({"error": "認証に失敗しました。"}), 401

    return None


def _check_admin_authorization(settings: Settings):
    if not settings.admin_api_token:
        return jsonify({"error": "管理者APIトークンが設定されていません。"}), 403

    submitted_token = (
        request.headers.get("X-CyLine-Admin-Token", "")
        or request.headers.get("X-CyLine-Token", "")
    )
    if submitted_token != settings.admin_api_token:
        return jsonify({"error": "管理者認証に失敗しました。"}), 401

    return None


def _read_lineup_input_from_form() -> LineupInput:
    manual_position = _read_manual_position_from_form()
    return LineupInput(
        valorant_map=request.form.get("map", ""),
        ability=request.form.get("ability", ""),
        jump=_read_bool_from_form("jump"),
        title=request.form.get("title", ""),
        description=request.form.get("description", ""),
        manual_position=manual_position,
    )


def _read_manual_position_from_form() -> ManualPosition | None:
    raw_position_x = request.form.get("position_x", "").strip()
    raw_position_y = request.form.get("position_y", "").strip()
    if not raw_position_x and not raw_position_y:
        return None

    if not raw_position_x or not raw_position_y:
        raise ValueError("position_xとposition_yは両方指定してください。")

    try:
        position_x = float(raw_position_x)
        position_y = float(raw_position_y)
    except ValueError as conversion_error:
        raise ValueError("position_xとposition_yは数値で指定してください。") from conversion_error

    return ManualPosition(x_percent=position_x, y_percent=position_y)


def _read_bool_from_form(field_name: str) -> bool:
    raw_value = request.form.get(field_name, "false").strip().lower()
    return raw_value in {"1", "true", "yes", "on", "jump"}


if __name__ == "__main__":
    run()
